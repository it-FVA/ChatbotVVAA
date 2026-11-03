"""Cuentas y permisos: tablas usuarios, usuarios_cambios y autorizados (lista blanca del login con Google).
(3/11, revisión 5.2 punto 12) Antes en db.py. Las funciones se llaman entre sí y a _req a través del paquete (`_db.x`), así
`monkeypatch.setattr(db, "x", …)` en las pruebas vale para todas. Los parámetros de los filtros van escapados con _q.
"""
import json, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timezone, timedelta

import db as _db
from ._cliente import _q


# Tabla autorizados(email text pk, rol 'creador'|'aprobador', agregado_por, creado) — migración `autorizados_login_google`.
# Login con Google: entran las cuentas del dominio de la Fundación (DOMINIO_FVA) MÁS los emails de esta tabla.
def autorizado(email):
    if not _db.disponible() or not email:
        return None
    r = _db._req("GET", f"?email=eq.{urllib.parse.quote(email.strip().lower())}&select=*", tabla="autorizados")
    return r[0] if r else None


def listar_autorizados(limite=200):
    if not _db.disponible():
        return []
    return _db._req("GET", f"?select=*&order=creado.desc&limit={limite}", tabla="autorizados") or []


def agregar_autorizado(email, rol, agregado_por, nota=None):
    """Alta o cambio de rol/nota (upsert por email). (22/10) rol admite 'admin' y hay columna `nota`
    (migración `usuarios_y_lista_blanca`)."""
    if not _db.disponible():
        return None
    url, key = _db._cfg()
    fila = {"email": email.strip().lower(), "rol": rol if rol in ("creador", "aprobador", "admin") else "creador",
            "agregado_por": agregado_por}
    if nota is not None:
        fila["nota"] = (nota or "").strip() or None
    data = json.dumps(fila).encode("utf-8")
    req = urllib.request.Request(f"{url}/rest/v1/autorizados", data=data, method="POST", headers={
        "apikey": key, "Authorization": "Bearer " + key, "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=representation"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8") or "[]")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Supabase {e.code}: {e.read().decode('utf-8','ignore')[:200]}")


def quitar_autorizado(email):
    return _db._req("DELETE", f"?email=eq.{urllib.parse.quote(email.strip().lower())}", tabla="autorizados")


# ---------------- Usuarios (22/10): tabla `usuarios` + registro `usuarios_cambios` (migración usuarios_y_lista_blanca) ----------------
# Contraseñas: solo el hash (bcrypt, api/cuentas.py). Mientras alguien no esté acá, la API cae en [usuarios] de secrets.
_USUARIO_COLS = "id,usuario,email,nombre,rol,clave_hash,clave_temporal,activo,creado,actualizado,ultimo_login,creado_por"


def _qu(v):
    return urllib.parse.quote(str(v).strip().lower())


def usuario_por_nombre(usuario):
    if not _db.disponible() or not usuario:
        return None
    r = _db._req("GET", f"?usuario=eq.{_qu(usuario)}&select={_USUARIO_COLS}", tabla="usuarios")
    return r[0] if r else None


def usuario_por_email(email):
    if not _db.disponible() or not email:
        return None
    r = _db._req("GET", f"?email=ilike.{_qu(email)}&select={_USUARIO_COLS}", tabla="usuarios")
    return r[0] if r else None


def usuario_por_id(uid):
    if not _db.disponible() or not uid:
        return None
    r = _db._req("GET", f"?id=eq.{urllib.parse.quote(str(uid))}&select={_USUARIO_COLS}", tabla="usuarios")
    return r[0] if r else None


def listar_usuarios(limite=500):
    if not _db.disponible():
        return []
    return _db._req("GET", f"?select={_USUARIO_COLS}&order=usuario.asc&limit={limite}", tabla="usuarios") or []


def crear_usuario(usuario, email=None, nombre=None, rol="creador", clave_hash=None, clave_temporal=False, creado_por=None):
    fila = {"usuario": usuario.strip().lower(), "email": (email or "").strip().lower() or None, "nombre": (nombre or "").strip() or None,
            "rol": rol if rol in ("creador", "aprobador", "admin") else "creador", "clave_hash": clave_hash,
            "clave_temporal": bool(clave_temporal), "creado_por": creado_por}
    r = _db._req("POST", "", fila, tabla="usuarios")
    return r[0] if r else None


def actualizar_usuario(uid, campos):
    """PATCH por id; actualiza `actualizado`. Devuelve la fila nueva."""
    campos = dict(campos)
    campos["actualizado"] = _db._ahora_iso()
    r = _db._req("PATCH", f"?id=eq.{urllib.parse.quote(str(uid))}", campos, tabla="usuarios")
    return r[0] if r else None


def borrar_usuario(uid):
    return _db._req("DELETE", f"?id=eq.{urllib.parse.quote(str(uid))}", tabla="usuarios")


def marcar_login(uid):
    try:
        _db._req("PATCH", f"?id=eq.{urllib.parse.quote(str(uid))}", {"ultimo_login": _db._ahora_iso()}, tabla="usuarios")
    except Exception:
        pass


# Columnas que guardan el nombre de usuario en las otras tablas: al renombrar se actualizan para no perder el historial.
_COLUMNAS_USUARIO = (("conversaciones", "usuario"), ("publicaciones", "usuario"), ("clips", "pedido_por"), ("uso_openai", "usuario"))


def renombrar_usuario_en_tablas(viejo, nuevo):
    """Devuelve {tabla: filas cambiadas} (o el error por tabla). No toca `publicaciones.resultado` (jsonb con
    propuesta_por/aprobada_por…): queda con el nombre viejo, es solo informativo."""
    salida = {}
    for tabla, col in _COLUMNAS_USUARIO:
        try:
            r = _db._req("PATCH", f"?{col}=eq.{urllib.parse.quote(viejo)}&select=id", {col: nuevo}, tabla=tabla)
            salida[tabla] = len(r or [])
        except Exception as e:
            salida[tabla] = f"error: {e}"
    return salida


def registrar_cambio_usuario(quien, accion, usuario=None, detalle=None):
    """Registro de lo que hacen los admins (tabla usuarios_cambios). Nunca guardar claves acá."""
    if not _db.disponible():
        return None
    try:
        return _db._req("POST", "", {"quien": quien, "accion": accion, "usuario": usuario, "detalle": detalle or {}}, tabla="usuarios_cambios")
    except Exception:
        return None


def listar_cambios_usuarios(limite=100):
    if not _db.disponible():
        return []
    return _db._req("GET", f"?select=id,cuando,quien,accion,usuario,detalle&order=cuando.desc&limit={limite}", tabla="usuarios_cambios") or []
