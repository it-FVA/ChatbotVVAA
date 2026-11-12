"""Configuración persistente (tabla config: clave jsonb), compartida por la API y la cola.
(3/11, revisión 5.2 punto 12) Antes en db.py. Las funciones se llaman entre sí y a _req a través del paquete (`_db.x`), así
`monkeypatch.setattr(db, "x", …)` en las pruebas vale para todas. Los parámetros de los filtros van escapados con _q.
"""
import json, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timezone, timedelta

import db as _db
from ._cliente import _q


# ---------------- Configuraciones persistentes (19/10) ----------------
# Tabla config(clave text pk, valor jsonb, actualizado, por): lo que el equipo ajusta desde el Panel admin y tiene que
# valer también para la cola de GitHub Actions (que no ve la sesión de la API). Hoy una sola clave:
# 'clips_estilo' = estilo por defecto de los subtítulos de los recortes nuevos (migración config_tabla_y_clips_estilo).
# (19/10, tarde) Frase del día: 'frase_activa' (bool, apagada por defecto), 'frase_hora' ("07:00" Argentina), 'frase_imagen' (URL de
# la foto de fondo por defecto), 'frase_pie' (lo que va al final del caption) y 'frase_estilo' (logo, tipografía, posición).

def obtener_config(clave, defecto=None):
    if not _db.disponible():
        return defecto
    r = _db._req("GET", f"?clave=eq.{urllib.parse.quote(clave)}&select=valor", tabla="config")
    return r[0]["valor"] if r else defecto


def listar_config():
    """(3/11) Todas las claves con quién y cuándo las cambió (Administración → Configuración)."""
    return _db.consulta("config", select="clave,valor,actualizado,por", order="clave")


def guardar_config(clave, valor, usuario=None):
    """Crea o reemplaza la clave (upsert por la clave primaria). valor=None se guarda como "" (la columna no admite null)."""
    if valor is None:
        valor = ""
    url, key = _db._cfg()
    data = json.dumps({"clave": clave, "valor": valor, "por": usuario,
                       "actualizado": datetime.now(timezone.utc).isoformat()}).encode("utf-8")
    # (12/11) cabeceras con el helper del paquete: con la clave acotada de la cola el `apikey` tiene que ser la anon, no el JWT
    # propio (el gateway daba «Invalid API key» y la cola no podía guardar config: ni metricas_ultima_captura ni el token de IG).
    from ._cliente import _cabeceras
    req = urllib.request.Request(f"{url}/rest/v1/config", data=data, method="POST", headers=_cabeceras(key, {
        "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates,return=representation"}))
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8") or "[]")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Supabase {e.code}: {e.read().decode('utf-8','ignore')[:200]}")
