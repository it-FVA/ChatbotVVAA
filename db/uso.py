"""Actividad y uso de OpenAI (tabla uso_openai y lecturas transversales para «¿hubo movimiento?»).
(3/11, revisión 5.2 punto 12) Antes en db.py. Las funciones se llaman entre sí y a _req a través del paquete (`_db.x`), así
`monkeypatch.setattr(db, "x", …)` en las pruebas vale para todas. Los parámetros de los filtros van escapados con _q.
"""
import json, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timezone, timedelta

import db as _db
from ._cliente import _q


# ---------------- Uso (21/10, Franco: "¿hubo movimiento?" en pantalla) ----------------
def uso_actividad(dias=28):
    """Todo lo que pasó en los últimos `dias`: conversaciones (con cuántos mensajes propios), piezas y recortes.
    Devuelve {"conversaciones": [...], "publicaciones": [...], "clips": [...]} con los campos mínimos."""
    if not _db.disponible():
        return {"conversaciones": [], "publicaciones": [], "clips": []}
    import datetime as _dt
    desde = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=dias)).strftime("%Y-%m-%dT%H:%M:%SZ")   # sin "+": en la URL se vuelve espacio
    convs = _db._req("GET", f"?select=id,usuario,titulo,creado,actualizado,mensajes&actualizado=gte.{_q(desde)}&order=actualizado.desc&limit=500") or []
    for c in convs:
        ms = c.get("mensajes") or []
        c["n_mensajes"] = sum(1 for m in ms if m.get("role") == "user")
        c.pop("mensajes", None)
    pubs = _db._req("GET", f"?select=id,usuario,canal,modo,estado,titulo,creado&creado=gte.{_q(desde)}&order=creado.desc&limit=500", tabla="publicaciones") or []
    clips = _db._req("GET", f"?select=id,pedido_por,formato,estado,titulo,creado&creado=gte.{_q(desde)}&order=creado.desc&limit=500", tabla="clips") or []
    return {"conversaciones": convs, "publicaciones": pubs, "clips": clips}


def uso_ultima_vez():
    """{usuario: fecha de la última conversación tocada}, sobre todo el historial (sin la papelera)."""
    if not _db.disponible():
        return {}
    filas = _db._req("GET", "?select=usuario,actualizado&borrada=is.null&order=actualizado.desc&limit=2000") or []
    out = {}
    for f in filas:
        u = f.get("usuario")
        if u and u not in out:
            out[u] = f.get("actualizado")
    return out


# ---------------- Uso de OpenAI (21/10, monitoreo de costo) ----------------
# Tabla uso_openai (migración uso_openai): id, creado, usuario, modelo, que (chat/auxiliar/embedding),
# tokens_entrada, tokens_salida, tokens_cache. La escribe nucleo._registrar_uso en cada llamada.
# Los precios NO están en el código: viven en config 'openai_precios' = {modelo: {"entrada": USD por 1M tokens,
# "salida": USD por 1M, "cache": USD por 1M}} y los carga Franco desde Panel admin → Uso (sin precio, se muestran
# solo los tokens: nunca un costo inventado).
def registrar_uso(fila):
    if not _db.disponible():
        return None
    try:
        return _db._req("POST", "", fila, tabla="uso_openai")
    except Exception:
        return None


def uso_openai(dias=28, desde=None, hasta=None):
    """Filas de uso_openai: de los últimos `dias`, o entre `desde` y `hasta` (fechas ISO 'AAAA-MM-DD'). Hasta 20.000."""
    if not _db.disponible():
        return []
    import datetime as _dt
    if desde is None:
        desde = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=dias)).strftime("%Y-%m-%dT%H:%M:%SZ")
    q = f"?select=creado,usuario,modelo,que,tokens_entrada,tokens_salida,tokens_cache&creado=gte.{_q(desde)}"
    if hasta:
        q += f"&creado=lt.{_q(hasta)}"
    return _db._req("GET", q + "&order=creado.desc&limit=20000", tabla="uso_openai") or []
