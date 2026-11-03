"""Servicios y costos (tabla servicios).
(3/11, revisión 5.2 punto 12) Antes en db.py. Las funciones se llaman entre sí y a _req a través del paquete (`_db.x`), así
`monkeypatch.setattr(db, "x", …)` en las pruebas vale para todas. Los parámetros de los filtros van escapados con _q.
"""
import json, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timezone, timedelta

import db as _db
from ._cliente import _q


# ---------------- Servicios y costos (21/10, Franco: "todos los servicios que usamos, qué cuestan y para qué") ----------------
# Tabla servicios (migración servicios_costos): nombre, proveedor, para_que, plan, costo_mensual_usd, confirmado
# (el monto sale de la factura/plan verificado; si no, es referencia), desde, url, notas, activo, actualizado_por.
CAMPOS_SERVICIO = "id,nombre,proveedor,para_que,plan,costo_mensual_usd,confirmado,desde,url,notas,activo,actualizado_por,actualizado"


def listar_servicios(solo_activos=False):
    if not _db.disponible():
        return []
    q = f"?select={CAMPOS_SERVICIO}&order=costo_mensual_usd.desc.nullslast,nombre.asc"
    if solo_activos:
        q += "&activo=is.true"
    return _db._req("GET", q, tabla="servicios") or []


def guardar_servicio(datos, usuario=None):
    """Crea (sin id) o actualiza (con id) un servicio."""
    datos = dict(datos)
    datos["actualizado_por"] = usuario
    import datetime as _dt
    datos["actualizado"] = _dt.datetime.now(_dt.timezone.utc).isoformat()
    sid = datos.pop("id", None)
    if sid:
        return _db._req("PATCH", f"?id=eq.{_q(sid)}", datos, tabla="servicios")
    return _db._req("POST", "", datos, tabla="servicios")


def borrar_servicio(sid):
    return _db._req("DELETE", f"?id=eq.{_q(sid)}", tabla="servicios")
