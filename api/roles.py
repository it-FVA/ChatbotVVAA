"""Roles (creador / aprobador / publicación directa).

NOTA: es una COPIA de publicar_ui.roles (13/10; roles admin del 21/10). No se importa publicar_ui porque ese módulo importa streamlit
en su primera línea y lee st.secrets; acá la lista se lee del entorno con los mismos nombres (APROBADORES,
ADMINS, PUBLICACION_DIRECTA, separados por coma). Si cambia la regla en publicar_ui.roles, cambiarla acá también
(el plan de migración prevé unificarlas en servicios.py).

(21/10) Para las cuentas que entran con Google el usuario es el email: se admite que la lista tenga el email
completo o solo la parte antes de la arroba (franco == franco@…). El rol que diga la tabla `autorizados`
se suma al de la lista.
"""
import os


def _lista(clave, defecto):
    return [u.strip() for u in str(os.environ.get(clave, defecto)).split(",") if u.strip()]


def _esta(usuario, lista):
    u = (usuario or "").strip().lower()
    local = u.split("@", 1)[0]
    return any(x.lower() in (u, local) for x in lista)


def roles(usuario, rol_tabla=None):
    """Tres niveles, acumulativos (misma regla que publicar_ui.roles, 21/10, Franco):
    - CREADOR DE CONTENIDO (todos): chat, arma piezas en simulado, las manda a aprobación, sus recortes.
    - APROBADOR (APROBADORES): además aprueba y rechaza, ve la cola, el registro, la papelera y los recortes de todos.
    - ADMIN (ADMINS, por defecto franco,beto): además Frase del día, Dashboard y toda la configuración (estilo por
      defecto de los subtítulos, precios, servicios y costos, lista de autorizados). Un admin es también aprobador.
      Julián es aprobador pero no admin.
    - PUBLICACIÓN DIRECTA (PUBLICACION_DIRECTA; por defecto = los aprobadores): publica sin aprobación.
    rol_tabla: 'aprobador' o 'admin' si la tabla autorizados lo dice (login con Google)."""
    admins = _lista("ADMINS", "franco,beto")
    aprob = sorted(set(_lista("APROBADORES", "julian,franco,beto")) | set(admins))
    directa = _lista("PUBLICACION_DIRECTA", ",".join(aprob))
    admin = _esta(usuario, admins) or (rol_tabla == "admin")
    aprueba = admin or _esta(usuario, aprob) or (rol_tabla == "aprobador")
    return {"crea": True, "aprueba": aprueba, "admin": admin, "publica": _esta(usuario, directa),
            "nombre": "admin" if admin else ("aprobador" if aprueba else "creador de contenido"),
            "aprobadores": aprob, "admins": admins, "publicadores": directa}


def roles_de_fila(fila):
    """(22/10) Rol de una persona que está en la tabla `usuarios`: sale de `fila["rol"]`, sin mirar las listas de
    secrets (salvo PUBLICACION_DIRECTA, que sigue siendo una lista; si está vacía publican los aprobadores)."""
    rol = fila.get("rol") or "creador"
    admin = rol == "admin"
    aprueba = admin or rol == "aprobador"
    admins = _lista("ADMINS", "franco,beto")
    aprob = sorted(set(_lista("APROBADORES", "julian,franco,beto")) | set(admins))
    directa = _lista("PUBLICACION_DIRECTA", "")
    publica = aprueba if not directa else _esta(fila.get("usuario"), directa)
    return {"crea": True, "aprueba": aprueba, "admin": admin, "publica": publica,
            "nombre": "admin" if admin else ("aprobador" if aprueba else "creador de contenido"),
            "aprobadores": aprob, "admins": admins, "publicadores": directa}
