"""La tabla metricas y las lecturas que necesita la pantalla Métricas de Administración (8/11, Franco; pedido de Beto).

metricas(id, creado, ambito pieza|canal|resumen, ref, canal, fuente api|manual|ia, periodo_desde, periodo_hasta, datos jsonb, nota,
por, capturado): una fila por CAPTURA, así queda la historia. «La última» de cada (ref, fuente) es la que se muestra.
Migración: api/migraciones/20261108_1200_metricas.sql. Contrato: web/maquetas/metricas-contrato.md.

  guardar_metrica(fila)                         inserta una captura y devuelve la fila guardada
  ultimas_metricas(ambito, refs, fuente)        la última de cada (ref, fuente), una sola consulta
  publicaciones_para_metricas(desde_iso)        las piezas desde una fecha, con lo que hace falta para las campañas
  publicacion_por_id(pid)                       una pieza (id, canal, usuario, titulo) para validar la carga a mano
  piezas_de_proyectos()                         proyecto_items de tipo «pieza»: a qué campaña pertenece cada publicación

Sin Supabase (db.disponible() falso) todo devuelve vacío. Los errores de la base (RuntimeError) los convierte la ruta en HTTP 503.
"""
import db as _db
from ._cliente import _q

COLS = "id,creado,ambito,ref,canal,fuente,periodo_desde,periodo_hasta,datos,nota,por,capturado"


def guardar_metrica(fila):
    """Inserta una captura. Devuelve la fila guardada (o None sin Supabase)."""
    if not _db.disponible():
        return None
    r = _db.insertar("metricas", fila)
    return r[0] if r else None


def ultimas_metricas(ambito, refs=None, fuente=None):
    """{(ref, fuente): fila} con la captura más reciente de cada par. Una sola consulta ordenada por `capturado.desc`;
    el "quedarse con la primera de cada par" se hace acá en Python. `refs` (lista) y `fuente` filtran si se pasan."""
    if not _db.disponible():
        return {}
    filtros = {"ambito": ("eq", ambito)}
    if refs is not None:
        refs = [str(r) for r in refs]
        if not refs:
            return {}
        filtros["ref"] = ("in", refs)
    if fuente:
        filtros["fuente"] = ("eq", fuente)
    out = {}
    for f in _db.consulta("metricas", filtros, COLS, order="capturado.desc", limite=5000):
        out.setdefault((str(f.get("ref")), f.get("fuente")), f)
    return out


def publicaciones_para_metricas(desde_iso):
    """Piezas cuya fecha (creación, programada o de proceso) es de `desde_iso` en adelante. La fecha efectiva exacta
    (procesado_en → fecha_programada → creado) la resuelve metricas.py; acá solo se trae de más para no perder ninguna. Hasta 5.000."""
    if not _db.disponible():
        return []
    cols = "id,creado,usuario,canal,modo,titulo,estado,fecha_programada,procesado_en,resultado,imagen_url"
    if not desde_iso:
        return _db.consulta("publicaciones", None, cols, order="creado.desc", limite=5000)
    d = _q(desde_iso)
    return _db._req("GET", f"?select={cols}&or=(creado.gte.{d},fecha_programada.gte.{d},procesado_en.gte.{d})&order=creado.desc&limit=5000",
                    tabla="publicaciones") or []


def piezas_de_proyectos():
    """Todas las filas de proyecto_items de tipo «pieza»: [{proyecto_id, item_id}]."""
    if not _db.disponible():
        return []
    return _db.consulta("proyecto_items", {"tipo": ("eq", "pieza")}, "proyecto_id,item_id", limite=20000)


def publicacion_por_id(pid):
    """{id, canal, usuario, titulo} de una publicación, o None si no existe (o no hay Supabase)."""
    if not _db.disponible():
        return None
    r = _db.consulta("publicaciones", {"id": ("eq", pid)}, "id,canal,usuario,titulo", limite=1)
    return r[0] if r else None
