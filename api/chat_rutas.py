"""Lo que la pantalla de chat de la web necesita además del chat en sí (22/10, fase 2 del plan de interfaz propia).
Una sola lógica de negocio para las piezas del chat; si cambia una regla
allá, cambiarla acá. El chat en streaming sigue en api/main.py + api/chat.py.

Rutas (todas con sesión; la conversación tiene que ser de la persona):
  PATCH  /conversaciones/{id}                      {titulo}: renombrar (= «✏️ Renombrar» de la barra)
  DELETE /conversaciones/{id}                      a la papelera (= «🗑️ Borrar conversación»; db.borrar_conversacion marca `borrada`)
  POST   /conversaciones/{id}/restaurar            la saca de la papelera (solo la propia)
  GET    /conversaciones/{id}/mensajes/{n}/docx    la respuesta n como Word (documentos.md_a_docx; «⬇️ Word»)
  GET    /conversaciones/{id}/mensajes/{n}/xlsx    las tablas de la respuesta n como Excel (documentos.tablas_a_xlsx; «⬇️ Excel»)
  GET    /conversaciones/{id}/recortes             estado de los clips de los videos citados en esa conversación (para refrescar las tarjetas)
  POST   /recortes                                 {video_id, inicio_ms, fin_ms, formato, titulo}: = «✂️ Pedir el recorte» / «📱 Pedir en vertical»
  GET    /banco?consulta=&formato=                 fotos del banco de WordPress
  GET    /publicaciones/modos                      el modo de cada canal y si se puede mandar a aprobación
  POST   /publicaciones/borrador                   = «💾 Guardar borrador» (db.guardar_borrador)
  POST   /publicaciones/a-aprobar                  = «📨 Enviar a aprobación» (db.proponer_publicacion(aprobacion=True))
"""
import os, re, logging, unicodedata
from urllib.parse import quote
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from . import auth, roles as _roles
from .pieza import Pieza, ZONA_HORARIA     # (3/11) el modelo único de la pieza (también lo usa publicar_rutas)
import db            # noqa: E402  (api/__init__ pone la raíz del repo en sys.path)
import publicar      # noqa: E402
import documentos    # noqa: E402
import canales       # noqa: E402

log = logging.getLogger("api")
router = APIRouter(tags=["chat"])

# Constantes de publicación. (3/11) Los canales salen del registro único canales.py.
CANALES = canales.nombres()        # {"wordpress": "WordPress", ...}: los de Diseñar
MODO_TXT = {"apagado": "apagado: este canal no está disponible",
            "simulado": "simulado: arma la pieza y la muestra, NO la manda",
            "borrador": "borrador: la crea en WordPress sin publicar; se publica desde el panel",
            "privado": "privado: sube el video como privado; se publica desde YouTube Studio",
            "real": "REAL: publica de verdad"}
RECORTE_MAX_MS = 15 * 60 * 1000    # nucleo._ejecutar_tool('pedir_recorte'): un recorte dura menos de 15 minutos
TIPO_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
TIPO_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


# ---------------- Modelos de entrada ----------------
class Renombrar(BaseModel):
    titulo: str


class PedidoRecorte(BaseModel):
    video_id: str
    inicio_ms: int
    fin_ms: int
    formato: str = "horizontal"     # 'horizontal' | 'vertical'
    titulo: Optional[str] = None


# ---------------- Helpers ----------------
def _conversacion(cid, usuario):
    if not db.disponible():
        raise HTTPException(503, "Sin Supabase: no hay conversaciones guardadas.")
    c = db.cargar_conversacion_de(cid, usuario)
    if not c:
        raise HTTPException(404, "No existe esa conversación (o no es tuya).")
    return c


def _texto_plano(t):
    """Copia: para redes, saca markdown y links, deja texto pegable."""
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\1", t or "")
    t = re.sub(r"https?://\S+", "", t)
    t = re.sub(r"^\s{0,3}#{1,6}\s*", "", t, flags=re.M)
    t = re.sub(r"^\s*>\s?", "", t, flags=re.M)
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)
    t = re.sub(r"(?<!\w)[_*](.+?)[_*](?!\w)", r"\1", t)
    t = re.sub(r"^\s*[-*]\s+", "• ", t, flags=re.M)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def _fecha_iso(p: Pieza):
    """'YYYY-MM-DDTHH:MM:SS' como arma el formulario (hora 09:00 si falta), o None si no se programa (= Pieza.fecha_iso)."""
    return p.fecha_iso()


def _validar_pieza(p: Pieza):
    canal = (p.canal or "").strip().lower()
    if canal not in CANALES:
        raise HTTPException(400, "Elegí el canal (WordPress, Instagram, Facebook o YouTube). El newsletter se arma en su editor: Campañas → Newsletter.")
    if not (p.texto or "").strip():
        raise HTTPException(400, "Falta el texto de la pieza.")
    if canales.CANALES[canal].requiere_titulo and not (p.titulo or "").strip():
        raise HTTPException(400, f"En {CANALES[canal]} hace falta un título.")
    return canal


def _adjunto(nombre, ext):
    """Content-Disposition con el nombre en ASCII (sin tildes) y, aparte, el nombre real en UTF-8 (RFC 5987)."""
    ascii_ = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode() or "documento"
    return {"Content-Disposition": f'attachment; filename="{ascii_}.{ext}"; ' + "filename*=UTF-8''" + f"{quote(nombre)}.{ext}"}


def modos():
    """publicar.Config(os.environ).resumen(): el modo real de cada canal (en la API los secrets están en el entorno)."""
    try:
        return publicar.Config(os.environ).resumen()
    except Exception as e:
        log.warning("No pude leer la configuración de publicar: %s", e)
        return {c: "apagado" for c in canales.CANALES}


def _puede_proponer(canal, r):
    """«Enviar a aprobación» existe cuando el canal lo admite (canales.py) y el canal real está en 'real' o 'borrador'."""
    c = canales.canal(canal)
    return bool(c and c.puede_proponer(r.get(canal)))


def info_canales(r, rol):
    """(3/11) Lo que la web necesita de cada canal de Diseñar, armado acá y no en listas propias de la web: nombres, el modo real y
    el que ve esta persona (todos ven simulado: nadie publica directo desde el 5/11), si va a la cola con fecha, si pasa por aprobación y el
    aviso de qué va a pasar al enviar (con y sin fecha; «{cuando}» lo reemplaza la web por la fecha legible)."""
    out = {}
    for c in canales.de_disenar():
        modo_real = r.get(c.clave, "apagado")
        modo = modo_real if modo_real == "apagado" else "simulado"     # (5/11) nadie publica directo: lo que ve cada persona es simulado
        out[c.clave] = {"nombre": c.nombre, "texto_canal": c.texto, "detalle": c.detalle, "modo_real": modo_real, "modo": modo,
                        "texto": MODO_TXT.get(modo, modo), "a_aprobar": c.puede_proponer(modo_real), "acepta_aprobacion": c.acepta_aprobacion,
                        "requiere_titulo": c.requiere_titulo, "formato": c.formato, "va_a_la_cola": c.va_a_la_cola(modo),
                        "configurado": bool((r.get("configurado") or {}).get(c.clave, r.get({"wordpress": "wp_configurado", "instagram": "ig_configurado",
                                                                                               "facebook": "fb_configurado", "youtube": "yt_configurado"}.get(c.clave), False))),
                        "aviso_sin_fecha": canales.aviso(c.clave, modo, False), "aviso_con_fecha": canales.aviso(c.clave, modo, True)}
    return out


# ---------------- Conversaciones: renombrar, papelera, descargas ----------------
@router.patch("/conversaciones/{cid}")
def renombrar(cid: str, datos: Renombrar, usuario=Depends(auth.usuario_actual)):
    c = _conversacion(cid, usuario)
    titulo = " ".join((datos.titulo or "").split())[:120] or (c.get("titulo") or "Conversación")
    db.renombrar(c["id"], titulo)
    return {"ok": True, "id": c["id"], "titulo": titulo}


@router.delete("/conversaciones/{cid}")
def borrar(cid: str, usuario=Depends(auth.usuario_actual)):
    """A la papelera (db.PAPELERA_DIAS días): no se borra de verdad. Se puede deshacer con POST .../restaurar."""
    c = _conversacion(cid, usuario)
    db.borrar_conversacion(c["id"])
    return {"ok": True, "id": c["id"], "dias": db.PAPELERA_DIAS}


@router.post("/conversaciones/{cid}/restaurar")
def restaurar(cid: str, usuario=Depends(auth.usuario_actual)):
    if not db.disponible():
        raise HTTPException(503, "Sin Supabase: no hay conversaciones guardadas.")
    c = db.restaurar_conversacion_de(cid, usuario)
    if not c:
        raise HTTPException(404, "No hay una conversación tuya con ese id en la papelera.")
    return {"ok": True, "id": c["id"], "titulo": c.get("titulo")}


def _respuesta(cid, n, usuario):
    c = _conversacion(cid, usuario)
    mensajes = db.normalizar(c.get("mensajes"))
    if n < 0 or n >= len(mensajes) or mensajes[n].get("role") != "assistant":
        raise HTTPException(404, "Ese mensaje no es una respuesta del asistente.")
    return c, mensajes[n].get("content") or ""


@router.get("/conversaciones/{cid}/mensajes/{n}/docx")
def descargar_docx(cid: str, n: int, usuario=Depends(auth.usuario_actual)):
    c, texto = _respuesta(cid, n, usuario)
    titulo = (c.get("titulo") or "Documento del asistente").strip()
    try:
        datos = documentos.md_a_docx(texto, titulo)
    except Exception as e:
        raise HTTPException(500, f"No pude armar el Word: {e}")
    nombre = documentos.nombre_archivo(titulo)
    return Response(datos, media_type=TIPO_DOCX, headers=_adjunto(nombre, "docx"))


@router.get("/conversaciones/{cid}/mensajes/{n}/xlsx")
def descargar_xlsx(cid: str, n: int, usuario=Depends(auth.usuario_actual)):
    c, texto = _respuesta(cid, n, usuario)
    tablas = documentos.tablas_md(texto)
    if not tablas:
        raise HTTPException(404, "Esa respuesta no tiene tablas.")
    titulo = (c.get("titulo") or "Planilla").strip()
    try:
        datos = documentos.tablas_a_xlsx(tablas, titulo)
    except Exception as e:
        raise HTTPException(500, f"No pude armar el Excel: {e}")
    nombre = documentos.nombre_archivo(titulo)
    return Response(datos, media_type=TIPO_XLSX, headers=_adjunto(nombre, "xlsx"))


# ---------------- Recortes desde las tarjetas ----------------
@router.get("/conversaciones/{cid}/recortes")
def recortes_de_la_conversacion(cid: str, usuario=Depends(auth.usuario_actual)):
    """Los clips (en cualquier estado) de los videos citados en la conversación: la web los consulta cada minuto
    mientras alguno está en proceso, para pasar la tarjeta de «en proceso» a «Ver el recorte»."""
    c = _conversacion(cid, usuario)
    vids = set()
    for m in db.normalizar(c.get("mensajes")):
        for r in (m.get("mats") or []):
            if r.get("fuente") == "youtube" and r.get("doc"):
                vids.add(r["doc"])
    return db.clips_de(sorted(vids)) if vids else []


@router.post("/recortes")
def pedir_recorte(datos: PedidoRecorte, usuario=Depends(auth.usuario_actual)):
    """= los botones «✂️ Pedir el recorte» / «📱 Pedir en vertical», con las validaciones del
    chat (nucleo._ejecutar_tool 'pedir_recorte'): fin > inicio y menos de 15 minutos. El pedido queda firmado por la
    persona; la cola (recortar_pendientes.yml) lo corta en unos 15 minutos."""
    if not db.disponible():
        raise HTTPException(503, "No pude registrar el pedido (falta la base de datos).")
    vid = (datos.video_id or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,}", vid):
        raise HTTPException(400, "Falta el id del video.")
    ini, fin = int(datos.inicio_ms), int(datos.fin_ms)
    if ini < 0 or fin <= ini or fin - ini > RECORTE_MAX_MS:
        raise HTTPException(400, "El tramo no es válido (el fin tiene que ser mayor que el inicio y el recorte, de menos de 15 minutos).")
    formato = "vertical" if (datos.formato or "").lower().startswith("v") else "horizontal"
    r = db.pedir_clip(vid, ini, fin, formato, datos.titulo, usuario)
    if r == "ya":
        ya = [c for c in db.clips_de([vid]) if int(c["inicio_ms"]) == ini and int(c["fin_ms"]) == fin and c["formato"] == formato]
        c = ya[0] if ya else {}
        return {"ok": True, "ya": True, "id": c.get("id"), "estado": c.get("estado") or "pedido", "url": c.get("url"),
                "mensaje": ("Ese recorte ya estaba hecho." if c.get("estado") == "listo" else "Ese recorte ya estaba pedido; está en proceso.")}
    if not r:
        raise HTTPException(503, "No pude registrar el pedido.")
    return {"ok": True, "ya": False, "id": r, "estado": "pedido", "url": None,
            "mensaje": "Pedido. En unos minutos aparece «Ver el recorte» en esta tarjeta."}


# ---------------- Pieza propuesta: banco de fotos, borrador, aprobación ----------------
@router.get("/banco")
def banco(consulta: str = "", formato: str = "", n: int = 6, usuario=Depends(auth.usuario_actual)):
    """Fotos del banco de WordPress: primero las etiquetadas con el formato, después la consulta
    sola, después las recientes. [{id, url, miniatura, titulo, fuente}]; sin credenciales de WordPress, lista vacía.
    (5/11) fuente = "banco" | "biblioteca": con la config `banco_solo` prendida solo busca en lo que subió el banco de Drive (marca
    banco-fva) y, si no hay nada para la consulta, devuelve las últimas del banco, nunca la biblioteca entera."""
    n = max(1, min(int(n or 6), 12))
    consulta = (consulta or "").strip()
    formato = formato if formato in ("cuadrado", "vertical", "historia") else None
    try:
        cfg = publicar.Config(os.environ)
        try:   # (5/11) «Buscar solo en el banco» (Configuración → Banco de imágenes): solo lo que subió banco.py desde Drive
            solo_banco = db.obtener_config("banco_solo", False) is True
        except Exception:
            solo_banco = False
        if solo_banco:
            fmt = {"historia": "vertical"}.get(formato, formato)       # el banco usa cuadrado / vertical / horizontal
            res = publicar.buscar_imagenes_banco(cfg, consulta, n=n, solo_banco=True, formato=fmt) if consulta else []
            if not res and fmt:    # sin nada para la consulta: las últimas del banco de ese formato, y si no, las últimas del banco
                res = publicar.buscar_imagenes_banco(cfg, "", n=n, solo_banco=True, formato=fmt)
            if not res:
                res = publicar.buscar_imagenes_banco(cfg, "", n=n, solo_banco=True)
            return [dict(r, fuente="banco") for r in res]
        res = []
        if formato and formato not in consulta.lower():
            res = publicar.buscar_imagenes_banco(cfg, f"{consulta} {formato}".strip(), n=n)
            res = [r for r in res if formato in (r.get("titulo") or "").lower()]
        if not res and consulta:
            res = publicar.buscar_imagenes_banco(cfg, consulta, n=n)
        if not res:
            res = publicar.imagenes_recientes_banco(cfg, n=n)
        return [dict(r, fuente="biblioteca") for r in (res or [])]
    except Exception as e:
        log.warning("banco: %s", e)
        return []


@router.get("/publicaciones/modos")
def publicaciones_modos(s=Depends(auth.sesion)):
    """Para el recuadro: el modo de cada canal (como la línea «Instagram en modo real» del formulario), si esta persona
    publica en real y a qué canales puede mandar a aprobación."""
    r = modos()
    rol = auth.rol_sesion(s)      # (22/10) tabla usuarios primero, como /yo
    # el modo que se informa acá es el REAL del canal (la línea «Instagram en modo real»); el que ve la persona va en `modo_visto`
    canales_ = {c: dict(x, modo=x["modo_real"], modo_visto=x["modo"], texto=MODO_TXT.get(x["modo_real"], x["modo_real"])) for c, x in info_canales(r, rol).items()}
    return {"canales": canales_, "publica": bool(rol.get("publica")), "aprobadores": rol.get("aprobadores") or [],
            "todos": canales.para_web()}


@router.post("/publicaciones/borrador")
def guardar_borrador(p: Pieza, usuario=Depends(auth.usuario_actual)):
    """= «💾 Guardar borrador»: guarda todo sin mandar nada; se retoma desde «Mis publicaciones», filtro Borradores."""
    if not db.disponible():
        raise HTTPException(503, "No pude guardar el borrador (falta la base de datos).")
    canal = (p.canal or "").strip().lower()
    if canal not in CANALES:
        raise HTTPException(400, "Elegí el canal para guardar el borrador.")
    fecha_iso = _fecha_iso(p)
    pid = db.guardar_borrador(usuario, canal, p.titulo or "", p.texto or "", (p.imagen_url or "").strip() or None,
                              (fecha_iso + ZONA_HORARIA) if fecha_iso else None, p.a_borrador(canal, fecha_iso),
                              pid=p.borrador_id)
    if not pid:
        raise HTTPException(503, "No pude guardar el borrador.")
    return {"ok": True, "id": pid, "estado": "borrador",
            "mensaje": "Guardado como borrador. Lo retomás desde «Mis publicaciones», filtro Borradores."}


@router.post("/publicaciones/a-aprobar")
def enviar_a_aprobacion(p: Pieza, s=Depends(auth.sesion)):
    """= «📨 Enviar a aprobación» la pieza queda 'a_aprobar' para el panel.
    No sube la foto compuesta ni archivos (fase 3): la imagen es una URL del banco o nada."""
    usuario = s["usuario"]
    if not db.disponible():
        raise HTTPException(503, "No pude guardar la pieza para aprobación (falta la base de datos).")
    canal = _validar_pieza(p)
    r = modos()
    if not _puede_proponer(canal, r):
        if canal == "youtube":
            raise HTTPException(400, f"YouTube está en modo {r.get('youtube', 'apagado')}: no hay a dónde mandar el video cuando lo aprueben. Guardalo como borrador.")
        raise HTTPException(400, f"{CANALES[canal]} está en modo {r.get(canal, 'apagado')}: no hay a dónde mandar la pieza cuando la aprueben. Guardala como borrador.")
    fecha_iso = _fecha_iso(p)
    texto = p.texto if canal == "wordpress" else _texto_plano(p.texto)
    imagen_url = (p.imagen_url or "").strip() or None
    try:
        pid = db.proponer_publicacion(usuario, canal, r.get(canal), p.titulo or "", texto, imagen_url,
                                      (fecha_iso + ZONA_HORARIA) if fecha_iso else None,
                                      extra={"texto_imagen": (p.texto_imagen or None), "formato": None,
                                             "video_url": (p.video_url or None), "origen": "web"})
    except Exception as e:
        raise HTTPException(503, f"No pude guardar la pieza para aprobación: {e}")
    if not pid:
        raise HTTPException(503, "No pude guardar la pieza para aprobación.")
    try:                     # al mandarla, el borrador que se estaba retomando se elimina
        db.borrar_borrador(p.borrador_id, usuario)
    except Exception as e:
        log.warning("No pude borrar el borrador %s: %s", p.borrador_id, e)
    import avisos as _avisos
    _avisos.pieza_a_aprobar(db, pid, usuario, canal, p.titulo, texto)   # (2/11) Slack / mail a los aprobadores
    rol = auth.rol_sesion(s)
    quien = ", ".join(rol.get("aprobadores") or []) or "un aprobador"
    return {"ok": True, "id": pid, "estado": "a_aprobar",
            "mensaje": f"Quedó pendiente de aprobación ({quien}). Si la aprueban, sale por {CANALES[canal]}"
                       + (f" el {fecha_iso[:16].replace('T', ' ')}" if fecha_iso else " en la próxima corrida de la cola") + "."}
