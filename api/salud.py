"""Salud de los servicios (22/10/2026): la base de la futura pantalla «Salud» de Administración.

  GET /salud             lo de siempre (health check de Render, lo lee la web): ok, corpus, Supabase, modelo, Google…
  GET /salud/servicios   (admins, o ?token=SALUD_TOKEN / cabecera X-Salud-Token para un monitor externo) una lista de
                         chequeos con estado ok / aviso / error, detalle y «qué hacer». Cada corrida se guarda resumida en
                         la tabla salud_historial para poder decir «desde cuándo» está mal algo.
  GET /salud/historial   las últimas corridas guardadas (mismo permiso).
  GET /salud/capacidad   solo el bloque «capacidad» (uso vs. límite del plan por proveedor; también viene en /salud/servicios).
  PUT /salud/capacidad/config   (admins) umbrales_planes, presupuesto_openai_usd, vercel_uso_manual_gb.

Qué se chequea (cada uno es una función _chequear_* que devuelve un dict; corren en paralelo, con tope de tiempo):
  supabase          una consulta mínima (tabla config) y su latencia
  openai            models.retrieve del modelo de producción (gratis; cacheado 10 min)
  wordpress         GET /wp-json y, con WP_USER + WP_APP_PASSWORD, /wp/v2/users/me (las credenciales de la cola)
  instagram         token de Instagram Login (IG…): /me para la validez + META_IG_TOKEN_VENCE para el vencimiento (Meta no
                    permite debug_token con esos tokens); un token de Facebook Login iría por debug_token como el de la página
  facebook          lo mismo con el token de la página
  drive, youtube    los tokens OAuth (DRIVE_TOKEN_JSON / YOUTUBE_TOKEN_JSON): se canjea el refresh_token por un access
                    token en oauth2.googleapis.com (no consume cuota de Drive ni de YouTube; cacheado 10 min)
  cola_publicacion  última corrida de cola.yml en GitHub Actions (aviso si falló o tiene más de 45 min) y piezas
                    pendientes vencidas hace más de 30 min
  recortes          lo mismo con recortar_pendientes.yml y clips en estado 'pedido' hace más de 1 hora
  frase_del_dia     interruptor, foto por defecto, frase de hoy y de mañana
  api               la propia API: versión, desde cuándo corre, modo de vectores
  web               GET a la web (VITE_WEB_URL o el primer origen de CORS_ORIGENES)
  memoria           RSS del proceso (aviso al 80 % de MEMORIA_LIMITE_MB, error al 95 %; el free de Render tiene 512)

Regla de la casa: nada se inventa. Si un chequeo no se puede hacer (sin credenciales, sin red), lo dice tal cual.
"""
import os, json, time, base64, hmac, logging, datetime as dt, urllib.request, urllib.error, urllib.parse
from concurrent.futures import ThreadPoolExecutor

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from . import config, auth
import nucleo    # noqa: E402  (api/__init__ pone la raíz del repo en sys.path)
import db        # noqa: E402

log = logging.getLogger("api")
router = APIRouter(tags=["salud"])

ARRANQUE = time.time()
VERSION = "0.3 (salud + vectores en Supabase)"
REPO_GITHUB = "it-FVA/ChatbotVVAA"
TIMEOUT = 8                       # segundos por llamada externa
CACHE_SEG = 600                   # OpenAI, Meta, Google: 10 min
AVISO_VENCE_DIAS = 14
COLA_MAX_MIN = 45
PIEZA_VENCIDA_MIN = 30
CLIP_PEDIDO_MAX_MIN = 60
_CACHE = {}                       # nombre -> (t, resultado)
ORDEN_ESTADO = {"ok": 0, "aviso": 1, "error": 2}


# ---------------- helpers ----------------
def _ahora():
    return dt.datetime.now(dt.timezone.utc)


def _iso(d):
    return d.isoformat(timespec="seconds")


def _get(url, headers=None, timeout=TIMEOUT, method="GET", data=None):
    """(estado_http, cuerpo_texto, ms). Un error de red da estado 0 y el mensaje en el cuerpo. Los tests lo reemplazan."""
    t = time.time()
    req = urllib.request.Request(url, headers=headers or {}, method=method, data=data)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace"), int((time.time() - t) * 1000)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:500], int((time.time() - t) * 1000)
    except Exception as e:
        return 0, f"{type(e).__name__}: {e}"[:300], int((time.time() - t) * 1000)


def _json(texto):
    try:
        return json.loads(texto)
    except Exception:
        return None


def _cacheado(nombre, fn, segundos=CACHE_SEG):
    c = _CACHE.get(nombre)
    if c and time.time() - c[0] < segundos:
        return dict(c[1], cacheado=True)
    r = fn()
    _CACHE[nombre] = (time.time(), r)
    return r


def _res(nombre, estado, detalle, que_hacer=None, **extra):
    d = {"nombre": nombre, "estado": estado, "detalle": detalle, "que_hacer": que_hacer}
    d.update(extra)
    return d


def _fecha(valor):
    """ISO con o sin zona -> datetime UTC; None si no se puede."""
    if not valor:
        return None
    try:
        d = dt.datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def _minutos_desde(valor):
    d = _fecha(valor)
    return None if d is None else (_ahora() - d).total_seconds() / 60


def _hoy_argentina():
    return (_ahora() - dt.timedelta(hours=3)).date()


# ---------------- chequeos ----------------
def _chequear_supabase():
    if not db.disponible():
        return _res("supabase", "error", "Faltan SUPABASE_URL o SUPABASE_KEY.", "Cargarlas en el panel de Render (Environment).")
    t = time.time()
    try:
        db._req("GET", "?select=clave&limit=1", tabla="config")
        ms = int((time.time() - t) * 1000)
        estado = "ok" if ms < 2000 else "aviso"
        return _res("supabase", estado, f"Responde en {ms} ms.",
                    None if estado == "ok" else "Latencia alta: ver status.supabase.com o si el proyecto está pausado.", ms=ms)
    except Exception as e:
        return _res("supabase", "error", f"No responde: {str(e)[:200]}",
                    "Ver supabase.com, proyecto khgfqklieprcpxryqhtu (¿pausado por inactividad?) y la clave SUPABASE_KEY.")


def _openai_modelo(modelo):
    """Una llamada gratis: models.retrieve. Separada para que los tests la reemplacen."""
    return nucleo._get_client().models.retrieve(modelo)


def _chequear_openai():
    if not os.environ.get("OPENAI_API_KEY"):
        return _res("openai", "error", "Falta OPENAI_API_KEY.", "Cargarla en el panel de Render.")
    modelo = nucleo._modelo()

    def _ir():
        t = time.time()
        try:
            _openai_modelo(modelo)
            return _res("openai", "ok", f"La clave sirve y el modelo {modelo} existe ({int((time.time() - t) * 1000)} ms).", None, modelo=modelo)
        except Exception as e:
            msg = str(e)[:200]
            if "model" in msg.lower() and ("not" in msg.lower() or "404" in msg):
                return _res("openai", "error", f"OpenAI no reconoce el modelo {modelo}: {msg}", "Corregir ASISTENTE_MODELO en render.yaml.", modelo=modelo)
            return _res("openai", "error", f"OpenAI no responde: {msg}", "Revisar la clave (platform.openai.com, API keys) y el saldo.", modelo=modelo)
    return _cacheado("openai", _ir)


def _chequear_wordpress():
    sitio = os.environ.get("WP_SITE", "").replace("https://", "").replace("http://", "").strip("/")
    if not sitio:
        return _res("wordpress", "aviso", "Falta WP_SITE: la API no sabe qué sitio chequear.", "Agregar WP_SITE (viviragradecidos.org) al entorno.")
    st, cuerpo, ms = _get(f"https://{sitio}/wp-json/")
    if st != 200:
        return _res("wordpress", "error", f"https://{sitio}/wp-json/ respondió {st or 'sin conexión'} ({cuerpo[:120]}).",
                    "Entrar al sitio: si está caído es del hosting de WordPress; si da 401/403, un plugin de seguridad bloquea la REST API.", ms=ms)
    usuario, clave = os.environ.get("WP_USER", "").strip(), os.environ.get("WP_APP_PASSWORD", "").strip()
    if not (usuario and clave):
        return _res("wordpress", "aviso", f"El sitio responde ({ms} ms) pero la API no tiene WP_USER / WP_APP_PASSWORD: no puede verificar la cuenta con la que publica la cola.",
                    "Cargar WP_APP_PASSWORD en Render (es el mismo secret de GitHub Actions).", ms=ms)
    cred = base64.b64encode(f"{usuario}:{clave}".encode()).decode()
    st2, cuerpo2, ms2 = _get(f"https://{sitio}/wp-json/wp/v2/users/me?context=edit", {"Authorization": "Basic " + cred})
    if st2 == 200:
        d = _json(cuerpo2) or {}
        return _res("wordpress", "ok", f"Sitio y credenciales OK ({ms} + {ms2} ms); usuario {d.get('slug') or usuario}, roles {', '.join(d.get('roles') or []) or '?'}.", None, ms=ms + ms2)
    return _res("wordpress", "error", f"El sitio responde pero las credenciales de {usuario} fallan ({st2}).",
                "Generar una contraseña de aplicación nueva en WordPress (Usuarios, perfil, Application Passwords) y actualizar WP_APP_PASSWORD en Render y en los secrets de GitHub.", ms=ms + ms2)


def _chequear_meta(nombre, token, que):
    if not token:
        return _res(nombre, "aviso", f"Falta el token ({que}).", "Cargarlo en Render si se quiere monitorear el vencimiento desde acá.")

    def _ir():
        q = urllib.parse.urlencode({"input_token": token, "access_token": token})
        st, cuerpo, ms = _get(f"https://graph.facebook.com/debug_token?{q}")
        d = (_json(cuerpo) or {}).get("data") or {}
        if st != 200 or not d:
            err = ((_json(cuerpo) or {}).get("error") or {}).get("message") or cuerpo[:150]
            return _res(nombre, "error", f"Graph API no valida el token ({st}): {err}",
                        "Generar un token nuevo en developers.facebook.com (Graph API Explorer / Business Settings) y cargarlo en Render y en los secrets de GitHub.", ms=ms)
        if not d.get("is_valid"):
            return _res(nombre, "error", "El token NO es válido (is_valid=false).", "Generar un token nuevo (developers.facebook.com) y cargarlo en Render y en GitHub.", ms=ms)
        vence = int(d.get("expires_at") or 0)
        acceso = int(d.get("data_access_expires_at") or 0)
        scopes = ", ".join(d.get("scopes") or [])
        if vence == 0:
            det = f"Token válido, sin vencimiento (tipo {d.get('type', '?')}; permisos: {scopes})."
            estado, hacer = "ok", None
        else:
            f = dt.datetime.fromtimestamp(vence, dt.timezone.utc)
            dias = (f - _ahora()).days
            det = f"Token válido, vence el {f:%d/%m/%Y} ({dias} días; permisos: {scopes})."
            if dias < 0:
                estado, hacer = "error", "El token venció: generar uno nuevo y cargarlo en Render y en los secrets de GitHub."
            elif dias < AVISO_VENCE_DIAS:
                estado, hacer = "aviso", f"Vence en {dias} días: renovarlo antes (token de larga duración, 60 días) y cargarlo en Render y en GitHub."
            else:
                estado, hacer = "ok", None
        if acceso and estado == "ok" and (dt.datetime.fromtimestamp(acceso, dt.timezone.utc) - _ahora()).days < AVISO_VENCE_DIAS:
            estado, hacer = "aviso", "El acceso a datos (data_access_expires_at) vence en menos de 14 días: volver a autorizar la app."
        return _res(nombre, estado, det, hacer, vence=_iso(dt.datetime.fromtimestamp(vence, dt.timezone.utc)) if vence else None, ms=ms)
    return _cacheado(nombre, _ir)


def _chequear_ig_login(token):
    """Token de «Instagram Login» (empieza con IG…; publicar.py lo usa contra graph.instagram.com). Para estos tokens Meta no
    permite debug_token (403 «Application does not have permission», probado el 22/10): se verifica con /me y el vencimiento
    sale de META_IG_TOKEN_VENCE (AAAA-MM-DD, lo carga quien genera el token: duran 60 días). Sin esa variable, no se inventa."""
    def _ir():
        st, cuerpo, ms = _get(f"https://graph.instagram.com/v21.0/me?fields=id,username&access_token={urllib.parse.quote(token)}")
        d = _json(cuerpo) or {}
        if st != 200 or not d.get("id"):
            err = (d.get("error") or {}).get("message") or cuerpo[:150]
            return _res("instagram", "error", f"Instagram rechaza el token ({st}): {err}",
                        "Generar un token de larga duración nuevo (developers.facebook.com, app de Instagram, Generate token) y cargarlo en Render y en los secrets de GitHub, con META_IG_TOKEN_VENCE = hoy + 60 días.", ms=ms)
        det = f"Token válido para la cuenta @{d.get('username', '?')}."
        vence = os.environ.get("META_IG_TOKEN_VENCE", "").strip()
        f = _fecha(vence) if vence else None
        if f is None:
            return _res("instagram", "aviso", det + " Instagram no informa el vencimiento de este tipo de token (dura 60 días desde que se generó) y no está META_IG_TOKEN_VENCE.",
                        "Cargar META_IG_TOKEN_VENCE=AAAA-MM-DD en render.yaml (la fecha en que vence el token actual) para que esta fila avise 14 días antes.", ms=ms)
        dias = (f - _ahora()).days
        det += f" Vence el {f:%d/%m/%Y} según META_IG_TOKEN_VENCE ({dias} días)."
        if dias < 0:
            return _res("instagram", "error", det, "Según la fecha cargada ya venció (aunque /me todavía responda): generar un token nuevo y actualizar META_IG_TOKEN y META_IG_TOKEN_VENCE.", vence=_iso(f), ms=ms)
        if dias < AVISO_VENCE_DIAS:
            return _res("instagram", "aviso", det, f"Vence en {dias} días: generar un token nuevo, cargarlo en Render y GitHub y actualizar META_IG_TOKEN_VENCE.", vence=_iso(f), ms=ms)
        return _res("instagram", "ok", det, None, vence=_iso(f), ms=ms)
    return _cacheado("instagram", _ir)


def _chequear_instagram():
    token = os.environ.get("META_IG_TOKEN", "").strip()
    if token.startswith("IG"):
        return _chequear_ig_login(token)
    return _chequear_meta("instagram", token, "META_IG_TOKEN")


def _chequear_facebook():
    return _chequear_meta("facebook", os.environ.get("META_FB_PAGE_TOKEN", "").strip(), "META_FB_PAGE_TOKEN")


def _chequear_google(nombre, variable, reautorizar):
    crudo = os.environ.get(variable, "").strip()
    if not crudo:
        return _res(nombre, "aviso", f"Falta {variable}: la API no puede verificar el permiso.",
                    f"Cargar {variable} en Render (el mismo secret de GitHub Actions) si se quiere monitorear desde acá.")
    tok = _json(crudo)
    if not isinstance(tok, dict) or not tok.get("refresh_token"):
        return _res(nombre, "error", f"{variable} no es un JSON con refresh_token.", reautorizar)

    def _ir():
        data = urllib.parse.urlencode({"client_id": tok.get("client_id"), "client_secret": tok.get("client_secret"),
                                       "refresh_token": tok.get("refresh_token"), "grant_type": "refresh_token"}).encode()
        st, cuerpo, ms = _get("https://oauth2.googleapis.com/token", {"Content-Type": "application/x-www-form-urlencoded"}, method="POST", data=data)
        d = _json(cuerpo) or {}
        if st == 200 and d.get("access_token"):
            alcances = ", ".join(tok.get("scopes") or []) or d.get("scope", "?")
            return _res(nombre, "ok", f"El permiso sigue vigente: Google entregó un access token ({ms} ms; alcances: {alcances}).", None, ms=ms)
        err = d.get("error") or cuerpo[:120]
        hacer = reautorizar if err in ("invalid_grant", "unauthorized_client", "invalid_client") else "Puede ser un corte de Google: reintentar en unos minutos; si persiste, reautorizar."
        return _res(nombre, "error", f"Google rechazó el refresh_token ({st}): {err} {d.get('error_description', '')}".strip(), hacer, ms=ms)
    return _cacheado(nombre, _ir)


def _chequear_drive():
    return _chequear_google("drive", "DRIVE_TOKEN_JSON",
                            "Volver a autorizar: en la máquina de Franco, python autorizar_drive.py, y copiar el DRIVE_TOKEN_JSON nuevo a GitHub (secrets) y Render.")


def _chequear_youtube():
    return _chequear_google("youtube", "YOUTUBE_TOKEN_JSON",
                            "Volver a autorizar: python autorizar_youtube.py, y copiar el YOUTUBE_TOKEN_JSON nuevo a GitHub (secrets) y Render.")


def _ultima_corrida(workflow):
    """Última corrida del workflow en GitHub Actions (API pública; con GITHUB_TOKEN sube el límite de 60/h). Cacheada 5 min."""
    def _ir():
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "fva-api-salud"}
        if os.environ.get("GITHUB_TOKEN"):
            headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
        st, cuerpo, ms = _get(f"https://api.github.com/repos/{REPO_GITHUB}/actions/workflows/{workflow}/runs?per_page=1", headers)
        if st != 200:
            return {"error": f"GitHub respondió {st}: {cuerpo[:100]}", "ms": ms}
        runs = (_json(cuerpo) or {}).get("workflow_runs") or []
        if not runs:
            return {"error": "GitHub no tiene corridas de ese workflow", "ms": ms}
        r = runs[0]
        return {"status": r.get("status"), "conclusion": r.get("conclusion"), "cuando": r.get("run_started_at") or r.get("created_at"),
                "actualizado": r.get("updated_at"), "evento": r.get("event"), "url": r.get("html_url"), "ms": ms}
    return _cacheado("gh:" + workflow, _ir, 300)


def _evaluar_corrida(workflow, que):
    """(estado, texto, que_hacer, datos) de la última corrida de un workflow."""
    r = _ultima_corrida(workflow)
    url_acciones = f"https://github.com/{REPO_GITHUB}/actions/workflows/{workflow}"
    if r.get("error"):
        return "aviso", f"No pude leer GitHub Actions: {r['error']}.", f"Ver a mano {url_acciones}.", r
    mins = _minutos_desde(r.get("cuando"))
    hace = f"hace {int(mins)} min" if mins is not None else "en fecha desconocida"
    if r.get("status") != "completed":
        return "ok", f"{que}: hay una corrida en curso ({r.get('status')}, empezó {hace}).", None, r
    if r.get("conclusion") != "success":
        return "aviso", f"{que}: la última corrida ({hace}) terminó en {r.get('conclusion')}.", f"Abrir el log en {r.get('url') or url_acciones} y ver qué falló; si es un secret vencido, la fila de ese servicio lo dice.", r
    if mins is not None and mins > COLA_MAX_MIN:
        return "aviso", f"{que}: la última corrida fue {hace} (debería correr cada 15 min).", f"GitHub demora los cron; si pasan horas, correrla a mano ({url_acciones}, Run workflow) y revisar el cron externo (cron-job.org).", r
    return "ok", f"{que}: última corrida {hace}, OK.", None, r


def _chequear_cola():
    estado, texto, hacer, datos = _evaluar_corrida("cola.yml", "Cola de publicación")
    extra = {"corrida": datos}
    if db.disponible():
        try:
            vencidas = [p for p in db.listar_pendientes(vencidas=True) or [] if (_minutos_desde(p.get("fecha_programada")) or 0) > PIEZA_VENCIDA_MIN]
            extra["pendientes_vencidas"] = len(vencidas)
            if vencidas:
                mas = max(_minutos_desde(p.get("fecha_programada")) or 0 for p in vencidas)
                texto += f" Hay {len(vencidas)} pieza(s) pendiente(s) que debían salir hace más de {PIEZA_VENCIDA_MIN} min (la más vieja, {int(mas)} min)."
                if ORDEN_ESTADO[estado] < 1:
                    estado, hacer = "aviso", "La cola no las procesó: correr cola.yml a mano y ver el log; si una pieza falla siempre, cancelarla desde Mis publicaciones."
        except Exception as e:
            texto += f" (No pude leer las piezas pendientes: {str(e)[:80]}.)"
    return _res("cola_publicacion", estado, texto, hacer, **extra)


def _chequear_recortes():
    estado, texto, hacer, datos = _evaluar_corrida("recortar_pendientes.yml", "Recortes")
    extra = {"corrida": datos}
    if db.disponible():
        try:
            limite = _iso(_ahora() - dt.timedelta(minutes=CLIP_PEDIDO_MAX_MIN))
            viejos = db.clips_pedidos_antes(limite)
            extra["clips_pedidos_viejos"] = len(viejos)
            if viejos:
                nombres = ", ".join((c.get("titulo") or c.get("video_id") or "?")[:30] for c in viejos[:3])
                texto += f" Hay {len(viejos)} recorte(s) en estado 'pedido' desde hace más de {CLIP_PEDIDO_MAX_MIN // 60} h ({nombres})."
                if ORDEN_ESTADO[estado] < 1:
                    estado, hacer = "aviso", "Normalmente un recorte tarda 15 min. Si el original no está en Drive, la cola lo reintenta para siempre: verlo en Panel admin, Clips."
        except Exception as e:
            texto += f" (No pude leer los clips: {str(e)[:80]}.)"
    return _res("recortes", estado, texto, hacer, **extra)


def _chequear_frase():
    if not db.disponible():
        return _res("frase_del_dia", "aviso", "Sin Supabase no se puede ver la Frase del día.", None)
    try:
        activa = bool(db.obtener_config("frase_activa", False))
        foto = db.obtener_config("frase_imagen") or ""
        hoy = _hoy_argentina()
        fh, fm = db.frase_del_dia(hoy.isoformat()), db.frase_del_dia((hoy + dt.timedelta(days=1)).isoformat())
    except Exception as e:
        return _res("frase_del_dia", "error", f"No pude leer la configuración: {str(e)[:150]}", "Ver Supabase.")

    def _r(f):
        return None if not f else {"fecha": f.get("fecha"), "texto": (f.get("texto") or "")[:80], "autor": f.get("autor"),
                                   "estado": f.get("estado"), "con_foto": bool(f.get("imagen_url"))}
    datos = {"activa": activa, "foto_defecto": bool(foto), "hoy": _r(fh), "manana": _r(fm)}
    if not activa:
        return _res("frase_del_dia", "ok", "Interruptor apagado: no se encola nada." + (f" Frase de hoy: «{datos['hoy']['texto']}»." if fh else " Hoy no hay frase asignada."), None, **datos)
    problemas, hacer = [], []
    if not foto and not ((fh or {}).get("imagen_url") and (fm or {}).get("imagen_url")):
        problemas.append("no hay foto por defecto (sin foto la frase no se encola)")
        hacer.append("Panel admin, Frase del día, Cómo sale cada día: elegir la foto por defecto")
    if not fh:
        problemas.append("hoy no tiene frase asignada (la rotación debería llenarlo en la próxima corrida de la cola)")
    if not fm:
        problemas.append("mañana no tiene frase asignada")
    if problemas:
        return _res("frase_del_dia", "aviso", "Interruptor prendido, pero " + "; ".join(problemas) + ".", "; ".join(hacer) or "Ver Panel admin, Frase del día.", **datos)
    return _res("frase_del_dia", "ok", f"Prendida. Hoy: «{datos['hoy']['texto']}» ({fh.get('estado')}); mañana: «{datos['manana']['texto']}».", None, **datos)


def _chequear_api():
    seg = int(time.time() - ARRANQUE)
    n = len(nucleo._FRS) if nucleo._FRS is not None else 0
    estado = "ok" if n else "aviso"
    return _res("api", estado,
                f"Responde. Versión {VERSION}; corre desde hace {seg // 3600} h {seg % 3600 // 60} min; corpus {n} fragmentos; vectores: {os.environ.get('VECTORES', 'local') or 'local'}.",
                None if n else "El corpus no está cargado (API_CARGAR_CORPUS=0 o falló la carga): ver el log de Render.",
                arranque=_iso(dt.datetime.fromtimestamp(ARRANQUE, dt.timezone.utc)), segundos=seg, version=VERSION)


def _url_web():
    u = os.environ.get("VITE_WEB_URL", "").strip()
    if not u:
        origenes = [o.strip() for o in os.environ.get("CORS_ORIGENES", "").split(",") if o.strip()]
        u = origenes[0] if origenes else ""
    return u


def _chequear_web():
    u = _url_web()
    if not u:
        return _res("web", "aviso", "No sé la URL de la web (ni VITE_WEB_URL ni CORS_ORIGENES).", "Definir CORS_ORIGENES en render.yaml (ya debería estar).")
    st, cuerpo, ms = _get(u, {"User-Agent": "fva-api-salud"})
    if st == 200:
        return _res("web", "ok", f"{u} responde ({ms} ms).", None, url=u, ms=ms)
    return _res("web", "error", f"{u} respondió {st or 'sin conexión'}.", "Ver vercel.com, proyecto chatbot-vvaa, Deployments (¿falló el último build?).", url=u, ms=ms)


def _rss_mb():
    try:
        import psutil
        return psutil.Process().memory_info().rss / 2 ** 20
    except Exception:
        pass
    try:
        with open("/proc/self/status") as f:            # Linux sin psutil
            for l in f:
                if l.startswith("VmRSS:"):
                    return int(l.split()[1]) / 1024
    except Exception:
        pass
    return None


def _chequear_memoria():
    rss = _rss_mb()
    limite = nucleo._env_int("MEMORIA_LIMITE_MB", 512)
    if rss is None:
        return _res("memoria", "aviso", "No pude medir la memoria del proceso (falta psutil).", "Agregar psutil a api/requirements.txt.")
    pct = rss / limite * 100
    estado = "error" if pct >= 95 else "aviso" if pct >= 80 else "ok"
    hacer = None if estado == "ok" else "Cerca del límite del plan: Render reinicia el servicio al pasarse (Out of memory). Opciones: VECTORES=supabase (embeddings y BM25 fuera del proceso) o plan Standard."
    return _res("memoria", estado, f"RSS {rss:.0f} MB de {limite} MB ({pct:.0f} %).", hacer, rss_mb=round(rss), limite_mb=limite, porcentaje=round(pct))


CHEQUEOS = [_chequear_supabase, _chequear_openai, _chequear_wordpress, _chequear_instagram, _chequear_facebook,
            _chequear_drive, _chequear_youtube, _chequear_cola, _chequear_recortes, _chequear_frase,
            _chequear_api, _chequear_web, _chequear_memoria]


def correr():
    """Corre todos los chequeos en paralelo (los que se cuelgan quedan como error de tiempo). Devuelve el informe."""
    t = time.time()
    with ThreadPoolExecutor(max_workers=len(CHEQUEOS)) as ex:
        futuros = [(f, ex.submit(f)) for f in CHEQUEOS]
        resultados = []
        for f, fu in futuros:
            nombre = f.__name__.replace("_chequear_", "")
            try:
                resultados.append(fu.result(timeout=TIMEOUT + 4))
            except Exception as e:
                resultados.append(_res(nombre, "error", f"El chequeo falló o tardó demasiado: {type(e).__name__} {str(e)[:120]}",
                                       "Volver a consultar; si persiste, ver el log de la API."))
    general = max((r["estado"] for r in resultados), key=lambda e: ORDEN_ESTADO.get(e, 2))
    return {"creado": _iso(_ahora()), "estado": general, "chequeos": resultados, "ms": int((time.time() - t) * 1000)}


def desde_cuando(informe, historial, clave="chequeos"):
    """Para cada chequeo (o fila de capacidad) que no está ok: la fecha de la corrida más vieja de la racha actual con ese
    mismo estado (historial = filas de salud_historial más recientes primero, sin las de arranque, cada una con creado y
    detalle[clave] = [{nombre, estado}])."""
    for ch in informe.get(clave) or []:
        if ch["estado"] == "ok":
            continue
        desde = informe["creado"]
        for fila in historial:
            if fila.get("estado") == "arranque":
                continue
            previos = {c.get("nombre"): c.get("estado") for c in ((fila.get("detalle") or {}).get(clave) or [])}
            if previos.get(ch["nombre"]) == ch["estado"]:
                desde = fila.get("creado") or desde
            else:
                break
        ch["desde"] = desde
    return informe


def _guardar(informe):
    """Guarda la corrida resumida y agrega «desde» a los chequeos que no están ok. Nunca rompe la respuesta."""
    if not db.disponible():
        return informe
    try:
        historial = db.listar_salud(300)
        desde_cuando(informe, historial)
        desde_cuando(informe, historial, "capacidad")
        resumen = {"chequeos": [{"nombre": c["nombre"], "estado": c["estado"], "detalle": (c.get("detalle") or "")[:300]} for c in informe["chequeos"]],
                   "capacidad": [{"nombre": c.get("nombre"), "estado": c.get("estado"), "uso": c.get("uso"), "porcentaje": c.get("porcentaje")} for c in informe.get("capacidad") or []],
                   "ms": informe["ms"]}
        db.guardar_salud(informe["estado"], resumen)
    except Exception as e:
        log.warning("salud_historial: %s", e)
        informe["historial_aviso"] = f"No pude guardar en salud_historial: {str(e)[:150]} (¿falta la migración api/migraciones/salud_historial.sql?)"
    return informe


def _autorizar(request: Request, token):
    """Admin con sesión, o el token de monitoreo (SALUD_TOKEN) por ?token= o X-Salud-Token."""
    esperado = os.environ.get("SALUD_TOKEN", "").strip()
    dado = (token or request.headers.get("x-salud-token") or "").strip()
    if esperado and dado and hmac.compare_digest(esperado, dado):
        return "monitor"
    if dado and not esperado:
        raise HTTPException(403, "La API no tiene SALUD_TOKEN configurado: entrá como admin.")
    return auth.admin(request)


# ---------------- rutas ----------------
@router.get("/salud")
def salud():
    """Lo que ya devolvía (health check de Render y la web): compatible, más versión, arranque y modo de vectores."""
    n = len(nucleo._FRS) if nucleo._FRS is not None else 0
    return {"ok": True, "corpus_fragmentos": n, "corpus_cargado": n > 0, "supabase": db.disponible(),
            "modelo": nucleo._modelo(), "login_google": bool(os.environ.get("GOOGLE_CLIENT_ID")),
            "google_client_id": os.environ.get("GOOGLE_CLIENT_ID", "").strip() or None,   # lo usa el botón de la web; no es secreto
            "dominio_fva": config.dominio_fva(),
            "version": VERSION, "arranque": _iso(dt.datetime.fromtimestamp(ARRANQUE, dt.timezone.utc)),
            "vectores": os.environ.get("VECTORES", "local").strip().lower() or "local",
            "mail": _mail_publico()}


def _mail_publico():
    """(26/10) Frase del día por mail: solo lo no sensible, para comprobar desde afuera que las variables de Perfit quedaron
    bien cargadas (modo, qué falta, si la API de Perfit responde y la lista existe). Nunca devuelve claves ni URLs."""
    try:
        import perfit
        est = perfit.probar_conexion()
        return {"modo": est["modo"], "faltan": est["faltan"],
                "api_perfit": ("ok" if est["lista"] else ("error" if est["error"] else "sin_probar")),
                "lista": (est["lista"] or {}).get("nombre"), "activos": (est["lista"] or {}).get("activos")}
    except Exception as e:   # pragma: no cover
        return {"modo": "?", "error": str(e)[:80]}


@router.get("/salud/servicios")
def servicios(request: Request, token: str = None, guardar: bool = True):
    """Todos los chequeos. Solo admins (o el token de monitoreo). guardar=0 no escribe en salud_historial."""
    quien = _autorizar(request, token)
    informe = correr()
    informe["capacidad"] = capacidad()
    informe["consultado_por"] = quien
    return _guardar(informe) if guardar else informe


@router.get("/salud/historial")
def historial(request: Request, token: str = None, limite: int = 100):
    """Las últimas corridas guardadas (más recientes primero): para el «desde cuándo» de la pantalla."""
    _autorizar(request, token)
    if not db.disponible():
        return []
    try:
        return db.listar_salud(min(max(limite, 1), 1000))
    except Exception as e:
        raise HTTPException(503, f"No pude leer salud_historial: {str(e)[:150]}")


# ====================================================================================================================
# CAPACIDAD (22/10, pedido de Franco para el Dashboard de Administración): «¿funciona? ¿por qué? ¿cuánto cuesta? ¿por qué?».
# Por proveedor: uso actual, límite del plan vigente, porcentaje y un umbral (config umbrales_planes, default 70 %) a partir
# del cual el estado pasa a aviso «conviene pasar a plan pago», con la justificación (métrica, cuánto, desde cuándo).
# Límites: solo los confirmados en la documentación oficial van sin `referencia`; los demás llevan referencia=True y la fuente.
# Lo que no se puede medir (Vercel sin API key) se carga a mano (config vercel_uso_manual) y se dice que es manual.
# ====================================================================================================================
UMBRAL_DEFAULT = 70
LIMITES = {
    # confirmados el 22/10/2026 en la documentación oficial
    "supabase_db_mb": {"valor": 500, "unidad": "MB", "fuente": "supabase.com/pricing (22/10/2026): «500 MB database size per project included»; los proyectos Free se pausan tras 1 semana sin uso", "referencia": False},
    "render_ram_mb": {"valor": 512, "unidad": "MB", "fuente": "render.com/docs/compute-plans (22/10/2026): Free = 0.1 CPU, 512 MB; se duerme a los 15 min sin tráfico (render.com/docs/free)", "referencia": False},
    "render_horas_mes": {"valor": 750, "unidad": "h", "fuente": "render.com/docs/free (22/10/2026): 750 horas de instancia Free por workspace y mes", "referencia": False},
    # guía de uso, no un derecho del plan: va como referencia
    "vercel_transferencia_gb": {"valor": 100, "unidad": "GB/mes", "fuente": "vercel.com/docs/limits/fair-use-guidelines (22/10/2026): Hobby «First 100 GB» de Fast Data Transfer, como guía de uso típico; Hobby es solo para uso no comercial", "referencia": True},
}


def _umbral(proveedor):
    """config umbrales_planes: un número (para todos) o {"default": 70, "supabase": 80, …}."""
    try:
        u = db.obtener_config("umbrales_planes") if db.disponible() else None
    except Exception:
        u = None
    if isinstance(u, (int, float)):
        return float(u)
    if isinstance(u, dict):
        v = u.get(proveedor, u.get("default", UMBRAL_DEFAULT))
        try:
            return float(v)
        except (TypeError, ValueError):
            return float(UMBRAL_DEFAULT)
    return float(UMBRAL_DEFAULT)


def _plan_y_costo(proveedor):
    """Plan y costo mensual cargados en la tabla servicios (Panel admin → Servicios y costos), si están."""
    try:
        for s in (db.listar_servicios(solo_activos=True) if db.disponible() else []):
            if proveedor.lower() in ((s.get("proveedor") or "") + " " + (s.get("nombre") or "")).lower():
                return s.get("plan") or None, s.get("costo_mensual_usd"), bool(s.get("confirmado"))
    except Exception:
        pass
    return None, None, False


def _item(nombre, proveedor, metrica, uso, limite, unidad, umbral, fuente=None, referencia=False, plan=None, costo=None,
          costo_confirmado=False, extra=None, justificacion_ok=None, medido=True):
    """Arma la fila del Dashboard. porcentaje y estado salen de uso/limite/umbral; la justificación dice qué métrica y cuánto."""
    pct = round(uso / limite * 100) if (uso is not None and limite) else None
    if uso is None:
        estado, just = "sin_dato", justificacion_ok or f"No se pudo medir {metrica}."
    elif pct is not None and pct >= 100:
        estado, just = "error", f"{metrica}: {uso:g} de {limite:g} {unidad} ({pct} %): el plan {plan or 'actual'} está al límite."
    elif pct is not None and pct >= umbral:
        estado, just = "aviso", f"Conviene pasar a plan pago: {metrica} {uso:g} de {limite:g} {unidad} ({pct} %) supera el umbral del {umbral:g} %."
    else:
        estado = "ok"
        just = justificacion_ok or (f"{metrica}: {uso:g} de {limite:g} {unidad} ({pct} %), por debajo del umbral del {umbral:g} %." if pct is not None
                                    else f"{metrica}: {uso:g} {unidad}; no hay límite cargado para comparar.")
    d = {"nombre": nombre, "proveedor": proveedor, "plan": plan, "costo_mensual_usd": costo, "costo_confirmado": costo_confirmado,
         "metrica": metrica, "uso": uso, "limite": limite, "unidad": unidad, "porcentaje": pct, "umbral": umbral,
         "estado": estado, "justificacion": just, "fuente_limite": fuente, "referencia": referencia, "medido": medido}
    d.update(extra or {})
    return d


def _capacidad_supabase():
    umbral = _umbral("supabase")
    plan, costo, conf = _plan_y_costo("supabase")
    lim = LIMITES["supabase_db_mb"]
    if not db.disponible():
        return _item("Supabase", "supabase", "tamaño de la base", None, lim["valor"], lim["unidad"], umbral, lim["fuente"], plan=plan, costo=costo,
                     justificacion_ok="Faltan SUPABASE_URL / SUPABASE_KEY.")
    try:
        t = db.tamano_base()
    except Exception as e:
        return _item("Supabase", "supabase", "tamaño de la base", None, lim["valor"], lim["unidad"], umbral, lim["fuente"], plan=plan, costo=costo,
                     justificacion_ok=f"La base no respondió ({str(e)[:120]}): puede estar pausada (Free se pausa tras 1 semana sin uso) o falta la función SQL tamano_base().",
                     extra={"estado_forzado": "error"})
    mb = round((t.get("bytes") or 0) / 2 ** 20, 1)
    tablas = {k: v for k, v in (t.get("tablas") or {}).items()}
    grandes = sorted(tablas.items(), key=lambda kv: -(kv[1].get("bytes") or 0))[:6]
    return _item("Supabase", "supabase", "tamaño de la base", mb, lim["valor"], lim["unidad"], umbral, lim["fuente"], plan=plan or "Free",
                 costo=costo, costo_confirmado=conf,
                 extra={"tablas": {k: {"filas": v.get("filas"), "mb": round((v.get("bytes") or 0) / 2 ** 20, 1)} for k, v in grandes},
                        "nota": "El tamaño de la base incluye fragmentos_emb (vectores + texto del corpus) si se subió; las filas por tabla son la estimación de Postgres (reltuples)."})


def _capacidad_render():
    umbral = _umbral("render")
    plan, costo, conf = _plan_y_costo("render")
    lim = LIMITES["render_ram_mb"]
    limite = nucleo._env_int("MEMORIA_LIMITE_MB", lim["valor"])
    rss = _rss_mb()
    try:
        arranques_24h, arranques_7d = db.contar_arranques(24), db.contar_arranques(24 * 7)
    except Exception:
        arranques_24h, arranques_7d = None, None
    extra = {"arranques_24h": arranques_24h, "arranques_7d": arranques_7d, "corre_desde": _iso(dt.datetime.fromtimestamp(ARRANQUE, dt.timezone.utc)),
             "horas_mes_limite": LIMITES["render_horas_mes"]["valor"], "fuente_horas": LIMITES["render_horas_mes"]["fuente"],
             "nota": "Cada arranque registrado es un despertar en frío del plan free (~1 min sin responder). La memoria es el RSS del proceso en este instante; el pico (al cargar BM25) puede ser mayor."}
    it = _item("Render (API)", "render", "memoria del proceso", round(rss) if rss is not None else None, limite, lim["unidad"], umbral, lim["fuente"],
               plan=plan or "Free", costo=costo, costo_confirmado=conf, extra=extra)
    if arranques_24h and arranques_24h >= 5 and it["estado"] == "ok":
        it["estado"] = "aviso"
        it["justificacion"] += f" Además arrancó {arranques_24h} veces en 24 h: cada vez la gente espera ~1 min; un plan pago (Starter, 512 MB sin dormirse) lo evita."
    return it


def _capacidad_vercel():
    umbral = _umbral("vercel")
    plan, costo, conf = _plan_y_costo("vercel")
    lim = LIMITES["vercel_transferencia_gb"]
    manual = None
    try:
        manual = db.obtener_config("vercel_uso_manual") if db.disponible() else None
    except Exception:
        manual = None
    gb = None
    if isinstance(manual, dict):
        try:
            gb = float(manual.get("gb"))
        except (TypeError, ValueError):
            gb = None
    extra = {"uso_manual": manual if isinstance(manual, dict) else None, "url": _url_web() or None,
             "nota": "Sin VERCEL_TOKEN la API no puede leer el uso: el dato lo carga un admin (PUT /salud/capacidad/config {vercel_uso_manual_gb}) mirando vercel.com → Usage. La lectura automática queda para cuando haya token."}
    if gb is None:
        it = _item("Vercel (web)", "vercel", "transferencia del mes", None, lim["valor"], lim["unidad"], umbral, lim["fuente"], lim["referencia"], plan=plan or "Hobby",
                   costo=costo, costo_confirmado=conf, extra=extra, medido=False,
                   justificacion_ok="Uso no cargado: la API no puede leerlo sin VERCEL_TOKEN. Cargarlo a mano desde el panel para comparar con los 100 GB/mes de referencia.")
    else:
        it = _item("Vercel (web)", "vercel", "transferencia del mes (dato manual)", gb, lim["valor"], lim["unidad"], umbral, lim["fuente"], lim["referencia"], plan=plan or "Hobby",
                   costo=costo, costo_confirmado=conf, extra=extra, medido=False)
        if manual.get("fecha"):
            it["justificacion"] += f" Dato cargado a mano el {str(manual.get('fecha'))[:10]}" + (f" por {manual.get('por')}" if manual.get("por") else "") + "."
    return it


def _costo_fila(fila, precios):
    """USD de una fila de uso_openai según config openai_precios (misma fórmula que publicar_ui._costo), o None sin precio."""
    p = precios.get(fila.get("modelo") or "")
    if not p:
        return None
    ent, cache, sal = fila.get("tokens_entrada") or 0, fila.get("tokens_cache") or 0, fila.get("tokens_salida") or 0
    pc = p.get("cache") if p.get("cache") is not None else p.get("entrada", 0)
    return ((ent - cache) * p.get("entrada", 0) + cache * pc + sal * p.get("salida", 0)) / 1_000_000


def _capacidad_openai():
    umbral = _umbral("openai")
    plan, costo, conf = _plan_y_costo("openai")
    if not db.disponible():
        return _item("OpenAI", "openai", "gasto estimado del mes", None, None, "USD", umbral, plan=plan or "pago por uso", costo=costo,
                     justificacion_ok="Sin Supabase no hay registro de uso (tabla uso_openai).")
    hoy = _hoy_argentina()
    desde = hoy.replace(day=1).isoformat()
    try:
        filas = db.uso_openai(desde=desde)
        precios = db.obtener_config("openai_precios") or {}
        presupuesto = db.obtener_config("presupuesto_openai_usd")
    except Exception as e:
        return _item("OpenAI", "openai", "gasto estimado del mes", None, None, "USD", umbral, plan=plan or "pago por uso", costo=costo,
                     justificacion_ok=f"No pude leer uso_openai / config: {str(e)[:120]}")
    costos = [_costo_fila(f, precios) for f in filas]
    usd = round(sum(c for c in costos if c is not None), 2)
    sin_precio = sorted({(f.get("modelo") or "?") for f, c in zip(filas, costos) if c is None})
    tokens = {"entrada": sum(f.get("tokens_entrada") or 0 for f in filas), "salida": sum(f.get("tokens_salida") or 0 for f in filas),
              "cache": sum(f.get("tokens_cache") or 0 for f in filas), "llamadas": len(filas)}
    try:
        limite = float(presupuesto) if presupuesto not in (None, "", 0) else None
    except (TypeError, ValueError):
        limite = None
    dias = max(hoy.day, 1)
    proyeccion = round(usd / dias * 30, 2) if filas else 0.0
    extra = {"desde": desde, "tokens": tokens, "modelos_sin_precio": sin_precio, "proyeccion_30_dias_usd": proyeccion,
             "fuente_precios": {m: p.get("fuente") for m, p in precios.items() if isinstance(p, dict)},
             "nota": "Estimación con los precios de config openai_precios (por millón de tokens); el número real es el de la factura de OpenAI. Sin precio cargado para un modelo, sus tokens cuentan pero su costo no."}
    just_ok = None
    if limite is None:
        just_ok = f"Gasto estimado del mes: US$ {usd:.2f} ({tokens['llamadas']} llamadas). No hay presupuesto mensual cargado (config presupuesto_openai_usd) para comparar."
    it = _item("OpenAI", "openai", "gasto estimado del mes", usd, limite, "USD", umbral, "config presupuesto_openai_usd (lo fija la Fundación; no es un límite de OpenAI)",
               plan=plan or "pago por uso", costo=costo, costo_confirmado=conf, extra=extra, justificacion_ok=just_ok)
    if sin_precio:
        it["justificacion"] += f" Modelos sin precio cargado: {', '.join(sin_precio)}."
    return it


CAPACIDADES = [_capacidad_supabase, _capacidad_render, _capacidad_vercel, _capacidad_openai]


def capacidad():
    """La lista de proveedores para el Dashboard, con el peor estado al frente."""
    with ThreadPoolExecutor(max_workers=len(CAPACIDADES)) as ex:
        futs = [(f, ex.submit(f)) for f in CAPACIDADES]
        items = []
        for f, fu in futs:
            try:
                it = fu.result(timeout=TIMEOUT + 4)
                if it.pop("estado_forzado", None):
                    it["estado"] = "error"
                items.append(it)
            except Exception as e:
                items.append({"nombre": f.__name__.replace("_capacidad_", ""), "estado": "sin_dato", "justificacion": f"El cálculo falló: {type(e).__name__} {str(e)[:120]}"})
    orden = {"error": 0, "aviso": 1, "sin_dato": 2, "ok": 3}
    items.sort(key=lambda i: orden.get(i.get("estado"), 2))
    return items


def registrar_arranque():
    """Una fila estado='arranque' en salud_historial por cada arranque del proceso (para contar despertares del plan free).
    En un hilo, nunca frena el arranque. No se registra en los tests (API_CARGAR_CORPUS=0) ni sin Supabase."""
    if not db.disponible() or os.environ.get("API_CARGAR_CORPUS", "1") == "0":
        return False
    import threading

    def _ir():
        try:
            db.guardar_salud("arranque", {"version": VERSION, "vectores": os.environ.get("VECTORES", "local") or "local"})
        except Exception as e:
            log.warning("No pude registrar el arranque en salud_historial: %s", e)
    threading.Thread(target=_ir, daemon=True).start()
    return True


registrar_arranque()


class ConfigCapacidad(BaseModel):
    """Lo que un admin ajusta desde el Dashboard. Las claves que no vienen no se tocan."""
    umbrales_planes: Optional[dict] = None          # {"default": 70, "supabase": 80, …} (porcentajes)
    presupuesto_openai_usd: Optional[float] = None  # presupuesto mensual; 0 = sin presupuesto
    vercel_uso_manual_gb: Optional[float] = None    # GB transferidos este mes, leídos de vercel.com → Usage


@router.get("/salud/capacidad")
def capacidad_endpoint(request: Request, token: str = None):
    """Solo el bloque de capacidad (más barato que /salud/servicios): para el Dashboard."""
    _autorizar(request, token)
    return {"creado": _iso(_ahora()), "capacidad": capacidad()}


@router.put("/salud/capacidad/config")
def capacidad_config(datos: ConfigCapacidad, usuario=Depends(auth.admin)):
    if not db.disponible():
        raise HTTPException(503, "Sin Supabase no hay dónde guardar la configuración.")
    cambios = {}
    if datos.umbrales_planes is not None:
        malos = {k: v for k, v in datos.umbrales_planes.items() if not isinstance(v, (int, float)) or not 1 <= float(v) <= 100}
        if malos:
            raise HTTPException(400, f"Umbrales inválidos (tienen que ser porcentajes de 1 a 100): {malos}")
        db.guardar_config("umbrales_planes", datos.umbrales_planes, usuario)
        cambios["umbrales_planes"] = datos.umbrales_planes
    if datos.presupuesto_openai_usd is not None:
        if datos.presupuesto_openai_usd < 0:
            raise HTTPException(400, "El presupuesto no puede ser negativo.")
        db.guardar_config("presupuesto_openai_usd", datos.presupuesto_openai_usd, usuario)
        cambios["presupuesto_openai_usd"] = datos.presupuesto_openai_usd
    if datos.vercel_uso_manual_gb is not None:
        if datos.vercel_uso_manual_gb < 0:
            raise HTTPException(400, "Los GB no pueden ser negativos.")
        v = {"gb": datos.vercel_uso_manual_gb, "fecha": _iso(_ahora()), "por": usuario}
        db.guardar_config("vercel_uso_manual", v, usuario)
        cambios["vercel_uso_manual"] = v
    if not cambios:
        raise HTTPException(400, "No vino nada para cambiar.")
    return {"ok": True, "cambios": cambios}
