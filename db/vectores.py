"""Búsqueda en Postgres (tabla fragmentos_emb; funciones match_fragmentos_varios, match_lexico).
(3/11, revisión 5.2 punto 12) Antes en db.py. Las funciones se llaman entre sí y a _req a través del paquete (`_db.x`), así
`monkeypatch.setattr(db, "x", …)` en las pruebas vale para todas. Los parámetros de los filtros van escapados con _q.
"""
import json, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timezone, timedelta

import db as _db
from ._cliente import _q


def match_fragmentos(vectores, k=300):
    """Los k fragmentos más parecidos a CADA vector (lista de listas de 512 floats), fusionados por máximo.
    Devuelve {idx: similitud} ordenable; idx es la posición en fragmentos.jsonl."""
    if not vectores:
        return {}
    filas = _db._rpc("match_fragmentos_varios", {"query_embeddings": vectores, "k": int(k)})
    return {int(f["idx"]): float(f["similitud"]) for f in filas}


def match_lexico(consulta, k=300):
    """Búsqueda de texto de Postgres (to_tsvector spanish + ts_rank_cd): [idx, ...] del más al menos relevante."""
    if not (consulta or "").strip():
        return []
    return [int(f["idx"]) for f in _db._rpc("match_lexico", {"consulta": consulta, "k": int(k)})]


def contar_fragmentos_emb():
    """Cuántas filas tiene fragmentos_emb (para verificar que coincide con el corpus); -1 si no se pudo."""
    url, key = _db._cfg()
    req = urllib.request.Request(f"{url}/rest/v1/fragmentos_emb?select=idx&limit=1", headers={
        "apikey": key, "Authorization": "Bearer " + key, "Prefer": "count=exact", "Range-Unit": "items", "Range": "0-0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            rango = r.headers.get("Content-Range") or ""
            return int(rango.split("/")[-1]) if "/" in rango and not rango.endswith("*") else -1
    except Exception:
        return -1
