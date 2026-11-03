"""Roles (creador / aprobador / admin).

(3/11, revisión 5.3 punto 20) La única fuente es la columna `rol` de la tabla `usuarios` (o, para una sesión de Google que
no pudo crear su fila, el rol de la lista blanca `autorizados`). Se sacaron las listas APROBADORES / ADMINS /
PUBLICACION_DIRECTA del entorno: un usuario con cualquier permiso se maneja desde Administración → Usuarios.

Tres niveles, acumulativos:
- CREADOR DE CONTENIDO (todos): chat, arma piezas en simulado, las manda a aprobación, sus recortes.
- APROBADOR: además aprueba y rechaza, ve la cola, el registro, la papelera y los recortes de todos, y publica sin aprobación.
- ADMIN: además Frase del día, Dashboard y toda la configuración (estilo por defecto de los subtítulos, precios, servicios y
  costos, lista de autorizados, usuarios). Un admin es también aprobador.
"""


def roles(rol):
    """Los permisos de quien tiene ese rol ('creador' | 'aprobador' | 'admin'; cualquier otra cosa o None = creador)."""
    admin = rol == "admin"
    aprueba = admin or rol == "aprobador"
    return {"crea": True, "aprueba": aprueba, "admin": admin, "publica": aprueba,
            "nombre": "admin" if admin else ("aprobador" if aprueba else "creador de contenido"),
            "aprobadores": []}


def roles_de_fila(fila):
    """Rol de una persona que está en la tabla `usuarios`: sale de `fila["rol"]`."""
    return roles((fila or {}).get("rol"))
