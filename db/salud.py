"""Historial de salud de la API (tabla salud_historial) y tamaño de la base (función SQL tamano_base).
(3/11, revisión 5.2 punto 12) Antes en db.py. Las funciones se llaman entre sí y a _req a través del paquete (`_db.x`), así
`monkeypatch.setattr(db, "x", …)` en las pruebas vale para todas. Los parámetros de los filtros van escapados con _q.
"""
import json, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timezone, timedelta

import db as _db
from ._cliente import _q


# ---------------- Salud de los servicios (22/10, api/salud.py) ----------------
# Tabla salud_historial (migración api/migraciones/000_esquema_base.sql (tabla salud_historial)): id, creado, estado (ok/aviso/error), detalle jsonb
# ({chequeos: [{nombre, estado, detalle}], ms}). Una fila por corrida de GET /salud/servicios; sirve para decir «desde cuándo».
def guardar_salud(estado, detalle):
    return _db._req("POST", "", {"estado": estado, "detalle": detalle}, tabla="salud_historial")


def listar_salud(limite=100):
    """Las últimas corridas, más recientes primero."""
    if not _db.disponible():
        return []
    return _db._req("GET", f"?select=id,creado,estado,detalle&order=creado.desc&limit={limite}", tabla="salud_historial") or []


def contar_arranques(horas=24):
    """Cuántas veces arrancó la API en las últimas `horas` (filas estado='arranque' de salud_historial: en el plan free de
    Render cada arranque es un despertar en frío, ~1 min hasta responder)."""
    if not _db.disponible():
        return 0
    desde = (datetime.now(timezone.utc) - timedelta(hours=horas)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return len(_db._req("GET", f"?estado=eq.arranque&creado=gte.{_q(desde)}&select=creado&limit=1000", tabla="salud_historial") or [])


def tamano_base():
    """{bytes, tablas: {nombre: {filas, bytes}}} vía la función SQL _db.tamano_base() (migración tamano_base)."""
    return _db._rpc("tamano_base", {})
