"""
metricas.py — Métricas de campañas y canales (8/11, Franco; pedido de Beto: «que la app sea el centro de métricas de evolución de
campañas»). Contrato con la web: web/maquetas/metricas-contrato.md. Las rutas viven en api/metricas_rutas.py; el HTTP contra Meta,
en metricas_meta.py (Instagram y Facebook), metricas_youtube.py (YouTube, 8/11) y metricas_wordpress.py (el sitio, WordPress.com, 8/11); el asesor de campañas con IA, en metricas_asesor.py; la tabla, en db/metricas.py (migración 20261108_1200_metricas.sql).

Dos preguntas, dos mitades:
  1. «Cuánto hicimos» sale de nuestra base, sin APIs: campanas(periodo) cruza proyectos + proyecto_items (tipo «pieza» →
     publicaciones.id) + publicaciones + la última métrica de cada pieza (de la API o cargada a mano; si hay las dos, la de la API).
  2. «Cuánto llegó» depende de cada plataforma: canales_estado(cfg) arma una tarjeta por canal (Instagram, Facebook, YouTube y el sitio por API;
     mail y WhatsApp con enlace a la plataforma y carga a mano); capturar(cfg) pide los números a Meta, Google y WordPress.com y los guarda.

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


FRASE_DEL_DIA = {"id": "frase_del_dia", "nombre": "Frase del día (automática)", "emoji": "📅", "color": None, "dueno": None, "creado": None}
GRUPOS_HECHAS = ("publicada", "programada", "en_aprobacion")      # lo que cuenta como «hecho» en los totales (8/11, Franco)
CLAVE_EXCLUIR = "metricas_excluir_usuarios"


def usuarios_excluidos():
    """Los usuarios cuyas piezas no cuentan en Métricas (config metricas_excluir_usuarios; vacía por defecto). Nunca lanza."""
    try:
        v = db.obtener_config(CLAVE_EXCLUIR, [])
    except Exception:
        return set()
    return {str(u) for u in v if u} if isinstance(v, list) else set()


def campanas(periodo):
    """La respuesta de GET /campanas. `periodo` es el dict de api.admin_rutas.periodo() (desde/hasta ISO UTC).
    (8/11, Franco) Las piezas de los usuarios de metricas_excluir_usuarios no entran en nada. Las piezas de los usuarios de servicio
    (frase_del_dia, bot, cola, prueba) que no están en ningún Proyecto forman la campaña virtual «Frase del día (automática)», que va
    después de las reales y antes de «Sin campaña». Los totales suman solo publicada + programada + en_aprobacion."""
    from api.admin_rutas import SERVICIO           # recién acá: la cola no carga FastAPI
    vacia = {"id": "sueltas", "nombre": "Sin campaña", "emoji": None, "color": None, "dueno": None, "creado": None}
    excluidos = usuarios_excluidos()
    pubs = [p for p in db.publicaciones_para_metricas(periodo["desde"]) if _en_periodo(fecha_efectiva(p), periodo) and p.get("usuario") not in excluidos]
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
        clave = proyecto_de.get(pid) or ("frase_del_dia" if p.get("usuario") in SERVICIO else "sueltas")
        piezas_de.setdefault(clave, []).append(pieza)
    ids_proyecto = {v for v in proyecto_de.values()}
    proyectos = db.proyectos.proyectos_por_ids(ids_proyecto) if ids_proyecto else []
    camps = [_armar_campana(pr, piezas_de.get(str(pr["id"]), [])) for pr in proyectos]
    camps.sort(key=lambda c: (c["ultima"] or "", c["nombre"] or ""), reverse=True)
    if piezas_de.get("frase_del_dia"):
        camps.append(_armar_campana(FRASE_DEL_DIA, piezas_de["frase_del_dia"]))
    sueltas = _armar_campana(vacia, piezas_de.get("sueltas", []))
    todas = [p for c in camps + [sueltas] for p in c["piezas"]]
    totales = {"piezas": sum(1 for p in todas if p["estado_grupo"] in GRUPOS_HECHAS), **{g: sum(1 for p in todas if p["estado_grupo"] == g) for g in GRUPOS}, "por_canal": {}}
    for p in todas:
        if p["estado_grupo"] in GRUPOS_HECHAS:
            totales["por_canal"][p["canal"]] = totales["por_canal"].get(p["canal"], 0) + 1
    return {"periodo": periodo, "campanas": camps, "sueltas": sueltas, "totales": totales}


# ---------------- canales ----------------
_NOTAS = {
    "mail": ("no_hay", "Perfit: los reportes se ven en la plataforma; la API de métricas por campaña está sin confirmar."),
    "sitio": ("no_hay", "WordPress.com pide autorizar una app propia para leer las estadísticas; por ahora, el enlace."),
    "whatsapp": ("no_hay", "WhatsApp no da métricas de grupos."),
}


def _enlace(clave, cfg):
    if clave in ("instagram", "facebook"):
        return URL_META, "Ver en Meta Business Suite"
    if clave == "youtube":
        return "https://studio.youtube.com/", "Abrir YouTube Studio"
    if clave == "mail":
        return "https://app.myperfit.com/", "Ver en Perfit"
    if clave == "sitio":
        site = getattr(cfg, "wp_site", "") or ""
        return (f"https://wordpress.com/stats/day/{site}" if site else "https://wordpress.com/stats/"), "Ver en WordPress.com"
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


def _estado_api_youtube(configurado, fila):
    """('disponible'|'sin_permiso'|'error'|'pendiente', nota) de YouTube, según la última captura por API."""
    import metricas_youtube
    if not configurado:
        return "error", "Falta la conexión con YouTube en el servidor."
    if not fila:
        return "pendiente", "Todavía no se pidieron los números: tocá «Actualizar»."
    errores = (fila.get("datos") or {}).get("errores") or []
    if any(metricas_youtube.es_error_de_scope(e) for e in errores):
        return "sin_permiso", next(e for e in errores if metricas_youtube.es_error_de_scope(e))
    if errores and not _numeros(fila):
        return "error", errores[0]
    return "disponible", (f"Algo no se pudo traer: {errores[0]}" if errores else "")


RUTA_CONECTAR_SITIO = "/admin/metricas/wordpress/autorizar"      # (8/11, Franco) la web navega acá (redirige a WordPress.com)


def _estado_api_sitio(cfg, fila):
    """(estado, nota, conectado, conectar_url) del sitio (8/11, Franco). 'disponible' con token y números en la última captura;
    'pendiente' si hay app registrada pero falta conectar (o conectado y sin captura); 'no_hay' sin app; 'error' lo demás."""
    import metricas_wordpress as mw
    tok = mw.token_guardado()
    app = bool(getattr(cfg, "wpcom_client_id", "") and getattr(cfg, "wpcom_client_secret", ""))
    url = RUTA_CONECTAR_SITIO if app else None
    if not tok:
        if app:
            return "pendiente", mw.TEXTO_SIN_TOKEN, False, url
        return _NOTAS["sitio"][0], _NOTAS["sitio"][1], False, None
    if not fila:
        return "pendiente", "Todavía no se pidieron los números: tocá «Actualizar».", True, url
    errores = (fila.get("datos") or {}).get("errores") or []
    if any(mw.es_error_de_conexion(e) for e in errores):
        return "error", next(e for e in errores if mw.es_error_de_conexion(e)), True, url
    if errores and not _numeros(fila):
        return "error", errores[0], True, url
    return "disponible", (f"Algo no se pudo traer: {errores[0]}" if errores else ""), True, url


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
        conectado, conectar_url = False, None
        if clave in ("instagram", "facebook", "youtube"):
            if clave == "youtube":
                estado, nota = _estado_api_youtube(cfg.configurado.get(clave, False), fa)
            else:
                estado, nota = _estado_api_meta(clave, cfg.configurado.get(clave, False), fa)
            texto, icono, mod = _canal_texto(clave), ("pelicula" if clave == "youtube" else clave), modo(clave)
            configurado = bool(cfg.configurado.get(clave))
        else:
            if clave == "sitio":
                estado, nota, conectado, conectar_url = _estado_api_sitio(cfg, fa)
            else:
                (estado, nota), conectado, conectar_url = _NOTAS[clave], False, None
            texto = {"sitio": "Sitio web", "mail": "Mail (Newsletter y Frase del día)"}.get(clave) or _canal_texto(clave)
            icono = {"mail": "sobre", "sitio": "casa", "whatsapp": "celular"}[clave]
            mod = modo("wordpress" if clave == "sitio" else clave)
            configurado = bool(cfg.configurado.get("wordpress" if clave == "sitio" else clave))
        url, url_texto = _enlace(clave, cfg)
        if fa and fa.get("capturado") and (actualizado is None or fa["capturado"] > actualizado):
            actualizado = fa["capturado"]
        out.append({"clave": clave, "texto": texto, "icono": icono, "modo": mod, "configurado": configurado, "api": estado,
                    "nota_api": nota, "enlace": url, "enlace_texto": url_texto, "conectado": conectado, "conectar_url": conectar_url, "ultima": _fila_publica(fa),
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
        # (8/11, visto en vivo) una pieza que Meta rechaza (borrada, de otra cuenta, vencida) NO frena a las demás: se guarda con su
        # error y se sigue. El permiso de verdad se detecta arriba, a nivel cuenta; acá solo se informa si ninguna pieza dio números.
        n, con_numeros, perm_pieza = 0, 0, None
        for p in desde_pub:
            if p.get("canal") != clave:
                continue
            res = (mm.insights_pieza_instagram(cfg, id_plataforma(p), historia=_formato(p) == "historia") if clave == "instagram"
                   else mm.insights_posteo_facebook(cfg, id_plataforma(p)))
            db.guardar_metrica({"ambito": "pieza", "ref": str(p["id"]), "canal": clave, "fuente": "api", "datos": res, "por": por})
            n += 1
            if _numeros({"datos": res}):
                con_numeros += 1
            elif perm_pieza is None:
                perm_pieza = next((e for e in res.get("errores") or [] if mm.es_error_de_permiso(e)), None)
        if perm_pieza and n and not con_numeros:
            return {"ok": False, "piezas": 0, "error": perm_pieza}
        return {"ok": True, "piezas": con_numeros, "error": None}
    except Exception as e:      # nunca un 500 por un error de Meta o de la base
        return {"ok": False, "piezas": 0, "error": f"No pude traer los números de {nombre}: {type(e).__name__}: {mm._limpiar(str(e), getattr(cfg, 'ig_token', ''), getattr(cfg, 'fb_token', ''))[:160]}"}


def _captura_youtube(cfg, por, ahora, desde_pub):
    """Canal + videos de YouTube (8/11). Devuelve {"ok", "piezas", "error"}; nunca lanza. Si falta el permiso de Analytics el canal y los
    videos igual se guardan con lo que dio la Data API (vistas, me gusta, comentarios) y `error` dice qué hacer."""
    import metricas_youtube as my
    secretos = my._secretos(cfg)
    try:
        cuenta = my.insights_canal_youtube(cfg, DIAS_CUENTA)
        hoy = ahora.astimezone(ZONA_AR).date()
        db.guardar_metrica({"ambito": "canal", "ref": "youtube", "canal": "youtube", "fuente": "api",
                            "periodo_desde": (hoy - dt.timedelta(days=DIAS_CUENTA)).isoformat(), "periodo_hasta": hoy.isoformat(),
                            "datos": cuenta, "por": por})
        errores = cuenta.get("errores") or []
        sin_scope = next((e for e in errores if my.es_error_de_scope(e)), None)
        if errores and not _numeros({"datos": cuenta}):
            return {"ok": False, "piezas": 0, "error": sin_scope or errores[0]}
        n, con_numeros, otro = 0, 0, None
        for p in desde_pub:
            if p.get("canal") != "youtube":
                continue
            res = my.insights_video_youtube(cfg, id_plataforma(p), analytics=not sin_scope)
            db.guardar_metrica({"ambito": "pieza", "ref": str(p["id"]), "canal": "youtube", "fuente": "api", "datos": res, "por": por})
            n += 1
            if _numeros({"datos": res}):
                con_numeros += 1
            sin_scope = sin_scope or next((e for e in res.get("errores") or [] if my.es_error_de_scope(e)), None)
            otro = otro or next((e for e in res.get("errores") or [] if not my.es_error_de_scope(e)), None)
        if sin_scope:
            return {"ok": False, "piezas": con_numeros, "error": sin_scope}
        if n and not con_numeros:
            return {"ok": False, "piezas": 0, "error": otro}
        return {"ok": True, "piezas": con_numeros, "error": None}
    except Exception as e:      # nunca un 500 por un error de Google o de la base
        return {"ok": False, "piezas": 0, "error": f"No pude traer los números de YouTube: {type(e).__name__}: {my._limpiar(str(e), secretos)[:160]}"}


def _captura_sitio(cfg, por, ahora, desde_pub):
    """El sitio (WordPress.com, 8/11): cuenta de 28 días + entradas de WordPress publicadas. Devuelve {"ok", "piezas", "error"}; nunca lanza.
    Solo necesita el token guardado (no la app): así también corre en la cola, que no tiene WPCOM_CLIENT_*."""
    import metricas_wordpress as mw
    tok = None
    try:
        tok = mw.token_guardado()
        if not tok:
            app = bool(getattr(cfg, "wpcom_client_id", "") and getattr(cfg, "wpcom_client_secret", ""))
            return {"ok": False, "piezas": 0, "error": mw.TEXTO_SIN_TOKEN if app else mw.TEXTO_SIN_APP}
        t = tok["access_token"]
        site = getattr(cfg, "wp_site", "") or tok.get("blog_id") or ""
        cuenta = mw.insights_sitio(t, site, DIAS_CUENTA)
        hoy = ahora.astimezone(ZONA_AR).date()
        db.guardar_metrica({"ambito": "canal", "ref": "sitio", "canal": "sitio", "fuente": "api",
                            "periodo_desde": (hoy - dt.timedelta(days=DIAS_CUENTA)).isoformat(), "periodo_hasta": hoy.isoformat(),
                            "datos": cuenta, "por": por})
        errores = cuenta.get("errores") or []
        conexion = next((e for e in errores if mw.es_error_de_conexion(e)), None)
        if conexion:
            return {"ok": False, "piezas": 0, "error": conexion}
        if errores and not _numeros({"datos": cuenta}):
            return {"ok": False, "piezas": 0, "error": errores[0]}
        n, con_numeros, otro = 0, 0, None
        for p in desde_pub:
            if p.get("canal") != "wordpress":
                continue
            res = mw.insights_entrada(t, site, id_plataforma(p), DIAS_PIEZAS)
            db.guardar_metrica({"ambito": "pieza", "ref": str(p["id"]), "canal": "wordpress", "fuente": "api", "datos": res, "por": por})
            n += 1
            if _numeros({"datos": res}):
                con_numeros += 1
            otro = otro or next(iter(res.get("errores") or []), None)
        if n and not con_numeros:
            return {"ok": False, "piezas": 0, "error": otro}
        return {"ok": True, "piezas": con_numeros, "error": None}
    except Exception as e:      # nunca un 500 por un error de WordPress.com o de la base
        return {"ok": False, "piezas": 0, "error": f"No pude traer los números del sitio: {type(e).__name__}: {mw._limpiar(str(e), mw._secretos(cfg, (tok or {}).get('access_token')))[:160]}"}


def _piezas_a_capturar(todas, ahora):
    """Las publicadas en modo real de los últimos DIAS_PIEZAS días con id de la plataforma. Sin `todas` (la pasada de la cola)
    se saltean las que ya se capturaron hace menos de 20 h, salvo las historias (vencen a las 24 h: se piden cada hora mientras duren)."""
    desde = _iso(ahora - dt.timedelta(days=DIAS_PIEZAS))
    cand = []
    for p in db.publicaciones_para_metricas(desde):
        modos = ("real", "privado") if p.get("canal") == "youtube" else ("real",)       # YouTube sube en privado hasta la auditoría
        if p.get("estado") != "publicada" or p.get("modo") not in modos or p.get("canal") not in ("instagram", "facebook", "youtube", "wordpress"):
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
    """Pide a Instagram, Facebook, YouTube y WordPress.com los números (cuenta de 28 días + cada pieza real publicada en los últimos 60) y los guarda
    con fuente 'api'. Devuelve {"capturado", "instagram": {ok, piezas, error}, "facebook": {…}, "youtube": {…}, "sitio": {…}}. No lanza por errores
    de las plataformas."""
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
    res["youtube"] = (_captura_youtube(cfg, por, ahora, cand) if getattr(cfg, "yt_token_json", "") else
                      {"ok": False, "piezas": 0, "error": "Falta la conexión con YouTube en el servidor."})
    res["sitio"] = _captura_sitio(cfg, por, ahora, cand)
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


# ---------------- lo que funcionó (para el chat) ----------------
MAX_CARACTERES_MODELO = 1500        # tope del texto que ve el modelo del chat
DIAS_QUE_FUNCIONO = 90
_ALIAS_CANAL = {"newsletter": "mail", "mail": "mail", "wordpress": "sitio", "home": "sitio", "sitio": "sitio"}


def _canal_clave(c):
    c = (c or "").strip().lower()
    return _ALIAS_CANAL.get(c, c)


def _dia_ar(iso):
    d = _fecha(iso)
    if not d:
        return "?"
    a = d.astimezone(ZONA_AR)
    return f"{a.day}/{a.month}"


def _origen(fuente):
    return "desde la plataforma" if fuente == "api" else "anotado a mano"


def _clave_orden(m):
    """Mayor alcance primero; las que no tienen alcance van después, por vistas; después por interacciones."""
    for tier, k in ((2, "alcance"), (1, "vistas"), (0, "interacciones")):
        if isinstance(m.get(k), (int, float)):
            return (tier, m[k])
    return (-1, 0)


def _periodo_de_canal(f, dias_api=DIAS_CUENTA):
    if f.get("fuente") == "manual" and f.get("periodo_desde"):
        if f.get("periodo_hasta"):
            return f"{_dia_ar(f['periodo_desde'])} al {_dia_ar(f['periodo_hasta'])}"
        return f"desde el {_dia_ar(f['periodo_desde'])}"
    return f"últimos {dias_api} días"


def que_funciono(cfg, canal=None, formato=None, campana=None, dias=DIAS_QUE_FUNCIONO, tope=5):
    """(8/11, Beto) Lo que Métricas sabe de cómo rindieron las piezas publicadas, compacto y serializable, para que el chat lo use.
    Reutiliza campanas() y canales_estado(): mismas fuentes, mismas exclusiones de usuarios. «mejores» son solo piezas `publicada`
    con números (de la plataforma o anotados a mano); las de prueba o que no salieron nunca llevan alcance. Nada inventado:
    lo que falta queda en `sin_datos`. Puede levantar RuntimeError si la base falla (el que llama lo traduce)."""
    try:
        dias = max(1, min(int(dias or DIAS_QUE_FUNCIONO), 365))
    except (TypeError, ValueError):
        dias = DIAS_QUE_FUNCIONO
    desde = (_ahora() - dt.timedelta(days=dias)).strftime("%Y-%m-%dT%H:%M:%SZ")
    periodo = {"tipo": "dias", "dias": dias, "desde": desde, "hasta": None, "texto": f"últimos {dias} días"}
    ck = _canal_clave(canal) if canal else None
    data = campanas(periodo)
    buscado = " ".join((campana or "").lower().split())
    camps, todas = [], []
    for c in data["campanas"] + [data["sueltas"]]:
        if buscado and buscado not in " ".join((c.get("nombre") or "").lower().split()):
            continue
        piezas = [p for p in c["piezas"] if (not ck or _canal_clave(p["canal"]) == ck) and (not formato or p.get("formato") == formato)]
        hechas = [p for p in piezas if p["estado_grupo"] in GRUPOS_HECHAS]
        if not hechas:
            continue
        por_canal = {}
        for p in hechas:
            por_canal[p["canal_texto"]] = por_canal.get(p["canal_texto"], 0) + 1
        camps.append({"nombre": c.get("nombre"), "piezas_hechas": len(hechas), "por_canal": por_canal})
        todas += [dict(p, _campana=c.get("nombre")) for p in piezas]
    pub = [p for p in todas if p["estado_grupo"] == "publicada"]
    con = sorted([p for p in pub if p.get("metricas")], key=lambda p: _clave_orden(p["metricas"]), reverse=True)
    mejores = []
    for p in con[:max(int(tope), 0)]:
        m = p["metricas"]
        mejores.append({"titulo": p.get("titulo") or "", "canal": p["canal_texto"], "formato": p.get("formato"), "fecha": p.get("fecha"),
                        "campana": p["_campana"], "metricas": {k: m[k] for k in CLAVES_NORMALIZADAS if k in m},
                        "fuente": _origen(m.get("fuente")), "ver_url": p.get("ver_url")})
    sin = []
    if not pub:
        sin.append("No hay piezas publicadas en el período" + (" con ese filtro" if (ck or formato or campana) else ""))
    else:
        canales_con = {p["canal_texto"] for p in con}
        for nombre in sorted({p["canal_texto"] for p in pub} - canales_con):
            sin.append(f"{nombre}: ninguna pieza publicada tiene números")
        faltan = sum(1 for p in pub if not p.get("metricas") and p["canal_texto"] in canales_con)
        if faltan:
            sin.append(f"{faltan} {'pieza publicada' if faltan == 1 else 'piezas publicadas'} sin números")
    canales = []
    try:
        for c in (canales_estado(cfg)["canales"] if cfg is not None else []):
            if ck and _canal_clave(c["clave"]) != ck:
                continue
            f = c.get("ultima") or c.get("manual")
            if not f:
                sin.append(f"{c['texto']}: sin números de la cuenta")
                continue
            nums = _numeros(f)
            if not nums:
                continue
            canales.append(dict({k: nums[k] for k in ("alcance", "vistas", "interacciones", "seguidores") if k in nums}, canal=c["texto"],
                                fuente=_origen(f.get("fuente")), periodo=_periodo_de_canal(f)))
    except RuntimeError:
        raise
    except Exception:
        sin.append("Los números de las cuentas no se pudieron leer")
    return {"periodo": periodo["texto"], "desde": _dia_ar(desde), "campanas": camps, "mejores": mejores, "canales": canales, "sin_datos": sin}


def _nums_texto(m):
    return ", ".join(f"{k.replace('_', ' ')} {m[k]}" for k in CLAVES_NORMALIZADAS if k in m)


def texto_para_el_modelo(d, tope=MAX_CARACTERES_MODELO):
    """El resultado de la herramienta que_funciono, en texto compacto (≤ `tope` caracteres): cada número con su fuente y su período.
    Si no entra todo, se recorta de lo menos importante (canales, campañas, piezas del final) y se avisa."""
    cab = f"MÉTRICAS REALES (período: {d['periodo']}, desde el {d['desde']}). Usá solo estos números, con su fuente; no inventes otros."
    bloques = [("Mejores piezas publicadas:", [
                   f"- {_dia_ar(m['fecha'])} · {m['canal']}" + (f" · {m['formato']}" if m.get("formato") else "")
                   + f" · «{(m['titulo'] or 'sin título')[:60]}» (campaña {m['campana']}): {_nums_texto(m['metricas'])} [{m['fuente']}]"
                   for m in d["mejores"]]),
               ("Campañas:", [f"- {c['nombre']}: {c['piezas_hechas']} piezas ({', '.join(f'{k} {v}' for k, v in c['por_canal'].items())})"
                              for c in d["campanas"][:6]]),
               ("Cuentas:", [f"- {c['canal']}: {_nums_texto(c)} [{c['fuente']}, {c['periodo']}]" for c in d["canales"]]),
               ("Falta:", [f"- {s}" for s in d["sin_datos"]])]
    if not d["mejores"] and not d["canales"]:
        bloques = bloques[-1:]
        cab += "\nNo hay números para apoyarse: decilo y recomendá solo con la guía de canales."
    salida, pie = [cab], "(recortado)"
    for titulo, lineas in bloques:
        if not lineas:
            continue
        salida.append(titulo)
        for ln in lineas:
            if len("\n".join(salida + [ln, pie])) > tope:
                salida.append(pie)
                return "\n".join(salida)[:tope]
            salida.append(ln)
    return "\n".join(salida)[:tope]
