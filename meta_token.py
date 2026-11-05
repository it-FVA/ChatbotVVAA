"""
meta_token.py — El token de Instagram se renueva solo (5/11).

El token de «Instagram Login» (IGAB…) dura 60 días y se renueva con
  GET https://graph.instagram.com/refresh_access_token?grant_type=ig_refresh_token&access_token=<token>
(solo si tiene más de 24 h y no venció; el viejo sigue válido hasta su vencimiento).

Dónde vive: tabla `config`, clave `meta_ig_token` = {"token", "vence" ISO, "renovado" ISO}. La API y la cola leen el mismo, sin
redeploy. `META_IG_TOKEN` del entorno es solo la SEMILLA: se usa si no hay nada guardado o Supabase no está.
Nunca se imprime ni se registra el token.
"""
import os, json, time, datetime, urllib.request, urllib.parse, urllib.error

CLAVE = "meta_ig_token"
IG_REFRESH = "https://graph.instagram.com/refresh_access_token"
RENOVAR_ANTES_DIAS = 30        # se renueva cuando faltan menos de estos días
_CACHE_SEG = 60
_cache = {"t": 0.0, "v": None}


def _ahora():
    return datetime.datetime.now(datetime.timezone.utc)


def _fecha(s):
    try:
        d = datetime.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=datetime.timezone.utc)
    except Exception:
        return None


def _guardado():
    """El registro de config.meta_ig_token, o None si no hay / Supabase no está / falla la lectura."""
    try:
        import db
        if not db.disponible():
            return None
        v = db.obtener_config(CLAVE)
        if isinstance(v, dict) and str(v.get("token") or "").strip():
            return v
    except Exception as e:
        print(f"meta_token: no pude leer config.{CLAVE}: {type(e).__name__}")
    return None


def info_token(usar_cache=False):
    """{"token", "origen": "config"|"entorno"|"ninguno", "vence": datetime|None, "renovado": datetime|None}."""
    if usar_cache and _cache["v"] is not None and time.time() - _cache["t"] < _CACHE_SEG:
        return _cache["v"]
    g = _guardado()
    if g:
        r = {"token": str(g["token"]).strip(), "origen": "config", "vence": _fecha(g.get("vence")), "renovado": _fecha(g.get("renovado"))}
    else:
        tok = os.environ.get("META_IG_TOKEN", "").strip()
        v = os.environ.get("META_IG_TOKEN_VENCE", "").strip()
        r = {"token": tok, "origen": "entorno" if tok else "ninguno", "vence": _fecha(v) if v else None, "renovado": None}
    _cache["t"], _cache["v"] = time.time(), r
    return r


def token_ig_vigente(usar_cache=True):
    """El token a usar: el guardado en config, o META_IG_TOKEN del entorno."""
    return info_token(usar_cache)["token"]


def _http_refresh(token):
    """GET al refresh de Meta → dict de la respuesta. Lanza RuntimeError con el mensaje de Meta (sin el token)."""
    url = IG_REFRESH + "?" + urllib.parse.urlencode({"grant_type": "ig_refresh_token", "access_token": token})
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        try:
            msg = (json.loads(e.read().decode("utf-8", "ignore")).get("error") or {}).get("message", "")
        except Exception:
            msg = ""
        raise RuntimeError(f"Meta {e.code}: {msg[:200]}")
    except Exception as e:
        raise RuntimeError(f"{type(e).__name__}: sin respuesta de Meta")


def renovar_token_ig(forzar=False):
    """Renueva si falta menos de RENOVAR_ANTES_DIAS (o forzar, o no se conoce el vencimiento). Devuelve
    {"renovado": bool, "vence": ISO|None, "motivo": str}. Si falla deja el viejo y avisa en el log; no lanza."""
    import db
    inf = info_token()
    if not inf["token"]:
        print("token IG: no hay token (ni en config ni META_IG_TOKEN); no renuevo")
        return {"renovado": False, "vence": None, "motivo": "sin token"}
    vence = inf["vence"]
    if not forzar and vence is not None and (vence - _ahora()).days >= RENOVAR_ANTES_DIAS:
        return {"renovado": False, "vence": vence.isoformat(timespec="seconds"), "motivo": "vigente"}
    try:
        if not db.disponible():
            raise RuntimeError("sin Supabase: no tengo dónde guardar el token nuevo")
        d = _http_refresh(inf["token"])
        nuevo, seg = str(d.get("access_token") or "").strip(), int(d.get("expires_in") or 0)
        if not nuevo or seg <= 0:
            raise RuntimeError("Meta respondió sin access_token / expires_in")
        ahora = _ahora()
        nvence = ahora + datetime.timedelta(seconds=seg)
        db.guardar_config(CLAVE, {"token": nuevo, "vence": nvence.isoformat(timespec="seconds"), "renovado": ahora.isoformat(timespec="seconds")}, usuario="renovacion-automatica")
        _cache["v"] = None
        print(f"token IG: renovado, vence {nvence:%d/%m/%Y} ({seg // 86400} días)")
        return {"renovado": True, "vence": nvence.isoformat(timespec="seconds"), "motivo": "renovado"}
    except Exception as e:
        print(f"token IG: NO pude renovarlo ({e}); sigo con el actual" + (f", que vence {vence:%d/%m/%Y}" if vence else ""))
        return {"renovado": False, "vence": vence.isoformat(timespec="seconds") if vence else None, "motivo": f"error: {e}"[:200]}
