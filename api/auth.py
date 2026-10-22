"""Sesión y login.

- Sesión: cookie firmada (itsdangerous), HttpOnly, SameSite=Lax, 30 días. Secreto en SESION_SECRETO.
  Si falta, se genera uno al azar al arrancar (las sesiones se pierden al reiniciar; en producción ponerlo).
  COOKIE_SEGURA=1 marca la cookie como Secure (obligatorio detrás de HTTPS en producción).
- Login por usuario y contraseña: contra [usuarios] (secrets.toml) o USUARIOS_JSON, igual que app.py.
- Login con Google: la interfaz manda el id_token que le dio Google; acá se verifica con GOOGLE_CLIENT_ID
  y se admite si el email termina en DOMINIO_FVA o está en la tabla `autorizados` de Supabase
  (decisión de Franco 19/10: dominio de la Fundación MÁS una lista administrable).
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
    return s


def usuario_actual(request: Request):
    return sesion(request)["usuario"]


def aprobador(request: Request):
    s = sesion(request)
    if not _roles.roles(s["usuario"], s.get("rol_tabla"))["aprueba"]:
        raise HTTPException(403, "Solo para aprobadores.")
    return s["usuario"]


def admin(request: Request):
    """Configuración (estilo por defecto de los subtítulos, etc.): solo admins (ADMINS)."""
    s = sesion(request)
    if not _roles.roles(s["usuario"], s.get("rol_tabla"))["admin"]:
        raise HTTPException(403, "Solo para admins.")
    return s["usuario"]


def yo(s):
    """Lo que devuelve GET /yo: usuario, rol, idioma."""
    r = _roles.roles(s["usuario"], s.get("rol_tabla"))
    return {"usuario": s["usuario"], "origen": s.get("origen", "clave"), "idioma": config.idioma(s["usuario"]),
            "rol": {"nombre": r["nombre"], "crea": r["crea"], "aprueba": r["aprueba"], "admin": r["admin"], "publica": r["publica"]}}


# ---------------- Usuario y contraseña ----------------
def login_clave(usuario, clave):
    """Misma regla que app.py: el usuario está en la lista y la contraseña coincide tal cual."""
    us = config.usuarios()
    return bool(usuario) and usuario in us and str(us[usuario]) == str(clave)


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
    """(email admitido?, rol_tabla, motivo). Dominio de la Fundación o tabla autorizados."""
    import db
    dominio = config.dominio_fva()
    if dominio and email.endswith("@" + dominio):
        fila = None
        try:
            fila = db.autorizado(email)
        except Exception:
            pass
        return True, (fila or {}).get("rol"), "dominio"
    try:
        fila = db.autorizado(email)
    except Exception as e:
        log.warning("No pude consultar autorizados: %s", e)
        fila = None
    if fila:
        return True, fila.get("rol"), "lista"
    return False, None, "no_autorizado"
