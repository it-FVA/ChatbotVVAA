"""Lo que la pantalla de chat de la web necesita además del chat en sí (22/10, fase 2 del plan de interfaz propia).
Misma lógica de negocio que la app de Streamlit (app.py y publicar_ui.formulario), sin inventar otra; si cambia una regla
allá, cambiarla acá. El chat en streaming sigue en api/main.py + api/chat.py.

Rutas (todas con sesión; la conversación tiene que ser de la persona):
  PATCH  /conversaciones/{id}                      {titulo}: renombrar (= «✏️ Renombrar» de la barra)
  DELETE /conversaciones/{id}                      a la papelera (= «🗑️ Borrar conversación»; db.borrar_conversacion marca `borrada`)
  POST   /conversaciones/{id}/restaurar            la saca de la papelera (solo la propia)
  GET    /conversaciones/{id}/mensajes/{n}/docx    la respuesta n como Word (documentos.md_a_docx; «⬇️ Word» de app.py)
  GET    /conversaciones/{id}/mensajes/{n}/xlsx    las tablas de la respuesta n como Excel (documentos.tablas_a_xlsx; «⬇️ Excel»)
  GET    /conversaciones/{id}/recortes             estado de los clips de los videos citados en esa conversación (para refrescar las tarjetas)
  POST   /recortes                                 {video_id, inicio_ms, fin_ms, formato, titulo}: = «✂️ Pedir el recorte» / «📱 Pedir en vertical»
  GET    /banco?consulta=&formato=                 fotos del banco de WordPress (publicar_ui._banco)
  GET    /publicaciones/modos                      el modo de cada canal y si se puede mandar a aprobación (publicar_ui.formulario)
  POST   /publicaciones/borrador                   = «💾 Guardar borrador» (db.guardar_borrador, mismos campos que Streamlit)
  POST   /publicaciones/a-aprobar                  = «📨 Enviar a aprobación» (db.proponer_publicacion, como publicar_ui._enviar(aprobacion=True))
"""
import os, re, logging, unicodedata
from urllib.parse import quote
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from . import auth, roles as _roles
import db            # noqa: E402  (api/__init__ pone la raíz del repo en sys.path)
import publicar      # noqa: E402
import documentos    # noqa: E402

log = logging.getLogger("api")
router = APIRouter(tags=["chat"])

# Las mismas constantes que publicar_ui (ese módulo importa Streamlit y no se puede importar acá).
CANALES = {"wordpress": "WordPress", "instagram": "Instagram", "facebook": "Facebook", "youtube": "YouTube"}
ZONA_HORARIA = "-03:00"            # publicar_ui.ZONA_HORARIA: las fechas del recuadro son hora de Argentina
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


class Pieza(BaseModel):
    """Lo que la persona dejó en el recuadro «Publicar esta pieza» de la web (los campos del recuadro de Streamlit)."""
    canal: str                       # wordpress | instagram | facebook | youtube
    titulo: str = ""
    texto: str = ""
    imagen_url: Optional[str] = None
    fecha: Optional[str] = None      # 'YYYY-MM-DD'
    hora: Optional[str] = None       # 'HH:MM'
    texto_imagen: Optional[str] = None
    firma: Optional[str] = None
    imagen_busqueda: Optional[str] = None
    video_url: Optional[str] = None
    video_formato: Optional[str] = None
    borrador_id: Optional[str] = None   # (uuid) si se está retomando un borrador: se actualiza (o se elimina al mandar a aprobación)


# ---------------- Helpers ----------------
def _conversacion(cid, usuario):
    if not db.disponible():
        raise HTTPException(503, "Sin Supabase: no hay conversaciones guardadas.")
    c = db.cargar_conversacion_de(cid, usuario)
    if not c:
        raise HTTPException(404, "No existe esa conversación (o no es tuya).")
    return c


def _texto_plano(t):
    """Copia de publicar_ui._texto_plano: para redes, saca markdown y links, deja texto pegable."""
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
    """'YYYY-MM-DDTHH:MM:SS' como arma el formulario (hora 09:00 si falta), o None si no se programa."""
    if not p.fecha:
        return None
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.fecha):
        raise HTTPException(400, "La fecha tiene que ser AAAA-MM-DD.")
    hora = (p.hora or "09:00").strip()
    if not re.fullmatch(r"\d{1,2}:\d{2}", hora):
        raise HTTPException(400, "La hora tiene que ser HH:MM.")
    hh, mm = hora.split(":")
    return f"{p.fecha}T{int(hh):02d}:{int(mm):02d}:00"


def _validar_pieza(p: Pieza):
    canal = (p.canal or "").strip().lower()
    if canal not in CANALES:
        raise HTTPException(400, "Elegí el canal (WordPress, Instagram, Facebook o YouTube). El newsletter se arma en su editor, en Streamlit.")
    if not (p.texto or "").strip():
        raise HTTPException(400, "Falta el texto de la pieza.")
    if canal in ("wordpress", "youtube") and not (p.titulo or "").strip():
        raise HTTPException(400, f"En {CANALES[canal]} hace falta un título.")
    return canal


def _datos_borrador(p: Pieza, canal, fecha_iso):
    """El dict `pieza` que guarda publicar_ui (botón «💾 Guardar borrador») y que formulario() sabe retomar.
    Las claves de diseño (fmt, logo, tipografía…) quedan en None: el diseño de la foto es de la fase 3."""
    return {"canal": canal, "titulo": p.titulo or "", "texto": p.texto or "", "texto_imagen": p.texto_imagen or "",
            "video_url": p.video_url or None, "video_formato": p.video_formato or None, "vfmt": None,
            "url": p.imagen_url or "", "busq": p.imagen_busqueda or "", "firma": p.firma or None,
            "fmt": None, "logo": None, "plogo": None, "tipo": None, "peso": None, "pos": None, "ali": None,
            "fecha": fecha_iso[:10] if fecha_iso else None, "hora": fecha_iso[11:16] if fecha_iso else None,
            "origen": "web"}


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
        return {"wordpress": "apagado", "instagram": "apagado", "facebook": "apagado", "youtube": "apagado"}


def _puede_proponer(canal, r):
    """publicar_ui.formulario: «Enviar a aprobación» existe para WordPress, Instagram y Facebook cuando el canal real está
    en 'real' o 'borrador' (si no, no hay a dónde mandarla cuando la aprueben)."""
    return canal in ("wordpress", "instagram", "facebook") and r.get(canal) in ("real", "borrador")


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
    """= los botones «✂️ Pedir el recorte» / «📱 Pedir en vertical» de app._botones_clip, con las validaciones del
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
    """Fotos del banco de WordPress, como publicar_ui._banco: primero las etiquetadas con el formato, después la consulta
    sola, después las recientes. [{id, url, miniatura, titulo}]; sin credenciales de WordPress, lista vacía."""
    n = max(1, min(int(n or 6), 12))
    consulta = (consulta or "").strip()
    formato = formato if formato in ("cuadrado", "vertical", "historia") else None
    try:
        cfg = publicar.Config(os.environ)
        res = []
        if formato and formato not in consulta.lower():
            res = publicar.buscar_imagenes_banco(cfg, f"{consulta} {formato}".strip(), n=n)
            res = [r for r in res if formato in (r.get("titulo") or "").lower()]
        if not res and consulta:
            res = publicar.buscar_imagenes_banco(cfg, consulta, n=n)
        if not res:
            res = publicar.imagenes_recientes_banco(cfg, n=n)
        return res or []
    except Exception as e:
        log.warning("banco: %s", e)
        return []


@router.get("/publicaciones/modos")
def publicaciones_modos(s=Depends(auth.sesion)):
    """Para el recuadro: el modo de cada canal (como la línea «Instagram en modo real» del formulario), si esta persona
    publica en real y a qué canales puede mandar a aprobación."""
    r = modos()
    rol = _roles.roles(s["usuario"], s.get("rol_tabla"))
    return {"canales": {c: {"nombre": nombre, "modo": r.get(c, "apagado"), "texto": MODO_TXT.get(r.get(c, "apagado"), r.get(c, "")),
                            "a_aprobar": _puede_proponer(c, r)} for c, nombre in CANALES.items()},
            "publica": bool(rol.get("publica")), "aprobadores": rol.get("aprobadores") or []}


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
                              (fecha_iso + ZONA_HORARIA) if fecha_iso else None, _datos_borrador(p, canal, fecha_iso),
                              pid=p.borrador_id)
    if not pid:
        raise HTTPException(503, "No pude guardar el borrador.")
    return {"ok": True, "id": pid, "estado": "borrador",
            "mensaje": "Guardado como borrador. Lo retomás desde «Mis publicaciones», filtro Borradores."}


@router.post("/publicaciones/a-aprobar")
def enviar_a_aprobacion(p: Pieza, s=Depends(auth.sesion)):
    """= «📨 Enviar a aprobación» (publicar_ui._enviar con aprobacion=True): la pieza queda 'a_aprobar' para el panel.
    No sube la foto compuesta ni archivos (fase 3): la imagen es una URL del banco o nada."""
    usuario = s["usuario"]
    if not db.disponible():
        raise HTTPException(503, "No pude guardar la pieza para aprobación (falta la base de datos).")
    canal = _validar_pieza(p)
    r = modos()
    if not _puede_proponer(canal, r):
        if canal == "youtube":
            raise HTTPException(400, "YouTube no pasa por aprobación: el video se publica desde Publicar en Streamlit (fase 3 en la web).")
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
    if p.borrador_id:        # como Streamlit: al mandarla, el borrador que se estaba retomando se elimina
        try:
            db._req("DELETE", f"?id=eq.{quote(str(p.borrador_id))}&estado=eq.borrador&usuario=eq.{quote(usuario)}", tabla="publicaciones")
        except Exception:
            pass
    rol = _roles.roles(usuario, s.get("rol_tabla"))
    quien = ", ".join(rol.get("aprobadores") or []) or "un aprobador"
    return {"ok": True, "id": pid, "estado": "a_aprobar",
            "mensaje": f"Quedó pendiente de aprobación ({quien}). Si la aprueban, sale por {CANALES[canal]}"
                       + (f" el {fecha_iso[:16].replace('T', ' ')}" if fecha_iso else " en la próxima corrida de la cola") + "."}
