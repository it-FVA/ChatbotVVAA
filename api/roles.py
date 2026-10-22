"""Roles (creador / aprobador / publicación directa).

NOTA: es una COPIA de publicar_ui.roles (13/10). No se importa publicar_ui porque ese módulo importa streamlit
en su primera línea y lee st.secrets; acá la lista se lee del entorno con los mismos nombres (APROBADORES,
PUBLICACION_DIRECTA, separados por coma). Si cambia la regla en publicar_ui.roles, cambiarla acá también
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
    """Tres niveles, acumulativos (texto de publicar_ui.roles):
    - CREADOR DE CONTENIDO (todos): chat, arma piezas en simulado, las manda a aprobación.
    - APROBADOR / ADMIN (APROBADORES): panel admin: aprueba, rechaza, ve la cola y el registro.
    - PUBLICACIÓN DIRECTA (PUBLICACION_DIRECTA; por defecto = los aprobadores): publica sin aprobación.
    rol_tabla: 'aprobador' si la tabla autorizados lo dice (login con Google)."""
    aprob = _lista("APROBADORES", "julian,franco,beto")
    directa = _lista("PUBLICACION_DIRECTA", ",".join(aprob))
    aprueba = _esta(usuario, aprob) or (rol_tabla == "aprobador")
    return {"crea": True, "aprueba": aprueba, "publica": _esta(usuario, directa),
            "nombre": "aprobador / admin" if aprueba else "creador de contenido",
            "aprobadores": aprob, "publicadores": directa}
