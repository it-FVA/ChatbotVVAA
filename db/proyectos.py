"""Proyectos (carpetas colaborativas): tablas proyectos, proyecto_items y compartidos, más las lecturas por ids de las otras tablas
que la pantalla necesita para dibujar lo que hay en cada carpeta.
(3/11, revisión 5.2 punto 12) Antes api/proyectos.py armaba 30 consultas PostgREST a mano sobre db._req. Acá todo pasa por
consulta/insertar/actualizar/borrar, que escapan siempre. Los errores (RuntimeError) los convierte api/proyectos en HTTP 503.
"""
import db as _db

COLS = "id,nombre,descripcion,dueno,padre_id,color,emoji,creado,actualizado"
COLS_ITEM = "id,proyecto_id,tipo,item_id,datos,agregado_por,agregado"
COLS_COMP = "id,tipo,item_id,con_usuario,permiso,compartido_por,creado"


def _ids(ids):
    return sorted({str(i) for i in ids if i})


# ---------------- proyectos ----------------
def proyecto_por_id(pid):
    r = _db.consulta("proyectos", {"id": ("eq", pid)}, COLS)
    return r[0] if r else None


def proyectos_de(usuario):
    return _db.consulta("proyectos", {"dueno": ("eq", usuario)}, COLS, order="nombre.asc")


def proyectos_por_ids(ids):
    ids = _ids(ids)
    return _db.consulta("proyectos", {"id": ("in", ids)}, COLS, order="nombre.asc") if ids else []


def subcarpetas_de(pid):
    return _db.consulta("proyectos", {"padre_id": ("eq", pid)}, COLS, order="nombre.asc")


def crear_proyecto(fila):
    r = _db.insertar("proyectos", fila)
    return r[0] if r else None


def actualizar_proyecto(pid, cambios):
    r = _db.actualizar("proyectos", {"id": ("eq", pid)}, cambios)
    return r[0] if r else None


def tocar_proyecto(pid):
    _db.actualizar("proyectos", {"id": ("eq", pid)}, {"actualizado": _db._ahora_iso()})


def borrar_proyecto(pid):
    """Borra la carpeta (las subcarpetas y los ítems caen por on delete cascade) y lo compartido sobre ella."""
    _db.borrar("proyectos", {"id": ("eq", pid)})
    _db.borrar("compartidos", {"tipo": ("eq", "proyecto"), "item_id": ("eq", pid)})


# ---------------- ítems ----------------
def items_de(pid):
    return _db.consulta("proyecto_items", {"proyecto_id": ("eq", pid)}, COLS_ITEM, order="agregado.desc")


def items_de_varios(pids):
    pids = _ids(pids)
    return _db.consulta("proyecto_items", {"proyecto_id": ("in", pids)}, "id,proyecto_id,tipo,item_id") if pids else []


def item_por_id(iid):
    r = _db.consulta("proyecto_items", {"id": ("eq", iid)}, COLS_ITEM)
    return r[0] if r else None


def ubicaciones_de(tipo, item_id):
    return _db.consulta("proyecto_items", {"tipo": ("eq", tipo), "item_id": ("eq", item_id)}, COLS_ITEM)


def agregar_item(fila):
    r = _db.insertar("proyecto_items", fila)
    return r[0] if r else None


def borrar_item(iid):
    _db.borrar("proyecto_items", {"id": ("eq", iid)})


def mover_item(iid, proyecto_id):
    r = _db.actualizar("proyecto_items", {"id": ("eq", iid)}, {"proyecto_id": proyecto_id})
    return r[0] if r else None


def quitar_item_de_todos(tipo, item_id):
    _db.borrar("proyecto_items", {"tipo": ("eq", tipo), "item_id": ("eq", str(item_id))})


# ---------------- compartidos ----------------
def compartidos_de(tipo, item_id):
    return _db.consulta("compartidos", {"tipo": ("eq", tipo), "item_id": ("eq", item_id)}, COLS_COMP, order="creado.asc")


def compartidos_con(usuario, tipo=None):
    f = {"con_usuario": ("eq", usuario)}
    if tipo:
        f["tipo"] = ("eq", tipo)
    return _db.consulta("compartidos", f, COLS_COMP, order="creado.desc")


def compartidos_de_varios(tipo, ids):
    ids = _ids(ids)
    return _db.consulta("compartidos", {"tipo": ("eq", tipo), "item_id": ("in", ids)}, COLS_COMP) if ids else []


def compartir(fila):
    return _db.insertar("compartidos", fila)


def cambiar_permiso(cid, permiso):
    return _db.actualizar("compartidos", {"id": ("eq", cid)}, {"permiso": permiso})


def descompartir(tipo, item_id, con_usuario):
    _db.borrar("compartidos", {"tipo": ("eq", tipo), "item_id": ("eq", item_id), "con_usuario": ("eq", con_usuario)})


# ---------------- lo que hay adentro (lecturas por ids de las otras tablas) ----------------
def conversacion_por_id(cid):
    """Una conversación viva por id, de quien sea (el permiso lo decide api/proyectos.conversacion_accesible)."""
    r = _db.consulta("conversaciones", {"id": ("eq", cid), "borrada": ("is", None)}, "id,usuario,titulo,mensajes,creado,actualizado")
    return r[0] if r else None


def conversaciones_por_ids(ids, solo_vivas=False, order=None):
    ids = _ids(ids)
    if not ids:
        return []
    f = {"id": ("in", ids)}
    if solo_vivas:
        f["borrada"] = ("is", None)
    return _db.consulta("conversaciones", f, "id,usuario,titulo,actualizado,borrada", order=order)


def clips_por_ids(ids):
    ids = _ids(ids)
    return _db.consulta("clips", {"id": ("in", ids)}, "id,titulo,video_id,formato,estado,url,creado,pedido_por") if ids else []


def publicaciones_por_ids(ids):
    ids = _ids(ids)
    return _db.consulta("publicaciones", {"id": ("in", ids)}, "id,usuario,canal,estado,titulo,texto,imagen_url,creado") if ids else []
