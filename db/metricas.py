"""La tabla metricas y las lecturas que necesita la pantalla Métricas de Administración (8/11, Franco; pedido de Beto).

metricas(id, creado, ambito pieza|canal|resumen, ref, canal, fuente api|manual|ia, periodo_desde, periodo_hasta, datos jsonb, nota,
por, capturado): una fila por CAPTURA, así queda la historia. «La última» de cada (ref, fuente) es la que se muestra.
Migración: api/migraciones/20261108_1200_metricas.sql. Contrato: web/maquetas/metricas-contrato.md.

  guardar_metrica(fila)                         inserta una captura y devuelve la fila guardada
  ultimas_metricas(ambito, refs, fuente)        la última de cada (ref, fuente), una sola consulta
  captura_cerca_de(ambito, ref, fecha, …)       (12/11) la captura por API más cercana a una fecha, dentro de una ventana (el «período anterior»)
  serie_canal(ref, dias)                        (12/11) las capturas por API de un canal en los últimos días, una por día (la última, hora Argentina)
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


def captura_cerca_de(ambito, ref, fecha, desde=None, hasta=None):
    """(12/11, Franco) La captura por API (fuente 'api') de (ambito, ref) cuyo `capturado` está más cerca de `fecha` (datetime o ISO),
    dentro de la ventana [desde, hasta] (datetimes o ISO; sin ellas, sin límite). None si no hay ninguna (o no hay Supabase).
    Sirve para comparar con «hace 28 días»: la tabla guarda todas las capturas, así que hay historia."""
    import datetime as dt

    def a_dt(v):
        if isinstance(v, dt.datetime):
            return v if v.tzinfo else v.replace(tzinfo=dt.timezone.utc)
        try:
            d = dt.datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        except ValueError:
            return None
        return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)

    if not _db.disponible():
        return None
    objetivo = a_dt(fecha)
    if objetivo is None:
        return None
    filtros = [("ambito", ("eq", ambito)), ("ref", ("eq", str(ref))), ("fuente", ("eq", "api"))]
    for op, v in (("gte", desde), ("lte", hasta)):
        if v is not None and a_dt(v) is not None:
            filtros.append(("capturado", (op, a_dt(v).strftime("%Y-%m-%dT%H:%M:%SZ"))))
    mejor, dist = None, None
    for f in _db.consulta("metricas", filtros, COLS, order="capturado.desc", limite=2000):
        c = a_dt(f.get("capturado"))
        if c is None:
            continue
        d = abs((c - objetivo).total_seconds())
        if dist is None or d < dist:
            mejor, dist = f, d
    return mejor


def serie_canal(ref, dias):
    """(12/11, Franco) Las capturas por API (ambito 'canal', fuente 'api') de `ref` de los últimos `dias` días, UNA POR DÍA: la última de cada día
    en hora Argentina (UTC-3), de la más vieja a la más nueva. La cola captura cada hora; para la tendencia alcanza un punto por día.
    Cada elemento es la fila de la tabla (con `datos`, `capturado`…). [] sin Supabase o sin capturas."""
    import datetime as dt
    if not _db.disponible():
        return []
    ar = dt.timezone(dt.timedelta(hours=-3))
    desde = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=int(dias))).strftime("%Y-%m-%dT%H:%M:%SZ")
    filtros = [("ambito", ("eq", "canal")), ("ref", ("eq", str(ref))), ("fuente", ("eq", "api")), ("capturado", ("gte", desde))]
    por_dia = {}
    for f in _db.consulta("metricas", filtros, COLS, order="capturado.asc", limite=5000):
        try:
            c = dt.datetime.fromisoformat(str(f.get("capturado")).replace("Z", "+00:00"))
        except ValueError:
            continue
        c = c if c.tzinfo else c.replace(tzinfo=dt.timezone.utc)
        dia = c.astimezone(ar).date().isoformat()
        previa = por_dia.get(dia)
        if previa is None or c >= previa[0]:
            por_dia[dia] = (c, f)
    return [por_dia[d][1] for d in sorted(por_dia)]


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
