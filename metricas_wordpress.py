"""
metricas_wordpress.py — Las estadísticas del sitio (viviragradecidos.org), traídas de WordPress.com (8/11, Franco: «sumar el sitio web a
Métricas con una autorización de dos clics desde la pantalla»). Contrato: web/maquetas/metricas-contrato.md. Misma forma que
metricas_youtube.py.

SOLO HTTP contra WordPress.com (más guardar/leer el token en `config`, como meta_token.py). Cada función de lectura devuelve el dict
NORMALIZADO del contrato:

    {"visitas", "visitantes", "me_gusta", "comentarios"   (enteros; la clave está SOLO si WordPress.com dio el número: nunca un 0 inventado),
     "crudo": {lo que devolvió, chico: top_posts, referentes, clics, período},
     "errores": [textos en castellano: qué no se pudo traer y por qué]}

  url_autorizacion(cfg, redirect_uri, state)    la dirección de WordPress.com a la que se manda a la persona (primer clic)
  canjear_codigo(cfg, code, redirect_uri)       (token, None) o (None, «texto de error») — el código que vuelve en el callback
  insights_sitio(token, site, dias=28)          el sitio: visitas, visitantes, me gusta y comentarios del período + top de entradas, referentes y clics
  insights_entrada(token, site, post_id, dias)  una entrada: visitas
  es_error_de_conexion(texto)                   ¿el texto de `errores` es el de «falta (volver a) conectar con WordPress.com»?
  token_guardado() / guardar_token(...) / borrar_token()    config.wpcom_token = {access_token, blog_id, blog_url, autorizado_en, por}

Qué hace falta (lo registra Franco a mano, una sola vez): una app en https://developer.wordpress.com/apps/ (tipo Web, redirect URL =
<API>/admin/metricas/wordpress/callback), que da Client ID y Client Secret → variables WPCOM_CLIENT_ID y WPCOM_CLIENT_SECRET en Render.
Después, el botón «Conectar con WordPress.com» de Métricas hace el flujo «authorization code».

Endpoints usados (WordPress.com REST API v1.1; todos GET con `Authorization: Bearer <token>`):
  · Autorizar   GET  https://public-api.wordpress.com/oauth2/authorize?client_id&redirect_uri&response_type=code&blog&scope=global&state
  · Canjear     POST https://public-api.wordpress.com/oauth2/token  (client_id, client_secret, redirect_uri, code, grant_type=authorization_code)
                     Doc: https://developer.wordpress.com/docs/oauth2/
  · Resumen     GET  /rest/v1.1/sites/{site}/stats/summary?period=day&num=28      → views, visitors, likes, comments (suma del período)
                     Doc: https://developer.wordpress.com/docs/api/1.1/get/sites/%24site/stats/summary/
  · Top         GET  /rest/v1.1/sites/{site}/stats/top-posts?period=day&num=28&summarize=1&max=5   → entradas más vistas
                     Doc: https://developer.wordpress.com/docs/api/1.1/get/sites/%24site/stats/top-posts/
  · Referentes  GET  /rest/v1.1/sites/{site}/stats/referrers?period=day&num=28&summarize=1&max=5  → de dónde llegan
                     Doc: https://developer.wordpress.com/docs/api/1.1/get/sites/%24site/stats/referrers/
  · Clics       GET  /rest/v1.1/sites/{site}/stats/clicks?period=day&num=28&summarize=1&max=5     → enlaces salientes que más se tocan
                     Doc: https://developer.wordpress.com/docs/api/1.1/get/sites/%24site/stats/clicks/
  · Entrada     GET  /rest/v1.1/sites/{site}/stats/post/{post_id}?fields=views     → vistas de TODA la vida de la entrada
                     Doc: https://developer.wordpress.com/docs/api/1.1/get/sites/%24site/stats/post/%24post_id/
  (`site` es el dominio, viviragradecidos.org, o el blog_id que devolvió el canje.)

El token NUNCA va en `crudo` ni en `errores` (se le saca a cualquier texto que venga de WordPress.com, igual que el client_secret).

SIN CONFIRMAR (acá no hay app registrada ni token; la forma de las respuestas sale de la documentación):
  · Que el token del flujo «authorization code» no expire hasta que se revoque: la doc de OAuth2 lo da a entender (solo el flujo
    «implicit» dura 2 semanas), pero no se probó. Si venciera, el sitio pasa a «Falta conectar con WordPress.com» y se reconecta con un clic.
  · Que `scope=global` sea necesario: sin `scope` el token queda atado al sitio elegido en `blog`, que alcanzaría para las estadísticas.
    Se pide `global` porque así lo pidió Franco; si WordPress.com rechazara ese valor, se saca de URL_AUTORIZAR.
  · La forma exacta de `summary` (con `num` devuelve la suma del período), de `top-posts` (con `summarize` viene en `summary.postviews`,
    sin él en `days.<fecha>.postviews`), de `referrers`/`clicks` (`summary.groups[]` con `name` y `total`). Las funciones leen las dos
    formas y, si no entienden la respuesta, dejan el campo fuera del crudo en vez de inventarlo.
  · Que `stats/post/{id}` acepte `fields=views` y entregue el total histórico (no el del período): por eso `insights_entrada` anota en el
    crudo «vistas desde que se publicó».
"""
import datetime as dt, json, urllib.parse

from publicar import _http

URL_AUTORIZAR = "https://public-api.wordpress.com/oauth2/authorize"
URL_TOKEN = "https://public-api.wordpress.com/oauth2/token"
URL_API = "https://public-api.wordpress.com/rest/v1.1"
CLAVE_TOKEN = "wpcom_token"
MAX_ITEMS = 5

TEXTO_SIN_APP = "Falta registrar la app de WordPress.com en el servidor (WPCOM_CLIENT_ID y WPCOM_CLIENT_SECRET)."
TEXTO_SIN_TOKEN = "Falta conectar con WordPress.com (un clic)"
TEXTO_TOKEN_INVALIDO = "WordPress.com ya no acepta la conexión: hay que volver a conectar (un clic)"
TEXTO_SIN_SITIO = "Falta el sitio de WordPress (WP_SITE) en el servidor."


# ---------------- helpers ----------------
def _limpiar(texto, secretos):
    t = str(texto)
    for s in secretos:
        if s:
            t = t.replace(s, "***")
    return t


def _secretos(cfg=None, *extra):
    s = set(x for x in extra if x)
    if cfg is not None and getattr(cfg, "wpcom_client_secret", ""):
        s.add(cfg.wpcom_client_secret)
    return s


def es_error_de_conexion(texto):
    t = str(texto)
    return t.startswith(TEXTO_SIN_TOKEN) or t.startswith("WordPress.com ya no acepta la conexión")


def _mensaje(err):
    """(código o motivo, mensaje) del error de WordPress.com (dict de la API o el que arma publicar._http)."""
    e = err if isinstance(err, dict) else {"message": str(err)}
    motivo = str(e.get("error") or e.get("code") or "")
    return motivo, " ".join(str(e.get("message") or e.get("error_description") or e.get("error") or "error desconocido").split())


def _es_token_invalido(err):
    motivo, msg = _mensaje(err)
    m = (motivo + " " + msg).lower()
    return any(x in m for x in ("invalid_token", "unauthorized", "authorization_required", "token is invalid", "token has expired", "revoked", "not_authorized"))


def _texto_error(err, secretos):
    motivo, msg = _mensaje(err)
    return _limpiar(f"({motivo}) {msg}" if motivo and motivo.lower() not in msg.lower() else msg, secretos)[:240]


def _get(token, ruta, params=None):
    url = f"{URL_API}{ruta}" + (f"?{urllib.parse.urlencode(params)}" if params else "")
    return _http(url, "GET", {"Authorization": f"Bearer {token}", "Accept": "application/json", "User-Agent": "fva-herramienta/0.1"})


def _entero(v):
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return int(v)
    try:
        return int(str(v).strip())
    except ValueError:
        return None


def _salida(normal, crudo, errores):
    out = {k: v for k, v in normal.items() if v is not None}
    out["crudo"] = crudo
    out["errores"] = errores
    return out


def _site(site):
    return urllib.parse.quote(str(site or "").replace("https://", "").replace("http://", "").strip("/"), safe="")


# ---------------- autorización (flujo «authorization code») ----------------
def url_autorizacion(cfg, redirect_uri, state):
    """A dónde se manda a la persona para que autorice. `state` lo firma quien llama (api/metricas_rutas.py)."""
    p = {"client_id": cfg.wpcom_client_id, "redirect_uri": redirect_uri, "response_type": "code", "scope": "global", "state": state}
    if getattr(cfg, "wp_site", ""):
        p["blog"] = cfg.wp_site
    return f"{URL_AUTORIZAR}?{urllib.parse.urlencode(p)}"


def canjear_codigo(cfg, code, redirect_uri):
    """Cambia el código que vuelve en el callback por el token. (dict, None) con {access_token, blog_id, blog_url, scope} o (None, texto)."""
    if not (getattr(cfg, "wpcom_client_id", "") and getattr(cfg, "wpcom_client_secret", "")):
        return None, TEXTO_SIN_APP
    if not code:
        return None, "WordPress.com no mandó el código de autorización."
    secretos = _secretos(cfg, code)
    datos = urllib.parse.urlencode({"client_id": cfg.wpcom_client_id, "client_secret": cfg.wpcom_client_secret, "redirect_uri": redirect_uri,
                                    "code": code, "grant_type": "authorization_code"}).encode()
    r, err = _http(URL_TOKEN, "POST", {"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json",
                                       "User-Agent": "fva-herramienta/0.1"}, datos)
    if r is None:
        return None, f"WordPress.com no aceptó la autorización: {_texto_error(err, secretos)}"
    tok = str(r.get("access_token") or "").strip()
    if not tok:
        return None, "WordPress.com respondió sin el permiso de acceso."
    return {"access_token": tok, "blog_id": str(r.get("blog_id") or "") or None, "blog_url": r.get("blog_url") or None,
            "scope": r.get("scope") or None}, None


# ---------------- token guardado ----------------
def token_guardado():
    """El registro de config.wpcom_token, o None si no hay / Supabase no está / falla la lectura. Nunca se imprime."""
    try:
        import db
        if not db.disponible():
            return None
        v = db.obtener_config(CLAVE_TOKEN)
        if isinstance(v, dict) and str(v.get("access_token") or "").strip():
            return v
    except Exception as e:
        print(f"metricas_wordpress: no pude leer config.{CLAVE_TOKEN}: {type(e).__name__}")
    return None


def guardar_token(token, por=None):
    """Guarda {access_token, blog_id, blog_url, autorizado_en, por} en config.wpcom_token. `token` es el dict de canjear_codigo."""
    import db
    reg = {"access_token": token["access_token"], "blog_id": token.get("blog_id"), "blog_url": token.get("blog_url"),
           "autorizado_en": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "por": por}
    db.guardar_config(CLAVE_TOKEN, reg, por)
    return {k: v for k, v in reg.items() if k != "access_token"}


def borrar_token(por=None):
    """Desconecta: deja la clave vacía (la columna no admite null; token_guardado() ya no la toma por válida)."""
    import db
    db.guardar_config(CLAVE_TOKEN, "", por)


# ---------------- lectura ----------------
def _suma(v):
    return _entero(v)


def _items(lista, claves_nombre):
    out = []
    for x in (lista or [])[:MAX_ITEMS]:
        if not isinstance(x, dict):
            continue
        nombre = next((str(x[k]) for k in claves_nombre if x.get(k)), None)
        n = _entero(x.get("views") if x.get("views") is not None else x.get("total"))
        if nombre and n is not None:
            out.append({"nombre": nombre[:120], "vistas": n})
    return out


def _top_posts(r):
    if not isinstance(r, dict):
        return None
    lista = (r.get("summary") or {}).get("postviews")
    if lista is None and isinstance(r.get("days"), dict):          # sin summarize: una lista por día → se suman por entrada
        acum = {}
        for d in r["days"].values():
            for x in (d or {}).get("postviews") or []:
                if isinstance(x, dict) and x.get("title"):
                    a = acum.setdefault(x.get("id") or x["title"], {"title": x["title"], "views": 0})
                    a["views"] += _entero(x.get("views")) or 0
        lista = sorted(acum.values(), key=lambda a: -a["views"])
    items = _items(lista, ("title",))
    return [{"titulo": i["nombre"], "vistas": i["vistas"]} for i in items] if lista is not None else None


def _grupos(r):
    """referrers y clicks: summary.groups[] con name/group y total (o results)."""
    if not isinstance(r, dict):
        return None
    grupos = (r.get("summary") or {}).get("groups")
    if grupos is None:
        return None
    items = _items(grupos, ("name", "group"))
    return [{"nombre": i["nombre"], "vistas": i["vistas"]} for i in items]


def _falla(err, secretos, errores, que):
    if _es_token_invalido(err):
        if TEXTO_TOKEN_INVALIDO not in errores:
            errores.append(TEXTO_TOKEN_INVALIDO)
    else:
        errores.append(f"WordPress.com no dio {que}: {_texto_error(err, secretos)}")


def insights_sitio(token, site, dias=28):
    """El sitio en los últimos `dias` días: visitas (views), visitantes, me gusta y comentarios (stats/summary) + top de entradas,
    referentes y clics (crudo). Si falla lo secundario, igual devuelve lo de summary y anota el motivo en `errores`."""
    if not token:
        return _salida({}, {}, [TEXTO_SIN_TOKEN])
    if not site:
        return _salida({}, {}, [TEXTO_SIN_SITIO])
    secretos = _secretos(None, token)
    errores, crudo, normal = [], {"periodo_dias": dias}, {}
    base = f"/sites/{_site(site)}/stats"
    p = {"period": "day", "num": dias}
    r, err = _get(token, f"{base}/summary", p)
    if r is None:
        _falla(err, secretos, errores, "las estadísticas del sitio")
        return _salida({}, crudo, errores)
    for clave, campo in (("visitas", "views"), ("visitantes", "visitors"), ("me_gusta", "likes"), ("comentarios", "comments")):
        normal[clave] = _suma(r.get(campo))
    if r.get("date"):
        crudo["fecha"] = str(r["date"])[:10]
    if not any(v is not None for v in normal.values()):
        errores.append("WordPress.com devolvió las estadísticas sin los números esperados.")
    extra = {"top_posts": ("top-posts", dict(p, summarize=1, max=MAX_ITEMS), _top_posts, "las entradas más vistas"),
             "referentes": ("referrers", dict(p, summarize=1, max=MAX_ITEMS), _grupos, "de dónde llegan las visitas"),
             "clics": ("clicks", dict(p, summarize=1, max=MAX_ITEMS), _grupos, "los enlaces más tocados")}
    for clave, (ruta, params, leer, que) in extra.items():
        rr, ee = _get(token, f"{base}/{ruta}", params)
        if rr is None:
            _falla(ee, secretos, errores, que)
            continue
        lista = leer(rr)
        if lista is not None:
            crudo[clave] = lista
    return _salida(normal, crudo, errores)


def insights_entrada(token, site, post_id, dias=28):
    """Una entrada de WordPress: sus vistas. OJO: stats/post/{id} da el total desde que se publicó (no el de `dias`), y el crudo lo dice."""
    if not token:
        return _salida({}, {}, [TEXTO_SIN_TOKEN])
    if not post_id:
        return _salida({}, {}, ["La pieza no tiene el id de la entrada de WordPress."])
    if not site:
        return _salida({}, {}, [TEXTO_SIN_SITIO])
    secretos = _secretos(None, token)
    errores, crudo = [], {"post_id": str(post_id), "vistas_desde": "que se publicó"}
    r, err = _get(token, f"/sites/{_site(site)}/stats/post/{urllib.parse.quote(str(post_id), safe='')}", {"fields": "views"})
    if r is None:
        _falla(err, secretos, errores, "las vistas de la entrada")
        return _salida({}, crudo, errores)
    visitas = _entero(r.get("views"))
    if visitas is None:
        errores.append("WordPress.com no dio las vistas de la entrada.")
    return _salida({"visitas": visitas}, crudo, errores)
