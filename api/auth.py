"""Sesión y login.

- Sesión: cookie firmada (itsdangerous), HttpOnly, SameSite=Lax, 30 días. Secreto en SESION_SECRETO.
  Si falta, se genera uno al azar al arrancar (las sesiones se pierden al reiniciar; en producción ponerlo).
  COOKIE_SEGURA=1 marca la cookie como Secure (obligatorio detrás de HTTPS en producción).
- Login por usuario y contraseña: la tabla `usuarios` de Supabase (hash bcrypt, api/cuentas.py). Desde el 3/11 es la única
  fuente: ya no hay contraseñas en secrets ni en USUARIOS_JSON.
- Roles: salen de la columna `rol` de esa tabla (roles.roles_de_fila). Ya no hay listas APROBADORES/ADMINS/PUBLICACION_DIRECTA.
- Login con Google: la interfaz manda el id_token que le dio Google; acá se verifica con GOOGLE_CLIENT_ID
  y se admite si el email ya tiene cuenta en `usuarios`, si termina en DOMINIO_FVA o si está en la lista blanca
  (`autorizados`). La primera vez crea la fila en `usuarios` con el rol de la lista.
"""
import os, secrets as _secrets, logging
from fastapi import HTTPException, Request, Response
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from . import config, roles as _roles
import canales       # noqa: E402  (api/__init__ pone la raíz del repo en sys.path)

log = logging.getLogger("api")
COOKIE = os.environ.get("COOKIE_NOMBRE", "fva_sesion")   # (22/10) configurable: varias APIs locales en localhost no se pisan la sesión
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


_ser_estado = {}


def firmar_estado(datos, proposito):
    """(8/11, Franco) Un texto firmado con el secreto de sesión pero con otra «sal» por propósito (no sirve como cookie de sesión):
    lo usa el «Conectar con WordPress.com» de Métricas como `state` del flujo OAuth. Vence al leerlo (leer_estado)."""
    return _estado(proposito).dumps(datos)


def leer_estado(token, proposito, max_age):
    """Los datos de firmar_estado si la firma es válida y no pasaron `max_age` segundos; si no, None."""
    try:
        return _estado(proposito).loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None


def _estado(proposito):
    if proposito not in _ser_estado:
        _ser_estado[proposito] = URLSafeTimedSerializer(_serializador().secret_keys[-1], salt="fva-estado-" + proposito)
    return _ser_estado[proposito]


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
    """Rol de la sesión: el de su fila en la tabla `usuarios`; si no tiene fila (una sesión de Google que no pudo crearla), el
    de la lista blanca que quedó en la cookie. `aprobadores` = quienes pueden revisar hoy (para los textos «lo revisa …»)."""
    from . import cuentas
    fila = _fila(s["usuario"])
    r = _roles.roles_de_fila(fila) if fila else _roles.roles(s.get("rol_tabla"))
    return dict(r, aprobadores=cuentas.nombres_aprobadores())


def usuario_actual(request: Request):
    return sesion(request)["usuario"]


def aprobador(request: Request):
    s = sesion(request)
    if not rol_sesion(s)["aprueba"]:
        raise HTTPException(403, "Solo para aprobadores.")
    return s["usuario"]


def aprobador_o_admin(request: Request):
    """(8/11, Franco) Métricas está en Gestión: la ven quienes aprueban y los admins (un admin siempre aprueba, pero se chequean los dos)."""
    s = sesion(request)
    r = rol_sesion(s)
    if not (r["aprueba"] or r["admin"]):
        raise HTTPException(403, "Solo para quienes aprueban o administran.")
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
            "rol": {"nombre": r["nombre"], "crea": r["crea"], "aprueba": r["aprueba"], "admin": r["admin"], "publica": r["publica"]},
            # (3/11) el registro de canales (canales.py): la web no tiene listas propias (menú, nombres visibles, filtro de Mis publicaciones)
            "canales": canales.para_web()}


# ---------------- Usuario y contraseña ----------------
def login_clave(usuario, clave):
    """Devuelve la fila de `usuarios` si el usuario y la clave son correctos, None si no.
    Levanta 403/409 si la cuenta está desactivada o no tiene clave todavía."""
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
    return None


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
