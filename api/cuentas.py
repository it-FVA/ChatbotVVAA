"""Cuentas de usuario (22/10): tabla `usuarios` de Supabase, lista blanca, «¿Primera vez?», cambio de clave y el
panel de administración (solo admins).

Reglas:
- La contraseña se guarda SOLO como hash bcrypt (`clave_hash`). Nunca en claro, nunca en el registro de cambios.
- Quién puede crear cuenta: un email del dominio DOMINIO_FVA siempre; cualquier otro, solo si está en la lista
  blanca (tabla `autorizados`, que además dice el rol). Sin servicio de mail no hay verificación del email:
  PENDIENTE (hoy la persona escribe el email y se le cree).
- Transición: mientras alguien no esté en la tabla, `api/auth.py` cae en [usuarios]/USUARIOS_JSON (secrets) y las
  listas APROBADORES/ADMINS. `api/importar_usuarios.py` pasa a todos a la tabla; después se saca ese fallback.
- Un admin no puede quitarse el rol admin, desactivarse ni borrarse; tampoco dejar la tabla sin ningún admin activo.
- Todo cambio hecho por un admin queda en `usuarios_cambios` (quién, acción, a quién, detalle).
"""
import os, re, time, logging, secrets as _secrets
from datetime import datetime, timezone

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from . import config, auth, roles as _roles
import db

log = logging.getLogger("api")
router = APIRouter()

ROLES = ("creador", "aprobador", "admin")
RE_USUARIO = re.compile(r"^[a-z0-9][a-z0-9._-]{2,39}$")
RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CLAVE_MIN = 8
CACHE_SEG = 30          # la fila del usuario se relee de la tabla como mucho cada 30 s (rol, activo, clave temporal)
_cache = {}


# ---------------- Hash ----------------
def hashear(clave):
    rondas = int(os.environ.get("BCRYPT_RONDAS", "12"))      # los tests bajan a 4 para no tardar
    return bcrypt.hashpw(clave.encode("utf-8")[:72], bcrypt.gensalt(rondas)).decode("ascii")


def verificar_hash(clave, h):
    try:
        return bool(h) and bcrypt.checkpw((clave or "").encode("utf-8")[:72], h.encode("ascii"))
    except Exception:
        return False


def clave_temporal_nueva():
    """12 caracteres al azar (letras y números), fáciles de dictar."""
    alfabeto = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(_secrets.choice(alfabeto) for _ in range(12))


# ---------------- Lectura con caché ----------------
def _503(e):
    txt = str(e)
    if "does not exist" in txt or "PGRST205" in txt or "Supabase 404" in txt:
        return HTTPException(503, "Falta correr la migración api/migraciones/usuarios_y_lista_blanca.sql en Supabase.")
    return HTTPException(503, f"No pude hablar con Supabase: {txt[:160]}")


def fila_de(usuario, fresco=False):
    """La fila de `usuarios` de esa persona (o None si no está en la tabla / no hay Supabase). Con caché corta."""
    if not usuario or not db.disponible():
        return None
    u = usuario.strip().lower()
    ahora = time.time()
    if not fresco and u in _cache and ahora - _cache[u][0] < CACHE_SEG:
        return _cache[u][1]
    try:
        fila = db.usuario_por_nombre(u)
    except Exception as e:
        log.warning("No pude leer la tabla usuarios: %s", e)
        return _cache.get(u, (0, None))[1]
    _cache[u] = (ahora, fila)
    return fila


def olvidar(usuario=None):
    if usuario:
        _cache.pop(usuario.strip().lower(), None)
    else:
        _cache.clear()


def permitido(email):
    """(permitido?, rol de la lista o None, motivo 'dominio'|'lista'|'no'). Regla de la lista blanca."""
    email = (email or "").strip().lower()
    dominio = config.dominio_fva()
    fila = None
    try:
        fila = db.autorizado(email)
    except Exception as e:
        log.warning("No pude consultar la lista blanca: %s", e)
    if dominio and email.endswith("@" + dominio):
        return True, (fila or {}).get("rol"), "dominio"
    if fila:
        return True, fila.get("rol"), "lista"
    return False, None, "no"


def rol_inicial(email, rol_lista):
    """Rol con el que nace una cuenta: el de la lista blanca; si no dice nada, el que diga la lista vieja de
    secrets para ese nombre (franco@… hereda lo de franco); si no, creador."""
    if rol_lista in ROLES:
        return rol_lista
    r = _roles.roles(email, None)
    return "admin" if r["admin"] else ("aprobador" if r["aprueba"] else "creador")


# ---------------- Validaciones ----------------
def validar_usuario(u):
    u = (u or "").strip().lower()
    if not RE_USUARIO.match(u):
        raise HTTPException(400, "El usuario tiene que tener de 3 a 40 caracteres: letras minúsculas, números, punto, guion o guion bajo, y empezar con letra o número.")
    return u


def validar_clave(c):
    c = c or ""
    if len(c) < CLAVE_MIN:
        raise HTTPException(400, f"La contraseña tiene que tener al menos {CLAVE_MIN} caracteres.")
    if c.strip() != c:
        raise HTTPException(400, "La contraseña no puede empezar ni terminar con espacios.")
    if c.isdigit() or c.isalpha():
        raise HTTPException(400, "La contraseña tiene que mezclar letras y números (o signos).")
    return c


def validar_email(e):
    e = (e or "").strip().lower()
    if not RE_EMAIL.match(e):
        raise HTTPException(400, "Ese email no parece válido.")
    return e


def _existe_usuario(u):
    """En la tabla o en la lista vieja de secrets (mientras conviven)."""
    if fila_de(u, fresco=True):
        return True
    return u in {k.lower() for k in config.usuarios()}


def publico(fila):
    """La fila sin el hash, con `tiene_clave`."""
    if not fila:
        return None
    f = {k: v for k, v in fila.items() if k != "clave_hash"}
    f["tiene_clave"] = bool(fila.get("clave_hash"))
    return f


# ---------------- Modelos ----------------
class Verificar(BaseModel):
    email: str


class PrimeraVez(BaseModel):
    email: str
    usuario: str
    clave: str


class CambioClave(BaseModel):
    actual: str
    nueva: str


class NuevoUsuario(BaseModel):
    usuario: str
    email: str | None = None
    nombre: str | None = None
    rol: str = "creador"
    clave: str = "sin"          # 'sin' (la crea la persona desde «Primera vez») o 'temporal'


class EdicionUsuario(BaseModel):
    nombre: str | None = None
    email: str | None = None
    rol: str | None = None
    activo: bool | None = None


class Renombrar(BaseModel):
    usuario: str


class ResetClave(BaseModel):
    modo: str = "temporal"      # 'temporal' | 'sin_clave'


class ListaBlanca(BaseModel):
    email: str
    rol: str = "creador"
    nota: str | None = None


# ---------------- Crear cuenta la primera vez ----------------
@router.post("/cuentas/verificar")
def verificar(datos: Verificar):
    """Paso 1 de «¿Primera vez?»: ¿este email puede crear cuenta? No revela la lista: solo sí/no para ese email."""
    email = validar_email(datos.email)
    if not db.disponible():
        raise HTTPException(503, "Sin Supabase no se pueden crear cuentas.")
    try:
        existente = db.usuario_por_email(email)
    except RuntimeError as e:
        raise _503(e)
    if existente:
        if not existente.get("activo", True):
            raise HTTPException(403, "Esa cuenta está desactivada. Hablá con un admin.")
        return {"permitido": True, "motivo": "cuenta", "usuario": existente["usuario"], "sin_clave": not existente.get("clave_hash"),
                "mensaje": None if not existente.get("clave_hash") else "Ese email ya tiene cuenta: entrá con tu usuario y contraseña (o con Google)."}
    ok, rol, motivo = permitido(email)
    if not ok:
        raise HTTPException(403, "Ese email no está habilitado para crear una cuenta. Si creés que debería estarlo, pedile a un admin de la Fundación que lo agregue.")
    return {"permitido": True, "motivo": motivo, "usuario": None, "sin_clave": True, "mensaje": None}


@router.post("/cuentas/primera-vez")
def primera_vez(datos: PrimeraVez, resp: Response):
    """Paso 2: elige usuario y contraseña. Crea la fila (rol de la lista blanca o creador) o le pone clave a una
    cuenta que un admin dejó «sin clave». Inicia la sesión."""
    email = validar_email(datos.email)
    clave = validar_clave(datos.clave)
    if not db.disponible():
        raise HTTPException(503, "Sin Supabase no se pueden crear cuentas.")
    try:
        existente = db.usuario_por_email(email)
        if existente:
            if not existente.get("activo", True):
                raise HTTPException(403, "Esa cuenta está desactivada. Hablá con un admin.")
            if existente.get("clave_hash"):
                raise HTTPException(409, "Ese email ya tiene cuenta con contraseña. Entrá con tu usuario, o pedile a un admin que te la resetee.")
            fila = db.actualizar_usuario(existente["id"], {"clave_hash": hashear(clave), "clave_temporal": False})
            db.registrar_cambio_usuario(fila["usuario"], "primera_vez", fila["usuario"], {"email": email, "cuenta": "existente"})
        else:
            ok, rol_lista, motivo = permitido(email)
            if not ok:
                raise HTTPException(403, "Ese email no está habilitado para crear una cuenta. Si creés que debería estarlo, pedile a un admin de la Fundación que lo agregue.")
            usuario = validar_usuario(datos.usuario)
            if _existe_usuario(usuario):
                raise HTTPException(409, "Ese nombre de usuario ya está en uso. Probá con otro.")
            fila = db.crear_usuario(usuario, email=email, rol=rol_inicial(email, rol_lista), clave_hash=hashear(clave),
                                    creado_por="primera_vez")
            db.registrar_cambio_usuario(usuario, "primera_vez", usuario, {"email": email, "motivo": motivo, "rol": fila["rol"]})
    except RuntimeError as e:
        raise _503(e)
    olvidar(fila["usuario"])
    db.marcar_login(fila["id"])
    auth.emitir(resp, fila["usuario"], "clave")
    return auth.yo({"usuario": fila["usuario"], "origen": "clave"})


# ---------------- Cambiar mi contraseña ----------------
@router.post("/cuentas/clave")
def cambiar_clave(datos: CambioClave, s=Depends(auth.sesion)):
    fila = fila_de(s["usuario"], fresco=True)
    if not fila:
        raise HTTPException(409, "Tu usuario todavía está en la lista vieja (secrets) y no en la tabla: pedile a un admin que corra la importación.")
    if not fila.get("clave_hash"):
        raise HTTPException(409, "Tu cuenta no tiene contraseña (entrás con Google). Creala desde «¿Primera vez?» con tu email.")
    if not verificar_hash(datos.actual, fila["clave_hash"]):
        raise HTTPException(401, "La contraseña actual no es correcta.")
    nueva = validar_clave(datos.nueva)
    if nueva == datos.actual:
        raise HTTPException(400, "La contraseña nueva tiene que ser distinta de la actual.")
    try:
        db.actualizar_usuario(fila["id"], {"clave_hash": hashear(nueva), "clave_temporal": False})
    except RuntimeError as e:
        raise _503(e)
    db.registrar_cambio_usuario(fila["usuario"], "clave_propia", fila["usuario"], {})
    olvidar(fila["usuario"])
    return {"ok": True}


# ---------------- Administración: usuarios ----------------
def _admin(request: Request):
    return auth.admin(request)


def _fila_o_404(uid):
    try:
        fila = db.usuario_por_id(uid)
    except RuntimeError as e:
        raise _503(e)
    if not fila:
        raise HTTPException(404, "No existe ese usuario.")
    return fila


def _admins_activos():
    return [f for f in db.listar_usuarios() if f.get("rol") == "admin" and f.get("activo", True)]


def _proteger_ultimo_admin(fila, quien, accion):
    """Si la acción le saca a `fila` la condición de admin activo, no puede ser uno mismo ni el último."""
    if fila["usuario"] == quien:
        raise HTTPException(400, f"No podés {accion} tu propia cuenta de admin. Pedíselo a otro admin.")
    if fila.get("rol") == "admin" and fila.get("activo", True) and len(_admins_activos()) <= 1:
        raise HTTPException(400, "Es el único admin activo: antes nombrá a otro admin.")


@router.get("/admin/usuarios")
def admin_usuarios(quien=Depends(_admin)):
    if not db.disponible():
        return {"usuarios": [], "en_secrets": sorted(config.usuarios())}
    try:
        filas = [publico(f) for f in db.listar_usuarios()]
    except RuntimeError as e:
        raise _503(e)
    en_tabla = {f["usuario"] for f in filas}
    # Los que siguen solo en secrets (todavía no importados): se muestran para que se vea quién falta.
    pendientes = sorted(u for u in config.usuarios() if u.lower() not in en_tabla)
    return {"usuarios": filas, "en_secrets": pendientes}


@router.post("/admin/usuarios", status_code=201)
def admin_crear(datos: NuevoUsuario, quien=Depends(_admin)):
    usuario = validar_usuario(datos.usuario)
    if datos.rol not in ROLES:
        raise HTTPException(400, "Rol inválido.")
    email = validar_email(datos.email) if datos.email else None
    try:
        if _existe_usuario(usuario):
            raise HTTPException(409, "Ese nombre de usuario ya existe.")
        if email and db.usuario_por_email(email):
            raise HTTPException(409, "Ya hay una cuenta con ese email.")
        temporal = clave_temporal_nueva() if datos.clave == "temporal" else None
        fila = db.crear_usuario(usuario, email=email, nombre=datos.nombre, rol=datos.rol,
                                clave_hash=hashear(temporal) if temporal else None, clave_temporal=bool(temporal), creado_por=quien)
    except RuntimeError as e:
        raise _503(e)
    db.registrar_cambio_usuario(quien, "crear", usuario, {"rol": datos.rol, "email": email, "clave": "temporal" if temporal else "sin"})
    return {"usuario": publico(fila), "clave_temporal": temporal}


@router.patch("/admin/usuarios/{uid}")
def admin_editar(uid: str, datos: EdicionUsuario, quien=Depends(_admin)):
    fila = _fila_o_404(uid)
    cambios, detalle = {}, {}
    if datos.nombre is not None:
        cambios["nombre"] = datos.nombre.strip() or None
    if datos.email is not None:
        email = validar_email(datos.email) if datos.email.strip() else None
        if email and email != (fila.get("email") or "").lower():
            otro = db.usuario_por_email(email)
            if otro and otro["id"] != fila["id"]:
                raise HTTPException(409, "Ya hay otra cuenta con ese email.")
        cambios["email"] = email
    if datos.rol is not None and datos.rol != fila.get("rol"):
        if datos.rol not in ROLES:
            raise HTTPException(400, "Rol inválido.")
        if fila.get("rol") == "admin":
            _proteger_ultimo_admin(fila, quien, "sacarle el rol admin a")
        cambios["rol"] = datos.rol
        detalle["rol"] = {"de": fila.get("rol"), "a": datos.rol}
    if datos.activo is not None and datos.activo != fila.get("activo", True):
        if not datos.activo:
            _proteger_ultimo_admin(fila, quien, "desactivar")
        cambios["activo"] = datos.activo
        detalle["activo"] = datos.activo
    if not cambios:
        return {"usuario": publico(fila)}
    try:
        nueva = db.actualizar_usuario(fila["id"], cambios)
    except RuntimeError as e:
        raise _503(e)
    olvidar(fila["usuario"])
    for k in ("nombre", "email"):
        if k in cambios:
            detalle[k] = cambios[k]
    accion = "rol" if "rol" in cambios else ("activar" if cambios.get("activo") else ("desactivar" if "activo" in cambios else "editar"))
    db.registrar_cambio_usuario(quien, accion, fila["usuario"], detalle)
    return {"usuario": publico(nueva)}


@router.post("/admin/usuarios/{uid}/renombrar")
def admin_renombrar(uid: str, datos: Renombrar, quien=Depends(_admin)):
    """Cambia el nombre de usuario y lo actualiza en conversaciones, publicaciones, clips y uso_openai."""
    fila = _fila_o_404(uid)
    nuevo = validar_usuario(datos.usuario)
    viejo = fila["usuario"]
    if nuevo == viejo:
        return {"usuario": publico(fila), "tablas": {}}
    if _existe_usuario(nuevo):
        raise HTTPException(409, "Ese nombre de usuario ya existe.")
    try:
        nueva = db.actualizar_usuario(fila["id"], {"usuario": nuevo})
    except RuntimeError as e:
        raise _503(e)
    tablas = db.renombrar_usuario_en_tablas(viejo, nuevo)
    olvidar(viejo)
    olvidar(nuevo)
    db.registrar_cambio_usuario(quien, "renombrar", nuevo, {"de": viejo, "a": nuevo, "tablas": tablas})
    return {"usuario": publico(nueva), "tablas": tablas, "sesion_propia": viejo == quien}


@router.post("/admin/usuarios/{uid}/clave")
def admin_reset_clave(uid: str, datos: ResetClave, quien=Depends(_admin)):
    """Resetea la contraseña: 'temporal' (se muestra UNA vez y hay que cambiarla al entrar) o 'sin_clave'
    (la persona la crea desde «¿Primera vez?» con su email)."""
    fila = _fila_o_404(uid)
    if datos.modo not in ("temporal", "sin_clave"):
        raise HTTPException(400, "Modo inválido: temporal o sin_clave.")
    if datos.modo == "sin_clave" and not fila.get("email"):
        raise HTTPException(400, "Para dejarla sin clave la cuenta necesita un email (es lo que pide «¿Primera vez?»). Cargale el email primero o usá una clave temporal.")
    temporal = clave_temporal_nueva() if datos.modo == "temporal" else None
    try:
        db.actualizar_usuario(fila["id"], {"clave_hash": hashear(temporal) if temporal else None, "clave_temporal": bool(temporal)})
    except RuntimeError as e:
        raise _503(e)
    olvidar(fila["usuario"])
    db.registrar_cambio_usuario(quien, "clave", fila["usuario"], {"modo": datos.modo})
    return {"ok": True, "clave_temporal": temporal, "modo": datos.modo}


@router.delete("/admin/usuarios/{uid}")
def admin_borrar(uid: str, quien=Depends(_admin)):
    fila = _fila_o_404(uid)
    _proteger_ultimo_admin(fila, quien, "borrar")
    try:
        db.borrar_usuario(fila["id"])
    except RuntimeError as e:
        raise _503(e)
    olvidar(fila["usuario"])
    db.registrar_cambio_usuario(quien, "borrar", fila["usuario"], {"email": fila.get("email"), "rol": fila.get("rol")})
    return {"ok": True}


# ---------------- Administración: lista blanca ----------------
@router.get("/admin/lista-blanca")
def lista_blanca(quien=Depends(_admin)):
    if not db.disponible():
        return {"emails": [], "dominio": config.dominio_fva()}
    try:
        return {"emails": db.listar_autorizados(), "dominio": config.dominio_fva()}
    except RuntimeError as e:
        raise _503(e)


@router.put("/admin/lista-blanca")
def lista_blanca_alta(datos: ListaBlanca, quien=Depends(_admin)):
    email = validar_email(datos.email)
    if datos.rol not in ROLES:
        raise HTTPException(400, "Rol inválido.")
    try:
        existia = db.autorizado(email)
        r = db.agregar_autorizado(email, datos.rol, quien, nota=datos.nota if datos.nota is not None else "")
    except RuntimeError as e:
        raise _503(e)
    db.registrar_cambio_usuario(quien, "lista_editar" if existia else "lista_alta", email, {"rol": datos.rol, "nota": datos.nota})
    return {"ok": True, "fila": (r or [None])[0]}


@router.delete("/admin/lista-blanca/{email}")
def lista_blanca_baja(email: str, quien=Depends(_admin)):
    email = validar_email(email)
    try:
        db.quitar_autorizado(email)
    except RuntimeError as e:
        raise _503(e)
    db.registrar_cambio_usuario(quien, "lista_baja", email, {})
    return {"ok": True}


@router.get("/admin/cambios")
def cambios(quien=Depends(_admin), limite: int = 100):
    try:
        return db.listar_cambios_usuarios(min(limite, 500))
    except RuntimeError as e:
        raise _503(e)
