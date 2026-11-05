"""El cliente REST de Supabase (PostgREST con urllib): lo único que habla con la base.
(3/11, revisión 5.2 punto 12) Antes repartido en db.py. Acá viven _req (la llamada cruda), consulta() (la ÚNICA forma de armar una
consulta con filtros: escapa siempre los valores), _rpc y los helpers de fecha/escape. Los módulos por dominio (db/publicaciones.py…)
los usan a través del paquete (`_db._req`), así las pruebas que reemplazan `db._req` por una base de juguete siguen valiendo.
"""
import json, os, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timezone

import db as _db


def _cfg():
    """(url, clave). (3/11, revisión 5.3 punto 21) Si existe SUPABASE_KEY_COLA (la clave acotada de la cola, rol de Postgres «cola»:
    api/migraciones/manual_cola_rol.sql) se usa esa; si no, SUPABASE_KEY (service_role). Solo la cola de GitHub Actions la tiene:
    la API de Render no, así que sigue con service_role."""
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    if url.endswith("/rest/v1"):          # por si pegan la URL con /rest/v1
        url = url[:-len("/rest/v1")]
    return url, os.environ.get("SUPABASE_KEY_COLA", "").strip() or os.environ.get("SUPABASE_KEY", "")


# (5/11) Clave pública «anon» del proyecto (publishable: está en cualquier cliente del navegador, no es un secreto). El gateway de
# Supabase exige en la cabecera `apikey` una clave CONOCIDA (anon o service_role); un JWT propio como el de la cola ahí da
# «Invalid API key». Por eso con SUPABASE_KEY_COLA el `apikey` es la anon y el rol va solo en `Authorization: Bearer`.
ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImtoZ2Zxa2xpZXByY3B4cnlxaHR1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODgzNTY1MTIsImV4cCI6MjEwMzkzMjUxMn0.0rTFai5tTQaImYlHDGw51_NU6VlwhD8FNon0kKG9M5Y"


def _cabeceras(key, extra=None):
    """apikey + Authorization para una clave: service_role o anon van en las dos; la clave acotada de la cola solo en Bearer."""
    apikey = key
    if key and key == os.environ.get("SUPABASE_KEY_COLA", "").strip():
        apikey = os.environ.get("SUPABASE_ANON_KEY", "").strip() or ANON_KEY
    h = {"apikey": apikey, "Authorization": "Bearer " + key}
    h.update(extra or {})
    return h


def disponible():
    url, key = _db._cfg()
    return bool(url and key)


def _q(v):
    """Un valor dentro de un filtro de PostgREST, escapado (un `&` o un `,` en un id no agrega filtros)."""
    return urllib.parse.quote(str(v), safe="")


def _ahora_iso():
    return datetime.now(timezone.utc).isoformat()


def _req(method, params="", body=None, tabla="conversaciones", prefer=None, timeout=30):
    """La llamada cruda a PostgREST. `params` ya armado (empieza con ?). Devuelve la lista de filas (o [] si no hay cuerpo).
    Errores HTTP, cortes de red y timeouts → RuntimeError con texto legible."""
    url, key = _db._cfg()
    full = f"{url}/rest/v1/{tabla}{params}"
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = urllib.request.Request(full, data=data, method=method, headers=_cabeceras(key, {
        "Content-Type": "application/json", "Prefer": prefer or "return=representation"}))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            txt = r.read().decode("utf-8")
            return json.loads(txt) if txt.strip() else []
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Supabase {e.code}: {e.read().decode('utf-8','ignore')[:200]}")
    except (urllib.error.URLError, TimeoutError, OSError) as e:      # (3/11) corte de red o timeout: mismo tipo de error que el HTTP
        motivo = getattr(e, "reason", None) or e
        raise RuntimeError(f"Supabase sin conexión ({type(motivo).__name__}: {str(motivo)[:150]})")


def filtros_a_params(filtros=None, select=None, order=None, limite=None):
    """Arma el query string de PostgREST escapando SIEMPRE los valores.
    filtros: dict {columna: (operador, valor)} o lista de (columna, operador, valor); valor None con 'is' → is.null;
             'in' recibe una lista. Ej.: {"id": ("eq", pid), "estado": ("in", ["a", "b"]), "borrada": ("is", None)}."""
    partes = []
    items = filtros.items() if isinstance(filtros, dict) else (filtros or [])
    for item in items:
        col, (op, val) = (item[0], (item[1], item[2])) if len(item) == 3 else item
        if op == "in":
            v = "(" + ",".join(_q(x) for x in val) + ")"
        elif op == "is":
            v = "null" if val is None else ("true" if val else "false")
        else:
            v = _q(val)
        partes.append(f"{col}={op}.{v}")
    if select:
        partes.append("select=" + (select if isinstance(select, str) else ",".join(select)))
    if order:
        partes.append("order=" + order)
    if limite:
        partes.append(f"limit={int(limite)}")
    return ("?" + "&".join(partes)) if partes else ""


def consulta(tabla, filtros=None, select="*", order=None, limite=None):
    """LA función de lectura: SELECT con filtros escapados. Devuelve la lista de filas."""
    return _db._req("GET", filtros_a_params(filtros, select, order, limite), tabla=tabla) or []


def insertar(tabla, fila_o_filas, select=None, upsert=None):
    """INSERT (o upsert por `upsert`=columna/s de conflicto). Devuelve las filas creadas."""
    params = filtros_a_params(None, select) if select else ""
    if upsert:
        params += ("&" if params else "?") + f"on_conflict={upsert}"
    if upsert:
        return _db._req("POST", params, fila_o_filas, tabla=tabla, prefer="resolution=merge-duplicates,return=representation") or []
    return _db._req("POST", params, fila_o_filas, tabla=tabla) or []


def actualizar(tabla, filtros, campos, select=None):
    """UPDATE con filtros escapados. Devuelve las filas cambiadas."""
    return _db._req("PATCH", filtros_a_params(filtros, select), campos, tabla=tabla) or []


def borrar(tabla, filtros):
    """DELETE con filtros escapados (nunca sin filtros)."""
    if not filtros:
        raise ValueError("borrar() exige filtros")
    return _db._req("DELETE", filtros_a_params(filtros), tabla=tabla) or []


def ping():
    """Una lectura mínima para saber si la base responde (api/salud)."""
    return _db._req("GET", "?select=clave&limit=1", tabla="config")


def _rpc(nombre, body, timeout=30):
    url, key = _db._cfg()
    req = urllib.request.Request(f"{url}/rest/v1/rpc/{nombre}", data=json.dumps(body).encode("utf-8"), method="POST",
                                 headers=_db._cabeceras(key, {"Content-Type": "application/json"}))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            txt = r.read().decode("utf-8")
            return json.loads(txt) if txt.strip() else []
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Supabase rpc/{nombre} {e.code}: {e.read().decode('utf-8', 'ignore')[:200]}")
