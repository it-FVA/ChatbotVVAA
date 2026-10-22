"""Sesión y login.

- Sesión: cookie firmada (itsdangerous), HttpOnly, SameSite=Lax, 30 días. Secreto en SESION_SECRETO.
  Si falta, se genera uno al azar al arrancar (las sesiones se pierden al reiniciar; en producción ponerlo).
  COOKIE_SEGURA=1 marca la cookie como Secure (obligatorio detrás de HTTPS en producción).
- Login por usuario y contraseña (22/10): PRIMERO la tabla `usuarios` de Supabase (hash bcrypt, api/cuentas.py);
  si el usuario no está en la tabla, cae en [usuarios] (secrets.toml) / USUARIOS_JSON, igual que app.py.
  TRANSICIÓN: cuando todos estén en la tabla (api/importar_usuarios.py), sacar ese fallback (login_clave, roles
  y _existe_usuario en cuentas.py) y la variable USUARIOS_JSON; Streamlit (app.py) sigue leyendo secrets hasta
  que se migre o se apague.
- Roles: si la persona está en la tabla, el rol sale de ahí (roles.roles_de_fila); si no, de las listas
  APROBADORES/ADMINS como hasta ahora.
- Login con Google: la interfaz manda el id_token que le dio Google; acá se verifica con GOOGLE_CLIENT_ID
  y se admite si el email ya tiene cuenta en `usuarios`, si termina en DOMINIO_FVA o si está en la lista blanca
  (`autorizados`). La primera vez crea la fila en `usuarios` con el rol de la lista.
"""
import os, secrets as _secrets, logging
from fastapi import HTTPException, Request, Response
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from . import config, roles as _roles

log = logging.getLogger("api")
COOKIE = "fva_sesion"
DURACION = 30 * 24 * 3600
_ser = None


def _serializador():
    global _ser
    if _ser is None:
        secreto = os.environ.get("SESION_SECRETO")
        if not secreto:
            secreto = _secrets.token_urlsafe(32)
            log.warning("SESION_SECRETO no está definido: uso uno al azar (las sesiones se pierden al reiniciar).")
        _ser = URLSafeTimedSerializer(secreto, salt="fva-sesion")
    return _ser


def emitir(resp: Response, usuario, origen, rol_tabla=None):
    token = _serializador().dumps({"usuario": usuario, "origen": origen, "rol_tabla": rol_tabla})
    resp.set_cookie(COOKIE, token, max_age=DURACION, httponly=True,
                    samesite=os.environ.get("COOKIE_SAMESITE", "lax"),
                    secure=os.environ.get("COOKIE_SEGURA", "0") == "1", path="/")


def cerrar(resp: Response):
    resp.delete_cookie(COOKIE, path="/")


def leer(request: Request):
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    try:
        return _serializador().loads(token, max_age=DURACION)
    except (BadSignature, SignatureExpired):
        return None


# ---------------- Dependencias ----------------
def sesion(request: Request):
    s = leer(request)
    if not s or not s.get("usuario"):
        raise HTTPException(401, "Hay que iniciar sesión.")
    fila = _fila(s["usuario"])
    if fila and not fila.get("activo", True):
        raise HTTPException(401, "La cuenta está desactivada.")
    return s


def _fila(usuario):
    from . import cuentas
    return cuentas.fila_de(usuario)


def rol_sesion(s):
    """Rol de la sesión: de la tabla `usuarios` si la persona está ahí; si no, de las listas de secrets."""
    fila = _fila(s["usuario"])
    if fila:
        return _roles.roles_de_fila(fila)
    return _roles.roles(s["usuario"], s.get("rol_tabla"))


def usuario_actual(request: Request):
    return sesion(request)["usuario"]


def aprobador(request: Request):
    s = sesion(request)
    if not rol_sesion(s)["aprueba"]:
        raise HTTPException(403, "Solo para aprobadores.")
    return s["usuario"]


def admin(request: Request):
    """Configuración (estilo por defecto de los subtítulos, etc.): solo admins (ADMINS)."""
    s = sesion(request)
    if not rol_sesion(s)["admin"]:
        raise HTTPException(403, "Solo para admins.")
    return s["usuario"]


def yo(s):
    """Lo que devuelve GET /yo: usuario, rol, idioma."""
    r = rol_sesion(s)
    fila = _fila(s["usuario"]) or {}
    return {"usuario": s["usuario"], "origen": s.get("origen", "clave"), "idioma": config.idioma(s["usuario"]),
            "nombre": fila.get("nombre"), "email": fila.get("email"), "en_tabla": bool(fila),
            "tiene_clave": bool(fila.get("clave_hash")) if fila else True,
            "debe_cambiar_clave": bool(fila.get("clave_temporal")),
            "rol": {"nombre": r["nombre"], "crea": r["crea"], "aprueba": r["aprueba"], "admin": r["admin"], "publica": r["publica"]}}


# ---------------- Usuario y contraseña ----------------
def login_clave(usuario, clave):
    """Devuelve la fila de `usuarios` si entró por la tabla, "secrets" si entró por la lista vieja, None si no.
    Levanta 403/409 si la cuenta de la tabla está desactivada o no tiene clave todavía."""
    from . import cuentas
    usuario = (usuario or "").strip()
    if not usuario:
        return None
    fila = cuentas.fila_de(usuario, fresco=True)
    if fila:
        if not fila.get("activo", True):
            raise HTTPException(403, "La cuenta está desactivada. Hablá con un admin.")
        if not fila.get("clave_hash"):
            raise HTTPException(409, "Tu cuenta todavía no tiene contraseña: creala desde «¿Primera vez? Creá tu cuenta» con tu email (o entrá con Google).")
        return fila if cuentas.verificar_hash(clave, fila["clave_hash"]) else None
    # Fallback (transición): la lista vieja de secrets, tal cual app.py. Sacar cuando todos estén en la tabla.
    us = config.usuarios()
    return "secrets" if usuario in us and str(us[usuario]) == str(clave) else None


# ---------------- Google ----------------
def verificar_google(id_token):
    """Devuelve el email verificado del id_token, o levanta HTTPException."""
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    if not client_id:
        raise HTTPException(503, "El login con Google no está configurado (falta GOOGLE_CLIENT_ID: hace falta el proyecto de Google Cloud).")
    try:
        from google.oauth2 import id_token as _idt
        from google.auth.transport import requests as _greq
        info = _idt.verify_oauth2_token(id_token, _greq.Request(), client_id)
    except Exception as e:
        raise HTTPException(401, f"Token de Google inválido: {e}")
    email = (info.get("email") or "").strip().lower()
    if not email or not info.get("email_verified", False):
        raise HTTPException(401, "La cuenta de Google no tiene un email verificado.")
    return email


def admitir_google(email):
    """(fila de usuarios o None, admitido?, rol_tabla, motivo). Orden: cuenta existente por email → dominio de la
    Fundación → lista blanca. La primera vez crea la fila en `usuarios` (rol de la lista; franco@dominio hereda el
    de 'franco' en las listas viejas; si existe 'franco' en la tabla sin email, se le asigna este email)."""
    import db
    from . import cuentas
    email = (email or "").strip().lower()
    fila = None
    if db.disponible():
        try:
            fila = db.usuario_por_email(email)
        except Exception as e:
            log.warning("No pude buscar el email en usuarios: %s", e)
    if fila:
        if not fila.get("activo", True):
            raise HTTPException(403, "La cuenta está desactivada. Hablá con un admin.")
        return fila, True, fila.get("rol"), "cuenta"
    ok, rol_lista, motivo = cuentas.permitido(email)
    if not ok:
        return None, False, None, "no_autorizado"
    if db.disponible():
        try:
            local = email.split("@", 1)[0]
            vieja = db.usuario_por_nombre(local) if motivo == "dominio" else None
            if vieja and not vieja.get("email") and vieja.get("activo", True):
                fila = db.actualizar_usuario(vieja["id"], {"email": email})
                db.registrar_cambio_usuario(fila["usuario"], "google_vincular", fila["usuario"], {"email": email})
            else:
                fila = db.crear_usuario(email, email=email, rol=cuentas.rol_inicial(email, rol_lista), creado_por="google")
                db.registrar_cambio_usuario(email, "google_alta", email, {"motivo": motivo, "rol": fila["rol"]})
            cuentas.olvidar(fila["usuario"])
        except Exception as e:
            log.warning("No pude crear/vincular la cuenta de Google en usuarios: %s", e)
            fila = None
    return fila, True, rol_lista, motivo
