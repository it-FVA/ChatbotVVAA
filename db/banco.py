"""Banco de imágenes (tabla banco_imagenes): lo que banco.sincronizar_banco subió desde Drive a WordPress (5/11).
Una fila por archivo de Drive (drive_id es la clave): nombre, modified_time, wp_id, url, formato, etiquetas, subido_en.
Las funciones se llaman a través del paquete (`_db.x`) para que `monkeypatch.setattr(db, "x", …)` valga en las pruebas.
"""
from datetime import datetime, timezone

import db as _db


def banco_registro():
    """{drive_id: {modified_time, wp_id, …}} de todo lo subido. Sin Supabase: {}."""
    if not _db.disponible():
        return {}
    filas = _db.consulta("banco_imagenes", select="drive_id,nombre,modified_time,wp_id,url,formato,subido_en", limite=20000)
    return {f["drive_id"]: f for f in filas}


def banco_guardar(drive_id, nombre, modified_time, wp_id, url, formato, etiquetas):
    """Upsert por drive_id (si el archivo cambió y se re-subió, la fila se actualiza)."""
    fila = {"drive_id": drive_id, "nombre": nombre, "modified_time": modified_time, "wp_id": wp_id, "url": url,
            "formato": formato, "etiquetas": list(etiquetas or []), "subido_en": datetime.now(timezone.utc).isoformat()}
    return _db.insertar("banco_imagenes", fila, upsert="drive_id")


def banco_resumen():
    """{"total", "por_formato": {formato: n}, "ultima": ISO de la última subida o None}."""
    if not _db.disponible():
        return {"total": 0, "por_formato": {}, "ultima": None}
    filas = _db.consulta("banco_imagenes", select="formato,subido_en", limite=20000)
    por = {}
    for f in filas:
        k = f.get("formato") or "sin formato"
        por[k] = por.get(k, 0) + 1
    ultima = max((f.get("subido_en") or "" for f in filas), default="") or None
    return {"total": len(filas), "por_formato": por, "ultima": ultima}
