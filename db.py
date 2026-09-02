"""
Guardado de conversaciones en Supabase (Postgres). Compartido por las dos UIs.
Config por entorno/secrets: SUPABASE_URL, SUPABASE_KEY (service_role key).

Si no hay credenciales, disponible() da False y las apps siguen andando SIN guardar
(modo prototipo), así nunca se rompe por falta de base.

Tabla esperada (crear una vez en Supabase → SQL Editor):

    create table conversaciones (
      id uuid primary key default gen_random_uuid(),
      usuario text not null,
      titulo text,
      mensajes jsonb not null default '[]',
      creado timestamptz not null default now(),
      actualizado timestamptz not null default now()
    );
    create index on conversaciones (usuario, actualizado desc);
"""
import os, json, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timezone


def _cfg():
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    if url.endswith("/rest/v1"):          # por si pegan la URL con /rest/v1
        url = url[:-len("/rest/v1")]
    return url, os.environ.get("SUPABASE_KEY", "")


def disponible():
    url, key = _cfg()
    return bool(url and key)


def normalizar(mensajes):
    """Lleva cualquier mensaje (rol/texto o role/content) al formato canónico."""
    out = []
    for m in (mensajes or []):
        if m.get("role"):
            role = m["role"]
        elif m.get("rol") == "u":
            role = "user"
        else:
            role = "assistant"
        out.append({"role": role,
                    "content": m.get("content", m.get("texto", "")),
                    "mats": m.get("mats") or [],
                    "query": m.get("query", "")})
    return out


def _req(method, params="", body=None):
    url, key = _cfg()
    full = f"{url}/rest/v1/conversaciones{params}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(full, data=data, method=method, headers={
        "apikey": key, "Authorization": "Bearer " + key,
        "Content-Type": "application/json", "Prefer": "return=representation"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            txt = r.read().decode("utf-8")
            return json.loads(txt) if txt.strip() else []
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Supabase {e.code}: {e.read().decode('utf-8','ignore')[:200]}")


def listar_conversaciones(usuario):
    """[{id, titulo, actualizado}] del usuario, más recientes primero."""
    u = urllib.parse.quote(usuario)
    return _req("GET", f"?usuario=eq.{u}&select=id,titulo,actualizado&order=actualizado.desc")


def cargar_conversacion(cid):
    r = _req("GET", f"?id=eq.{cid}&select=id,titulo,mensajes")
    return r[0] if r else None


def listar_todas(limite=1000):
    """Todas las conversaciones (para el panel de revisión). Más recientes primero."""
    return _req("GET", f"?select=id,usuario,titulo,actualizado&order=actualizado.desc&limit={limite}")


def exportar_todas(limite=1000):
    """Todas las conversaciones COMPLETAS (con mensajes), para descargar."""
    return _req("GET", f"?select=id,usuario,titulo,mensajes,creado,actualizado&order=actualizado.desc&limit={limite}")


def crear_conversacion(usuario, titulo, mensajes):
    r = _req("POST", "", body={"usuario": usuario, "titulo": titulo, "mensajes": mensajes})
    return r[0]["id"] if r else None


def actualizar_conversacion(cid, titulo, mensajes):
    ahora = datetime.now(timezone.utc).isoformat()
    _req("PATCH", f"?id=eq.{cid}", body={"titulo": titulo, "mensajes": mensajes, "actualizado": ahora})


def renombrar(cid, titulo):
    """Solo cambia el título (no toca los mensajes)."""
    _req("PATCH", f"?id=eq.{cid}", body={"titulo": titulo})


def guardar_mensajes(cid, mensajes):
    """Solo actualiza los mensajes (no toca el título)."""
    ahora = datetime.now(timezone.utc).isoformat()
    _req("PATCH", f"?id=eq.{cid}", body={"mensajes": mensajes, "actualizado": ahora})


def borrar_conversacion(cid):
    _req("DELETE", f"?id=eq.{cid}")
