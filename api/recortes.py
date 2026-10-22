"""Recortes (fase 1 del plan de interfaz propia, 21/10 noche): lo que la pantalla «Mis recortes» de la web y su editor visual
necesitan. Es la MISMA lógica de negocio que publicar_ui._mis_recortes / _editor_recorte (validaciones del tramo, qué va a
clips.edicion, la nota, qué se puede borrar y quién), sin inventar otra; si cambia una regla allá, cambiarla acá.

Lo nuevo respecto de Streamlit: `edicion["segmentos"]` = [[a_ms, b_ms], ...] absolutos del original, los pedazos del tramo que se
conservan (partir + sacar del medio, editor visual); la cola (procesar_clips.py) los aplica con recortar_clip.cortar(segmentos=).
(22/10) La lista va EN EL ORDEN DE SALIDA: el editor deja mover los pedazos, y si el orden no es el del original la cola los pega en
ese orden. Validaciones: sin solapamiento entre pedazos, cada uno de al menos 0,5 s, el total entre 2 s y 3 min; si cambian los
pedazos y había subtítulos corregidos, se descartan con aviso (misma regla que al cambiar el tramo).

Rutas (todas con sesión):
  GET    /recortes                     mis recortes · ?equipo=1 los listos de otras personas · ?todos=1 (aprobadores) todos
  GET    /recortes/opciones            tipografías, tamaños, colores, fondos, posiciones (recortar_clip) + estilo por defecto
  GET    /recortes/estilo-defecto      config clips_estilo (normalizado)      · PUT (solo admins) lo cambia
  GET    /recortes/{id}                un recorte con líneas de subtítulo, estilo actual y permisos
  POST   /recortes/{id}/edicion        guarda clips.edicion y vuelve el pedido a 'pedido' (= «🔁 Regenerar el recorte»)
  DELETE /recortes/{id}                borra el archivo de WordPress y la fila (= «🗑 Borrar»)
  GET    /recortes/{id}/usos           piezas que usan ese video (aviso antes de borrar)
  POST   /recortes/{id}/reintentar     (aprobadores) un recorte en error vuelve a 'pedido' (= «↻ Reintentar»)
"""
import os, datetime, logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from . import auth, roles as _roles
import db                      # noqa: E402  (api/__init__ pone la raíz del repo en sys.path)
import publicar                # noqa: E402
import recortar_clip as rc     # noqa: E402

log = logging.getLogger("api")
router = APIRouter(prefix="/recortes", tags=["recortes"])

MIN_MS, MAX_MS = 2000, 180000          # el tramo tiene que durar entre 2 s y 3 min (publicar_ui._editor_recorte)
MIN_PEDAZO_MS = 500                    # (22/10) cada pedazo conservado dura al menos medio segundo
ESTADOS = {"listo": "listo", "pedido": "en proceso", "error": "error"}


# ---------------- Modelos de entrada ----------------
class Linea(BaseModel):
    inicio: str          # 'HH:MM:SS,mmm' (como lo devuelve leer_srt; los tiempos no se editan)
    fin: str
    texto: str = ""


class Edicion(BaseModel):
    """Lo que la persona cambió en el editor. Las claves que no vienen no se tocan."""
    inicio_ms: Optional[int] = None
    fin_ms: Optional[int] = None
    segmentos: Optional[list[list[int]]] = None   # [[a_ms, b_ms], ...] absolutos, EN ORDEN DE SALIDA: los pedazos que se conservan; [] = ninguno (todo el tramo)
    lineas: Optional[list[Linea]] = None          # subtítulos por línea (vertical); si viene, manda sobre `srt`
    srt: Optional[str] = None                     # o el SRT entero
    estilo: Optional[dict] = None
    quitar_pausas: Optional[bool] = None
    descartar_srt: bool = True                    # si cambió el tramo y había subtítulos corregidos: descartarlos y rearmarlos (como la casilla de Streamlit)


class EstiloDefecto(BaseModel):
    estilo: dict


# ---------------- Helpers ----------------
def _sesion_y_rol(request: Request):
    s = auth.sesion(request)
    r = _roles.roles(s["usuario"], s.get("rol_tabla"))
    return s["usuario"], r["aprueba"]


def _cargar(cid):
    if not db.disponible():
        raise HTTPException(503, "Sin Supabase: no hay recortes.")
    c = db.obtener_clip(cid)
    if not c:
        raise HTTPException(404, "No existe ese recorte.")
    return c


def _propio(c, usuario):
    return c.get("pedido_por") in (usuario, "bot")


def _estilo_defecto_equipo():
    try:
        return db.obtener_config("clips_estilo")
    except Exception as e:
        log.warning("No pude leer clips_estilo: %s", e)
        return None


def _decorar(c, usuario, aprueba):
    """Campos derivados que dibuja la pantalla (los mismos que calcula publicar_ui._mis_recortes)."""
    propio = _propio(c, usuario)
    listo = c.get("estado") == "listo" and bool(c.get("url"))
    e = c.get("edicion") or {}
    c["propio"] = propio
    c["puede_editar"] = (propio or aprueba) and listo          # «✏️ Editar recorte» solo en un recorte listo y propio (o aprobador)
    c["puede_borrar"] = propio or aprueba                     # en «Del equipo» no se borra lo ajeno
    c["regenerando"] = c.get("estado") == "pedido" and bool(e) and bool(c.get("url"))
    c["estado_texto"] = "regenerando con los cambios" if c["regenerando"] else ESTADOS.get(c.get("estado"), c.get("estado"))
    c["miniatura"] = f"https://img.youtube.com/vi/{c['video_id']}/hqdefault.jpg" if c.get("video_id") else None
    c["duracion_ms"] = int(c.get("fin_ms") or 0) - int(c.get("inicio_ms") or 0)
    c["sin_pausas"] = e.get("sin_pausas") if listo else None
    c["segmentos_hechos"] = e.get("segmentos_hechos") if listo else None
    c["timeline"] = e.get("timeline") if listo else None
    return c


def _mmss(ms):
    ms = int(ms or 0)
    return f"{ms // 60000:02d}:{ms // 1000 % 60:02d}"


def _opciones():
    return {
        "tipografias": list(rc.FUENTES_CLIPS),
        "tamanos": dict(rc.TAMANOS),
        "colores": dict(rc.COLORES),
        "fondos": {n: {"tipo": t, "color": col, "alpha": a} for n, (t, col, a) in rc.FONDOS.items()},
        "posiciones": list(rc.POSICIONES_SUB),
        "estilo_defecto": dict(rc.ESTILO_DEFECTO),
        "limites": {"min_ms": MIN_MS, "max_ms": MAX_MS, "min_pedazo_ms": MIN_PEDAZO_MS},
    }


# ---------------- Rutas ----------------
@router.get("")
def listar(request: Request, todos: bool = False, equipo: bool = False, buscar: str = ""):
    """Como «Recortes» en Streamlit: los que pidió la persona (o el bot en su nombre). equipo=1: la biblioteca compartida (los
    LISTOS de las demás personas, para abrir y publicar; sin editar ni borrar). todos=1 (solo aprobadores): todo el equipo, como
    Panel admin → Clips. buscar: filtra por título, video o quién lo pidió."""
    usuario, aprueba = _sesion_y_rol(request)
    if todos and not aprueba:
        raise HTTPException(403, "Solo para aprobadores.")
    if not db.disponible():
        return []
    filas = db.listar_clips(200)
    if equipo:
        filas = [c for c in filas if c.get("pedido_por") not in (usuario, "bot") and c.get("estado") == "listo" and c.get("url")]
    elif not todos:
        filas = [c for c in filas if _propio(c, usuario)]
    if buscar.strip():
        b = buscar.strip().lower()
        filas = [c for c in filas if b in ((c.get("titulo") or "") + " " + (c.get("video_id") or "") + " " + (c.get("pedido_por") or "")).lower()]
    return [_decorar(c, usuario, aprueba) for c in filas]


@router.get("/opciones")
def opciones(request: Request):
    """Las listas de recortar_clip para los controles de estilo (son las mismas que usa libass al quemar), los límites del tramo y
    el estilo por defecto del equipo (config clips_estilo; null si nadie lo guardó: vale ESTILO_DEFECTO)."""
    auth.sesion(request)
    d = _opciones()
    d["estilo_equipo"] = _estilo_defecto_equipo() if db.disponible() else None
    return d


@router.get("/estilo-defecto")
def estilo_defecto(request: Request):
    auth.sesion(request)
    guardado = _estilo_defecto_equipo() if db.disponible() else None
    return {"estilo": rc.normalizar_estilo(guardado), "guardado": bool(guardado)}


@router.put("/estilo-defecto")
def guardar_estilo_defecto(datos: EstiloDefecto, usuario=Depends(auth.admin)):
    """Panel admin → Clips → «💾 Guardar como estilo por defecto»: vale para los recortes verticales nuevos. Es configuración: solo admins (21/10)."""
    if not db.disponible():
        raise HTTPException(503, "Sin Supabase.")
    estilo = rc.normalizar_estilo(datos.estilo)
    db.guardar_config("clips_estilo", estilo, usuario)
    return {"ok": True, "estilo": estilo}


@router.get("/{cid}")
def uno(cid: str, request: Request):
    usuario, aprueba = _sesion_y_rol(request)
    c = _decorar(_cargar(cid), usuario, aprueba)
    e = c.get("edicion") or {}
    srt = e.get("srt") or c.get("srt") or ""
    c["srt_actual"] = srt
    c["lineas"] = rc.leer_srt(srt)
    c["srt_corregido"] = bool(e.get("srt"))
    c["estilo_actual"] = rc.normalizar_estilo(e.get("estilo") or c.get("estilo") or (_estilo_defecto_equipo() if db.disponible() else None))
    c["estilo_propio"] = bool(e.get("estilo") or c.get("estilo"))
    return c


@router.post("/{cid}/edicion")
def editar(cid: str, datos: Edicion, request: Request):
    """= «🔁 Regenerar el recorte» (publicar_ui._editor_recorte): arma clips.edicion con lo que cambió, valida el tramo (fin > inicio,
    entre 2 s y 3 min), avisa si los subtítulos corregidos eran del tramo anterior, pone estado 'pedido' y la nota. La cola de la
    nube lo aplica en ~15 min. Devuelve {ok, edicion, partes, avisos, mensaje}."""
    usuario, aprueba = _sesion_y_rol(request)
    c = _cargar(cid)
    if not (_propio(c, usuario) or aprueba):
        raise HTTPException(403, "Este recorte lo pidió otra persona: solo quien lo pidió o un aprobador pueden cambiarlo.")
    if c.get("estado") != "listo":
        raise HTTPException(409, "Solo se edita un recorte que ya está listo." + (" Este está en proceso." if c.get("estado") == "pedido" else ""))
    edicion = dict(c.get("edicion") or {})
    nueva = dict(edicion)
    partes, avisos = [], []
    vertical = c.get("formato") == "vertical"

    # --- Tramo ---
    ini0, fin0 = int(c["inicio_ms"]), int(c["fin_ms"])
    ini_ms = int(datos.inicio_ms) if datos.inicio_ms is not None else ini0
    fin_ms = int(datos.fin_ms) if datos.fin_ms is not None else fin0
    if ini_ms < 0:
        raise HTTPException(400, "El inicio no puede ser negativo.")
    dur = (fin_ms - ini_ms) / 1000
    if fin_ms <= ini_ms:
        raise HTTPException(400, "El fin tiene que ser después del inicio.")
    if fin_ms - ini_ms < MIN_MS:
        raise HTTPException(400, f"Dura {dur:.1f} s: muy corto. Tiene que durar al menos 2 segundos.")
    if fin_ms - ini_ms > MAX_MS:
        raise HTTPException(400, f"Dura {dur / 60:.1f} min: muy largo. Como mucho 3 minutos.")
    tramo_cambio = (ini_ms, fin_ms) != (ini0, fin0)
    if tramo_cambio:
        nueva["inicio_ms"], nueva["fin_ms"] = ini_ms, fin_ms
        partes.append(f"tramo {_mmss(ini_ms)}–{_mmss(fin_ms)}")
    else:
        nueva.pop("inicio_ms", None)
        nueva.pop("fin_ms", None)

    # --- Segmentos (partir, sacar del medio y, desde el 22/10, reordenar): se guardan normalizados, absolutos, en ms, en orden de salida ---
    if datos.segmentos is not None:
        try:
            rel = rc.normalizar_segmentos(datos.segmentos, ini_ms, fin_ms)   # recorta al tramo, une contiguos, ValueError si se pisan
        except ValueError as e:
            raise HTTPException(400, str(e))
        if rel is None:
            nueva.pop("segmentos", None)
        else:
            corto = min(b - a for a, b in rel)
            if corto * 1000 < MIN_PEDAZO_MS:
                raise HTTPException(400, f"Hay un pedazo que dura {corto:.1f} s: cada pedazo tiene que durar al menos medio segundo.")
            total = sum(b - a for a, b in rel) * 1000
            if total < MIN_MS:
                raise HTTPException(400, "Lo que queda del recorte dura menos de 2 segundos.")
            if total > MAX_MS:
                raise HTTPException(400, f"Los pedazos suman {total / 60000:.1f} min: muy largo. Como mucho 3 minutos.")
            nueva["segmentos"] = [[ini_ms + int(round(a * 1000)), ini_ms + int(round(b * 1000))] for a, b in rel]
    segmentos_cambio = nueva.get("segmentos") != edicion.get("segmentos")
    if segmentos_cambio:
        seg = nueva.get("segmentos") or []
        n = len(seg)
        reordenados = any(seg[i][1] > seg[i + 1][0] for i in range(n - 1))
        partes.append(((f"{n} pedazos conservados" if n != 1 else "1 pedazo conservado") + (" en otro orden" if reordenados else "")) if n else "sin pedazos sacados")

    # --- Quitar pausas largas (21/10) ---
    pausas_antes = bool(edicion.get("quitar_pausas"))
    quitar = pausas_antes if datos.quitar_pausas is None else bool(datos.quitar_pausas)
    if quitar != pausas_antes:
        nueva["quitar_pausas"] = quitar
        partes.append("sin pausas largas" if quitar else "con las pausas")
        if not quitar and edicion.get("sin_pausas") and (edicion.get("srt") or "").strip():
            avisos.append("Los subtítulos que corregiste son del video sin pausas: al volver a poner las pausas se arman de nuevo "
                          "desde la transcripción (después los podés volver a corregir).")
            nueva.pop("srt", None)

    # --- Subtítulos (solo vertical) ---
    if vertical:
        srt_actual = edicion.get("srt") or c.get("srt") or ""
        nuevo_srt = None
        if datos.lineas is not None:
            nuevo_srt = rc.armar_srt_de_lineas([l.model_dump() for l in datos.lineas])
        elif datos.srt is not None:
            nuevo_srt = datos.srt.strip().replace("\r", "")
        if tramo_cambio or segmentos_cambio:
            # (22/10) cambiar los pedazos (sacar, estirar, reordenar) mueve la timeline igual que cambiar el tramo: misma regla
            que = "el tramo" if tramo_cambio else "los pedazos"
            corregido = (nuevo_srt if nuevo_srt is not None else edicion.get("srt") or "").strip()
            if (corregido and corregido != (c.get("srt") or "").strip()) or edicion.get("srt"):
                if datos.descartar_srt:
                    nueva.pop("srt", None)
                    partes.append("subtítulos rearmados")
                    avisos.append(f"Como cambiaste {que}, los subtítulos se arman de nuevo desde la transcripción para el video nuevo; "
                                  "los corregidos se descartaron. Cuando el video esté listo los podés volver a corregir.")
                else:
                    nueva["srt"] = corregido
                    avisos.append("Los subtítulos que corregiste corresponden al tramo anterior: con el tramo nuevo pueden quedar corridos o cortados." if tramo_cambio
                                  else "Los subtítulos que corregiste corresponden al video anterior: con los pedazos nuevos pueden quedar corridos o cortados.")
            else:
                avisos.append(f"Como cambiaste {que}, los subtítulos se arman de nuevo desde la transcripción para el video nuevo.")
        elif nuevo_srt is not None:
            if not nuevo_srt.strip():
                raise HTTPException(400, "Quedaron todas las líneas vacías: el video saldría sin subtítulos. Dejá al menos una.")
            if nuevo_srt.strip() != srt_actual.strip():
                nueva["srt"] = nuevo_srt
                partes.append("subtítulos corregidos")

        # --- Estilo ---
        if datos.estilo is not None:
            actual = rc.normalizar_estilo(edicion.get("estilo") or c.get("estilo") or _estilo_defecto_equipo())
            estilo = rc.normalizar_estilo(datos.estilo)
            if estilo != actual:
                nueva["estilo"] = estilo
                partes.append("estilo")
            elif "estilo" in edicion:
                nueva["estilo"] = edicion["estilo"]

    if nueva == edicion:
        raise HTTPException(400, "Todavía no cambiaste nada.")
    hoy = datetime.date.today().strftime("%d/%m")
    nota = f"Cambios de {usuario} el {hoy}: {', '.join(partes) or 'edición'}. El video anterior se reemplaza cuando termine."
    db.actualizar_clip(cid, {"edicion": nueva, "estado": "pedido", "error": None, "nota": nota})
    return {"ok": True, "edicion": nueva, "partes": partes, "avisos": avisos,
            "mensaje": "Listo, en unos 15 minutos el recorte aparece con los cambios."}


@router.get("/{cid}/usos")
def usos(cid: str, request: Request):
    """Piezas (no borrador/prueba) que usan ese video: para avisar antes de borrar (db.publicaciones_con_video)."""
    auth.sesion(request)
    c = _cargar(cid)
    try:
        return db.publicaciones_con_video(c.get("url")) if c.get("url") else []
    except Exception as e:
        log.warning("publicaciones_con_video: %s", e)
        return []


@router.delete("/{cid}")
def borrar(cid: str, request: Request):
    """= «🗑 Borrar» de Mis recortes: saca el archivo de WordPress (publicar.borrar_media_por_url) y la fila. Si está listo y
    WordPress no lo borra, no se borra la fila (502 con el aviso). En proceso o con error: se borra lo que haya."""
    usuario, aprueba = _sesion_y_rol(request)
    c = _cargar(cid)
    if not (_propio(c, usuario) or aprueba):
        raise HTTPException(403, "Este recorte lo pidió otra persona: solo quien lo pidió o un aprobador pueden borrarlo.")
    cfg = publicar.Config(os.environ)
    aviso = None
    if c.get("url"):
        ok, aviso = publicar.borrar_media_por_url(cfg, c["url"], quien=usuario)
        if not ok and c.get("estado") == "listo":
            raise HTTPException(502, aviso)
    db.borrar_clip(cid)
    return {"ok": True, "aviso": aviso}


@router.post("/{cid}/reintentar")
def reintentar(cid: str, usuario=Depends(auth.aprobador)):
    """Panel admin → Clips → «↻ Reintentar»: un recorte en error vuelve a la cola (respeta la edición si la hay)."""
    c = _cargar(cid)
    if c.get("estado") != "error":
        raise HTTPException(409, "Solo se reintenta un recorte que falló.")
    db.actualizar_clip(cid, {"estado": "pedido", "error": None})
    return {"ok": True}
