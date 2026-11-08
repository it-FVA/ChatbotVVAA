"""
metricas.py — Métricas de campañas y canales (8/11, Franco; pedido de Beto: «que la app sea el centro de métricas de evolución de
campañas»). Contrato con la web: web/maquetas/metricas-contrato.md. Las rutas viven en api/metricas_rutas.py; el HTTP contra Meta,
en metricas_meta.py; el resumen con IA, en metricas_resumen.py; la tabla, en db/metricas.py (migración 20261108_1200_metricas.sql).

Dos preguntas, dos mitades:
  1. «Cuánto hicimos» sale de nuestra base, sin APIs: campanas(periodo) cruza proyectos + proyecto_items (tipo «pieza» →
     publicaciones.id) + publicaciones + la última métrica de cada pieza (de la API o cargada a mano; si hay las dos, la de la API).
  2. «Cuánto llegó» depende de cada plataforma: canales_estado(cfg) arma una tarjeta por canal (Instagram y Facebook por API;
     YouTube, mail, sitio y WhatsApp con enlace a la plataforma y carga a mano); capturar(cfg) pide los números a Meta y los guarda.

  GRUPO_ESTADO / grupo_de(estado)   el único lugar donde se agrupan los estados de una pieza (publicada, programada, en_aprobacion…)
  CLAVES_NORMALIZADAS               las claves de números que acepta la carga a mano y que usa la API
  campanas(periodo)                 GET /admin/metricas/campanas
  canales_estado(cfg)               GET /admin/metricas/canales
  capturar(cfg, por)                POST /admin/metricas/actualizar (cuenta de 28 días + cada pieza real publicada en los últimos 60)
  capturar_si_toca(cfg)             lo llama procesar_cola.py al final de cada pasada: captura si pasó más de 1 hora (nunca lanza)
  validar_manual / guardar_manual   PUT /admin/metricas/manual

Reglas de la casa: nada inventado (lo que una plataforma no da, no está: ni un 0); nunca se guarda ni se imprime un token; los
textos para la persona van en rioplatense y sin jerga («la conexión con Instagram», no «el token»).
Las fechas son en hora Argentina (UTC-3), como api/admin_rutas.py (cuyo `periodo()` se importa recién cuando se necesita, para que
la cola no cargue FastAPI).
"""
import re, datetime as dt

import db

ZONA_AR = dt.timezone(dt.timedelta(hours=-3))      # igual que api.admin_rutas.ZONA_AR

# (8/11) Único lugar donde se define a qué grupo pertenece cada estado de una pieza. Cualquier otro estado → «prueba».
GRUPO_ESTADO = {
    "publicada": "publicada",
    "pendiente": "programada", "lista": "programada", "procesando": "programada", "enviando": "programada",
    "a_aprobar": "en_aprobacion",
    "borrador": "borrador",
    "simulada": "prueba", "prueba": "prueba", "registrada": "prueba",
    "rechazada": "no_salio", "cancelada": "no_salio", "error": "no_salio",
}
GRUPOS = ("publicada", "programada", "en_aprobacion", "borrador", "prueba", "no_salio")

CLAVES_NORMALIZADAS = ("alcance", "vistas", "me_gusta", "comentarios", "guardados", "compartidos", "clics", "interacciones",
                       "seguidores", "seguidores_nuevos", "visitas", "visitantes", "enviados", "aperturas", "respuestas")

# Los canales de la pantalla, en este orden. «sitio» junta home + wordpress.
CLAVES_CANAL = ("instagram", "facebook", "youtube", "mail", "sitio", "whatsapp")
URL_META = "https://business.facebook.com/latest/insights/overview"
DIAS_CUENTA = 28            # ventana de los números de la cuenta
DIAS_PIEZAS = 60            # hasta cuándo atrás se piden los números de cada pieza
HORAS_ENTRE_CAPTURAS = 1    # capturar_si_toca
CLAVE_ULTIMA_CAPTURA = "metricas_ultima_captura"


def grupo_de(estado):
    return GRUPO_ESTADO.get((estado or "").strip().lower(), "prueba")


def _ahora():
    return dt.datetime.now(dt.timezone.utc)


def _iso(d):
    return d.isoformat(timespec="seconds")


def _fecha(valor):
    if not valor:
        return None
    try:
        d = dt.datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def fecha_efectiva(p):
    """La fecha que cuenta para el período: procesado_en, si no fecha_programada, si no creado."""
    return p.get("procesado_en") or p.get("fecha_programada") or p.get("creado")


def _en_periodo(iso, periodo):
    d = _fecha(iso)
    if not d:
        return False
    s = d.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return periodo["desde"] <= s and (not periodo.get("hasta") or s < periodo["hasta"])


def _res(p):
    r = p.get("resultado")
    return r if isinstance(r, dict) else {}


def _ultimo(p):
    u = _res(p).get("ultimo")
    return u if isinstance(u, dict) else {}


def id_plataforma(p):
    """El id que Instagram o Facebook le dieron a la pieza al publicarla: resultado.ultimo.id, si no resultado.id."""
    i = _ultimo(p).get("id") or _res(p).get("id")
    return str(i) if i else None


def _ver_url(p):
    u, r = _ultimo(p), _res(p)
    return u.get("permalink") or u.get("link") or r.get("permalink") or r.get("link") or None


def _formato(p):
    r = _res(p)
    f = r.get("formato")
    if f in ("historia", "cuadrado", "reel", "carrusel"):
        return f
    if r.get("video_url"):
        return "reel"
    if isinstance(r.get("imagenes"), list) and len(r["imagenes"]) >= 2:
        return "carrusel"
    return None


def _numeros(fila):
    """Solo los números normalizados de una fila de metricas (sin crudo ni errores)."""
    datos = (fila or {}).get("datos") or {}
    return {k: datos[k] for k in CLAVES_NORMALIZADAS if isinstance(datos.get(k), (int, float)) and not isinstance(datos.get(k), bool)}


def _por_canal_vacio():
    return {g: 0 for g in GRUPOS}


def _canal_texto(clave):
    try:
        import canales
        c = canales.canal(clave)
        return c.texto if c else (clave or "")
    except Exception:       # pragma: no cover
        return clave or ""


# ---------------- campañas ----------------
def _chunks(xs, n):
    xs = list(xs)
    return [xs[i:i + n] for i in range(0, len(xs), n)]


def metricas_de_piezas(ids):
    """{id de pieza: {numeros…, fuente, capturado}} con la última de la API o, si no hay, la última cargada a mano."""
    out = {}
    for tanda in _chunks(sorted({str(i) for i in ids}), 40):     # la lista va en la URL: de a 40 ids
        api = db.ultimas_metricas("pieza", refs=tanda, fuente="api")
        man = db.ultimas_metricas("pieza", refs=tanda, fuente="manual")
        for ref in tanda:
            fila = api.get((ref, "api")) or man.get((ref, "manual"))
            if fila and _numeros(fila):
                out[ref] = dict(_numeros(fila), fuente=fila.get("fuente"), capturado=fila.get("capturado"))
    return out


def _armar_campana(proyecto, piezas):
    por_canal, por_estado = {}, _por_canal_vacio()
    for p in piezas:
        por_canal.setdefault(p["canal"], _por_canal_vacio())[p["estado_grupo"]] += 1
        por_estado[p["estado_grupo"]] += 1
    fechas = [p["fecha"] for p in piezas if p["fecha"]]
    base = {"id": proyecto.get("id"), "nombre": proyecto.get("nombre"), "emoji": proyecto.get("emoji"), "color": proyecto.get("color"),
            "dueno": proyecto.get("dueno"), "creado": proyecto.get("creado")}
    return dict(base, piezas_total=len(piezas), por_canal=por_canal, por_estado=por_estado,
                primera=min(fechas) if fechas else None, ultima=max(fechas) if fechas else None,
                piezas=sorted(piezas, key=lambda p: p["fecha"] or "", reverse=True))


def campanas(periodo):
    """La respuesta de GET /campanas. `periodo` es el dict de api.admin_rutas.periodo() (desde/hasta ISO UTC)."""
    vacia = {"id": "sueltas", "nombre": "Sin campaña", "emoji": None, "color": None, "dueno": None, "creado": None}
    pubs = [p for p in db.publicaciones_para_metricas(periodo["desde"]) if _en_periodo(fecha_efectiva(p), periodo)]
    items = db.piezas_de_proyectos()
    proyecto_de = {}
    for it in items:                                   # una pieza vive en una sola carpeta; si hubiera dos, vale la primera
        proyecto_de.setdefault(str(it.get("item_id")), str(it.get("proyecto_id")))
    mets = metricas_de_piezas([p["id"] for p in pubs])
    piezas_de = {}
    for p in pubs:
        pid = str(p["id"])
        estado = p.get("estado")
        pieza = {"id": pid, "canal": p.get("canal"), "canal_texto": _canal_texto(p.get("canal")), "titulo": p.get("titulo") or "",
                 "estado": estado, "estado_grupo": grupo_de(estado), "fecha": fecha_efectiva(p), "ver_url": _ver_url(p),
                 "formato": _formato(p), "usuario": p.get("usuario"), "modo": p.get("modo"), "metricas": mets.get(pid)}
        piezas_de.setdefault(proyecto_de.get(pid, "sueltas"), []).append(pieza)
    ids_proyecto = {v for v in proyecto_de.values()}
    proyectos = db.proyectos.proyectos_por_ids(ids_proyecto) if ids_proyecto else []
    camps = [_armar_campana(pr, piezas_de.get(str(pr["id"]), [])) for pr in proyectos]
    camps.sort(key=lambda c: (c["ultima"] or "", c["nombre"] or ""), reverse=True)
    sueltas = _armar_campana(vacia, piezas_de.get("sueltas", []))
    todas = [p for c in camps + [sueltas] for p in c["piezas"]]
    totales = {"piezas": len(todas), **{g: sum(1 for p in todas if p["estado_grupo"] == g) for g in GRUPOS}, "por_canal": {}}
    for p in todas:
        totales["por_canal"][p["canal"]] = totales["por_canal"].get(p["canal"], 0) + 1
    return {"periodo": periodo, "campanas": camps, "sueltas": sueltas, "totales": totales}


# ---------------- canales ----------------
_NOTAS = {
    "youtube": ("pendiente", "Se pide cuando Google responda la auditoría de la API (en curso)."),
    "mail": ("no_hay", "Perfit: los reportes se ven en la plataforma; la API de métricas por campaña está sin confirmar."),
    "sitio": ("no_hay", "WordPress.com pide autorizar una app propia para leer las estadísticas; por ahora, el enlace."),
    "whatsapp": ("no_hay", "WhatsApp no da métricas de grupos."),
}


def _enlace(clave, cfg):
    if clave in ("instagram", "facebook"):
        return URL_META, "Ver en Meta Business Suite"
    if clave == "youtube":
        return "https://studio.youtube.com/", "Abrir YouTube Studio → Estadísticas"
    if clave == "mail":
        return "https://app.myperfit.com/", "Ver reportes en Perfit"
    if clave == "sitio":
        site = getattr(cfg, "wp_site", "") or ""
        return (f"https://wordpress.com/stats/day/{site}" if site else "https://wordpress.com/stats/"), "Ver estadísticas en WordPress.com"
    return None, None


def _estado_api_meta(clave, configurado, fila):
    """('disponible'|'sin_permiso'|'error'|'pendiente', nota) de Instagram o Facebook, según la última captura por API."""
    import metricas_meta
    nombre = "Instagram" if clave == "instagram" else "Facebook"
    if not configurado:
        return "error", f"Falta la conexión con {nombre} en el servidor."
    if not fila:
        return "pendiente", "Todavía no se pidieron los números: tocá «Actualizar»."
    datos = fila.get("datos") or {}
    errores = datos.get("errores") or []
    if any(metricas_meta.es_error_de_permiso(e) for e in errores):
        return "sin_permiso", next(e for e in errores if metricas_meta.es_error_de_permiso(e))
    if errores and not _numeros(fila):
        return "error", errores[0]
    return "disponible", (f"Algo no se pudo traer: {errores[0]}" if errores else "")


def _fila_publica(f, con_nota=False):
    if not f:
        return None
    r = {"datos": f.get("datos") or {}, "periodo_desde": f.get("periodo_desde"), "periodo_hasta": f.get("periodo_hasta"),
         "capturado": f.get("capturado"), "fuente": f.get("fuente")}
    if con_nota:
        r.update(nota=f.get("nota"), por=f.get("por"))
    return r


def canales_estado(cfg):
    """La respuesta de GET /canales: los seis canales siempre, en orden, con la última captura por API y la última carga a mano."""
    api = db.ultimas_metricas("canal", refs=list(CLAVES_CANAL), fuente="api")
    man = db.ultimas_metricas("canal", refs=list(CLAVES_CANAL), fuente="manual")
    modo = lambda c: cfg.modo(c)
    out, actualizado = [], None
    for clave in CLAVES_CANAL:
        fa, fm = api.get((clave, "api")), man.get((clave, "manual"))
        if clave in ("instagram", "facebook"):
            estado, nota = _estado_api_meta(clave, cfg.configurado.get(clave, False), fa)
            texto, icono, mod = _canal_texto(clave), clave, modo(clave)
            configurado = bool(cfg.configurado.get(clave))
        else:
            estado, nota = _NOTAS[clave]
            texto = {"sitio": "Sitio web", "mail": "Mail (Newsletter y Frase del día)"}.get(clave) or _canal_texto(clave)
            icono = {"mail": "sobre", "sitio": "casa", "youtube": "pelicula", "whatsapp": "celular"}[clave]
            mod = modo("wordpress" if clave == "sitio" else clave)
            configurado = bool(cfg.configurado.get("wordpress" if clave == "sitio" else clave))
        url, url_texto = _enlace(clave, cfg)
        if fa and fa.get("capturado") and (actualizado is None or fa["capturado"] > actualizado):
            actualizado = fa["capturado"]
        out.append({"clave": clave, "texto": texto, "icono": icono, "modo": mod, "configurado": configurado, "api": estado,
                    "nota_api": nota, "enlace": url, "enlace_texto": url_texto, "ultima": _fila_publica(fa),
                    "manual": _fila_publica(fm, con_nota=True)})
    return {"actualizado": actualizado, "canales": out}


# ---------------- carga a mano ----------------
def validar_manual(ambito, ref, canal, desde, hasta, datos):
    """Valida el PUT /manual. Devuelve (canal, datos_limpios) o levanta ValueError con el texto para la persona."""
    if ambito not in ("canal", "pieza"):
        raise ValueError("El ámbito tiene que ser «canal» o «pieza».")
    if not (ref or "").strip():
        raise ValueError("Falta decir a qué canal o pieza corresponden los números.")
    if ambito == "canal" and ref not in CLAVES_CANAL:
        raise ValueError(f"Canal desconocido: {ref}. Los posibles son {', '.join(CLAVES_CANAL)}.")
    if not isinstance(datos, dict) or not datos:
        raise ValueError("Cargá al menos un número.")
    limpios = {}
    for k, v in datos.items():
        if k not in CLAVES_NORMALIZADAS:
            raise ValueError(f"«{k}» no es un dato que se pueda anotar. Los posibles son {', '.join(CLAVES_NORMALIZADAS)}.")
        if isinstance(v, bool) or not isinstance(v, int) or v < 0:
            raise ValueError(f"«{k}» tiene que ser un número entero, 0 o más.")
        limpios[k] = v
    for etiqueta, f in (("desde", desde), ("hasta", hasta)):
        if f is not None and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(f)):
            raise ValueError(f"La fecha «{etiqueta}» tiene que ser AAAA-MM-DD.")
    if desde and hasta and str(desde) > str(hasta):
        raise ValueError("La fecha «desde» no puede ser posterior a «hasta».")
    return (ref if ambito == "canal" else canal), limpios


def guardar_manual(usuario, ambito, ref, canal, desde, hasta, datos, nota):
    """Guarda la carga a mano (fuente 'manual') y devuelve la fila. Levanta ValueError si algo no está bien."""
    canal, limpios = validar_manual(ambito, ref, canal, desde, hasta, datos)
    if ambito == "pieza":
        pub = db.publicacion_por_id(ref)
        if not pub:
            raise ValueError("No existe esa pieza.")
        canal = pub.get("canal")
    fila = {"ambito": ambito, "ref": ref, "canal": canal, "fuente": "manual", "periodo_desde": desde or None, "periodo_hasta": hasta or None,
            "datos": limpios, "nota": (nota or "").strip() or None, "por": usuario}
    return db.guardar_metrica(fila)


# ---------------- captura por API ----------------
def _captura_canal(cfg, clave, por, todas, ahora, desde_pub):
    """Cuenta + piezas de un canal de Meta. Devuelve {"ok", "piezas", "error"}; nunca lanza."""
    import metricas_meta as mm
    nombre = "Instagram" if clave == "instagram" else "Facebook"
    try:
        if clave == "instagram":
            cuenta = mm.insights_cuenta_instagram(cfg, DIAS_CUENTA)
        else:
            cuenta = mm.insights_pagina_facebook(cfg, DIAS_CUENTA)
        hoy = ahora.astimezone(ZONA_AR).date()
        db.guardar_metrica({"ambito": "canal", "ref": clave, "canal": clave, "fuente": "api",
                            "periodo_desde": (hoy - dt.timedelta(days=DIAS_CUENTA)).isoformat(), "periodo_hasta": hoy.isoformat(),
                            "datos": cuenta, "por": por})
        errores = cuenta.get("errores") or []
        permiso = [e for e in errores if mm.es_error_de_permiso(e)]
        hay_numeros = bool(_numeros({"datos": cuenta}))
        if permiso:
            return {"ok": False, "piezas": 0, "error": permiso[0]}
        if errores and not hay_numeros:
            return {"ok": False, "piezas": 0, "error": errores[0]}
        n, perm_pieza = 0, None
        for p in desde_pub:
            if p.get("canal") != clave:
                continue
            res = (mm.insights_pieza_instagram(cfg, id_plataforma(p), historia=_formato(p) == "historia") if clave == "instagram"
                   else mm.insights_posteo_facebook(cfg, id_plataforma(p)))
            if any(mm.es_error_de_permiso(e) for e in res.get("errores") or []):
                perm_pieza = next(e for e in res["errores"] if mm.es_error_de_permiso(e))
                break                                          # sin permiso no tiene sentido seguir pidiendo pieza por pieza
            db.guardar_metrica({"ambito": "pieza", "ref": str(p["id"]), "canal": clave, "fuente": "api", "datos": res, "por": por})
            n += 1
        if perm_pieza:
            return {"ok": False, "piezas": n, "error": perm_pieza}
        return {"ok": True, "piezas": n, "error": None}
    except Exception as e:      # nunca un 500 por un error de Meta o de la base
        return {"ok": False, "piezas": 0, "error": f"No pude traer los números de {nombre}: {type(e).__name__}: {mm._limpiar(str(e), getattr(cfg, 'ig_token', ''), getattr(cfg, 'fb_token', ''))[:160]}"}


def _piezas_a_capturar(todas, ahora):
    """Las publicadas en modo real de los últimos DIAS_PIEZAS días con id de la plataforma. Sin `todas` (la pasada de la cola)
    se saltean las que ya se capturaron hace menos de 20 h, salvo las historias (vencen a las 24 h: se piden cada hora mientras duren)."""
    desde = _iso(ahora - dt.timedelta(days=DIAS_PIEZAS))
    cand = []
    for p in db.publicaciones_para_metricas(desde):
        if p.get("estado") != "publicada" or p.get("modo") != "real" or p.get("canal") not in ("instagram", "facebook"):
            continue
        d = _fecha(fecha_efectiva(p))
        if not id_plataforma(p) or not d or d < ahora - dt.timedelta(days=DIAS_PIEZAS):
            continue
        if _formato(p) == "historia" and d < ahora - dt.timedelta(hours=26):
            continue                                            # Instagram ya borró sus métricas
        cand.append(p)
    if todas:
        return cand
    previas = {}
    for tanda in _chunks([str(p["id"]) for p in cand], 40):
        previas.update(db.ultimas_metricas("pieza", refs=tanda, fuente="api"))
    out = []
    for p in cand:
        f = previas.get((str(p["id"]), "api"))
        c = _fecha(f.get("capturado")) if f else None
        if _formato(p) == "historia" or not c or c < ahora - dt.timedelta(hours=20):
            out.append(p)
    return out


def capturar(cfg, por="api", todas=True):
    """Pide a Instagram y Facebook los números (cuenta de 28 días + cada pieza real publicada en los últimos 60) y los guarda
    con fuente 'api'. Devuelve {"capturado", "instagram": {ok, piezas, error}, "facebook": {…}}. No lanza por errores de Meta."""
    ahora = _ahora()
    try:
        cand = _piezas_a_capturar(todas, ahora)
    except Exception:
        cand = []
    res = {"capturado": _iso(ahora)}
    for clave in ("instagram", "facebook"):
        hay = bool(cfg.ig_token and cfg.ig_id) if clave == "instagram" else bool(cfg.fb_token and cfg.fb_page_id)
        res[clave] = (_captura_canal(cfg, clave, por, todas, ahora, cand) if hay else
                      {"ok": False, "piezas": 0, "error": f"Falta la conexión con {'Instagram' if clave == 'instagram' else 'Facebook'} en el servidor."})
    return res


def capturar_si_toca(cfg):
    """Lo llama procesar_cola.py: captura si pasó más de 1 hora desde la última (config metricas_ultima_captura). Nunca lanza.
    Devuelve el resultado de capturar() o None si no tocaba. Marca la hora aunque falle, para no insistir cada 15 minutos."""
    try:
        if not db.disponible():
            return None
        ahora = _ahora()
        ult = _fecha(db.obtener_config(CLAVE_ULTIMA_CAPTURA))
        if ult and ahora - ult < dt.timedelta(hours=HORAS_ENTRE_CAPTURAS):
            return None
        try:
            return capturar(cfg, por="cola", todas=False)
        finally:
            db.guardar_config(CLAVE_ULTIMA_CAPTURA, _iso(ahora), "cola")
    except Exception:
        return None
