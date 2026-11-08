"""Modo campaña del chat (8/11, Beto, tarjeta Trello 99). Cuando la conversación llega a un plan (tema + piezas por canal) y la
persona pide armar o guardar la campaña, el modelo llama a la herramienta `proponer_campana` (nucleo.py) y la API hace esto:

  1. crea el Proyecto con el nombre de la campaña (o usa uno propio que ya se llame igual),
  2. guarda cada pieza como borrador en `publicaciones` (db.guardar_borrador, con la misma forma que guarda Diseñar: el dict `pieza`
     de api/pieza.py en resultado.pieza, más resultado.formato, resultado.fuente y resultado.porque),
  3. agrega las piezas al Proyecto como ítems tipo `pieza`,
  4. después de guardar la conversación, la agrega también como ítem `conversacion` (agregar_conversacion).

Devuelve el evento SSE `campana`: {proyecto_id, nombre, piezas: [{id, canal, canal_texto, titulo, formato, fuente, porque, url_editar}]}.
`url_editar` es la ruta de la web que abre ese borrador: /publicar?borrador=<id>, o /newsletter?borrador=<id> para el newsletter.
Un borrador es de quien chatea (dueño del Proyecto también): nada sale a ningún canal hasta que lo envíe desde Diseñar.
"""
import logging
from typing import Optional

import canales
import db
from db import proyectos as dbp
from . import newsletter_rutas as _nl
from .pieza import Pieza
import newsletter

log = logging.getLogger("api")

MAX_PIEZAS = 6
# Formato que pide el chat → formato de la foto en Diseñar (cuadrado | vertical | historia). Un reel o un carrusel necesitan un video
# o varias fotos que el chat no tiene: la pieza queda como foto del formato más cercano y el formato pedido va en resultado.formato.
_FORMATO_FOTO = {"historia": "historia", "cuadrado": "cuadrado", "reel": "vertical", "carrusel": "cuadrado"}


def _formato_foto(canal, formato):
    if canal not in ("instagram", "facebook"):
        return None
    f = _FORMATO_FOTO.get(formato)
    if f == "historia" and canal != "instagram":
        f = None                      # la historia es solo de Instagram
    return f


def _pieza_normal(canal, p):
    """(titulo, texto, dict `pieza` del borrador) de una pieza de Instagram, Facebook, YouTube o blogpost."""
    pieza = Pieza(canal=canal, titulo=p["titulo"], texto=p["texto"], texto_imagen=p.get("texto_imagen") or None,
                  firma=p.get("firma") or None, formato=_formato_foto(canal, p.get("formato")))
    return p["titulo"], p["texto"], pieza.a_borrador(canal, None)


def _pieza_newsletter(p):
    """El newsletter se retoma en su propio editor: plantilla + datos, con el título de la pieza de asunto y el texto de reflexión
    (lo mismo que hace el editor al recibir una pieza del chat)."""
    datos = _nl._completar("mensual", {"asunto": p["titulo"], "reflexion": p["texto"]})
    return _nl._titulo(datos), newsletter.armar_html("mensual", datos), {"plantilla": "mensual", "datos": datos}


def url_editar(canal, pid):
    return f"/newsletter?borrador={pid}" if canal == "newsletter" else f"/publicar?borrador={pid}"


def _proyecto_propio(usuario, nombre):
    """Un proyecto de la persona con ese nombre (sin distinguir mayúsculas ni espacios de más), o None."""
    buscado = " ".join(nombre.split()).lower()
    for p in dbp.proyectos_de(usuario):
        if " ".join((p.get("nombre") or "").split()).lower() == buscado:
            return p
    return None


def crear(usuario, campana) -> tuple[Optional[dict], str]:
    """campana: lo que devuelve nucleo._campana_de_args ({nombre, descripcion, piezas}). Devuelve (evento, aviso para el modelo).
    Sin base de datos o sin piezas guardadas: (None, motivo)."""
    if not db.disponible():
        return None, "No se pudo guardar la campaña: falta la conexión con la base de datos. Decile a la persona que lo intente más tarde."
    try:
        proyecto = _proyecto_propio(usuario, campana["nombre"])
        reutilizado = bool(proyecto)
        if not proyecto:
            proyecto = dbp.crear_proyecto({"nombre": campana["nombre"], "descripcion": campana.get("descripcion") or None,
                                           "dueno": usuario, "padre_id": None, "color": None, "emoji": None})
        if not proyecto:
            return None, "No se pudo crear el proyecto de la campaña."
        guardadas = []
        for p in campana["piezas"][:MAX_PIEZAS]:
            canal = p["canal"]
            if canal == "newsletter":
                titulo, texto, datos_pieza = _pieza_newsletter(p)
            else:
                titulo, texto, datos_pieza = _pieza_normal(canal, p)
            # resultado.formato (lo que lee Mis publicaciones), la fuente y el porqué: para abrir la pieza y saber de dónde sale
            conservar = {"formato": p.get("formato") or None, "fuente": p.get("fuente") or None, "porque": p.get("porque") or None,
                         "origen": "campana_chat", "campana": campana["nombre"]}
            pid = db.guardar_borrador(usuario, canal, titulo, texto, None, None, datos_pieza, conservar=conservar)
            if not pid:
                log.warning("campaña: no pude guardar el borrador de %s", canal)
                continue
            dbp.agregar_item({"proyecto_id": proyecto["id"], "tipo": "pieza", "item_id": str(pid), "datos": None, "agregado_por": usuario})
            guardadas.append({"id": str(pid), "canal": canal, "canal_texto": canales.textos().get(canal, canal), "titulo": titulo,
                              "formato": p.get("formato") or "", "fuente": p.get("fuente") or "", "porque": p.get("porque") or "",
                              "url_editar": url_editar(canal, pid)})
        if not guardadas:
            return None, "No se pudo guardar ninguna pieza de la campaña."
        dbp.tocar_proyecto(proyecto["id"])
    except Exception as e:           # la base no contesta, falta una migración, etc.: el chat sigue y le cuenta a la persona
        log.warning("campaña: %s", e)
        return None, "No se pudo guardar la campaña (falló la base de datos). Decile a la persona que lo intente de nuevo."
    evento = {"proyecto_id": proyecto["id"], "nombre": proyecto["nombre"], "piezas": guardadas}
    aviso = (f"Campaña «{proyecto['nombre']}» guardada{' en el proyecto que ya existía' if reutilizado else ''} con {len(guardadas)} piezas "
             "como borrador. Respondé en UNA o dos líneas: decile que abajo tiene la campaña con cada pieza para abrir en Diseñar. NO repitas las piezas.")
    return evento, aviso


def agregar_conversacion(usuario, proyecto_id, cid):
    """Suma la conversación al Proyecto de la campaña. Una conversación vive en un solo proyecto: si ya está en otro, no se la
    saca de ahí (devuelve False). Corre después de guardar la conversación, porque en una nueva el id recién existe entonces."""
    if not cid or not proyecto_id or not db.disponible():
        return False
    try:
        from .proyectos import conversacion_accesible
        if not conversacion_accesible(cid, usuario):
            return False
        ubic = dbp.ubicaciones_de("conversacion", str(cid))
        if any(u["proyecto_id"] == proyecto_id for u in ubic):
            return True
        if ubic:
            return False
        dbp.agregar_item({"proyecto_id": proyecto_id, "tipo": "conversacion", "item_id": str(cid), "datos": None, "agregado_por": usuario})
        dbp.tocar_proyecto(proyecto_id)
        return True
    except Exception as e:
        log.warning("campaña: no pude agregar la conversación al proyecto: %s", e)
        return False
