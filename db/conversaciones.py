"""Conversaciones del chat y su papelera (tabla conversaciones).
(3/11, revisión 5.2 punto 12) Antes en db.py. Las funciones se llaman entre sí y a _req a través del paquete (`_db.x`), así
`monkeypatch.setattr(db, "x", …)` en las pruebas vale para todas. Los parámetros de los filtros van escapados con _q.
"""
import json, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timezone, timedelta

import db as _db
from ._cliente import _q


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
                    "pieza": m.get("pieza") or None,     # (24/9) recuadro "Publicar esta pieza"
                    "campana": m.get("campana") or None,  # (8/11) campaña guardada desde el chat (Proyecto + borradores)
                    "query": m.get("query", "")})
    return out


def listar_conversaciones(usuario):
    """[{id, titulo, actualizado}] del usuario, más recientes primero (sin las de la papelera)."""
    u = urllib.parse.quote(usuario)
    return _db._req("GET", f"?usuario=eq.{_q(u)}&borrada=is.null&select=id,titulo,actualizado&order=actualizado.desc")


def cargar_conversacion(cid):
    r = _db._req("GET", f"?id=eq.{_q(cid)}&select=id,titulo,mensajes,revisado,nota")
    return r[0] if r else None


def listar_todas(limite=1000, solo_no_revisadas=False):
    """Conversaciones (para el panel de revisión). Más recientes primero.
    Con solo_no_revisadas=True trae solo las que faltan revisar."""
    filtro = "&revisado=is.false" if solo_no_revisadas else ""
    return _db._req("GET", f"?select=id,usuario,titulo,actualizado,revisado&borrada=is.null{filtro}"
                       f"&order=actualizado.desc&limit={limite}")


def exportar_todas(limite=1000):
    """Todas las conversaciones COMPLETAS (con mensajes), para descargar."""
    return _db._req("GET", f"?select=id,usuario,titulo,mensajes,revisado,nota,creado,actualizado"
                       f"&order=actualizado.desc&limit={limite}")


def exportar_no_revisadas(limite=1000):
    """Solo las conversaciones NO revisadas, COMPLETAS (con mensajes)."""
    return _db._req("GET", f"?revisado=is.false&select=id,usuario,titulo,mensajes,creado,actualizado"
                       f"&order=actualizado.desc&limit={limite}")


def marcar_revisada(cid, revisado=True, nota=None):
    """Marca (o desmarca) una conversación como revisada, con nota opcional."""
    body = {"revisado": revisado}
    if nota is not None:
        body["nota"] = nota
    _db._req("PATCH", f"?id=eq.{_q(cid)}", body=body)


def crear_conversacion(usuario, titulo, mensajes):
    r = _db._req("POST", "", body={"usuario": usuario, "titulo": titulo, "mensajes": mensajes})
    return r[0]["id"] if r else None


def actualizar_conversacion(cid, titulo, mensajes):
    ahora = datetime.now(timezone.utc).isoformat()
    _db._req("PATCH", f"?id=eq.{_q(cid)}", body={"titulo": titulo, "mensajes": mensajes, "actualizado": ahora})


def renombrar(cid, titulo):
    """Solo cambia el título (no toca los mensajes)."""
    _db._req("PATCH", f"?id=eq.{_q(cid)}", body={"titulo": titulo})


def guardar_mensajes(cid, mensajes):
    """Solo actualiza los mensajes (no toca el título)."""
    ahora = datetime.now(timezone.utc).isoformat()
    _db._req("PATCH", f"?id=eq.{_q(cid)}", body={"mensajes": mensajes, "actualizado": ahora})


# ---------------- Papelera (15/10, pedido de Franco tras una conversación que Julián borró sin querer) ----------------
# "Borrar" ya no borra: marca `borrada` con la fecha. La conversación desaparece de la lista de la persona,
# los aprobadores la pueden restaurar desde el Panel admin durante PAPELERA_DIAS, y después se borra de verdad.
PAPELERA_DIAS = 30


def borrar_conversacion(cid):
    _db._req("PATCH", f"?id=eq.{_q(cid)}", {"borrada": datetime.now(timezone.utc).isoformat()})


def listar_papelera(limite=200):
    return _db._req("GET", f"?borrada=not.is.null&select=id,usuario,titulo,actualizado,borrada&order=borrada.desc&limit={limite}")


def restaurar_conversacion(cid):
    return _db._req("PATCH", f"?id=eq.{_q(cid)}", {"borrada": None})


def vaciar_papelera_vencida(dias=PAPELERA_DIAS):
    """Borra de verdad lo que lleva más de `dias` en la papelera. Devuelve cuántas."""
    if not _db.disponible():
        return 0
    limite = (datetime.now(timezone.utc) - timedelta(days=dias)).isoformat()
    viejas = _db._req("GET", f"?borrada=lt.{urllib.parse.quote(limite)}&select=id") or []
    for c in viejas:
        _db._req("DELETE", f"?id=eq.{_q(c['id'])}")
    return len(viejas)


# ---------------- API HTTP (21/10, fase 0 de la interfaz propia; carpeta api/) ----------------
# Funciones nuevas, solo para la API; las de arriba no cambian.

def cargar_conversacion_de(cid, usuario):
    """La conversación solo si es de esa persona y no está en la papelera (la API no confía en el id suelto)."""
    r = _db._req("GET", f"?id=eq.{urllib.parse.quote(str(cid))}&usuario=eq.{urllib.parse.quote(usuario)}&borrada=is.null"
                    f"&select=id,usuario,titulo,mensajes,creado,actualizado")
    return r[0] if r else None


def restaurar_conversacion_de(cid, usuario):
    """(22/10, web) Saca de la papelera una conversación solo si es de esa persona. Devuelve la fila o None."""
    r = _db._req("PATCH", f"?id=eq.{urllib.parse.quote(str(cid))}&usuario=eq.{urllib.parse.quote(usuario)}&borrada=not.is.null",
             {"borrada": None})
    return r[0] if r else None
