"""Recortes de video (tabla clips).
(3/11, revisión 5.2 punto 12) Antes en db.py. Las funciones se llaman entre sí y a _req a través del paquete (`_db.x`), así
`monkeypatch.setattr(db, "x", …)` en las pruebas vale para todas. Los parámetros de los filtros van escapados con _q.
"""
import json, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timezone, timedelta

import db as _db
from ._cliente import _q


# ---------------- Clips exactos (15/10, pedido de Beto) ----------------
# Tabla clips(video_id, inicio_ms, fin_ms, formato, estado, url, pedido_por, titulo, error, procesado_en,
#             srt, edicion, nota, estilo).
# Estados: 'pedido' (lo pidió alguien desde una tarjeta del chat) → 'listo' (recortar_pendientes.yml lo
# cortó desde el original en Drive y lo subió a WordPress; url) o 'error'.
# (19/10) srt: los subtítulos tal como se quemaron (solo vertical). edicion (JSON): lo que la persona cambió desde
# «✏️ Editar recorte» y la cola aplica al regenerar: {"srt": "..."} (subtítulos corregidos), "inicio_ms"/"fin_ms" (tramo
# nuevo; al terminar la cola los pasa a las columnas y los saca del JSON) y "estilo" (tipografía, tamaño, colores,
# negrita, posición de los subtítulos; ver recortar_clip.ESTILO_DEFECTO). estilo (19/10, tarde): el estilo con el que
# se quemaron los subtítulos (lo escribe la cola; la sección «Estilo» arranca de ahí). nota: aviso corto que se ve
# en la tarjeta. (La columna srt_editado quedó vacía y se puede borrar.)

def clips_de(video_ids):
    """Todos los clips (en cualquier estado) de esos videos, para dibujar las tarjetas en una sola consulta."""
    if not _db.disponible() or not video_ids:
        return []
    ids = ",".join(urllib.parse.quote(v) for v in sorted(set(video_ids)))
    return _db._req("GET", f"?video_id=in.({ids})&select=id,video_id,inicio_ms,fin_ms,formato,estado,url,error", tabla="clips") or []


def pedir_clip(video_id, inicio_ms, fin_ms, formato, titulo, usuario):
    if not _db.disponible():
        return None
    fila = {"video_id": video_id, "inicio_ms": int(inicio_ms), "fin_ms": int(fin_ms), "formato": formato,
            "titulo": (titulo or "")[:200], "pedido_por": usuario, "estado": "pedido"}
    try:
        r = _db._req("POST", "", fila, tabla="clips")
        return r[0]["id"] if r else None
    except RuntimeError as e:
        if "duplicate" in str(e) or "23505" in str(e):
            return "ya"
        raise


def clips_pedidos(limite=20):
    if not _db.disponible():
        return []
    return _db._req("GET", f"?estado=eq.pedido&select=id,video_id,inicio_ms,fin_ms,formato,titulo,pedido_por,url,edicion&order=creado.asc&limit={limite}", tabla="clips") or []


def listar_clips(limite=60):
    """Todos los clips, más recientes primero (solapa Clips del panel admin)."""
    if not _db.disponible():
        return []
    return _db._req("GET", f"?select=id,creado,video_id,inicio_ms,fin_ms,formato,titulo,pedido_por,estado,url,error,procesado_en,srt,edicion,nota,estilo,compartido&order=creado.desc&limit={limite}", tabla="clips") or []


def actualizar_clip(cid, campos):
    return _db._req("PATCH", f"?id=eq.{_q(cid)}", campos, tabla="clips")


def borrar_clip(cid):
    """(16/10) Saca el pedido de la tabla (el archivo de WordPress se borra aparte, en publicar.borrar_media_por_url)."""
    return _db._req("DELETE", f"?id=eq.{_q(cid)}", tabla="clips")


# ---------------- API HTTP, fase 1 (21/10, noche): editor de recortes de la web ----------------
def obtener_clip(cid):
    """Una fila de clips por id (las mismas columnas que listar_clips), o None."""
    if not _db.disponible() or not cid:
        return None
    r = _db._req("GET", f"?id=eq.{urllib.parse.quote(str(cid))}&select=id,creado,video_id,inicio_ms,fin_ms,formato,titulo,pedido_por,estado,url,error,procesado_en,srt,edicion,nota,estilo,compartido", tabla="clips")
    return r[0] if r else None


def clips_pedidos_antes(creado_antes_iso):
    """Clips que siguen en 'pedido' y se pidieron antes de esa fecha (ISO): los que la cola no procesó a tiempo."""
    if not _db.disponible():
        return []
    return _db._req("GET", f"?estado=eq.pedido&creado=lt.{urllib.parse.quote(creado_antes_iso)}&select=id,creado,video_id,titulo,pedido_por,formato&order=creado.asc&limit=50", tabla="clips") or []
