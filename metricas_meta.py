"""
metricas_meta.py — Los números de Instagram y Facebook, traídos de Meta (8/11, Franco; pedido de Beto: «que la app sea el centro
de métricas de evolución de campañas»). Contrato: web/maquetas/metricas-contrato.md.

SOLO HTTP contra Meta: no toca la base de datos (eso lo hace metricas.py). Cada función devuelve el dict NORMALIZADO del contrato:

    {"alcance", "vistas", "me_gusta", "comentarios", "guardados", "compartidos", "clics", "interacciones", "seguidores",
     "seguidores_nuevos", "respuestas"   (enteros; la clave está SOLO si la plataforma dio el número: nunca un 0 inventado),
     "crudo": {lo que devolvió Meta, tal cual},
     "errores": [textos en castellano: qué no se pudo traer y por qué]}

  insights_cuenta_instagram(cfg, dias=28)            la cuenta de Instagram (seguidores + alcance, vistas… de los últimos `dias`)
  insights_pieza_instagram(cfg, media_id, historia)  un posteo, carrusel, reel o historia
  insights_pagina_facebook(cfg, dias=28)             la página de Facebook (seguidores + suma de los valores diarios)
  insights_posteo_facebook(cfg, post_id)             un posteo de la página
  es_error_de_permiso(texto)                         ¿el texto de `errores` es el de «falta un permiso»? (lo usa metricas.canales_estado)

Instagram usa IG_HOST (graph.instagram.com) porque el token es de «Instagram Login»; Facebook usa FB_HOST (graph.facebook.com) con el
token de la página. El token NUNCA va en `crudo` ni en `errores` (se le saca a cualquier texto que venga de Meta).

OJO — SIN CONFIRMAR EN VIVO: Meta cambia los nombres de las métricas cada pocos meses (ya retiró `impressions` y `plays` de
Instagram, y varias `page_*` de Facebook). Las listas están en constantes arriba de todo (METRICAS_*) para tocar un solo lugar.
Si Meta rechaza una métrica, no se cae todo: se reintenta de a una y lo que no se pudo queda anotado en `errores`.
Permisos: Instagram necesita `instagram_manage_insights` y Facebook `read_insights`; si faltan, `errores` lo dice en castellano.
"""
import time, urllib.parse

import publicar
from publicar import IG_HOST, FB_HOST, _http

# --- Listas de métricas por pedido (Meta las cambia: tocar acá) ---
METRICAS_IG_CUENTA = ["reach", "views", "accounts_engaged", "total_interactions", "follows_and_unfollows"]
METRICAS_IG_PIEZA = ["reach", "views", "saved", "shares", "total_interactions"]
METRICAS_IG_HISTORIA = ["reach", "views", "replies", "shares", "navigation"]
METRICAS_IG_REEL = ["reach", "views", "saved", "shares", "total_interactions", "ig_reels_avg_watch_time"]
# (8/11, visto en vivo) Meta retiró `page_impressions` (11/2025) y las `*_impressions_unique` (6/2026): v25 las reemplaza por
# page_media_view (vistas) y page_total_media_view_unique (alcance). Lo mismo a nivel posteo (post_media_view, post_total_media_view_unique).
METRICAS_FB_PAGINA = ["page_media_view", "page_total_media_view_unique", "page_post_engagements", "page_views_total", "page_daily_follows"]
METRICAS_FB_POSTEO = ["post_media_view", "post_total_media_view_unique", "post_clicks", "post_reactions_by_type_total"]

# métrica de Meta → clave normalizada. Las que no están acá (accounts_engaged, navigation, ig_reels_avg_watch_time…) van solo al crudo.
MAPA_IG = {"reach": "alcance", "views": "vistas", "saved": "guardados", "shares": "compartidos",
           "total_interactions": "interacciones", "replies": "respuestas"}
MAPA_FB_PAGINA = {"page_media_view": "vistas", "page_total_media_view_unique": "alcance", "page_post_engagements": "interacciones", "page_daily_follows": "seguidores_nuevos"}
MAPA_FB_POSTEO = {"post_media_view": "vistas", "post_total_media_view_unique": "alcance", "post_clicks": "clics"}

TEXTO_SIN_PERMISO_IG = "Falta el permiso instagram_manage_insights en la conexión con Instagram"
TEXTO_SIN_PERMISO_FB = "Falta el permiso read_insights en la conexión con Facebook"
CODIGOS_PERMISO = (10, 200, 190)


# ---------------- helpers ----------------
_TOKENS_VISTOS = set()      # los tokens que pasaron por _llamar en este proceso: se les saca a cualquier texto de error


def _registrar_tokens(cfg):
    _TOKENS_VISTOS.update(t for t in (getattr(cfg, "ig_token", ""), getattr(cfg, "fb_token", "")) if t)


def _limpiar(texto, *secretos):
    """El texto sin ningún token (aunque Meta lo repitiera en un mensaje)."""
    t = str(texto)
    for s in set(secretos) | _TOKENS_VISTOS:
        if s:
            t = t.replace(s, "***")
    return t


def _texto_error(err, token):
    """Un error de Meta (dict) → '(#100) mensaje' sin token y en una línea."""
    e = (err or {}).get("error") if isinstance(err, dict) and isinstance(err.get("error"), dict) else (err or {})
    if not isinstance(e, dict):
        e = {"message": str(e)}
    cod = e.get("code")
    msg = _limpiar(" ".join(str(e.get("message") or "error desconocido").split()), token)[:240]
    return f"(#{cod}) {msg}" if cod is not None else msg


def _es_permiso(err):
    e = (err or {}).get("error") if isinstance(err, dict) and isinstance(err.get("error"), dict) else (err or {})
    if not isinstance(e, dict):
        return False
    msg = str(e.get("message") or "").lower()
    if "not enough viewers" in msg:           # historias con pocas vistas: el código es el mismo (10) pero no es un permiso
        return False
    if e.get("code") == 100:                  # (8/11, visto en vivo) «Unsupported get request… does not exist»: la pieza ya no está
        return False                          # en Instagram (borrada o de otra cuenta); el mensaje nombra «permissions» pero no es eso
    return e.get("code") in CODIGOS_PERMISO or "permission" in msg


def es_error_de_permiso(texto):
    return str(texto).startswith("Falta el permiso")


def _llamar(host, ruta, params, token):
    """GET con el token en la query (como el resto de publicar.py). Devuelve (json, error_de_meta)."""
    _TOKENS_VISTOS.add(token)
    q = urllib.parse.urlencode(dict(params, access_token=token))
    return _http(f"{host}/{ruta}?{q}", "GET")


def _valor(item):
    """El número de un ítem de insights: total_value.value (cuenta) o values[0].value (pieza). None si no es un entero."""
    v = None
    if isinstance(item.get("total_value"), dict):
        v = item["total_value"].get("value")
    elif item.get("values"):
        v = item["values"][0].get("value")
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _suma_diaria(item):
    """Facebook entrega un valor por día: se suman los que son números."""
    vals = [x.get("value") for x in (item.get("values") or []) if isinstance(x.get("value"), (int, float))]
    return int(sum(vals)) if vals else None


def _insights(host, ruta, metricas, extra, token, reintento, errores, texto_permiso):
    """Pide `metricas` juntas; si Meta rechaza la lista entera (por una métrica retirada o no válida para ese tipo de pieza)
    reintenta con `reintento` (lista de grupos: [["reach"]] o una por una) anotando el rechazo en `errores`.
    Devuelve ([ítems de insights], hubo_permiso_denegado)."""
    r, err = _llamar(host, ruta, dict(extra, metric=",".join(metricas)), token)
    if r is not None and isinstance(r.get("data"), list):
        return r["data"], False
    if _es_permiso(err):
        errores.append(f"{texto_permiso} (Meta: {_texto_error(err, token)})")   # (8/11) con el motivo de Meta, para diagnosticar
        return [], True
    errores.append(f"Meta rechazó {', '.join(metricas)}: {_texto_error(err, token)}")
    items = []
    for grupo in reintento:
        r, err = _llamar(host, ruta, dict(extra, metric=",".join(grupo)), token)
        if r is not None and isinstance(r.get("data"), list):
            items += r["data"]
        else:
            if _es_permiso(err):
                errores.append(f"{texto_permiso} (Meta: {_texto_error(err, token)})")
                return items, True
            if len(reintento) > 1:
                errores.append(f"Meta rechazó {', '.join(grupo)}: {_texto_error(err, token)}")
    return items, False


def _entero(v):
    return int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _salida(normal, crudo, errores):
    out = {k: v for k, v in normal.items() if v is not None}
    out["crudo"] = crudo
    out["errores"] = errores
    return out


def _ventana(dias):
    ahora = int(time.time())
    return {"since": ahora - int(dias) * 86400, "until": ahora}


# ---------------- Instagram ----------------
def insights_cuenta_instagram(cfg, dias=28):
    """La cuenta de Instagram: seguidores + lo de los últimos `dias` días (alcance, vistas, interacciones)."""
    _registrar_tokens(cfg)
    errores, crudo, normal = [], {}, {}
    if not (cfg.ig_token and cfg.ig_id):
        return _salida({}, {}, ["No hay conexión con Instagram configurada."])
    tok = cfg.ig_token
    r, err = _llamar(IG_HOST, cfg.ig_id, {"fields": "followers_count,media_count"}, tok)
    if r is not None:
        crudo["cuenta"] = {k: r.get(k) for k in ("followers_count", "media_count")}
        normal["seguidores"] = _entero(r.get("followers_count"))
    else:
        errores.append(TEXTO_SIN_PERMISO_IG if _es_permiso(err) else f"Instagram no dio los seguidores: {_texto_error(err, tok)}")
    items, _perm = _insights(IG_HOST, f"{cfg.ig_id}/insights", METRICAS_IG_CUENTA,
                             dict(period="day", metric_type="total_value", **_ventana(dias)), tok, [["reach"]], errores, TEXTO_SIN_PERMISO_IG)
    crudo["insights"] = {i.get("name"): i.get("total_value") for i in items}
    for i in items:
        clave = MAPA_IG.get(i.get("name"))
        if clave:
            normal[clave] = _entero(_valor(i))
        if i.get("name") == "follows_and_unfollows":      # sin confirmar: solo si Meta abre el desglose por tipo, se toman las altas
            for res in ((i.get("total_value") or {}).get("breakdowns") or [{}])[0].get("results") or []:
                if "FOLLOWER" in [str(x).upper() for x in res.get("dimension_values") or []] and "NON" not in str(res.get("dimension_values")).upper():
                    normal["seguidores_nuevos"] = _entero(res.get("value"))
    return _salida(normal, crudo, errores)


def insights_pieza_instagram(cfg, media_id, historia=False):
    """Un posteo, carrusel, reel o historia de Instagram. Las historias vencen a las 24 h: pasado ese tiempo `errores` lo dice."""
    _registrar_tokens(cfg)
    errores, crudo, normal = [], {}, {}
    if not (cfg.ig_token and media_id):
        return _salida({}, {}, ["No hay conexión con Instagram configurada." if not cfg.ig_token else "La pieza no tiene el id de Instagram."])
    tok = cfg.ig_token
    campos = "media_type,permalink" if historia else "like_count,comments_count,media_type,permalink"
    r, err = _llamar(IG_HOST, str(media_id), {"fields": campos}, tok)
    tipo = None
    if r is not None:
        crudo["pieza"] = {k: r.get(k) for k in ("like_count", "comments_count", "media_type", "permalink") if k in r}
        normal["me_gusta"] = _entero(r.get("like_count"))
        normal["comentarios"] = _entero(r.get("comments_count"))
        tipo = r.get("media_type")
    else:
        errores.append(f"{TEXTO_SIN_PERMISO_IG} (Meta: {_texto_error(err, tok)})" if _es_permiso(err) else f"Instagram no dio los datos de la pieza: {_texto_error(err, tok)}")
    if historia:
        metricas = METRICAS_IG_HISTORIA
    elif str(tipo).upper() == "VIDEO":
        metricas = METRICAS_IG_REEL
    else:
        metricas = METRICAS_IG_PIEZA
    antes = len(errores)
    items, _perm = _insights(IG_HOST, f"{media_id}/insights", metricas, {}, tok, [[m] for m in metricas], errores, TEXTO_SIN_PERMISO_IG)
    if historia and not items and len(errores) > antes and not any(es_error_de_permiso(e) for e in errores):
        errores.append("Instagram ya no da las métricas de esta historia: las borra a las 24 horas de publicada.")
    crudo["insights"] = {i.get("name"): (i.get("values") or [{}])[0].get("value") if i.get("values") else i.get("total_value") for i in items}
    for i in items:
        clave = MAPA_IG.get(i.get("name"))
        if clave:
            normal[clave] = _entero(_valor(i))
    return _salida(normal, crudo, errores)


# ---------------- Facebook ----------------
def insights_pagina_facebook(cfg, dias=28):
    """La página de Facebook: seguidores + la suma de los valores diarios de los últimos `dias` días."""
    _registrar_tokens(cfg)
    errores, crudo, normal = [], {}, {}
    if not (cfg.fb_page_id and cfg.fb_token):
        return _salida({}, {}, ["No hay conexión con Facebook configurada."])
    tok = cfg.fb_token
    r, err = _llamar(FB_HOST, cfg.fb_page_id, {"fields": "followers_count,fan_count"}, tok)
    if r is not None:
        crudo["pagina"] = {k: r.get(k) for k in ("followers_count", "fan_count")}
        normal["seguidores"] = _entero(r.get("followers_count") if r.get("followers_count") is not None else r.get("fan_count"))
    else:
        errores.append(f"{TEXTO_SIN_PERMISO_FB} (Meta: {_texto_error(err, tok)})" if _es_permiso(err) else f"Facebook no dio los seguidores: {_texto_error(err, tok)}")
    items, _perm = _insights(FB_HOST, f"{cfg.fb_page_id}/insights", METRICAS_FB_PAGINA, dict(period="day", **_ventana(dias)), tok,
                             [[m] for m in METRICAS_FB_PAGINA], errores, TEXTO_SIN_PERMISO_FB)
    crudo["insights"] = {}
    for i in items:
        total = _suma_diaria(i)
        crudo["insights"][i.get("name")] = total
        clave = MAPA_FB_PAGINA.get(i.get("name"))
        if clave and total is not None:
            normal[clave] = total
    return _salida(normal, crudo, errores)


def insights_posteo_facebook(cfg, post_id):
    """Un posteo de la página de Facebook."""
    _registrar_tokens(cfg)
    errores, crudo, normal = [], {}, {}
    if not (cfg.fb_token and post_id):
        return _salida({}, {}, ["No hay conexión con Facebook configurada." if not cfg.fb_token else "La pieza no tiene el id de Facebook."])
    tok = cfg.fb_token
    r, err = _llamar(FB_HOST, str(post_id), {"fields": "shares,reactions.summary(true),comments.summary(true)"}, tok)
    if r is not None:
        reacc = ((r.get("reactions") or {}).get("summary") or {}).get("total_count")
        coment = ((r.get("comments") or {}).get("summary") or {}).get("total_count")
        comp = (r.get("shares") or {}).get("count")
        crudo["posteo"] = {"compartidos": comp, "reacciones": reacc, "comentarios": coment}
        normal.update(me_gusta=_entero(reacc), comentarios=_entero(coment), compartidos=_entero(comp if comp is not None else 0))
    else:
        errores.append(f"{TEXTO_SIN_PERMISO_FB} (Meta: {_texto_error(err, tok)})" if _es_permiso(err) else f"Facebook no dio los datos del posteo: {_texto_error(err, tok)}")
    items, _perm = _insights(FB_HOST, f"{post_id}/insights", METRICAS_FB_POSTEO, {}, tok, [[m] for m in METRICAS_FB_POSTEO], errores, TEXTO_SIN_PERMISO_FB)
    crudo["insights"] = {}
    for i in items:
        v = (i.get("values") or [{}])[0].get("value")
        crudo["insights"][i.get("name")] = v
        clave = MAPA_FB_POSTEO.get(i.get("name"))
        if clave:
            normal[clave] = _entero(v)
    return _salida(normal, crudo, errores)
