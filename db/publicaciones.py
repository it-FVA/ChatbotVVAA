"""La tabla publicaciones: registro, cola, aprobación, borradores, Mis publicaciones.
(3/11, revisión 5.2 punto 12) Antes en db.py. Las funciones se llaman entre sí y a _req a través del paquete (`_db.x`), así
`monkeypatch.setattr(db, "x", …)` en las pruebas vale para todas. Los parámetros de los filtros van escapados con _q.
"""
import json, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timezone, timedelta

import db as _db
from ._cliente import _q


# ---------------- Publicaciones (pestaña Publicar) ----------------
# Tabla creada el 24/9 (migración crear_publicaciones):
#   publicaciones(id, creado, usuario, canal, modo, titulo, texto, imagen_url,
#                 fecha_programada, estado, resultado jsonb)
def registrar_publicacion(usuario, canal, modo, titulo, texto, imagen_url, fecha_programada, estado, resultado):
    if not _db.disponible():
        return None
    fila = {"usuario": usuario, "canal": canal, "modo": modo, "titulo": titulo, "texto": texto,
            "imagen_url": imagen_url, "fecha_programada": fecha_programada, "estado": estado,
            "resultado": resultado or {}}
    r = _db._req("POST", "", fila, tabla="publicaciones")
    return r[0]["id"] if r else None


# ---------------- Cola de publicación (25/9) ----------------
# Una pieza con fecha en un canal que no programa solo (Instagram; Facebook fuera de modo real)
# se guarda con estado 'pendiente'. procesar_cola.py la publica cuando vence y la deja en
# 'publicada' / 'simulada' / 'error'. Desde la app se puede cancelar ('cancelada').

def encolar_publicacion(usuario, canal, modo, titulo, texto, imagen_url, fecha_programada, extra=None, por=None):
    """`usuario` es la dueña de la pieza. `por` (4/11): quien la encoló, si es otra persona que la editaba por un proyecto compartido."""
    if not _db.disponible():
        return None
    fila = {"usuario": usuario, "canal": canal, "modo": modo, "titulo": titulo, "texto": texto,
            "imagen_url": imagen_url, "fecha_programada": fecha_programada, "estado": "pendiente",
            "resultado": dict(extra or {}, encolada_por=por or usuario)}
    r = _db._req("POST", "", fila, tabla="publicaciones")
    return r[0]["id"] if r else None


def listar_pendientes(vencidas=False, limite=50):
    """Piezas en cola. vencidas=True: solo las que ya tienen que salir (fecha <= ahora)."""
    if not _db.disponible():
        return []
    q = (f"?estado=eq.pendiente&select=id,creado,usuario,canal,modo,titulo,texto,imagen_url,fecha_programada,intentos,resultado"
         f"&order=fecha_programada.asc&limit={limite}")
    if vencidas:
        ahora = datetime.now(timezone.utc).isoformat()
        q += "&fecha_programada=lte." + urllib.parse.quote(ahora)
    return _db._req("GET", q, tabla="publicaciones")


def actualizar_publicacion(pid, campos):
    if not _db.disponible():
        return None
    return _db._req("PATCH", f"?id=eq.{_q(pid)}", campos, tabla="publicaciones")


def reclamar_publicacion(pid, resultado=None):
    """(3/11) La cola la toma antes de llamar al conector: pasa de 'pendiente' a 'procesando' SOLO si todavía está pendiente
    (un PATCH condicional, atómico en Postgres). Devuelve True si la tomó; False si otra corrida se le adelantó."""
    if not _db.disponible():
        return False
    res = dict(resultado or {}, procesando_desde=datetime.now(timezone.utc).isoformat())
    r = _db._req("PATCH", f"?id=eq.{_q(pid)}&estado=eq.pendiente", {"estado": "procesando", "resultado": res}, tabla="publicaciones")
    return bool(r)


def liberar_procesando_viejas(minutos=30):
    """(3/11) Si una corrida murió con piezas en 'procesando' (el job tiene tope de 10 min), las vuelve a 'pendiente' pasados
    `minutos`. Devuelve los ids liberados."""
    if not _db.disponible():
        return []
    corte = datetime.now(timezone.utc) - timedelta(minutes=minutos)
    liberadas = []
    for p in _db._req("GET", "?estado=eq.procesando&select=id,resultado", tabla="publicaciones") or []:
        desde = (p.get("resultado") or {}).get("procesando_desde")
        try:
            vieja = not desde or datetime.fromisoformat(desde) < corte
        except ValueError:
            vieja = True
        if vieja and _db._req("PATCH", f"?id=eq.{_q(p['id'])}&estado=eq.procesando", {"estado": "pendiente"}, tabla="publicaciones"):
            liberadas.append(p["id"])
    return liberadas


def cancelar_publicacion(pid, usuario):
    return _db.actualizar_publicacion(pid, {"estado": "cancelada",
                                        "procesado_en": datetime.now(timezone.utc).isoformat(),
                                        "resultado": {"cancelada_por": usuario}})


# ---------------- Aprobación (13/10, reunión: niveles normal · aprobación · publicación) ----------------
# Quien no publica en real manda la pieza con estado 'a_aprobar'. Un aprobador la ve en el panel,
# la aprueba (pasa a 'pendiente' en la cola, con fecha) o la rechaza ('rechazada', con nota).
# Todo queda en la misma tabla con quién hizo qué y cuándo.

def proponer_publicacion(usuario, canal, modo, titulo, texto, imagen_url, fecha_programada, extra=None, por=None):
    """`usuario` es la dueña de la pieza. `por` (4/11): quien la mandó a aprobación, si es otra persona con permiso de edición."""
    if not _db.disponible():
        return None
    fila = {"usuario": usuario, "canal": canal, "modo": modo, "titulo": titulo, "texto": texto,
            "imagen_url": imagen_url, "fecha_programada": fecha_programada, "estado": "a_aprobar",
            "resultado": dict(extra or {}, propuesta_por=por or usuario,
                              propuesta_en=datetime.now(timezone.utc).isoformat(timespec="seconds"))}
    r = _db._req("POST", "", fila, tabla="publicaciones")
    return r[0]["id"] if r else None


def listar_a_aprobar(limite=50):
    if not _db.disponible():
        return []
    q = (f"?estado=eq.a_aprobar&select=id,creado,usuario,canal,modo,titulo,texto,imagen_url,fecha_programada,resultado"
         f"&order=creado.asc&limit={limite}")
    return _db._req("GET", q, tabla="publicaciones")


def _resultado_actual(pid):
    r = _db._req("GET", f"?id=eq.{_q(pid)}&select=resultado", tabla="publicaciones")
    return (r[0].get("resultado") or {}) if r else {}


def aprobar_publicacion(pid, usuario, fecha_programada, modo, resultado_previo=None):
    if resultado_previo is None:
        resultado_previo = _db._resultado_actual(pid)
    return _db.actualizar_publicacion(pid, {"estado": "pendiente", "fecha_programada": fecha_programada, "modo": modo,
                                        "resultado": dict(resultado_previo or {}, aprobada_por=usuario,
                                                          aprobada_en=datetime.now(timezone.utc).isoformat(timespec="seconds"))})


def rechazar_publicacion(pid, usuario, nota, resultado_previo=None):
    if resultado_previo is None:
        resultado_previo = _db._resultado_actual(pid)
    previo = dict(resultado_previo or {})
    if previo.get("rechazada_por"):      # (4/11) una pieza corregida que se vuelve a rechazar: el rechazo anterior queda en la lista
        previo["rechazos"] = list(previo.get("rechazos") or []) + [
            {"por": previo.get("rechazada_por"), "en": previo.get("rechazada_en"), "nota": previo.get("nota") or ""}]
    return _db.actualizar_publicacion(pid, {"estado": "rechazada",
                                        "procesado_en": datetime.now(timezone.utc).isoformat(),
                                        "resultado": dict(previo, rechazada_por=usuario, nota=nota or "",
                                                          rechazada_en=datetime.now(timezone.utc).isoformat(timespec="seconds"))})


# (4/11) Una pieza rechazada vuelve al circuito: se corrige en la misma fila y se reenvía. Estas claves de `resultado` son su
# historial y pasan de una versión a la siguiente (guardar la corrección, reenviar a aprobación).
HISTORIAL = ("rechazada_por", "rechazada_en", "nota", "rechazos", "corregida_por", "corregida_en")


def historial_de(resultado):
    return {k: v for k, v in (resultado or {}).items() if k in HISTORIAL}


def reproponer_publicacion(pid, usuario, canal, modo, titulo, texto, imagen_url, fecha_programada, extra=None, por=None, previo=None):
    """(4/11) «Enviar a aprobación» desde un borrador o una rechazada que se está corrigiendo: la MISMA fila pasa a 'a_aprobar'
    (mismo id: la carpeta y el historial no se pierden). `usuario` es la dueña, `por` quien la manda."""
    if not _db.disponible():
        return None
    ahora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    resultado = dict(historial_de(previo), **(extra or {}))
    resultado.update(propuesta_por=por or usuario, propuesta_en=ahora)
    if (previo or {}).get("rechazada_por"):
        resultado["reenviada_en"] = ahora
    fila = {"usuario": usuario, "canal": canal, "modo": modo, "titulo": titulo, "texto": texto, "imagen_url": imagen_url,
            "fecha_programada": fecha_programada, "estado": "a_aprobar", "procesado_en": None, "resultado": resultado}
    r = _db._req("PATCH", f"?id=eq.{_q(pid)}", fila, tabla="publicaciones")
    return pid if r is not None else None


def listar_mias(usuario, limite=50):
    """(13/10) Todo lo que esta persona creó: propuestas, piezas aprobadas, publicadas, simuladas."""
    if not _db.disponible():
        return []
    q = (f"?select=id,creado,usuario,canal,modo,titulo,texto,imagen_url,estado,fecha_programada,procesado_en,resultado,compartido"
         f"&usuario=eq.{urllib.parse.quote(usuario)}&order=creado.desc&limit={limite}")
    return _db._req("GET", q, tabla="publicaciones")


def listar_compartidas(usuario, limite=50):
    """(2/11) Las piezas que otras personas compartieron con el equipo (publicaciones.compartido), como clips «Del equipo»."""
    if not _db.disponible():
        return []
    q = (f"?select=id,creado,usuario,canal,modo,titulo,texto,imagen_url,estado,fecha_programada,procesado_en,resultado,compartido"
         f"&compartido=is.true&usuario=neq.{urllib.parse.quote(usuario)}&order=creado.desc&limit={limite}")
    return _db._req("GET", q, tabla="publicaciones")


# ---------------- Borradores y limpieza (13/10, pedido de Franco) ----------------
# Una pieza que no va a ningún lado todavía se guarda como 'borrador' (con todos sus parámetros en
# resultado.pieza) y se retoma desde "Mis publicaciones". Lo que no sirve se elimina: borradores,
# pruebas simuladas y rechazadas propias. Lo publicado / aprobado / propuesto no se borra (registro).
ELIMINABLES = ("borrador", "prueba", "simulada", "simulado", "rechazada", "cancelada", "error")


def guardar_borrador(usuario, canal, titulo, texto, imagen_url, fecha_programada, pieza, pid=None, por=None, conservar=None):
    """`usuario` es la dueña. `por` (4/11): quien lo guardó, si es otra persona con permiso de edición por un proyecto
    (queda en resultado.editada_por; la dueña no cambia)."""
    if not _db.disponible():
        return None
    ahora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    resultado = dict(conservar or {}, pieza=pieza, guardado_en=ahora)   # conservar: el historial de un rechazo (4/11)
    resultado["imagenes"] = (pieza or {}).get("imagenes") or None       # (5/11, Franco) carrusel: también al nivel de video_url
    if por and por != usuario:
        resultado.update(editada_por=por, editada_en=ahora)
    fila = {"usuario": usuario, "canal": canal, "modo": "borrador", "titulo": titulo, "texto": texto,
            "imagen_url": imagen_url, "fecha_programada": fecha_programada, "estado": "borrador",
            "resultado": resultado}
    if pid:
        r = _db._req("PATCH", f"?id=eq.{_q(pid)}", fila, tabla="publicaciones")
        return pid if r is not None else None
    r = _db._req("POST", "", fila, tabla="publicaciones")
    return r[0]["id"] if r else None


def eliminar_publicacion(pid, usuario):
    """Borra de verdad, solo si es de esta persona y está en un estado eliminable."""
    if not _db.disponible():
        return False
    r = _db._req("GET", f"?id=eq.{_q(pid)}&select=usuario,estado", tabla="publicaciones")
    if not r or r[0].get("usuario") != usuario or r[0].get("estado") not in ELIMINABLES:
        return False
    _db._req("DELETE", f"?id=eq.{_q(pid)}", tabla="publicaciones")
    return True


def listar_registro(limite=60):
    """(13/10) Registro completo para el panel admin: quién creó, quién aprobó o rechazó, qué pasó."""
    if not _db.disponible():
        return []
    q = (f"?select=id,creado,usuario,canal,modo,titulo,texto,estado,fecha_programada,procesado_en,resultado"
         f"&order=creado.desc&limit={limite}")
    return _db._req("GET", q, tabla="publicaciones")


def listar_mis_propuestas(usuario, limite=10):
    """Las piezas que esta persona mandó a aprobación, con su estado actual."""
    if not _db.disponible():
        return []
    q = (f"?select=id,creado,canal,titulo,texto,estado,fecha_programada,resultado&usuario=eq.{urllib.parse.quote(usuario)}"
         f"&resultado->>propuesta_por=eq.{urllib.parse.quote(usuario)}&order=creado.desc&limit={limite}")
    return _db._req("GET", q, tabla="publicaciones")


def publicaciones_con_video(url):
    """Piezas (de cualquier estado menos borrador/prueba) cuyo resultado tiene ese video_url: para avisar antes de borrar un recorte."""
    if not _db.disponible() or not url:
        return []
    q = "?select=id,usuario,canal,estado,titulo&resultado->>video_url=eq." + urllib.parse.quote(url) + "&estado=not.in.(borrador,prueba,simulada,rechazada,cancelada)"
    return _db._req("GET", q, tabla="publicaciones") or []


def listar_publicaciones(usuario=None, limite=30):
    if not _db.disponible():
        return []
    q = f"?select=id,creado,usuario,canal,modo,titulo,estado,fecha_programada&order=creado.desc&limit={limite}"
    if usuario:
        q += "&usuario=eq." + urllib.parse.quote(usuario)
    return _db._req("GET", q, tabla="publicaciones")


def obtener_publicacion(pid):
    """Una fila completa por id (la usan la cola de la frase, Mis publicaciones, Aprobación y Compartir), o None."""
    r = _db.consulta("publicaciones", {"id": ("eq", pid)},
                     "id,creado,usuario,canal,modo,titulo,texto,imagen_url,estado,fecha_programada,procesado_en,intentos,resultado,compartido")
    return r[0] if r else None


def obtener_borrador(pid, usuario, canal=None):
    """(3/11) Un borrador propio por id (el newsletter lo usa para retomar), o None."""
    f = {"id": ("eq", pid), "usuario": ("eq", usuario), "estado": ("eq", "borrador")}
    if canal:
        f["canal"] = ("eq", canal)
    r = _db.consulta("publicaciones", f, "id,creado,titulo,texto,resultado")
    return r[0] if r else None


def borrar_borrador(pid, usuario):
    """(3/11) Al enviar, el borrador que se estaba retomando se elimina (solo si sigue siendo borrador, o una rechazada que se
    corrigió (4/11), y es de esa persona)."""
    if not pid:
        return
    _db.borrar("publicaciones", {"id": ("eq", pid), "estado": ("in", ["borrador", "rechazada"]), "usuario": ("eq", usuario)})


# ---------------- Frase del día por mail (26/10): tabla frase_envios ----------------
# Un renglón por destinatario y por día. La pieza 'mail' de publicaciones (estado 'enviando') agrupa el envío del día;
# publicacion_id null + prueba=true = prueba suelta del equipo. Lo escribe frase_mail.py.
def publicaciones_por_estado(estado, canal=None, limite=20):
    if not _db.disponible():
        return []
    q = f"?estado=eq.{urllib.parse.quote(estado)}&select=id,creado,usuario,canal,modo,titulo,texto,imagen_url,fecha_programada,intentos,resultado&order=fecha_programada.asc&limit={limite}"
    if canal:
        q += f"&canal=eq.{urllib.parse.quote(canal)}"
    return _db._req("GET", q, tabla="publicaciones") or []
