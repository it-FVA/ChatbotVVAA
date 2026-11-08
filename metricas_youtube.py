"""
metricas_youtube.py — Los números de YouTube, traídos de Google (8/11, Franco: «avanzar con YouTube ya»). Contrato:
web/maquetas/metricas-contrato.md. Misma forma que metricas_meta.py.

SOLO HTTP contra Google: no toca la base de datos (eso lo hace metricas.py). Cada función devuelve el dict NORMALIZADO del contrato:

    {"vistas", "me_gusta", "comentarios", "compartidos", "seguidores", "seguidores_nuevos"   (enteros; la clave está SOLO si Google
     dio el número: nunca un 0 inventado),
     "crudo": {lo que devolvió Google, chico, sin series},
     "errores": [textos en castellano: qué no se pudo traer y por qué]}

  insights_canal_youtube(cfg, dias=28)          el canal: suscriptores y vistas (Data API) + el período (Analytics, si hay permiso)
  insights_video_youtube(cfg, video_id)         un video: vistas, me gusta, comentarios (Data API) + compartidos y retención (Analytics)
  es_error_de_scope(texto)                      ¿el texto de `errores` es el de «falta autorizar la lectura de estadísticas»?

Dos APIs de Google, dos permisos (scopes):
  · YouTube Data API v3 (`youtube.readonly`, que el token ya tiene): channels.list y videos.list. CUOTA: 10.000 unidades por día para
    todo el proyecto; una lectura de channels o de videos cuesta 1 unidad (una subida de video cuesta 1.600). Una captura con 20 videos
    gasta ~21: sobra.
  · YouTube Analytics API v2 (`yt-analytics.readonly`, que el token NO tenía hasta el 8/11: hay que volver a correr
    autorizar_youtube.py y pegar el JSON nuevo en Render y GitHub). Tiene cuota propia, aparte de la Data API. Sus números llegan
    con 48-72 horas de demora: el último día o dos siempre vienen incompletos. Sin ese permiso, `errores` dice qué hacer y la
    función igual devuelve lo que dio la Data API.

REGLA DE GOOGLE (retención): los datos de Analytics no se pueden guardar más de 30 días sin que la persona reconfirme la autorización.
Por eso la captura guarda SOLO totales normalizados y un `crudo` chico (nunca series día por día) y cada captura trae el período
que cubre (`crudo.periodo`).

El access token va en el encabezado Authorization y NUNCA en `crudo` ni en `errores` (se le saca a cualquier texto que venga de Google,
igual que el refresh_token y el client_secret).

OJO — SIN CONFIRMAR EN VIVO (acá no hay token de YouTube): la forma de las respuestas sale de la documentación de Google. Lo que más
conviene mirar en la primera captura real: que `reports` acepte `endDate` = ayer (UTC) y los nombres de las columnas.
"""
import datetime as dt, json, re, time, urllib.parse

import publicar
from publicar import _http

URL_DATA = "https://www.googleapis.com/youtube/v3"
URL_ANALYTICS = "https://youtubeanalytics.googleapis.com/v2/reports"

METRICAS_CANAL = "views,estimatedMinutesWatched,averageViewDuration,subscribersGained,subscribersLost,likes,comments,shares"
METRICAS_VIDEO = "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,likes,shares,subscribersGained"

TEXTO_SIN_TOKEN = "No hay conexión con YouTube configurada."
TEXTO_SIN_SCOPE = ("Falta autorizar la lectura de estadísticas de YouTube (correr autorizar_youtube.py de nuevo y pegar el JSON nuevo "
                   "en Render)")
TEXTO_VIDEO_NO_EXISTE = "Ese video ya no existe en YouTube o no es de este canal."

# nombre de la columna de Analytics → clave normalizada. El resto (minutos, duración) va al crudo.
MAPA_CANAL = {"views": "vistas", "likes": "me_gusta", "comments": "comentarios", "shares": "compartidos", "subscribersGained": "seguidores_nuevos"}
MAPA_VIDEO = {"shares": "compartidos"}

_ACCESOS = {}       # refresh_token_json → (access_token, vence): un access token dura 1 h; una captura pide uno por video sin esto


# ---------------- helpers ----------------
def _secretos(cfg, *extra):
    s = set(x for x in extra if x)
    try:
        t = json.loads(getattr(cfg, "yt_token_json", "") or "{}")
        s.update(str(t[k]) for k in ("refresh_token", "client_secret", "token") if t.get(k))
    except Exception:
        pass
    return s


def _limpiar(texto, secretos):
    t = str(texto)
    for s in secretos:
        if s:
            t = t.replace(s, "***")
    return t


def _olvidar_token():
    _ACCESOS.clear()


def _acceso(cfg):
    """(access_token, None) o (None, texto de error en castellano). Cacheado 50 minutos."""
    clave = getattr(cfg, "yt_token_json", "") or ""
    if not clave:
        return None, TEXTO_SIN_TOKEN
    hit = _ACCESOS.get(clave)
    if hit and hit[1] > time.time():
        return hit[0], None
    tok, err = publicar._yt_access_token(cfg)
    if not tok:
        motivo = ""
        if isinstance(err, dict):
            motivo = str(err.get("error_description") or err.get("error") or err.get("message") or "")
            if isinstance(err.get("error"), dict):
                motivo = str(err["error"].get("message") or "")
        return None, "No pude renovar la conexión con YouTube" + (f": {_limpiar(' '.join(motivo.split()), _secretos(cfg))[:160]}" if motivo else ".")
    _ACCESOS[clave] = (tok, time.time() + 50 * 60)
    return tok, None


def _error_google(err):
    """(código, motivo, mensaje) de un error de Google (dict de la API o el que arma publicar._http)."""
    e = (err or {}).get("error") if isinstance(err, dict) and isinstance(err.get("error"), dict) else (err or {})
    if not isinstance(e, dict):
        e = {"message": str(e)}
    motivos = [str(x.get("reason") or "") for x in (e.get("errors") or []) if isinstance(x, dict)]
    return e.get("code"), (motivos[0] if motivos else str(e.get("status") or "")), " ".join(str(e.get("message") or "error desconocido").split())


def _es_scope(err):
    cod, motivo, msg = _error_google(err)
    m = msg.lower()
    return ("insufficient authentication scopes" in m or "insufficient permission" in m or "access_token_scope_insufficient" in motivo.lower()
            or "insufficientpermissions" in motivo.lower() or ("scope" in m and cod in (401, 403)))


def es_error_de_scope(texto):
    return str(texto).startswith("Falta autorizar la lectura de estadísticas")


def _texto_error(err, secretos):
    cod, motivo, msg = _error_google(err)
    if "quota" in motivo.lower() or "quota" in msg.lower():
        return "Google agotó la cuota diaria de lecturas de YouTube: se reinicia solo al día siguiente."
    return _limpiar(f"({cod}) {msg}" if cod is not None else msg, secretos)[:240]


def _get(url, params, tok):
    return _http(f"{url}?{urllib.parse.urlencode(params)}", "GET", {"Authorization": f"Bearer {tok}", "Accept": "application/json"})


def _entero(v):
    """Google entrega los contadores como texto («"1234"»). None si no es un número."""
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


def _duracion_seg(iso8601):
    """«PT1H2M30S» → 3750. None si no se entiende."""
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", str(iso8601 or ""))
    if not m or not any(m.groups()):
        return None
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def _ayer():
    """Analytics acepta hasta el día de hoy en hora del Pacífico; ayer (UTC) nunca es futuro en ningún huso."""
    return dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)


def _reporte(tok, metricas, desde, hasta, filtro, secretos, errores):
    """Una fila de Analytics como {columna: número} o None. Anota en `errores` el motivo (scope, cuota u otro)."""
    params = {"ids": "channel==MINE", "startDate": desde.isoformat(), "endDate": hasta.isoformat(), "metrics": metricas}
    if filtro:
        params["filters"] = filtro
    r, err = _get(URL_ANALYTICS, params, tok)
    if r is None:
        if _es_scope(err):
            if TEXTO_SIN_SCOPE not in errores:
                errores.append(TEXTO_SIN_SCOPE)
        else:
            errores.append(f"YouTube Analytics no dio los números del período: {_texto_error(err, secretos)}")
        return None
    cols = [c.get("name") for c in (r.get("columnHeaders") or []) if isinstance(c, dict)]
    filas = r.get("rows") or []
    if not cols or not filas or not isinstance(filas[0], list):
        return {}           # sin datos todavía (Analytics demora 48-72 h): no es un error ni un 0
    return dict(zip(cols, filas[0]))


# ---------------- canal ----------------
def insights_canal_youtube(cfg, dias=28):
    """El canal: suscriptores + vistas (Data API) y, si el token tiene el permiso de Analytics, lo de los últimos `dias` días."""
    errores, crudo, normal = [], {}, {}
    tok, e = _acceso(cfg)
    if not tok:
        return _salida({}, {}, [e])
    secretos = _secretos(cfg, tok)
    r, err = _get(f"{URL_DATA}/channels", {"part": "statistics,snippet", "mine": "true"}, tok)
    if r is None:
        errores.append(TEXTO_SIN_SCOPE if _es_scope(err) else f"YouTube no dio los datos del canal: {_texto_error(err, secretos)}")
        return _salida({}, {}, errores)
    items = r.get("items") or []
    if not items:
        errores.append("YouTube no devolvió ningún canal para esta conexión: puede que se autorizó con otra cuenta.")
        return _salida({}, {}, errores)
    est = items[0].get("statistics") or {}
    crudo["canal"] = {"titulo": (items[0].get("snippet") or {}).get("title"), "videos_total": _entero(est.get("videoCount"))}
    crudo["videos_total"] = _entero(est.get("videoCount"))
    if not est.get("hiddenSubscriberCount"):
        normal["seguidores"] = _entero(est.get("subscriberCount"))
    normal["vistas"] = _entero(est.get("viewCount"))
    crudo["vistas_es_historico"] = True          # viewCount es el total desde siempre, no el del período; Analytics lo pisa si responde

    fin = _ayer()
    ini = fin - dt.timedelta(days=int(dias) - 1)
    fila = _reporte(tok, METRICAS_CANAL, ini, fin, None, secretos, errores)
    if fila is not None:
        crudo["periodo"] = {"desde": ini.isoformat(), "hasta": fin.isoformat()}
        for col, clave in MAPA_CANAL.items():
            if _entero(fila.get(col)) is not None:
                normal[clave] = _entero(fila[col])
        if "views" in fila and _entero(fila["views"]) is not None:
            crudo["vistas_es_historico"] = False
            crudo["vistas_total_historico"] = _entero(est.get("viewCount"))
        for col, clave in (("estimatedMinutesWatched", "minutos_vistos"), ("averageViewDuration", "duracion_promedio_seg"),
                           ("subscribersLost", "seguidores_perdidos")):
            if _entero(fila.get(col)) is not None:
                crudo[clave] = _entero(fila[col])
        if not fila:
            crudo["analytics"] = "sin filas: Google todavía no tiene los números del período (demora 48-72 horas)"
    return _salida(normal, crudo, errores)


# ---------------- video ----------------
def insights_video_youtube(cfg, video_id, analytics=True):
    """Un video del canal. `analytics=False` saltea la segunda llamada (cuando ya se sabe que falta el permiso)."""
    errores, crudo, normal = [], {}, {}
    if not str(video_id or "").strip():
        return _salida({}, {}, ["La pieza no tiene el id de YouTube."])
    tok, e = _acceso(cfg)
    if not tok:
        return _salida({}, {}, [e])
    secretos = _secretos(cfg, tok)
    vid = str(video_id).strip()
    r, err = _get(f"{URL_DATA}/videos", {"part": "statistics,snippet,contentDetails,status", "id": vid}, tok)
    if r is None:
        errores.append(TEXTO_SIN_SCOPE if _es_scope(err) else f"YouTube no dio los datos del video: {_texto_error(err, secretos)}")
        return _salida({}, {}, errores)
    items = r.get("items") or []
    if not items:
        return _salida({}, {}, [TEXTO_VIDEO_NO_EXISTE])
    v = items[0]
    est, sn = v.get("statistics") or {}, v.get("snippet") or {}
    publicado = sn.get("publishedAt")
    crudo["video"] = {"titulo": sn.get("title"), "duracion": (v.get("contentDetails") or {}).get("duration"),
                      "duracion_seg": _duracion_seg((v.get("contentDetails") or {}).get("duration")),
                      "publicado": publicado, "privacidad": (v.get("status") or {}).get("privacyStatus")}
    normal["vistas"] = _entero(est.get("viewCount"))
    normal["me_gusta"] = _entero(est.get("likeCount"))          # puede faltar si el canal oculta los «me gusta»
    normal["comentarios"] = _entero(est.get("commentCount"))    # puede faltar si los comentarios están desactivados
    if not analytics:
        return _salida(normal, crudo, errores)
    try:
        ini = dt.datetime.fromisoformat(str(publicado).replace("Z", "+00:00")).date()
    except ValueError:
        ini = None
    fin = _ayer()
    if ini is None or ini > fin:
        return _salida(normal, crudo, errores)       # publicado hoy: Analytics todavía no tiene nada
    fila = _reporte(tok, METRICAS_VIDEO, ini, fin, f"video=={vid}", secretos, errores)
    if fila:
        crudo["periodo"] = {"desde": ini.isoformat(), "hasta": fin.isoformat()}
        for col, clave in MAPA_VIDEO.items():
            if _entero(fila.get(col)) is not None:
                normal[clave] = _entero(fila[col])
        for col, clave in (("estimatedMinutesWatched", "minutos_vistos"), ("averageViewDuration", "duracion_promedio_seg"),
                           ("averageViewPercentage", "porcentaje_visto")):
            if isinstance(fila.get(col), (int, float)) and not isinstance(fila.get(col), bool):
                crudo[clave] = round(fila[col], 1) if col == "averageViewPercentage" else int(fila[col])
    return _salida(normal, crudo, errores)
