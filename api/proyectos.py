"""«Proyectos» de la interfaz nueva (22/10): carpetas colaborativas donde se agrupan conversaciones, recortes, piezas e
imágenes; subcarpetas; compartir un proyecto o una conversación suelta con otra persona (ver / editar).
Tablas: proyectos, proyecto_items, compartidos (api/migraciones/proyectos_y_compartidos.sql). NADA se mueve de su tabla
original: un ítem del proyecto es solo una referencia (tipo + id). Pedido de Franco (22/10): «carpetas donde poner
conversaciones y agruparlas, compartir una carpeta o una conversación, verlo estilo Google Drive».

Reglas de acceso (las aplica este módulo):
  · dueño: todo (también borrar y compartir).
  · «editar» (compartido): agregar / sacar / mover ítems, renombrar, crear subcarpetas. No borra el proyecto ni lo comparte.
  · «ver»: solo lectura. El permiso de una carpeta vale para sus subcarpetas (se hereda hacia abajo).
  · una conversación / recorte / pieza está en UN proyecto o suelta: al agregarla a otro, se saca del anterior (si se puede editar).
  · una conversación compartida (directo o por proyecto) se puede abrir en el chat: lectura, o escribir si el permiso es «editar».

Rutas (todas con sesión):
  GET    /proyectos                                  mis proyectos + los compartidos conmigo (lista plana con padre_id) + dónde está cada ítem
  POST   /proyectos                                  {nombre, descripcion?, padre_id?, color?, emoji?}
  GET    /proyectos/{id}                             contenido: subcarpetas, ítems con resumen (título, fecha, miniatura, estado), migas, permiso
  PATCH  /proyectos/{id}                             {nombre?, descripcion?, padre_id?, color?, emoji?} (editar; mover de carpeta = padre_id)
  DELETE /proyectos/{id}                             solo el dueño (cascade: subcarpetas y referencias; NO borra conversaciones ni clips)
  POST   /proyectos/{id}/items                       {tipo, item_id, datos?} agrega (y lo saca de otro proyecto)
  DELETE /proyectos/{id}/items/{iid}                 saca del proyecto (no borra el original)
  POST   /proyectos/{id}/items/{iid}/mover           {proyecto_id} lo pasa a otra carpeta
  GET    /compartidos/{tipo}/{item_id}               con quién está compartido (proyecto | conversacion)
  PUT    /compartidos/{tipo}/{item_id}               {usuario, permiso}  (solo el dueño)
  DELETE /compartidos/{tipo}/{item_id}/{usuario}     descompartir (el dueño, o uno mismo para dejar de verlo)
  GET    /compartidos-conmigo                        {proyectos: [...], conversaciones: [...]}
  GET    /usuarios/buscar?q=                         [{usuario, nombre, email}] para el buscador de personas
"""
import logging, urllib.parse
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from . import auth
import db   # noqa: E402  (api/__init__ pone la raíz del repo en sys.path)

log = logging.getLogger("api")
router = APIRouter(tags=["proyectos"])

TIPOS_ITEM = ("conversacion", "recorte", "pieza", "imagen")
TIPOS_COMPARTIR = ("proyecto", "conversacion")
PERMISOS = ("ver", "editar")
NOMBRE_MAX = 80
PROFUNDIDAD_MAX = 6


# ---------------- Modelos ----------------
class ProyectoNuevo(BaseModel):
    nombre: str
    descripcion: Optional[str] = None
    padre_id: Optional[str] = None
    color: Optional[str] = None
    emoji: Optional[str] = None


class ProyectoCambios(BaseModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    padre_id: Optional[str] = None      # "" = pasarlo al primer nivel
    color: Optional[str] = None
    emoji: Optional[str] = None


class ItemNuevo(BaseModel):
    tipo: str
    item_id: str
    datos: Optional[dict] = None        # solo 'imagen': {url, miniatura?, titulo?}


class MoverItem(BaseModel):
    proyecto_id: str


class Compartir(BaseModel):
    usuario: str
    permiso: str = "ver"


# ---------------- Acceso a las tablas (todo pasa por db._req; los tests lo reemplazan) ----------------
def _q(v):
    return urllib.parse.quote(str(v))


def _req(method, params="", body=None, tabla="proyectos"):
    if not db.disponible():
        raise HTTPException(503, "Sin Supabase: los proyectos no están disponibles.")
    try:
        return db._req(method, params, body, tabla=tabla)
    except RuntimeError as e:
        txt = str(e)
        if "does not exist" in txt or "PGRST205" in txt or "Supabase 404" in txt:
            raise HTTPException(503, "Falta correr la migración api/migraciones/proyectos_y_compartidos.sql en Supabase.")
        raise HTTPException(503, f"No pude hablar con Supabase: {txt[:160]}")


COLS = "id,nombre,descripcion,dueno,padre_id,color,emoji,creado,actualizado"
COLS_ITEM = "id,proyecto_id,tipo,item_id,datos,agregado_por,agregado"
COLS_COMP = "id,tipo,item_id,con_usuario,permiso,compartido_por,creado"


def _ahora():
    return datetime.now(timezone.utc).isoformat()


def proyecto_por_id(pid):
    r = _req("GET", f"?id=eq.{_q(pid)}&select={COLS}")
    return r[0] if r else None


def proyectos_de(usuario):
    return _req("GET", f"?dueno=eq.{_q(usuario)}&select={COLS}&order=nombre.asc") or []


def proyectos_por_ids(ids):
    ids = sorted({str(i) for i in ids if i})
    if not ids:
        return []
    return _req("GET", f"?id=in.({','.join(_q(i) for i in ids)})&select={COLS}&order=nombre.asc") or []


def subcarpetas_de(pid):
    return _req("GET", f"?padre_id=eq.{_q(pid)}&select={COLS}&order=nombre.asc") or []


def items_de(pid):
    return _req("GET", f"?proyecto_id=eq.{_q(pid)}&select={COLS_ITEM}&order=agregado.desc", tabla="proyecto_items") or []


def items_de_varios(pids):
    pids = sorted({str(p) for p in pids if p})
    if not pids:
        return []
    return _req("GET", f"?proyecto_id=in.({','.join(_q(p) for p in pids)})&select=id,proyecto_id,tipo,item_id", tabla="proyecto_items") or []


def item_por_id(iid):
    r = _req("GET", f"?id=eq.{_q(iid)}&select={COLS_ITEM}", tabla="proyecto_items")
    return r[0] if r else None


def ubicaciones_de(tipo, item_id):
    return _req("GET", f"?tipo=eq.{_q(tipo)}&item_id=eq.{_q(item_id)}&select={COLS_ITEM}", tabla="proyecto_items") or []


def compartidos_de(tipo, item_id):
    return _req("GET", f"?tipo=eq.{_q(tipo)}&item_id=eq.{_q(item_id)}&select={COLS_COMP}&order=creado.asc", tabla="compartidos") or []


def compartidos_con(usuario, tipo=None):
    extra = f"&tipo=eq.{_q(tipo)}" if tipo else ""
    return _req("GET", f"?con_usuario=eq.{_q(usuario)}{extra}&select={COLS_COMP}&order=creado.desc", tabla="compartidos") or []


def compartidos_de_varios(tipo, ids):
    ids = sorted({str(i) for i in ids if i})
    if not ids:
        return []
    return _req("GET", f"?tipo=eq.{_q(tipo)}&item_id=in.({','.join(_q(i) for i in ids)})&select={COLS_COMP}", tabla="compartidos") or []


# ---------------- Permisos ----------------
def _cadena(p):
    """[p, padre, abuelo, …] hasta la raíz (como mucho PROFUNDIDAD_MAX+1 lecturas)."""
    out, visto = [], set()
    while p and p["id"] not in visto and len(out) <= PROFUNDIDAD_MAX:
        out.append(p)
        visto.add(p["id"])
        p = proyecto_por_id(p["padre_id"]) if p.get("padre_id") else None
    return out


def permiso_proyecto(p, usuario, cadena=None):
    """'dueño' | 'editar' | 'ver' | None, mirando el proyecto y sus carpetas de arriba (el permiso se hereda hacia abajo)."""
    if not p:
        return None
    if p.get("dueno") == usuario:
        return "dueño"
    cadena = cadena or _cadena(p)
    comp = compartidos_de_varios("proyecto", [c["id"] for c in cadena])
    permisos = {c["permiso"] for c in comp if c.get("con_usuario") == usuario}
    if "editar" in permisos:
        return "editar"
    if "ver" in permisos:
        return "ver"
    return None


def _proyecto_con(pid, usuario, minimo="ver"):
    """El proyecto y el permiso de la persona, o 404/403. minimo: 'ver' | 'editar' | 'dueño'."""
    p = proyecto_por_id(pid)
    if not p:
        raise HTTPException(404, "No existe ese proyecto.")
    perm = permiso_proyecto(p, usuario)
    if not perm:
        raise HTTPException(404, "No existe ese proyecto (o no tenés acceso).")
    if minimo == "dueño" and perm != "dueño":
        raise HTTPException(403, "Solo el dueño del proyecto puede hacer eso.")
    if minimo == "editar" and perm == "ver":
        raise HTTPException(403, "Este proyecto lo tenés solo para ver: no podés cambiarlo.")
    return p, perm


def conversacion_accesible(cid, usuario, editar=False):
    """Para el chat: (conversación, permiso) si es propia ('dueño'), compartida directo, o está en un proyecto compartido
    con la persona. None si no. Con editar=True exige 'dueño' o 'editar'. Es lo que main.py usa en GET /conversaciones/{id}
    y POST .../mensajes en vez de db.cargar_conversacion_de a secas."""
    c = db.cargar_conversacion_de(cid, usuario)
    if c:
        return c, "dueño"
    if not db.disponible():
        return None
    try:
        filas = db._req("GET", f"?id=eq.{_q(cid)}&borrada=is.null&select=id,usuario,titulo,mensajes,creado,actualizado")
    except Exception as e:          # la base no contesta: para el chat es «no existe», no un 500
        log.warning("conversacion_accesible: %s", e)
        return None
    if not filas:
        return None
    c = filas[0]
    permisos = set()
    try:
        for comp in compartidos_de("conversacion", c["id"]):
            if comp.get("con_usuario") == usuario:
                permisos.add(comp["permiso"])
        for u in ubicaciones_de("conversacion", c["id"]):
            perm = permiso_proyecto(proyecto_por_id(u["proyecto_id"]), usuario)
            if perm:
                permisos.add("editar" if perm in ("dueño", "editar") else "ver")
    except Exception as e:
        log.warning("conversacion_accesible (permisos): %s", e)
        return None
    if not permisos:
        return None
    perm = "editar" if "editar" in permisos else "ver"
    if editar and perm != "editar":
        return None
    return c, perm


# ---------------- Resúmenes de los ítems (una consulta por tipo) ----------------
def _titulo_pieza(p):
    t = (p.get("titulo") or "").strip()
    if t:
        return t
    txt = " ".join((p.get("texto") or "").split())
    return (txt[:70] + "…") if len(txt) > 70 else (txt or "Pieza")


def resumir_items(items, usuario):
    """Completa cada fila de proyecto_items con {titulo, fecha, miniatura, estado, url, dueno, existe}."""
    por_tipo = {}
    for it in items:
        por_tipo.setdefault(it["tipo"], set()).add(str(it["item_id"]))
    datos = {}
    if por_tipo.get("conversacion"):
        ids = ",".join(_q(i) for i in sorted(por_tipo["conversacion"]))
        for c in (_req("GET", f"?id=in.({ids})&select=id,usuario,titulo,actualizado,borrada", tabla="conversaciones") or []):
            datos[("conversacion", str(c["id"]))] = {"titulo": c.get("titulo") or "Conversación", "fecha": c.get("actualizado"),
                                                     "miniatura": None, "estado": "borrada" if c.get("borrada") else None,
                                                     "url": None, "dueno": c.get("usuario")}
    if por_tipo.get("recorte"):
        ids = ",".join(_q(i) for i in sorted(por_tipo["recorte"]))
        for c in (_req("GET", f"?id=in.({ids})&select=id,titulo,video_id,formato,estado,url,creado,pedido_por", tabla="clips") or []):
            datos[("recorte", str(c["id"]))] = {"titulo": c.get("titulo") or f"Recorte ({c.get('formato') or 'horizontal'})", "fecha": c.get("creado"),
                                                "miniatura": f"https://img.youtube.com/vi/{c['video_id']}/hqdefault.jpg" if c.get("video_id") else None,
                                                "estado": c.get("estado"), "url": c.get("url"), "dueno": c.get("pedido_por"),
                                                "formato": c.get("formato")}
    if por_tipo.get("pieza"):
        ids = ",".join(_q(i) for i in sorted(por_tipo["pieza"]))
        for p in (_req("GET", f"?id=in.({ids})&select=id,usuario,canal,estado,titulo,texto,imagen_url,creado", tabla="publicaciones") or []):
            datos[("pieza", str(p["id"]))] = {"titulo": _titulo_pieza(p), "fecha": p.get("creado"), "miniatura": p.get("imagen_url"),
                                              "estado": p.get("estado"), "url": None, "dueno": p.get("usuario"), "canal": p.get("canal")}
    out = []
    for it in items:
        d = datos.get((it["tipo"], str(it["item_id"])))
        if it["tipo"] == "imagen":
            dd = it.get("datos") or {}
            d = {"titulo": dd.get("titulo") or "Imagen", "fecha": it.get("agregado"), "miniatura": dd.get("miniatura") or dd.get("url"),
                 "estado": None, "url": dd.get("url") or it["item_id"], "dueno": it.get("agregado_por")}
        fila = dict(it)
        fila.update(d or {"titulo": "(ya no existe)", "fecha": it.get("agregado"), "miniatura": None, "estado": "no_existe", "url": None, "dueno": None})
        fila["existe"] = bool(d)
        fila["propio"] = (fila.get("dueno") == usuario)
        out.append(fila)
    return out


# ---------------- Helpers ----------------
def _nombre(n):
    n = " ".join((n or "").split())[:NOMBRE_MAX]
    if not n:
        raise HTTPException(400, "Falta el nombre del proyecto.")
    return n


def _publico(p, perm=None, extra=None):
    d = {"id": p["id"], "nombre": p.get("nombre"), "descripcion": p.get("descripcion"), "dueno": p.get("dueno"),
         "padre_id": p.get("padre_id"), "color": p.get("color"), "emoji": p.get("emoji"),
         "creado": p.get("creado"), "actualizado": p.get("actualizado"), "permiso": perm}
    if extra:
        d.update(extra)
    return d


def _tocar(pid):
    try:
        _req("PATCH", f"?id=eq.{_q(pid)}", {"actualizado": _ahora()})
    except HTTPException:
        pass


def _descendientes(raices, todos):
    """Ids de `raices` y todo lo que cuelga de ellas dentro de `todos` (lista de proyectos)."""
    hijos = {}
    for p in todos:
        hijos.setdefault(p.get("padre_id"), []).append(p["id"])
    out, cola = set(), [r for r in raices]
    while cola:
        x = cola.pop()
        if x in out:
            continue
        out.add(x)
        cola.extend(hijos.get(x, []))
    return out


def _usuario_existe(u):
    try:
        return bool(db.usuario_por_nombre(u))
    except Exception as e:
        log.warning("usuarios: %s", e)
        return False


# ---------------- Rutas: proyectos ----------------
@router.get("/proyectos")
def listar(usuario=Depends(auth.usuario_actual)):
    """Lista plana (padre_id arma el árbol): los míos, y los compartidos conmigo con sus subcarpetas (permiso heredado).
    `ubicaciones`: {tipo: {item_id: proyecto_id}} de todo lo que está en esos proyectos (para el chip de la barra)."""
    if not db.disponible():
        return {"proyectos": [], "ubicaciones": {}}
    mios = proyectos_de(usuario)
    comp = compartidos_con(usuario, "proyecto")
    por_id = {p["id"]: _publico(p, "dueño") for p in mios}
    raices = {c["item_id"]: c for c in comp}
    if raices:
        compartidos = proyectos_por_ids(raices.keys())
        # las subcarpetas de un proyecto compartido: bajando nivel por nivel
        frontera = list(compartidos)
        todos = list(compartidos)
        nivel = 0
        while frontera and nivel < PROFUNDIDAD_MAX:
            siguiente = []
            for p in frontera:
                siguiente.extend(subcarpetas_de(p["id"]))
            todos.extend(siguiente)
            frontera = siguiente
            nivel += 1
        # el permiso: el de la raíz compartida (si la persona lo tiene por dos raíces, gana editar)
        perm_de = {}
        for p in todos:
            if p["id"] in raices:
                perm_de[p["id"]] = raices[p["id"]]["permiso"]
        for p in todos:
            if p["id"] not in perm_de:
                perm_de[p["id"]] = perm_de.get(p.get("padre_id"), "ver")
        for p in todos:
            if p["id"] in por_id:
                continue
            c = raices.get(p["id"])
            por_id[p["id"]] = _publico(p, perm_de[p["id"]], {"compartido_por": c["compartido_por"] if c else None,
                                                             "raiz_compartida": p["id"] in raices})
    conteo = {}
    ubic = {t: {} for t in TIPOS_ITEM}
    for it in items_de_varios(por_id.keys()):
        conteo[it["proyecto_id"]] = conteo.get(it["proyecto_id"], 0) + 1
        ubic.setdefault(it["tipo"], {})[str(it["item_id"])] = it["proyecto_id"]
    # cuántas personas tienen cada proyecto mío
    con_quien = {}
    for c in compartidos_de_varios("proyecto", [p["id"] for p in mios]):
        con_quien[c["item_id"]] = con_quien.get(c["item_id"], 0) + 1
    lista = []
    for p in por_id.values():
        p["n_items"] = conteo.get(p["id"], 0)
        p["compartido_con_n"] = con_quien.get(p["id"], 0)
        lista.append(p)
    lista.sort(key=lambda p: (p["nombre"] or "").lower())
    return {"proyectos": lista, "ubicaciones": ubic}


@router.post("/proyectos")
def crear(datos: ProyectoNuevo, usuario=Depends(auth.usuario_actual)):
    nombre = _nombre(datos.nombre)
    padre_id = (datos.padre_id or "").strip() or None
    if padre_id:
        padre, _ = _proyecto_con(padre_id, usuario, "editar")
        if len(_cadena(padre)) >= PROFUNDIDAD_MAX:
            raise HTTPException(400, f"Demasiados niveles de carpetas (máximo {PROFUNDIDAD_MAX}).")
    fila = {"nombre": nombre, "descripcion": (datos.descripcion or "").strip() or None, "dueno": usuario, "padre_id": padre_id,
            "color": (datos.color or "").strip() or None, "emoji": (datos.emoji or "").strip()[:4] or None}
    r = _req("POST", "", fila)
    if not r:
        raise HTTPException(503, "No pude crear el proyecto.")
    p = r[0]
    return _publico(p, permiso_proyecto(p, usuario), {"n_items": 0, "compartido_con_n": 0})


@router.get("/proyectos/{pid}")
def ver(pid: str, usuario=Depends(auth.usuario_actual)):
    p, perm = _proyecto_con(pid, usuario)
    cadena = _cadena(p)
    migas = [{"id": x["id"], "nombre": x["nombre"]} for x in reversed(cadena)]
    # las migas solo hasta donde la persona tiene acceso
    if perm != "dueño":
        vis = []
        for x in reversed(cadena):
            if permiso_proyecto(x, usuario):
                vis.append({"id": x["id"], "nombre": x["nombre"]})
        migas = vis or migas[-1:]
    subs = [_publico(s, perm) for s in subcarpetas_de(p["id"])]
    for s in subs:
        s["n_items"] = len(items_de(s["id"]))
    items = resumir_items(items_de(p["id"]), usuario)
    comp = compartidos_de("proyecto", p["id"]) if perm == "dueño" else []
    return {"proyecto": _publico(p, perm), "permiso": perm, "migas": migas, "subcarpetas": subs, "items": items,
            "compartido_con": [{"usuario": c["con_usuario"], "permiso": c["permiso"], "creado": c.get("creado")} for c in comp]}


@router.patch("/proyectos/{pid}")
def editar(pid: str, datos: ProyectoCambios, usuario=Depends(auth.usuario_actual)):
    p, perm = _proyecto_con(pid, usuario, "editar")
    cambios = {}
    if datos.nombre is not None:
        cambios["nombre"] = _nombre(datos.nombre)
    if datos.descripcion is not None:
        cambios["descripcion"] = datos.descripcion.strip() or None
    if datos.color is not None:
        cambios["color"] = datos.color.strip() or None
    if datos.emoji is not None:
        cambios["emoji"] = datos.emoji.strip()[:4] or None
    if datos.padre_id is not None:
        nuevo = datos.padre_id.strip() or None
        if nuevo == p["id"]:
            raise HTTPException(400, "Una carpeta no puede ir adentro de sí misma.")
        if nuevo:
            padre, _ = _proyecto_con(nuevo, usuario, "editar")
            if any(x["id"] == p["id"] for x in _cadena(padre)):
                raise HTTPException(400, "No podés mover una carpeta adentro de una de sus subcarpetas.")
            if padre.get("dueno") != p.get("dueno"):
                raise HTTPException(400, "Solo se puede mover entre carpetas de la misma persona.")
        elif perm != "dueño":
            raise HTTPException(403, "Solo el dueño puede sacar la carpeta al primer nivel.")
        cambios["padre_id"] = nuevo
    if not cambios:
        return _publico(p, perm)
    cambios["actualizado"] = _ahora()
    r = _req("PATCH", f"?id=eq.{_q(p['id'])}", cambios)
    return _publico(r[0] if r else dict(p, **cambios), perm)


@router.delete("/proyectos/{pid}")
def borrar(pid: str, usuario=Depends(auth.usuario_actual)):
    """Borra la carpeta, sus subcarpetas y las referencias. Las conversaciones, recortes y piezas quedan donde estaban."""
    p, _ = _proyecto_con(pid, usuario, "dueño")
    _req("DELETE", f"?id=eq.{_q(p['id'])}")
    _req("DELETE", f"?tipo=eq.proyecto&item_id=eq.{_q(p['id'])}", tabla="compartidos")
    return {"ok": True, "id": p["id"]}


# ---------------- Rutas: ítems ----------------
def _validar_item(tipo, item_id, datos, usuario):
    if tipo not in TIPOS_ITEM:
        raise HTTPException(400, "El tipo tiene que ser conversacion, recorte, pieza o imagen.")
    item_id = (item_id or "").strip()
    if not item_id:
        raise HTTPException(400, "Falta el id del ítem.")
    if tipo == "conversacion":
        if not conversacion_accesible(item_id, usuario):
            raise HTTPException(404, "No existe esa conversación (o no tenés acceso).")
    elif tipo == "recorte":
        if not db.obtener_clip(item_id):
            raise HTTPException(404, "No existe ese recorte.")
    elif tipo == "pieza":
        if not db.obtener_publicacion(item_id):
            raise HTTPException(404, "No existe esa pieza.")
    elif tipo == "imagen":
        url = ((datos or {}).get("url") or item_id).strip()
        if not url.startswith("http"):
            raise HTTPException(400, "La imagen tiene que ser una URL.")
        item_id = url
        datos = {"url": url, "miniatura": (datos or {}).get("miniatura") or url, "titulo": ((datos or {}).get("titulo") or "").strip()[:120] or None}
    return item_id, (datos if tipo == "imagen" else None)


def _sacar_de_otros(tipo, item_id, usuario, salvo_pid):
    """Un ítem vive en un solo proyecto: lo saca de los demás que la persona pueda editar."""
    for u in ubicaciones_de(tipo, item_id):
        if u["proyecto_id"] == salvo_pid:
            continue
        otro = proyecto_por_id(u["proyecto_id"])
        if otro and permiso_proyecto(otro, usuario) in ("dueño", "editar"):
            _req("DELETE", f"?id=eq.{_q(u['id'])}", tabla="proyecto_items")
            _tocar(otro["id"])


@router.post("/proyectos/{pid}/items")
def agregar_item(pid: str, datos: ItemNuevo, usuario=Depends(auth.usuario_actual)):
    p, _ = _proyecto_con(pid, usuario, "editar")
    item_id, dd = _validar_item(datos.tipo, datos.item_id, datos.datos, usuario)
    _sacar_de_otros(datos.tipo, item_id, usuario, p["id"])
    ya = [u for u in ubicaciones_de(datos.tipo, item_id) if u["proyecto_id"] == p["id"]]
    if ya:
        fila = ya[0]
    else:
        r = _req("POST", "", {"proyecto_id": p["id"], "tipo": datos.tipo, "item_id": item_id, "datos": dd, "agregado_por": usuario}, tabla="proyecto_items")
        if not r:
            raise HTTPException(503, "No pude agregar el ítem.")
        fila = r[0]
        _tocar(p["id"])
    return {"ok": True, "ya": bool(ya), "item": resumir_items([fila], usuario)[0]}


@router.delete("/proyectos/{pid}/items/{iid}")
def quitar_item(pid: str, iid: str, usuario=Depends(auth.usuario_actual)):
    p, _ = _proyecto_con(pid, usuario, "editar")
    it = item_por_id(iid)
    if not it or it["proyecto_id"] != p["id"]:
        raise HTTPException(404, "Ese ítem no está en este proyecto.")
    _req("DELETE", f"?id=eq.{_q(it['id'])}", tabla="proyecto_items")
    _tocar(p["id"])
    return {"ok": True, "id": it["id"], "tipo": it["tipo"], "item_id": it["item_id"]}


@router.post("/proyectos/{pid}/items/{iid}/mover")
def mover_item(pid: str, iid: str, datos: MoverItem, usuario=Depends(auth.usuario_actual)):
    p, _ = _proyecto_con(pid, usuario, "editar")
    it = item_por_id(iid)
    if not it or it["proyecto_id"] != p["id"]:
        raise HTTPException(404, "Ese ítem no está en este proyecto.")
    destino, _ = _proyecto_con(datos.proyecto_id, usuario, "editar")
    if destino["id"] == p["id"]:
        return {"ok": True, "item": resumir_items([it], usuario)[0]}
    if any(u["proyecto_id"] == destino["id"] for u in ubicaciones_de(it["tipo"], it["item_id"])):
        _req("DELETE", f"?id=eq.{_q(it['id'])}", tabla="proyecto_items")       # ya estaba en el destino: solo lo sacamos de acá
        fila = [u for u in ubicaciones_de(it["tipo"], it["item_id"]) if u["proyecto_id"] == destino["id"]][0]
    else:
        r = _req("PATCH", f"?id=eq.{_q(it['id'])}", {"proyecto_id": destino["id"]}, tabla="proyecto_items")
        fila = r[0] if r else dict(it, proyecto_id=destino["id"])
    _tocar(p["id"])
    _tocar(destino["id"])
    return {"ok": True, "item": resumir_items([fila], usuario)[0]}


# ---------------- Rutas: compartir ----------------
def _objeto_compartible(tipo, item_id, usuario):
    """(fila, es_dueño) del proyecto o la conversación. 404 si no existe o no se ve."""
    if tipo == "proyecto":
        p = proyecto_por_id(item_id)
        if not p or not permiso_proyecto(p, usuario):
            raise HTTPException(404, "No existe ese proyecto (o no tenés acceso).")
        return p, p.get("dueno") == usuario
    if tipo == "conversacion":
        r = conversacion_accesible(item_id, usuario)
        if not r:
            raise HTTPException(404, "No existe esa conversación (o no tenés acceso).")
        return r[0], r[1] == "dueño"
    raise HTTPException(400, "Se comparte un proyecto o una conversación.")


@router.get("/compartidos/{tipo}/{item_id}")
def con_quien(tipo: str, item_id: str, usuario=Depends(auth.usuario_actual)):
    obj, dueno = _objeto_compartible(tipo, item_id, usuario)
    filas = compartidos_de(tipo, item_id)
    nombres = {}
    try:
        for u in db.listar_usuarios():
            nombres[u["usuario"]] = u.get("nombre")
    except Exception:
        pass
    return {"tipo": tipo, "item_id": item_id, "dueno": dueno,
            "con": [{"usuario": c["con_usuario"], "nombre": nombres.get(c["con_usuario"]), "permiso": c["permiso"],
                     "compartido_por": c.get("compartido_por"), "creado": c.get("creado")} for c in filas]}


@router.put("/compartidos/{tipo}/{item_id}")
def compartir(tipo: str, item_id: str, datos: Compartir, usuario=Depends(auth.usuario_actual)):
    obj, dueno = _objeto_compartible(tipo, item_id, usuario)
    if not dueno:
        raise HTTPException(403, "Solo quien lo creó puede compartirlo.")
    con = (datos.usuario or "").strip().lower()
    permiso = datos.permiso if datos.permiso in PERMISOS else "ver"
    if not con:
        raise HTTPException(400, "Falta el usuario.")
    if con == usuario:
        raise HTTPException(400, "No hace falta compartirlo con vos.")
    if not _usuario_existe(con):
        raise HTTPException(404, f"No encontré el usuario «{con}» en la tabla de usuarios.")
    ya = [c for c in compartidos_de(tipo, item_id) if c["con_usuario"] == con]
    if ya:
        _req("PATCH", f"?id=eq.{_q(ya[0]['id'])}", {"permiso": permiso}, tabla="compartidos")
    else:
        _req("POST", "", {"tipo": tipo, "item_id": item_id, "con_usuario": con, "permiso": permiso, "compartido_por": usuario}, tabla="compartidos")
    return {"ok": True, "usuario": con, "permiso": permiso, "nuevo": not ya}


@router.delete("/compartidos/{tipo}/{item_id}/{con}")
def descompartir(tipo: str, item_id: str, con: str, usuario=Depends(auth.usuario_actual)):
    """El dueño saca a cualquiera; una persona puede sacarse a sí misma (dejar de verlo)."""
    con = (con or "").strip().lower()
    obj, dueno = _objeto_compartible(tipo, item_id, usuario)
    if not dueno and con != usuario:
        raise HTTPException(403, "Solo quien lo creó puede dejar de compartirlo.")
    _req("DELETE", f"?tipo=eq.{_q(tipo)}&item_id=eq.{_q(item_id)}&con_usuario=eq.{_q(con)}", tabla="compartidos")
    return {"ok": True, "usuario": con}


@router.get("/compartidos-conmigo")
def conmigo(usuario=Depends(auth.usuario_actual)):
    """Lo que otras personas compartieron conmigo: proyectos (solo las raíces) y conversaciones sueltas."""
    if not db.disponible():
        return {"proyectos": [], "conversaciones": []}
    comp = compartidos_con(usuario)
    pids = [c["item_id"] for c in comp if c["tipo"] == "proyecto"]
    cids = [c["item_id"] for c in comp if c["tipo"] == "conversacion"]
    por = {(c["tipo"], c["item_id"]): c for c in comp}
    proyectos = []
    for p in proyectos_por_ids(pids):
        c = por[("proyecto", p["id"])]
        proyectos.append(_publico(p, c["permiso"], {"compartido_por": c["compartido_por"], "compartido_en": c.get("creado"),
                                                   "n_items": len(items_de(p["id"]))}))
    conversaciones = []
    if cids:
        ids = ",".join(_q(i) for i in sorted(set(cids)))
        for c in (_req("GET", f"?id=in.({ids})&borrada=is.null&select=id,usuario,titulo,actualizado&order=actualizado.desc", tabla="conversaciones") or []):
            comp_c = por[("conversacion", c["id"])]
            conversaciones.append({"id": c["id"], "titulo": c.get("titulo") or "Conversación", "actualizado": c.get("actualizado"),
                                   "dueno": c.get("usuario"), "permiso": comp_c["permiso"], "compartido_por": comp_c["compartido_por"],
                                   "compartido_en": comp_c.get("creado")})
    return {"proyectos": proyectos, "conversaciones": conversaciones}


@router.get("/usuarios/buscar")
def buscar_usuarios(q: str = "", usuario=Depends(auth.usuario_actual)):
    """Para el buscador de «Compartir»: usuarios activos de la tabla cuyo usuario, nombre o email contiene q (sin vos)."""
    if not db.disponible():
        return []
    q = (q or "").strip().lower()
    try:
        todos = db.listar_usuarios()
    except Exception as e:
        log.warning("buscar usuarios: %s", e)
        return []
    out = []
    for u in todos:
        if not u.get("activo", True) or u["usuario"] == usuario:
            continue
        campos = " ".join(filter(None, [u.get("usuario"), u.get("nombre"), u.get("email")])).lower()
        if not q or q in campos:
            out.append({"usuario": u["usuario"], "nombre": u.get("nombre"), "email": u.get("email")})
    return out[:20]
