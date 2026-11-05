"""Publicar, Mis publicaciones y Aprobación desde la web (fase 3 del plan de interfaz propia, 22/10).

Lógica de negocio de Publicar (formulario / envío / Mis publicaciones / Aprobación), sin inventar
otra: se reutilizan publicar.py (conectores), imagen.py (la foto con la frase encima) y db.py (tabla `publicaciones`). Si cambia
una regla allá, cambiarla acá. Lo que ya existía en chat_rutas.py (banco, modos, borrador y a-aprobar «cortos» de la pieza
propuesta) se reutiliza; acá están las versiones completas con el diseño de la foto, el envío real/simulado y el panel.

Rutas (todas con sesión):
  GET    /publicar/opciones                  logos, tipografías, pesos, posiciones, formatos, canales con su modo (real y el que ve esta persona)
  POST   /banco/subir                        (multipart `archivo`) sube una imagen a la biblioteca de WordPress (publicar.subir_imagen_wordpress)
  POST   /publicar/componer                  la foto con la frase encima, para la vista previa (imagen.componer_imagen); devuelve image/jpeg
  POST   /publicar/borrador                  = «💾 Guardar borrador» con TODOS los campos del formulario (diseño incluido)
  POST   /publicar/a-aprobar                 = «📨 Enviar a aprobación» (sube la imagen compuesta a WordPress y deja la pieza a_aprobar)
  POST   /publicar/enviar                    = «Enviar a <canal>» / «👁 Ver simulado»: {modo: real|simulado}; real ya no lo usa nadie (403): se publica desde Aprobación
  GET    /publicaciones/{id}                 una pieza (dueño o aprobador) con el dict `pieza` para retomar el borrador
  DELETE /publicaciones/{id}                 = «🗑 Eliminar» (db.eliminar_publicacion: solo propias y en estado eliminable)
  GET    /aprobacion/para-aprobar            (aprobadores) las piezas a_aprobar + el modo real de cada canal
  POST   /aprobacion/{id}/aprobar            {fecha, hora}: = «✅ Aprobar y programar» (newsletter: queda `lista`)
  POST   /aprobacion/{id}/rechazar           {nota}
  GET    /aprobacion/cola                    las piezas pendientes (db.listar_pendientes)  · POST /aprobacion/{id}/cancelar
  GET    /aprobacion/registro                el registro completo sin subidas/pruebas/borradores (NO_SON_PIEZAS)
  GET    /aprobacion/papelera                conversaciones borradas por cualquiera · POST /aprobacion/papelera/{id}/restaurar
  (Clips: GET /recortes?todos=1, POST /recortes/{id}/reintentar y GET/PUT /recortes/estilo-defecto ya existen en api/recortes.py.)
"""
import os, re, io, copy, hashlib, logging, datetime, contextvars, threading
from collections import OrderedDict
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel

from . import auth
from . import chat_rutas as cr
from . import presencia_rutas as _presencia
from .pieza import Pieza
import db            # noqa: E402  (api/__init__ pone la raíz del repo en sys.path)
import publicar      # noqa: E402
import imagen        # noqa: E402
import canales       # noqa: E402

log = logging.getLogger("api")
router = APIRouter(tags=["publicar"])

CANALES = cr.CANALES                       # {"wordpress": "WordPress", ...}
ZONA_HORARIA = cr.ZONA_HORARIA             # "-03:00"
# Nombre visible de cada canal (16/10, Franco: la entrada en WordPress se llama «Blogpost»). (3/11) Sale del registro canales.py.
CANAL_TXT = canales.textos()
# Texto de cada estado (sin los emojis: la web pone el icono)
ESTADO_TXT = {"a_aprobar": "pendiente de aprobación", "pendiente": "aprobada · programada", "procesando": "publicándose", "rechazada": "rechazada",
              "publicada": "publicada", "simulada": "simulada", "error": "error", "cancelada": "cancelada",
              "subida": "imagen subida", "draft": "borrador en WordPress", "programada": "programada",
              "PUBLICADO": "publicada", "borrador": "borrador", "prueba": "prueba (simulado)",
              "lista": "lista para enviar (pegar en Perfit)"}
NO_SON_PIEZAS = ("subida", "prueba", "borrador", "simulada", "simulado")   # fuera del registro del panel
FORMATO_POR_CANAL = canales.formato_por_canal()                            # formato de foto por canal (registro canales.py)
FIRMA_DEFECTO = "— Br. David"
MAX_IMAGEN_BYTES = 12 * 1024 * 1024
_CACHE_COMPUESTAS: "OrderedDict[str, bytes]" = OrderedDict()                 # cache por contenido
_CACHE_MAX = 24
_candado = threading.Lock()


# ---------------- Modelos de entrada ----------------
PiezaCompleta = Pieza        # (3/11) el modelo único está en api/pieza.py (lo comparte con chat_rutas); el nombre queda como alias


class Envio(PiezaCompleta):
    modo: str = "simulado"                      # 'real' (= «Enviar a <canal>», 403 siempre: nadie publica directo) | 'simulado' (= «Ver simulado»)


class Componer(BaseModel):
    imagen_url: str
    texto_imagen: str = ""
    firma: Optional[str] = FIRMA_DEFECTO
    formato: str = "cuadrado"
    tipografia: Optional[str] = None
    peso: str = "normal"
    posicion: str = "centro"
    alineacion: str = "centro"
    logo: Optional[str] = None
    posicion_logo: str = "abajo derecha"


class Aprobar(BaseModel):
    fecha: Optional[str] = None                 # 'YYYY-MM-DD'; sin fecha = hoy (como el date_input del panel)
    hora: Optional[str] = None                  # 'HH:MM'


class Rechazar(BaseModel):
    nota: str = ""


# ---------------- Registro de publicar.py → tabla publicaciones ----------------
# publicar.REGISTRAR_EXTRA es un global del módulo: acá se instala UNA vez y lee de una contextvar quién está enviando
# (la API atiende varias personas a la vez).
_contexto = contextvars.ContextVar("publicar_contexto", default=None)


def _hook_registro(entrada):
    ctx = _contexto.get()
    if not ctx:
        return
    # (22/10) una subida de imagen que NO pasó (modo simulado/apagado) o un borrado de media no son piezas: no quedan
    # como filas «prueba» del canal wordpress sin texto y confundían en «Mis publicaciones»
    if entrada.get("accion") in ("subir_imagen", "borrar_media") and entrada.get("resultado") != "subida":
        return
    pieza = entrada.get("pieza") or {}
    extra = {"editada_por": ctx["por"]} if ctx.get("por") else {}
    ctx["pid"] = db.registrar_publicacion(
        usuario=ctx.get("duena") or ctx["usuario"], canal=entrada.get("canal", ""), modo=entrada.get("modo", ""),
        titulo=(pieza.get("title") or entrada.get("titulo") or ctx.get("titulo") or "")[:200],
        texto=(pieza.get("content") or pieza.get("caption") or pieza.get("message") or pieza.get("description") or "")[:5000],
        imagen_url=pieza.get("image_url") or entrada.get("url"),
        fecha_programada=_con_zona(pieza.get("date") or pieza.get("fecha_programada") or ctx.get("fecha")),
        estado="prueba" if entrada.get("modo") == "simulado" else str(entrada.get("resultado", ""))[:60],
        resultado=dict({k: v for k, v in entrada.items() if k not in ("pieza",)},
                       texto_imagen=ctx.get("texto_imagen") or None, origen="web",
                       # (2/11, bug que encontró Julián) la prueba guarda el formulario completo, como un borrador, para «Retomar»
                       pieza=ctx.get("pieza_form") or None, **extra))


publicar.REGISTRAR_EXTRA = _hook_registro


def _con_zona(fecha):
    """La fecha del formulario es hora Argentina sin zona; en la base va con -03:00."""
    if fecha and len(fecha) >= 16 and fecha[-6] not in "+-" and not fecha.endswith("Z"):
        return fecha + ZONA_HORARIA
    return fecha


# ---------------- Helpers ----------------
def _rol(request: Request):
    s = auth.sesion(request)
    return s["usuario"], auth.rol_sesion(s)


def _cfg_real():
    return publicar.Config(os.environ)


def _cfg_simulada(cfg):
    """Quien no publica en real tiene todos los canales en simulado (los apagados siguen apagados)."""
    return cfg.simulada()


def _va_a_la_cola(canal, modo):
    """¿Una pieza con fecha va a la cola? (regla de cada canal en canales.py)"""
    c = canales.canal(canal)
    return bool(c and c.va_a_la_cola(modo))


def _sin_firma_repetida(texto_imagen, firma):
    t = (texto_imagen or "").rstrip()
    f = (firma or "").strip()
    if f and t.endswith(f):
        t = t[: -len(f)].rstrip(" \n—-–")
    return t


def _fecha_iso(fecha, hora):
    return Pieza(canal="instagram", fecha=fecha, hora=hora).fecha_iso()


def _fecha_hora_de_iso(fp):
    """('YYYY-MM-DD', 'HH:MM') en hora Argentina. Supabase devuelve fecha_programada en UTC (+00:00): se convierte; sin zona se toma tal cual."""
    fp = str(fp or "")
    if len(fp) < 10:
        return None, None
    try:
        t = datetime.datetime.fromisoformat(fp.replace("Z", "+00:00"))
        if t.tzinfo is not None:
            t = t.astimezone(datetime.timezone(datetime.timedelta(hours=-3)))
        return t.strftime("%Y-%m-%d"), (t.strftime("%H:%M") if len(fp) >= 16 else None)
    except ValueError:
        return fp[:10], (fp[11:16] if len(fp) >= 16 else None)


def _normalizar_diseno(p: PiezaCompleta, canal):
    """Los valores del diseño con los defaults; None en lo que no aplica."""
    con_frase = bool((p.texto_imagen or "").strip())
    logo = p.logo if p.logo in imagen.LOGOS else ("Sin logo" if p.logo is None else "Sin logo")
    formato = p.formato if p.formato in imagen.FORMATOS else FORMATO_POR_CANAL.get(canal, "cuadrado")
    if con_frase:
        tipografia = p.tipografia if p.tipografia in imagen.TIPOGRAFIAS else imagen.TIPOGRAFIA_DEFAULT
        peso = p.peso if p.peso in imagen.PESOS else "normal"
        posicion = p.posicion if p.posicion in imagen.POSICIONES else "centro"
        alineacion = p.alineacion if p.alineacion in imagen.ALINEACIONES else "centro"
    else:
        tipografia, peso, posicion, alineacion = imagen.TIPOGRAFIA_DEFAULT, "normal", "centro", "centro"
    return {"con_frase": con_frase, "logo": logo, "con_logo": logo != "Sin logo", "formato": formato, "tipografia": tipografia,
            "peso": peso, "posicion": posicion, "alineacion": alineacion,
            "posicion_logo": p.posicion_logo if p.posicion_logo in imagen.POSICIONES_LOGO else "abajo derecha",
            "firma": (p.firma if p.firma is not None else FIRMA_DEFECTO).strip() if con_frase else ""}


def _componer_cacheado(fuente_url, texto_imagen, firma, formato, tipografia, posicion, alineacion, logo, posicion_logo, peso):
    clave = "|".join(str(x) for x in (fuente_url, texto_imagen, firma, formato, tipografia, posicion, alineacion, logo, posicion_logo, peso))
    with _candado:
        if clave in _CACHE_COMPUESTAS:
            _CACHE_COMPUESTAS.move_to_end(clave)
            return _CACHE_COMPUESTAS[clave]
    datos = imagen.componer_imagen(fuente_url, texto_imagen, firma=firma, formato=formato, tipografia=tipografia, posicion=posicion,
                                   alineacion=alineacion, peso=peso, logo=logo, posicion_logo=posicion_logo)
    with _candado:
        _CACHE_COMPUESTAS[clave] = datos
        while len(_CACHE_COMPUESTAS) > _CACHE_MAX:
            _CACHE_COMPUESTAS.popitem(last=False)
    return datos


def _compuesta_de(p: PiezaCompleta, canal, avisos):
    """La imagen con la frase (y/o el logo) encima, como se arma antes de enviar; None si no corresponde."""
    if canal not in ("instagram", "facebook") or not (p.imagen_url or "").strip() or p.video_url or p.imagenes:
        return None, None
    d = _normalizar_diseno(p, canal)
    if not (d["con_frase"] or d["con_logo"]) or not p.usar_compuesta:
        return None, d
    try:
        datos = _componer_cacheado((p.imagen_url or "").strip(), _sin_firma_repetida((p.texto_imagen or "").strip(), d["firma"]) if d["con_frase"] else "",
                                   d["firma"], d["formato"], d["tipografia"], d["posicion"], d["alineacion"],
                                   d["logo"] if d["con_logo"] else None, d["posicion_logo"], d["peso"])
        return datos, d
    except Exception as e:
        avisos.append(f"No pude componer la imagen: {e}. Se sigue con la foto sola.")
        return None, d


def _subir_compuesta(cfg, compuesta, titulo, texto, usuario, avisos):
    """La imagen compuesta tiene que estar en internet para IG/FB: va a la biblioteca de WordPress."""
    nombre = f"pieza-{datetime.date.today().isoformat()}-{(titulo or texto)[:40]}".strip()
    nombre = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in nombre).strip("-") + ".jpg"
    res_img = publicar.subir_imagen_wordpress(cfg, compuesta, nombre, titulo=titulo or texto[:60], quien=usuario,
                                              pieza=titulo or texto[:60], etiquetas=["pieza-compuesta"])
    if res_img.get("url"):
        return res_img["url"]
    if res_img.get("modo") == "simulado":
        # (2/11) en «Ver simulado» todos los canales van en simulado, WordPress también: la compuesta no se sube y la vista
        # muestra la foto sola. No es un problema de configuración: al enviar de verdad se sube (WordPress está en borrador o real).
        avisos.append("Prueba simulada: la imagen con la frase encima no se sube al banco, por eso acá se ve la foto sola. Al enviarla de verdad se sube y sale con la frase.")
        return None
    avisos.append((res_img.get("aviso") or "No se pudo subir la imagen compuesta.") + " Se publica la foto sin la frase encima."
                  + (" (Para que funcione, WordPress tiene que estar en modo borrador o real.)" if res_img.get("modo") == "apagado" else ""))
    return None


def _validar(p: PiezaCompleta, simulado=False):
    canal = (p.canal or "").strip().lower()
    if canal not in CANALES:
        raise HTTPException(400, "Elegí el canal (Blogpost, Instagram, Facebook o YouTube). El newsletter se arma en su editor.")
    p.aplicar_carrusel(canal)     # (5/11, Franco) si es un carrusel: valida y deja imagen_url = la portada, sin frase ni logo
    if not (p.texto or "").strip():
        raise HTTPException(400, "Falta el texto de la pieza.")
    if canales.CANALES[canal].requiere_titulo and not (p.titulo or "").strip():
        raise HTTPException(400, f"En {CANAL_TXT[canal]} hace falta un título.")
    if canal == "youtube" and not (p.video_url or "").strip() and not simulado:
        raise HTTPException(400, "En YouTube hace falta el video: publicá un recorte (desde «Mis recortes» → Publicar). Subir un archivo de video propio todavía no se puede desde la web.")
    return canal


def _datos_borrador(p: Pieza, canal, fecha_iso):
    """El dict `pieza` que guarda «💾 Guardar borrador» y que el formulario sabe retomar (= Pieza.a_borrador)."""
    return p.a_borrador(canal, fecha_iso)


def pieza_de_fila(p):
    """La pieza para precargar el formulario desde cualquier fila (= Pieza.desde_fila), como dict con los campos del modelo.
    `borrador_id` es el id de la fila: la web lo anula si la fila no es un borrador."""
    return Pieza.desde_fila(p, _fecha_hora_de_iso).model_dump()


def decorar(p):
    """Campos derivados que dibuja «Mis publicaciones» / el panel."""
    res = p.get("resultado") or {}
    est = p.get("estado") or ""
    ultimo = res.get("ultimo") if isinstance(res.get("ultimo"), dict) else {}
    p["estado_texto"] = ESTADO_TXT.get(est, est)
    p["canal_texto"] = CANAL_TXT.get((p.get("canal") or "").lower(), p.get("canal") or "")
    p["video_url"] = res.get("video_url")
    p["imagenes"] = res.get("imagenes") or None      # (5/11, Franco) carrusel: las fotos en orden; imagen_url es la primera
    p["texto_imagen"] = res.get("texto_imagen")
    p["formato"] = res.get("formato")
    p["nota"] = res.get("nota")
    p["propuesta_por"] = res.get("propuesta_por")
    p["aprobada_por"], p["aprobada_en"] = res.get("aprobada_por"), res.get("aprobada_en")
    p["rechazada_por"], p["rechazada_en"] = res.get("rechazada_por"), res.get("rechazada_en")
    p["corregida_por"] = res.get("corregida_por")       # (4/11) quién corrigió una rechazada
    p["cancelada_por"] = res.get("cancelada_por")
    p["plantilla"] = (res.get("pieza") or {}).get("plantilla") or res.get("plantilla") if p.get("canal") == "newsletter" else None
    # «ver publicación ↗»: el permalink (IG/FB) o el link (WP/YT) de lo que efectivamente salió
    p["ver_url"] = ultimo.get("permalink") or ultimo.get("link") or res.get("permalink") or res.get("link") or None
    p["link_editar"] = ultimo.get("link_editar") or res.get("link_editar") or None
    p["error_texto"] = str(ultimo.get("aviso", ""))[:200] if est == "error" else None
    p["eliminable"] = est in db.ELIMINABLES
    p["compartido"] = bool(p.get("compartido"))      # (2/11) compartida con el equipo (publicaciones.compartido)
    # (2/11) también una prueba («Ver simulado»): Julián diseñó una historia, la probó sin guardar borrador y no podía retomarla
    # (4/11) y una rechazada: deja de ser final, se corrige en la misma fila y se reenvía (el newsletter, en su editor)
    p["retomable"] = est in ("borrador", "prueba", "rechazada")
    p["corregible"] = est == "rechazada"
    return p


def permiso_pieza(p, usuario, rol):
    """(4/11) 'dueño' | 'editar' | 'ver' | None. Editan la dueña, un aprobador y quien la tiene en un proyecto con permiso
    «editar» (directo o heredado de la carpeta de arriba). Ven además quien la tiene con «ver» y cualquiera si está
    compartida con el equipo."""
    if p.get("usuario") == usuario:
        return "dueño"
    if rol.get("aprueba"):
        return "editar"
    from .proyectos import permiso_por_proyectos
    perm = permiso_por_proyectos("pieza", p.get("id"), usuario)
    if perm:
        return perm
    return "ver" if p.get("compartido") else None


def _borrador_ajeno(borrador_id, usuario, rol):
    """(4/11) Para guardar / enviar un borrador retomado: devuelve la dueña si quien edita puede tocarlo (ella misma o alguien
    con permiso «editar»), None si no hay borrador, no es un borrador o no hay permiso. La pieza sigue siendo de su dueña."""
    if not borrador_id or not db.disponible():
        return None
    fila = db.obtener_publicacion(borrador_id)
    if not fila or fila.get("estado") not in CORREGIBLES:
        return None
    return fila.get("usuario") if permiso_pieza(fila, usuario, rol) in ("dueño", "editar") else None


# (4/11) lo que se retoma en la misma fila: un borrador y una rechazada que se corrige
CORREGIBLES = ("borrador", "rechazada")


def _cerrar_borrador(borrador_id, duena, nuevo_pid):
    """Al enviar o mandar a aprobación: las carpetas que tenían el borrador pasan a la pieza nueva, y el borrador se borra."""
    if not borrador_id or not duena:
        return
    if nuevo_pid:
        from .proyectos import reasignar_en_proyectos
        reasignar_en_proyectos("pieza", borrador_id, nuevo_pid)
    _borrar_borrador(borrador_id, duena)


def _fila(pid):
    if not db.disponible():
        raise HTTPException(503, "Sin Supabase: no hay publicaciones.")
    p = db.obtener_publicacion(pid)
    if not p:
        raise HTTPException(404, "No existe esa pieza.")
    return p


# ---------------- Opciones y banco ----------------
@router.get("/publicar/opciones")
def opciones(request: Request):
    """Para el formulario: las listas de imagen.py (logos, tipografías, pesos, posiciones, alineaciones, formatos), el modo real de
    cada canal y el que ve esta persona (Quien no publica en real ve todo simulado), si puede mandar a
    aprobación por canal, y su rol."""
    usuario, rol = _rol(request)
    r = cr.modos()
    return {"canales": cr.info_canales(r, rol), "publica": bool(rol.get("publica")), "aprueba": bool(rol.get("aprueba")), "rol": rol.get("nombre"),
            "aprobadores": rol.get("aprobadores") or [], "usuario": usuario,
            "logos": list(imagen.LOGOS), "logos_url": {k: v for k, v in imagen.LOGOS.items() if v},
            "posiciones_logo": list(imagen.POSICIONES_LOGO), "tipografias": list(imagen.TIPOGRAFIAS), "tipografia_defecto": imagen.TIPOGRAFIA_DEFAULT,
            "pesos": list(imagen.PESOS), "posiciones": list(imagen.POSICIONES), "alineaciones": list(imagen.ALINEACIONES),
            "formatos": {k: list(v) for k, v in imagen.FORMATOS.items()}, "formato_por_canal": FORMATO_POR_CANAL,
            "firma_defecto": FIRMA_DEFECTO, "zona": ZONA_HORARIA}


@router.post("/banco/subir")
async def subir_al_banco(archivo: UploadFile = File(...), titulo: str = Form(""), pieza: str = Form(""), usuario=Depends(auth.usuario_actual)):
    """= «…o subí un archivo (va al banco de WordPress)»: publicar.subir_imagen_wordpress con el modo real de WordPress.
    En simulado/apagado no sube nada y lo dice (para Instagram/Facebook la imagen tiene que estar en internet)."""
    tipo = (archivo.content_type or "").lower()
    if not tipo.startswith("image/"):
        raise HTTPException(400, "Solo imágenes (jpg, png, webp).")
    datos = await archivo.read()
    if not datos:
        raise HTTPException(400, "El archivo está vacío.")
    if len(datos) > MAX_IMAGEN_BYTES:
        raise HTTPException(413, "La imagen pesa más de 12 MB.")
    nombre = re.sub(r"[^A-Za-z0-9._-]+", "-", archivo.filename or "imagen.jpg").strip("-") or "imagen.jpg"
    try:
        res = publicar.subir_imagen_wordpress(_cfg_real(), datos, nombre, titulo=titulo or nombre, quien=usuario, pieza=pieza or titulo or nombre)
    except Exception as e:
        raise HTTPException(502, f"No pude subir la imagen a WordPress: {e}")
    return {"ok": bool(res.get("url")), "url": res.get("url"), "id": res.get("id"), "modo": res.get("modo"),
            "aviso": res.get("aviso") or ("Imagen subida a la biblioteca de medios (ya queda en el banco)." if res.get("url") else None)}


@router.post("/publicar/componer")
def componer(datos: Componer, usuario=Depends(auth.usuario_actual)):
    """La vista previa de la foto con la frase (imagen.componer_imagen, mismos parámetros que el formulario).
    Devuelve el JPEG. Sin frase ni logo, devuelve la foto recortada al formato."""
    url = (datos.imagen_url or "").strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "Hace falta la URL de la foto (del banco o una que ya esté en internet).")
    formato = datos.formato if datos.formato in imagen.FORMATOS else "cuadrado"
    logo = datos.logo if datos.logo in imagen.LOGOS and imagen.LOGOS.get(datos.logo) else None
    texto = (datos.texto_imagen or "").strip()
    firma = (datos.firma if datos.firma is not None else FIRMA_DEFECTO).strip() if texto else ""
    try:
        jpg = _componer_cacheado(url, _sin_firma_repetida(texto, firma), firma, formato,
                                 datos.tipografia if datos.tipografia in imagen.TIPOGRAFIAS else imagen.TIPOGRAFIA_DEFAULT,
                                 datos.posicion if datos.posicion in imagen.POSICIONES else "centro",
                                 datos.alineacion if datos.alineacion in imagen.ALINEACIONES else "centro",
                                 logo, datos.posicion_logo if datos.posicion_logo in imagen.POSICIONES_LOGO else "abajo derecha",
                                 datos.peso if datos.peso in imagen.PESOS else "normal")
    except Exception as e:
        raise HTTPException(502, f"No pude componer la imagen: {e}")
    return Response(jpg, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=600"})


# ---------------- Guardar borrador · Enviar a aprobación · Enviar / Ver simulado ----------------
class PiezaBorrador(PiezaCompleta):
    version: Optional[str] = None      # (5/11) la versión que la pantalla cargó (resultado.guardado_en): si otra persona guardó después, 409


@router.post("/publicar/borrador")
def guardar_borrador(p: PiezaBorrador, request: Request):
    """= «💾 Guardar borrador»: guarda todo (diseño incluido) sin mandar nada; se retoma desde «Mis publicaciones» → Borradores.
    Con borrador_id actualiza el mismo («al guardar se actualiza el mismo»). (4/11) También el de otra persona si quien guarda
    tiene permiso «editar» por un proyecto: sigue siendo de su dueña y queda quién lo editó por última vez."""
    usuario, rol = _rol(request)
    if not db.disponible():
        raise HTTPException(503, "No pude guardar el borrador (falta la base de datos).")
    canal = (p.canal or "").strip().lower()
    if canal not in CANALES:
        raise HTTPException(400, "Elegí el canal para guardar el borrador.")
    p.aplicar_carrusel(canal, estricto=False)
    fecha_iso = _fecha_iso(p.fecha, p.hora)
    duena = usuario
    conservar = None
    if p.borrador_id:
        fila = _fila(p.borrador_id)
        if fila.get("estado") not in CORREGIBLES:
            raise HTTPException(409, "Ese borrador ya no existe: se guarda uno nuevo si volvés a intentar sin el id.")
        duena = _borrador_ajeno(p.borrador_id, usuario, rol)
        if not duena:
            raise HTTPException(409, "Ese borrador es de otra persona y no tenés permiso para editarlo: se guarda uno nuevo, tuyo, si volvés a intentar sin el id.")
        c409 = _presencia.conflicto(p.version, *_presencia.version_de_fila(fila), usuario)     # (5/11) ¿alguien guardó mientras editabas?
        if c409:
            return c409
        # (4/11) una rechazada que se corrige pasa a borrador en la misma fila y conserva el rechazo (quién, cuándo, la nota)
        conservar = db.historial_de(fila.get("resultado"))
        if fila.get("estado") == "rechazada" or conservar.get("rechazada_por"):
            conservar.update(corregida_por=usuario, corregida_en=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"))
    pid = db.guardar_borrador(duena, canal, p.titulo or "", p.texto or "", (p.imagen_url or "").strip() or None,
                              (fecha_iso + ZONA_HORARIA) if fecha_iso else None, _datos_borrador(p, canal, fecha_iso), pid=p.borrador_id, por=usuario,
                              conservar=conservar)
    if not pid:
        raise HTTPException(503, "No pude guardar el borrador.")
    version = _version_guardada(pid)
    if duena != usuario:
        return {"ok": True, "id": pid, "estado": "borrador", "version": version, "mensaje": f"Cambios guardados. El borrador sigue siendo de {duena} y queda en la misma carpeta."}
    if p.borrador_id:
        return {"ok": True, "id": pid, "estado": "borrador", "version": version, "mensaje": "Cambios guardados en el mismo borrador. Lo retomás desde «Mis publicaciones»."}
    return {"ok": True, "id": pid, "estado": "borrador", "version": version, "mensaje": "Guardado como borrador. Lo retomás desde «Mis publicaciones», filtro Borradores."}


def _version_guardada(pid):
    """(5/11) La versión recién guardada (resultado.guardado_en), para que la pantalla la mande en el próximo guardado."""
    try:
        return _presencia.version_de_fila(db.obtener_publicacion(pid))[0]
    except Exception:
        return None


def _borrar_borrador(borrador_id, usuario):
    """Al enviar o mandar a aprobación, el borrador que se estaba retomando se elimina."""
    try:
        db.borrar_borrador(borrador_id, usuario)
    except Exception as e:
        log.warning("No pude borrar el borrador %s: %s", borrador_id, e)


@router.post("/publicar/a-aprobar")
def enviar_a_aprobacion(p: PiezaCompleta, request: Request):
    """= «📨 Enviar a aprobación» sube la imagen compuesta a WordPress (si hay frase o
    logo y WordPress está en borrador/real) y deja la pieza 'a_aprobar' con texto_imagen, formato y video_url para la cola."""
    usuario, rol = _rol(request)
    if not db.disponible():
        raise HTTPException(503, "No pude guardar la pieza para aprobación (falta la base de datos).")
    canal = _validar(p)
    r = cr.modos()
    if not cr._puede_proponer(canal, r):
        if canal == "youtube":
            raise HTTPException(400, f"YouTube está en modo {r.get('youtube', 'apagado')}: no hay a dónde mandar el video cuando lo aprueben. Guardalo como borrador.")
        raise HTTPException(400, f"{CANAL_TXT[canal]} está en modo {r.get(canal, 'apagado')}: no hay a dónde mandar la pieza cuando la aprueben. Guardala como borrador.")
    fecha_iso = _fecha_iso(p.fecha, p.hora)
    nombre = CANALES[canal]
    texto = p.texto if canal == "wordpress" else cr._texto_plano(p.texto)
    avisos = []
    imagen_url = (p.imagen_url or "").strip() or None
    compuesta, diseno = _compuesta_de(p, canal, avisos)
    duena = _borrador_ajeno(p.borrador_id, usuario, rol)     # (4/11) un borrador ajeno con permiso «editar» sigue siendo de su dueña
    token = _contexto.set({"usuario": usuario, "titulo": p.titulo, "texto_imagen": p.texto_imagen, "fecha": fecha_iso,
                           "pieza_form": _datos_borrador(p, canal, fecha_iso)})
    try:
        if compuesta is not None:
            url = _subir_compuesta(_cfg_real(), compuesta, p.titulo or "", texto, usuario, avisos)
            if url:
                imagen_url = url
    finally:
        _contexto.reset(token)
    formato = (p.vfmt if p.video_url else (diseno or {}).get("formato")) if canal in ("instagram", "facebook") else None
    # (4/11) el formulario completo (foto original y diseño) queda guardado: si la rechazan, se corrige desde ahí y no desde la
    # imagen ya compuesta
    extra = {"texto_imagen": (p.texto_imagen or None), "formato": formato or None, "video_url": (p.video_url or None), "imagenes": p.imagenes, "origen": "web",
             "pieza": _datos_borrador(p, canal, fecha_iso)}
    try:
        if duena:     # (4/11) un borrador o una rechazada que se corrige: la misma fila pasa a a_aprobar (mismo id, misma carpeta)
            previa = db.obtener_publicacion(p.borrador_id) or {}
            pid = db.reproponer_publicacion(p.borrador_id, duena, canal, r.get(canal), p.titulo or "", texto, imagen_url,
                                            (fecha_iso + ZONA_HORARIA) if fecha_iso else None, extra=extra, por=usuario,
                                            previo=previa.get("resultado"))
        else:
            pid = db.proponer_publicacion(usuario, canal, r.get(canal), p.titulo or "", texto, imagen_url,
                                          (fecha_iso + ZONA_HORARIA) if fecha_iso else None, extra=extra, por=usuario)
    except Exception as e:
        raise HTTPException(503, f"No pude guardar la pieza para aprobación: {e}")
    if not pid:
        raise HTTPException(503, "No pude guardar la pieza para aprobación.")
    import avisos as _avisos
    _avisos.pieza_a_aprobar(db, pid, usuario, canal, p.titulo, texto, formato)   # (2/11) Slack / mail a los aprobadores, en un hilo
    quien = ", ".join(rol.get("aprobadores") or []) or "un aprobador"
    return {"ok": True, "id": pid, "estado": "a_aprobar", "modo": "aprobacion", "imagen_url": imagen_url, "avisos": avisos,
            "mensaje": f"Quedó pendiente de aprobación ({quien}). Si la aprueban, sale por {nombre}"
                       + (f" el {fecha_iso[:16].replace('T', ' ')}" if fecha_iso else " en la próxima corrida de la cola") + "."}


@router.post("/publicar/enviar")
def enviar(p: Envio, request: Request):
    """= «Enviar a <canal>» (modo real, 403 siempre: nadie publica directo desde el 5/11) y «👁 Ver simulado» (modo simulado: arma la pieza tal cual
    saldría y la muestra; no manda nada y queda como 'prueba' en el registro). Sube la imagen compuesta
    a WordPress, encola si hay fecha y el canal no programa solo, o llama al conector. Devuelve el resultado del conector."""
    usuario, rol = _rol(request)
    simulado = (p.modo or "simulado") != "real"
    if not simulado:     # (5/11) nadie publica directo, tampoco aprobadores ni admins: se publica desde Aprobación
        raise HTTPException(403, "Las piezas se publican desde Aprobación: mandala a aprobación.")
    canal = _validar(p, simulado=simulado)
    nombre = CANALES[canal]
    cfg_real = _cfg_real()
    cfg = _cfg_simulada(cfg_real) if simulado else cfg_real
    modo = cfg.resumen()[canal]
    if modo == "apagado":
        raise HTTPException(400, f"{CANAL_TXT[canal]} está apagado. No se puede hacer nada por este canal.")
    fecha_iso = _fecha_iso(p.fecha, p.hora)
    texto = p.texto if canal == "wordpress" else cr._texto_plano(p.texto)
    titulo = (p.titulo or "").strip()
    avisos = []
    imagen_url = (p.imagen_url or "").strip() or None
    compuesta, diseno = _compuesta_de(p, canal, avisos)
    formato = (p.vfmt if p.video_url else (diseno or {}).get("formato")) if canal in ("instagram", "facebook") else None
    video_url = (p.video_url or "").strip() or None
    duena = _borrador_ajeno(p.borrador_id, usuario, rol)     # (4/11) un borrador ajeno con permiso «editar» sigue siendo de su dueña
    ctx = {"usuario": usuario, "titulo": titulo, "texto_imagen": p.texto_imagen, "fecha": fecha_iso,
           "pieza_form": _datos_borrador(p, canal, fecha_iso), "duena": duena or usuario,
           "por": usuario if duena and duena != usuario else None}
    token = _contexto.set(ctx)
    try:
        if compuesta is not None:
            # En «Ver simulado» la cfg es la simulada: no sube nada y avisa
            url = _subir_compuesta(cfg, compuesta, titulo, texto, usuario, avisos)
            if url:
                imagen_url = url
        if fecha_iso and _va_a_la_cola(canal, modo):
            try:
                pid = db.encolar_publicacion(duena or usuario, canal, modo, titulo, texto, imagen_url, fecha_iso + ZONA_HORARIA,
                                             extra={"texto_imagen": p.texto_imagen or None, "formato": formato or None, "video_url": video_url, "imagenes": p.imagenes, "origen": "web",
                                                    **({"viene_de": p.borrador_id} if duena else {})},
                                             por=usuario)
            except Exception as e:
                raise HTTPException(503, f"No pude guardar la pieza en la cola: {e}")
            if not pid:
                raise HTTPException(503, "No pude guardar la pieza en la cola (¿falta Supabase?).")
            _cerrar_borrador(p.borrador_id, duena, pid)
            cuando = fecha_iso[:16].replace("T", " ")
            return {"ok": True, "modo": modo, "encolada": True, "id": pid, "estado": "pendiente", "imagen_url": imagen_url, "avisos": avisos,
                    "aviso": f"Quedó en la cola para el {cuando}. Ese día sale sola por {nombre}, con el modo que tenga el canal en ese momento (hoy: {modo}). "
                             "Se puede cancelar desde Aprobación → En cola.",
                    "imagenes": p.imagenes,
                    "pieza": {"image_url": imagen_url, ("caption" if canal == "instagram" else "message"): texto, "fecha_programada": fecha_iso,
                              **({"imagenes": p.imagenes} if p.imagenes else {})}}
        try:   # (3/11) el mismo despacho que la cola: publicar.enviar_pieza con la pieza armada como una fila de `publicaciones`
            res = publicar.enviar_pieza(cfg, {"canal": canal, "titulo": titulo, "texto": texto, "imagen_url": imagen_url, "fecha_programada": fecha_iso,
                                              "resultado": {"video_url": video_url, "imagenes": p.imagenes, "formato": formato, "texto_imagen": p.texto_imagen or None}},
                                        quien=usuario)
        except HTTPException:
            raise
        except Exception as e:
            log.exception("publicar")
            res = {"ok": False, "modo": modo, "aviso": f"No pude publicar: {e}"}
    finally:
        _contexto.reset(token)
    if res.get("ok"):
        _cerrar_borrador(p.borrador_id, duena, ctx.get("pid"))
    salida = {k: v for k, v in res.items() if k in ("ok", "modo", "aviso", "estado", "id", "link", "link_editar", "permalink", "privacidad", "pieza")}
    salida.update(encolada=False, imagen_url=imagen_url, avisos=avisos, simulado=(modo == "simulado"),
                  texto_final=texto, formato=formato, video_url=video_url, imagenes=p.imagenes)
    return salida


# ---------------- Mis publicaciones: una pieza, retomar, eliminar ----------------
@router.get("/publicaciones/{pid}")
def una_publicacion(pid: str, request: Request):
    """La pieza decorada, más `pieza`: el dict con que el formulario se precarga («✏️ Retomar» o «Usar como base»).
    (4/11) La ve su dueña, un aprobador, cualquiera si la dueña la compartió con el equipo, y quien la tiene en un proyecto
    propio o compartido. `propia` dice si es de quien la mira. `permiso` (dueño, editar, ver): con «editar» la web la retoma
    (edición en colaboración), con «ver» la muestra en solo lectura."""
    usuario, rol = _rol(request)
    p = _fila(pid)
    permiso = permiso_pieza(p, usuario, rol)
    if not permiso:
        raise HTTPException(403, "Esa pieza es de otra persona y no está compartida con vos.")
    propia = permiso == "dueño"
    p = decorar(p)
    p["pieza"] = pieza_de_fila(p)
    p["propia"] = propia
    p["permiso"] = permiso               # (4/11) con «editar» se retoma la misma pieza: edición en colaboración
    p["editada_por"] = (p.get("resultado") or {}).get("editada_por")
    p["version"] = _presencia.version_de_fila(p)[0]     # (5/11) control de versión al guardar
    if permiso == "ver":
        p["retomable"] = False
    if not propia:                       # borrar sigue siendo solo de la dueña
        p["eliminable"] = False
    return p


@router.delete("/publicaciones/{pid}")
def eliminar_publicacion(pid: str, usuario=Depends(auth.usuario_actual)):
    """= «🗑 Eliminar»: borra de verdad, solo si es propia y está en un estado eliminable (db.ELIMINABLES)."""
    if not db.disponible():
        raise HTTPException(503, "Sin Supabase: no hay publicaciones.")
    if not db.eliminar_publicacion(pid, usuario):
        raise HTTPException(409, "Esa pieza no se puede eliminar (no es tuya o ya salió / está en proceso).")
    from .proyectos import quitar_de_todos_los_proyectos
    quitar_de_todos_los_proyectos("pieza", pid)      # (2/11) que no quede como «(ya no existe)» en una carpeta
    return {"ok": True}


class CompartirPieza(BaseModel):
    compartido: bool


@router.post("/publicaciones/{pid}/compartir")
def compartir_publicacion(pid: str, datos: CompartirPieza, usuario=Depends(auth.usuario_actual)):
    """(2/11, Franco) Como «Compartir» en Mis recortes: la persona dueña muestra la pieza en «Del equipo» de las demás (solo lectura)
    o deja de mostrarla. Solo la dueña."""
    if not db.disponible():
        raise HTTPException(503, "Sin Supabase: no hay publicaciones.")
    r = db.obtener_publicacion(pid)
    if not r:
        raise HTTPException(404, "No existe esa pieza.")
    if r.get("usuario") != usuario:
        raise HTTPException(403, "Solo quien hizo la pieza puede compartirla.")
    db.actualizar_publicacion(pid, {"compartido": bool(datos.compartido)})
    return {"ok": True, "compartido": bool(datos.compartido)}


# ---------------- Aprobación ----------------
@router.get("/aprobacion/para-aprobar")
def para_aprobar(usuario=Depends(auth.aprobador)):
    """Las piezas a_aprobar (más viejas primero) con los datos de la vista previa, y el modo REAL de cada canal (el panel lo muestra:
    «el canal hoy está en modo X»). Sugerencia de fecha/hora como el panel: la pedida, o hoy + 20 min."""
    if not db.disponible():
        return {"piezas": [], "modos": {}}
    r = cr.modos()
    ahora = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-3))) + datetime.timedelta(minutes=20)
    piezas = []
    for p in db.listar_a_aprobar():
        p = decorar(p)
        f, h = _fecha_hora_de_iso(p.get("fecha_programada"))
        p["fecha_sugerida"], p["hora_sugerida"] = (f or ahora.strftime("%Y-%m-%d")), (h or ahora.strftime("%H:%M"))
        piezas.append(p)
    return {"piezas": piezas, "modos": {c: r.get(c, "apagado") for c in CANALES}}


@router.post("/aprobacion/{pid}/aprobar")
def aprobar(pid: str, datos: Aprobar, usuario=Depends(auth.aprobador)):
    """= «✅ Aprobar y programar»: pasa a 'pendiente' con la fecha/hora elegida (editable) y el modo real del canal; la cola la saca
    ese día (corre cada 15 min). Newsletter: queda 'lista' (el HTML se descarga y se pega en Perfit)."""
    p = _fila(pid)
    if p.get("estado") != "a_aprobar":
        raise HTTPException(409, f"Esa pieza ya no está pendiente de aprobación (estado: {ESTADO_TXT.get(p.get('estado'), p.get('estado'))}).")
    res = p.get("resultado") or {}
    canal = p.get("canal") or ""
    ahora = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    if canal == "newsletter":
        db.actualizar_publicacion(pid, {"estado": "lista", "resultado": dict(res, aprobada_por=usuario, aprobada_en=ahora)})
        import avisos as _avisos
        _avisos.pieza_resuelta(db, p, "aprobada", usuario)
        return {"ok": True, "estado": "lista", "mensaje": "Aprobado. El HTML queda en «Mis publicaciones» de quien lo propuso y en el Registro, para descargar y pegar en Perfit."}
    fecha = datos.fecha or datetime.date.today().isoformat()
    hora = datos.hora or "09:00"
    fecha_iso = _fecha_iso(fecha, hora)
    modo = cr.modos().get(canal, "")
    db.aprobar_publicacion(pid, usuario, fecha_iso + ZONA_HORARIA, modo, res)
    import avisos as _avisos
    _avisos.pieza_resuelta(db, p, "aprobada", usuario, cuando=fecha_iso[:16].replace("T", " "))   # (2/11) aviso a quien la hizo
    return {"ok": True, "estado": "pendiente", "fecha_programada": fecha_iso + ZONA_HORARIA, "modo": modo,
            "mensaje": f"Aprobada. Sale por la cola el {fecha_iso[:16].replace('T', ' ')} (la cola corre cada 15 min)."}


@router.post("/aprobacion/{pid}/rechazar")
def rechazar(pid: str, datos: Rechazar, usuario=Depends(auth.aprobador)):
    """= «✖ Rechazar» con nota: quien la propuso lo ve en «Mis publicaciones» → Rechazadas."""
    p = _fila(pid)
    if p.get("estado") != "a_aprobar":
        raise HTTPException(409, "Esa pieza ya no está pendiente de aprobación.")
    db.rechazar_publicacion(pid, usuario, (datos.nota or "").strip(), p.get("resultado") or {})
    import avisos as _avisos
    _avisos.pieza_resuelta(db, p, "rechazada", usuario, nota=(datos.nota or "").strip() or None)   # (2/11) aviso a quien la hizo
    return {"ok": True, "estado": "rechazada", "mensaje": "Rechazada. Quien la propuso lo ve en «Mis publicaciones»."}


@router.get("/aprobacion/cola")
def cola(usuario=Depends(auth.aprobador)):
    """= «🗓 En cola»: las piezas pendientes, por fecha."""
    if not db.disponible():
        return []
    return [decorar(p) for p in db.listar_pendientes()]


@router.post("/aprobacion/{pid}/cancelar")
def cancelar(pid: str, usuario=Depends(auth.aprobador)):
    """= «Cancelar» de la cola: estado 'cancelada' con quién la canceló."""
    p = _fila(pid)
    if p.get("estado") != "pendiente":
        raise HTTPException(409, "Solo se cancela una pieza que está en la cola.")
    db.cancelar_publicacion(pid, usuario)
    return {"ok": True, "estado": "cancelada"}


@router.get("/aprobacion/registro")
def registro(usuario=Depends(auth.aprobador)):
    """= «📒 Registro»: quién creó cada pieza, quién la aprobó o rechazó y qué pasó (las últimas 60, sin subidas ni pruebas ni borradores)."""
    if not db.disponible():
        return []
    return [decorar(p) for p in db.listar_registro() if p.get("estado") not in NO_SON_PIEZAS]


@router.get("/aprobacion/papelera")
def papelera(usuario=Depends(auth.aprobador)):
    """= «🗑 Papelera»: conversaciones que alguien borró; se restauran durante db.PAPELERA_DIAS días."""
    if not db.disponible():
        return {"conversaciones": [], "dias": db.PAPELERA_DIAS}
    return {"conversaciones": db.listar_papelera() or [], "dias": db.PAPELERA_DIAS}


@router.post("/aprobacion/papelera/{cid}/restaurar")
def restaurar_de_papelera(cid: str, usuario=Depends(auth.aprobador)):
    """= «↩ Restaurar»: vuelve a aparecer en la lista de esa persona."""
    if not db.disponible():
        raise HTTPException(503, "Sin Supabase.")
    db.restaurar_conversacion(cid)
    return {"ok": True}
