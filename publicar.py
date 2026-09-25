"""
publicar.py — El módulo de publicación de la herramienta, con un switch por canal.

Lo usan los scripts de conectores/ hoy y la pestaña "Publicar" del chatbot mañana. Una sola implementación.

EL SWITCH — dos claves de configuración, una por canal, con cuatro valores posibles:
    PUBLICAR_WORDPRESS = "apagado" | "simulado" | "borrador" | "real"
    PUBLICAR_INSTAGRAM = "apagado" | "simulado" | "real"

    apagado   el canal no está disponible: la función devuelve un aviso y no hace nada.
    simulado  arma la pieza tal cual se mandaría, la muestra y la anota en el registro. NO llama a la API.
    borrador  (solo WordPress) crea la entrada en borrador. No se publica ni sale por newsletter.
              Una persona la publica desde el panel de WordPress: esa es la aprobación humana.
    real      publica de verdad. Instagram no tiene borradores: "real" = lo ven los seguidores.

REGLA DURA: el endpoint que publica solo se llama si el modo es exactamente "real".
Cualquier otro valor (incluida una clave mal escrita, vacía o ausente) NO publica. Ausente = "apagado".

Arranque acordado el 23/9: WordPress en "borrador", Instagram en "simulado".

De dónde lee la configuración:
    - en la app: el dict de st.secrets (misma forma que las demás claves: sueltas, arriba de [usuarios]).
    - en los scripts: el entorno, cargado desde clave.env (mismo nombre de claves).
Claves de acceso: WP_SITE, WP_USER, WP_APP_PASSWORD, META_IG_TOKEN, META_IG_USER_ID.

Imágenes: Instagram no acepta archivos, pide una URL pública y baja la imagen desde ahí. Por eso toda
imagen pasa primero por la biblioteca de medios de WordPress (subir_imagen_wordpress) y esa URL sirve
para los dos canales. La imagen queda en la biblioteca con título, fecha y etiquetas: en unos meses,
eso es el banco de imágenes.

Registro: cada llamada (simulada o real) deja una línea en conectores/registro_publicaciones.jsonl,
con fecha, canal, modo, quién, y qué se mandó. No va al repo.
"""
import os, json, base64, time, datetime, mimetypes, urllib.request, urllib.parse, urllib.error

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "registro_publicaciones.jsonl")
MODOS_WP = ("apagado", "simulado", "borrador", "real")
MODOS_IG = ("apagado", "simulado", "real")
MODOS_FB = ("apagado", "simulado", "real")    # real requiere META_FB_PAGE_ID y META_FB_PAGE_TOKEN (24/9)
MODOS_YT = ("apagado", "simulado", "privado", "real")   # (25/9) privado = sube el video como PRIVADO (se revisa en YouTube Studio)
YT_TOKEN_URL = "https://oauth2.googleapis.com/token"
YT_UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"
IG_HOST = "https://graph.instagram.com/v21.0"
FB_HOST = "https://graph.facebook.com/v21.0"

# Gancho opcional: la app lo reemplaza para guardar el registro también en Supabase.
REGISTRAR_EXTRA = None


# ----------------------------------------------------------------------------- configuración

def _cargar_env(path):
    if os.path.exists(path):
        for ln in open(path, encoding="utf-8"):
            ln = ln.strip()
            if ln and not ln.startswith("#") and "=" in ln:
                k, v = ln.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


class Config:
    """Lee las claves de un dict (st.secrets) o del entorno (clave.env). Nunca las imprime."""

    def __init__(self, fuente=None):
        if fuente is None:
            _cargar_env(os.path.join(BASE, "clave.env"))
            fuente = os.environ
        g = lambda k: str(fuente.get(k, "") or "").strip()
        self.modo_wp = g("PUBLICAR_WORDPRESS").lower() or "apagado"
        self.modo_ig = g("PUBLICAR_INSTAGRAM").lower() or "apagado"
        self.modo_fb = g("PUBLICAR_FACEBOOK").lower() or "apagado"
        if self.modo_wp not in MODOS_WP:
            self.modo_wp = "apagado"       # valor desconocido = no publicar
        if self.modo_ig not in MODOS_IG:
            self.modo_ig = "apagado"
        if self.modo_fb not in MODOS_FB:
            self.modo_fb = "apagado"
        self.modo_yt = g("PUBLICAR_YOUTUBE").lower() or "apagado"
        if self.modo_yt not in MODOS_YT:
            self.modo_yt = "apagado"
        # YouTube: el permiso otorgado (youtube_token.json) puede venir pegado en un secret
        # (YOUTUBE_TOKEN_JSON) o como archivo al lado de clave.env. Nunca se imprime.
        self.yt_token_json = g("YOUTUBE_TOKEN_JSON")
        if not self.yt_token_json:
            for p in (os.path.join(BASE, "youtube_token.json"),
                      os.path.join(BASE, "fva-transcripcion", "youtube_token.json"),
                      os.path.join(os.path.dirname(BASE), "fva-transcripcion", "youtube_token.json")):
                if os.path.exists(p):
                    self.yt_token_json = open(p, encoding="utf-8").read()
                    break
        self.wp_site = g("WP_SITE").replace("https://", "").replace("http://", "").strip("/")
        self.wp_user = g("WP_USER")
        self.wp_pass = g("WP_APP_PASSWORD")
        self.ig_token = g("META_IG_TOKEN")
        self.ig_id = g("META_IG_USER_ID")
        self.fb_page_id = g("META_FB_PAGE_ID")
        self.fb_token = g("META_FB_PAGE_TOKEN")

    def resumen(self):
        return {"wordpress": self.modo_wp, "instagram": self.modo_ig, "facebook": self.modo_fb, "youtube": self.modo_yt,
                "yt_configurado": bool(self.yt_token_json),
                "wp_configurado": bool(self.wp_site and self.wp_user and self.wp_pass),
                "ig_configurado": bool(self.ig_token and self.ig_id),
                "fb_configurado": bool(self.fb_page_id and self.fb_token)}


# ----------------------------------------------------------------------------- utilidades

def _registrar(entrada):
    entrada = {"fecha": datetime.datetime.now().isoformat(timespec="seconds"), **entrada}
    try:
        with open(REGISTRO, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entrada, ensure_ascii=False) + "\n")
    except Exception:
        pass                                   # en la nube el disco puede no ser escribible
    if REGISTRAR_EXTRA:
        try:
            REGISTRAR_EXTRA(entrada)
        except Exception:
            pass
    return entrada


def _http(url, method="GET", headers=None, data=None):
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.load(r), None
    except urllib.error.HTTPError as e:
        try:
            return None, json.load(e)
        except Exception:
            return None, {"code": e.code, "message": e.read().decode("utf-8", "replace")[:300]}
    except Exception as e:
        return None, {"message": str(e)[:300]}


def _wp_headers(cfg, extra=None):
    auth = "Basic " + base64.b64encode(f"{cfg.wp_user}:{cfg.wp_pass}".encode()).decode()
    h = {"Authorization": auth, "User-Agent": "fva-herramienta/0.1"}
    h.update(extra or {})
    return h


def _wp_api(cfg, path):
    return f"https://{cfg.wp_site}/wp-json/wp/v2/{path}"


# ----------------------------------------------------------------------------- Banco de imágenes
# (24/9) El banco es la biblioteca de medios de WordPress: URL pública (Instagram la exige), una
# imagen sirve para todos los canales, y las etiquetas van en el título/alt/descripción del adjunto.
# Julián arma carpetas en Drive con etiquetas en el nombre; un script las sube acá (card Trello).

def buscar_imagenes_banco(cfg, consulta, n=6):
    """Busca imágenes en la biblioteca de medios por palabras (título, alt, descripción).
    Devuelve [{id, url, miniatura, titulo}]. Sin credenciales o sin resultados: lista vacía.
    Prueba primero la consulta entera; si no hay nada, palabra por palabra (unión)."""
    if not cfg.wp_site:
        return []
    consulta = (consulta or "").strip()
    palabras = [p for p in consulta.replace(",", " ").split() if len(p) > 2]
    intentos = [consulta] + palabras if consulta else []
    vistos, out = set(), []
    for q in intentos:
        if len(out) >= n:
            break
        url = _wp_api(cfg, "media") + "?" + urllib.parse.urlencode({
            "search": q, "media_type": "image", "per_page": n, "orderby": "date", "order": "desc",
            "_fields": "id,source_url,title,alt_text,media_details"})
        r, err = _http(url, headers=_wp_headers(cfg) if cfg.wp_user and cfg.wp_pass else {"User-Agent": "fva-herramienta/0.1"})
        if not r:
            continue
        for m in r:
            if m["id"] in vistos:
                continue
            vistos.add(m["id"])
            sizes = ((m.get("media_details") or {}).get("sizes") or {})
            mini = (sizes.get("medium") or sizes.get("thumbnail") or {}).get("source_url") or m["source_url"]
            out.append({"id": m["id"], "url": m["source_url"], "miniatura": mini,
                        "titulo": ((m.get("title") or {}).get("rendered") or m.get("alt_text") or "")[:80]})
            if len(out) >= n:
                break
    return out


def imagenes_recientes_banco(cfg, n=6):
    """Las últimas imágenes subidas, para cuando la búsqueda no encuentra nada."""
    return buscar_imagenes_banco(cfg, "", n) or _recientes(cfg, n)


def _recientes(cfg, n):
    if not cfg.wp_site:
        return []
    url = _wp_api(cfg, "media") + "?" + urllib.parse.urlencode({
        "media_type": "image", "per_page": n, "orderby": "date", "order": "desc",
        "_fields": "id,source_url,title,alt_text,media_details"})
    r, err = _http(url, headers=_wp_headers(cfg) if cfg.wp_user and cfg.wp_pass else {"User-Agent": "fva-herramienta/0.1"})
    out = []
    for m in (r or []):
        sizes = ((m.get("media_details") or {}).get("sizes") or {})
        mini = (sizes.get("medium") or sizes.get("thumbnail") or {}).get("source_url") or m["source_url"]
        out.append({"id": m["id"], "url": m["source_url"], "miniatura": mini,
                    "titulo": ((m.get("title") or {}).get("rendered") or m.get("alt_text") or "")[:80]})
    return out


# ----------------------------------------------------------------------------- WordPress

def subir_imagen_wordpress(cfg, ruta_o_bytes, nombre, titulo="", etiquetas=None, quien="", pieza=""):
    """
    Sube una imagen a la biblioteca de medios del sitio. Devuelve {"ok", "url", "id", "modo"}.
    En "simulado" y "apagado" no sube nada. Lo que sube queda con título, texto alternativo,
    y en la descripción: fecha, pieza y etiquetas (así se arma el banco solo).
    """
    modo = cfg.modo_wp
    datos = ruta_o_bytes if isinstance(ruta_o_bytes, (bytes, bytearray)) else open(ruta_o_bytes, "rb").read()
    tipo = mimetypes.guess_type(nombre)[0] or "image/jpeg"
    desc = f"Subida por la herramienta el {datetime.date.today()}" + (f" para «{pieza}»" if pieza else "") \
           + (f". Etiquetas: {', '.join(etiquetas)}" if etiquetas else "") + (f". Por {quien}" if quien else "")
    base = {"canal": "wordpress", "accion": "subir_imagen", "modo": modo, "quien": quien,
            "nombre": nombre, "bytes": len(datos), "titulo": titulo, "etiquetas": etiquetas or []}
    if modo in ("apagado", "simulado"):
        _registrar({**base, "resultado": "no se subió (modo " + modo + ")"})
        return {"ok": modo == "simulado", "modo": modo, "url": None, "id": None,
                "aviso": "Simulado: la imagen no se subió." if modo == "simulado" else "WordPress está apagado."}
    if not (cfg.wp_site and cfg.wp_user and cfg.wp_pass):
        return {"ok": False, "modo": modo, "aviso": "Faltan las claves de WordPress."}
    h = _wp_headers(cfg, {"Content-Type": tipo,
                          "Content-Disposition": f'attachment; filename="{urllib.parse.quote(nombre)}"'})
    r, err = _http(_wp_api(cfg, "media"), "POST", h, datos)
    if not r:
        _registrar({**base, "resultado": "error", "error": err})
        return {"ok": False, "modo": modo, "aviso": "WordPress no aceptó la imagen: " + json.dumps(err, ensure_ascii=False)[:200]}
    # título / alt / descripción, en una segunda llamada (el POST de media no los toma bien)
    meta = json.dumps({"title": titulo or nombre, "alt_text": titulo or nombre, "description": desc}).encode()
    _http(_wp_api(cfg, f"media/{r['id']}"), "POST", _wp_headers(cfg, {"Content-Type": "application/json"}), meta)
    _registrar({**base, "resultado": "subida", "id": r["id"], "url": r.get("source_url")})
    return {"ok": True, "modo": modo, "url": r.get("source_url"), "id": r["id"]}


def publicar_wordpress(cfg, titulo, contenido_html, imagen_id=None, categorias=None, quien="", fecha=None):
    """
    Crea una entrada. Según el modo:
      apagado  -> no hace nada
      simulado -> devuelve la pieza armada, no llama a la API
      borrador -> crea la entrada con status=draft (no sale por newsletter)
      real     -> status=publish (sale por newsletter si el sitio lo tiene activo)
                  con `fecha` futura -> status=future: WordPress la publica solo ese día (Frase del día)
    `fecha`: "AAAA-MM-DDTHH:MM:SS" en la hora del sitio. En borrador la fecha queda guardada pero no publica.
    Devuelve {"ok", "modo", "estado", "id", "link_editar", "aviso", "pieza"}.
    """
    modo = cfg.modo_wp
    pieza = {"title": titulo, "content": contenido_html, "status": "publish" if modo == "real" else "draft"}
    if fecha:
        pieza["date"] = fecha
        if modo == "real" and fecha > datetime.datetime.now().isoformat(timespec="seconds"):
            pieza["status"] = "future"
    if imagen_id:
        pieza["featured_media"] = imagen_id
    if categorias:
        pieza["categories"] = categorias
    base = {"canal": "wordpress", "accion": "entrada", "modo": modo, "quien": quien, "titulo": titulo}
    if modo == "apagado":
        _registrar({**base, "resultado": "no se hizo nada (apagado)"})
        return {"ok": False, "modo": modo, "aviso": "WordPress está apagado.", "pieza": pieza}
    if modo == "simulado":
        _registrar({**base, "resultado": "simulado", "pieza": pieza})
        return {"ok": True, "modo": modo, "estado": "simulado", "pieza": pieza,
                "aviso": "Simulado: así quedaría la entrada. No se mandó nada a WordPress."}
    if not (cfg.wp_site and cfg.wp_user and cfg.wp_pass):
        return {"ok": False, "modo": modo, "aviso": "Faltan las claves de WordPress.", "pieza": pieza}
    # --- de acá para abajo se llama a la API. status sale de "draft" SOLO si modo == "real" (ver arriba).
    assert pieza["status"] in (("publish", "future") if modo == "real" else ("draft",))
    r, err = _http(_wp_api(cfg, "posts"), "POST", _wp_headers(cfg, {"Content-Type": "application/json"}),
                   json.dumps(pieza).encode())
    if not r:
        _registrar({**base, "resultado": "error", "error": err})
        return {"ok": False, "modo": modo, "aviso": "WordPress no aceptó la entrada: " + json.dumps(err, ensure_ascii=False)[:200], "pieza": pieza}
    link_editar = f"https://{cfg.wp_site}/wp-admin/post.php?post={r['id']}&action=edit"
    _registrar({**base, "resultado": r.get("status"), "id": r["id"], "link": r.get("link")})
    return {"ok": True, "modo": modo, "estado": r.get("status"), "id": r["id"], "link_editar": link_editar,
            "link": r.get("link"), "pieza": pieza,
            "aviso": {"draft": "Borrador creado. Se revisa y se publica desde WordPress.",
                      "future": f"PROGRAMADA para {fecha}. WordPress la publica sola ese día."}.get(r.get("status"), "PUBLICADA.")}


# ----------------------------------------------------------------------------- Instagram

def publicar_instagram(cfg, imagen_url, texto, quien=""):
    """
    Publica una imagen con texto. Según el modo:
      apagado  -> no hace nada
      simulado -> devuelve la pieza armada (imagen + texto tal cual saldría), no llama a la API
      real     -> contenedor + media_publish. LO VEN LOS SEGUIDORES.
    Instagram no tiene borradores. Devuelve {"ok", "modo", "id", "permalink", "aviso", "pieza"}.
    """
    modo = cfg.modo_ig
    pieza = {"image_url": imagen_url, "caption": texto}
    base = {"canal": "instagram", "accion": "imagen", "modo": modo, "quien": quien, "pieza": pieza}
    if modo == "apagado":
        _registrar({**base, "resultado": "no se hizo nada (apagado)"})
        return {"ok": False, "modo": modo, "aviso": "Instagram está apagado.", "pieza": pieza}
    if modo == "simulado":
        _registrar({**base, "resultado": "simulado"})
        return {"ok": True, "modo": modo, "pieza": pieza,
                "aviso": "Simulado: así quedaría el posteo. No se mandó nada a Instagram. "
                         "Para publicarlo hoy: bajar la imagen, copiar el texto y subirlo desde el teléfono."}
    if modo != "real":                     # regla dura: no hay otro camino a la API
        return {"ok": False, "modo": modo, "aviso": "Modo desconocido; no se publica.", "pieza": pieza}
    if not (cfg.ig_token and cfg.ig_id):
        return {"ok": False, "modo": modo, "aviso": "Faltan las claves de Instagram.", "pieza": pieza}
    if not imagen_url.startswith("https://"):
        return {"ok": False, "modo": modo, "aviso": "Instagram necesita una URL pública https de la imagen.", "pieza": pieza}

    def call(path, params, method="POST"):
        params = dict(params, access_token=cfg.ig_token)
        data = urllib.parse.urlencode(params).encode()
        url = f"{IG_HOST}/{path}"
        if method == "GET":
            return _http(url + "?" + data.decode(), "GET")
        return _http(url, "POST", {"Content-Type": "application/x-www-form-urlencoded"}, data)

    r, err = call(f"{cfg.ig_id}/media", {"image_url": imagen_url, "caption": texto})
    if not r:
        _registrar({**base, "resultado": "error contenedor", "error": err})
        return {"ok": False, "modo": modo, "aviso": "Instagram no aceptó la imagen: " + json.dumps(err, ensure_ascii=False)[:200], "pieza": pieza}
    cid = r["id"]
    for _ in range(12):                    # Instagram procesa la imagen; esperar a que esté lista
        s, _e = call(cid, {"fields": "status_code,status"}, "GET")
        if s and s.get("status_code") == "FINISHED":
            break
        if s and s.get("status_code") == "ERROR":
            _registrar({**base, "resultado": "error procesando", "error": s})
            return {"ok": False, "modo": modo, "aviso": "Instagram no pudo procesar la imagen: " + str(s.get("status"))[:200], "pieza": pieza}
        time.sleep(3)
    r, err = call(f"{cfg.ig_id}/media_publish", {"creation_id": cid})
    if not r:
        _registrar({**base, "resultado": "error publicar", "error": err})
        return {"ok": False, "modo": modo, "aviso": "No se pudo publicar: " + json.dumps(err, ensure_ascii=False)[:200], "pieza": pieza}
    m, _e = call(r["id"], {"fields": "permalink"}, "GET")
    permalink = (m or {}).get("permalink")
    _registrar({**base, "resultado": "PUBLICADO", "id": r["id"], "permalink": permalink})
    return {"ok": True, "modo": modo, "id": r["id"], "permalink": permalink, "pieza": pieza,
            "aviso": "PUBLICADO en Instagram."}


# ----------------------------------------------------------------------------- Facebook (solo simulado)

def publicar_facebook(cfg, imagen_url, texto, quien="", fecha=None):
    """
    Publica en la página de Facebook de la Fundación (Graph API). Según el modo:
      apagado  -> no hace nada
      simulado -> arma la pieza y la muestra; no llama a la API
      real     -> con imagen: POST /{page}/photos (url + caption); sin imagen: POST /{page}/feed (message).
                  Con `fecha` futura (ISO): publicación PROGRAMADA por Facebook (published=false +
                  scheduled_publish_time), entre 10 minutos y 30 días. LO VEN LOS SEGUIDORES al publicarse.
    Requiere META_FB_PAGE_ID y META_FB_PAGE_TOKEN (token de página, permisos pages_manage_posts).
    """
    modo = cfg.modo_fb
    pieza = {"image_url": imagen_url, "message": texto, "fecha_programada": fecha}
    base = {"canal": "facebook", "accion": "post", "modo": modo, "quien": quien, "pieza": pieza}
    if modo == "apagado":
        _registrar({**base, "resultado": "no se hizo nada (apagado)"})
        return {"ok": False, "modo": modo, "aviso": "Facebook está apagado.", "pieza": pieza}
    if modo == "simulado":
        _registrar({**base, "resultado": "simulado"})
        return {"ok": True, "modo": modo, "pieza": pieza,
                "aviso": "Simulado: así quedaría el posteo en Facebook. No se mandó nada. "
                         "Para publicarlo hoy: copiá el texto y subilo desde la página."}
    if modo != "real":                     # regla dura
        return {"ok": False, "modo": modo, "aviso": "Modo desconocido; no se publica.", "pieza": pieza}
    if not (cfg.fb_page_id and cfg.fb_token):
        return {"ok": False, "modo": modo, "aviso": "Faltan las claves de Facebook (META_FB_PAGE_ID / META_FB_PAGE_TOKEN).", "pieza": pieza}

    params = {"access_token": cfg.fb_token}
    if fecha:
        try:
            ts = int(datetime.datetime.fromisoformat(fecha).timestamp())
        except Exception:
            return {"ok": False, "modo": modo, "aviso": "Fecha inválida.", "pieza": pieza}
        if ts < time.time() + 600:
            return {"ok": False, "modo": modo, "aviso": "Facebook exige programar con al menos 10 minutos de anticipación.", "pieza": pieza}
        params.update({"published": "false", "scheduled_publish_time": str(ts)})
    if imagen_url:
        if not imagen_url.startswith("https://"):
            return {"ok": False, "modo": modo, "aviso": "Facebook necesita una URL pública https de la imagen.", "pieza": pieza}
        params.update({"url": imagen_url, "caption": texto})
        path = f"{cfg.fb_page_id}/photos"
    else:
        params.update({"message": texto})
        path = f"{cfg.fb_page_id}/feed"
    data = urllib.parse.urlencode(params).encode()
    r, err = _http(f"{FB_HOST}/{path}", "POST", {"Content-Type": "application/x-www-form-urlencoded"}, data)
    if not r:
        _registrar({**base, "resultado": "error", "error": err})
        return {"ok": False, "modo": modo, "aviso": "Facebook no aceptó el posteo: " + json.dumps(err, ensure_ascii=False)[:200], "pieza": pieza}
    post_id = r.get("post_id") or r.get("id")
    _registrar({**base, "resultado": "PROGRAMADO" if fecha else "PUBLICADO", "id": post_id})
    return {"ok": True, "modo": modo, "id": post_id, "pieza": pieza,
            "permalink": f"https://www.facebook.com/{post_id}" if post_id else None,
            "aviso": (f"PROGRAMADO en Facebook para {fecha}." if fecha else "PUBLICADO en Facebook.")}


# ----------------------------------------------------------------------------- uso desde la terminal

if __name__ == "__main__":
    cfg = Config()
    print("Modos activos:", json.dumps(cfg.resumen(), ensure_ascii=False))
    print("Registro:", REGISTRO)


# ----------------------------------------------------------------------------- YouTube (25/9)

def _yt_access_token(cfg):
    """Cambia el refresh_token guardado por un access_token vigente (1 h). Sin librerías de Google."""
    try:
        t = json.loads(cfg.yt_token_json)
    except Exception:
        return None, {"message": "YOUTUBE_TOKEN_JSON / youtube_token.json no es un JSON válido"}
    data = urllib.parse.urlencode({"client_id": t.get("client_id"), "client_secret": t.get("client_secret"),
                                   "refresh_token": t.get("refresh_token"), "grant_type": "refresh_token"}).encode()
    r, err = _http(YT_TOKEN_URL, "POST", {"Content-Type": "application/x-www-form-urlencoded"}, data)
    if not r or not r.get("access_token"):
        return None, err or r
    return r["access_token"], None


def publicar_youtube(cfg, video_bytes, titulo, descripcion, quien="", fecha=None, etiquetas=None, nombre_archivo="video.mp4"):
    """Sube un video al canal. Modos:
       apagado  -> nada
       simulado -> arma la ficha (título, descripción) y la muestra; no sube
       privado  -> sube el video como PRIVADO (se revisa y se publica desde YouTube Studio)
       real     -> sube como PÚBLICO; con fecha futura lo deja privado con publishAt (YouTube lo publica solo)
    Con la app de Google en modo Prueba, YouTube deja los videos subidos por API en privado
    hasta que la app pase la verificación, aunque se pida público."""
    modo = cfg.modo_yt
    pieza = {"title": (titulo or "")[:100], "description": (descripcion or "")[:5000],
             "tags": list(etiquetas or [])[:20], "fecha_programada": fecha}
    base = {"canal": "youtube", "accion": "video", "modo": modo, "quien": quien, "titulo": pieza["title"],
            "archivo": nombre_archivo, "bytes": len(video_bytes or b"")}
    if modo == "apagado":
        _registrar({**base, "resultado": "no se hizo nada (apagado)"})
        return {"ok": False, "modo": modo, "aviso": "YouTube está apagado.", "pieza": pieza}
    if modo == "simulado":
        _registrar({**base, "resultado": "simulado", "pieza": pieza})
        return {"ok": True, "modo": modo, "pieza": pieza,
                "aviso": "Simulado: así quedaría la ficha del video en YouTube. No se subió nada."}
    if modo not in ("privado", "real"):
        return {"ok": False, "modo": modo, "aviso": "Modo desconocido; no se sube.", "pieza": pieza}
    if not cfg.yt_token_json:
        return {"ok": False, "modo": modo, "aviso": "Falta el permiso de YouTube (YOUTUBE_TOKEN_JSON o youtube_token.json).", "pieza": pieza}
    if not video_bytes:
        return {"ok": False, "modo": modo, "aviso": "Falta el archivo de video.", "pieza": pieza}
    if not pieza["title"]:
        return {"ok": False, "modo": modo, "aviso": "YouTube exige un título.", "pieza": pieza}
    token, err = _yt_access_token(cfg)
    if not token:
        _registrar({**base, "resultado": "error", "error": err})
        return {"ok": False, "modo": modo, "aviso": "No pude renovar el permiso de YouTube: " + json.dumps(err, ensure_ascii=False)[:200], "pieza": pieza}
    status = {"privacyStatus": "private", "selfDeclaredMadeForKids": False}
    if modo == "real":
        if fecha:
            try:
                dt = datetime.datetime.fromisoformat(fecha)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=datetime.timezone(datetime.timedelta(hours=-3)))
                status["publishAt"] = dt.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            except Exception:
                return {"ok": False, "modo": modo, "aviso": "Fecha inválida.", "pieza": pieza}
        else:
            status["privacyStatus"] = "public"
    meta = {"snippet": {"title": pieza["title"], "description": pieza["description"], "tags": pieza["tags"],
                        "categoryId": "22"}, "status": status}
    mime = mimetypes.guess_type(nombre_archivo)[0] or "video/mp4"
    # 1) abrir la sesión de subida reanudable
    req = urllib.request.Request(YT_UPLOAD_URL, data=json.dumps(meta).encode("utf-8"), method="POST", headers={
        "Authorization": "Bearer " + token, "Content-Type": "application/json; charset=UTF-8",
        "X-Upload-Content-Type": mime, "X-Upload-Content-Length": str(len(video_bytes))})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            upload_url = r.headers.get("Location")
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", "replace")[:300]
        _registrar({**base, "resultado": "error", "error": err})
        return {"ok": False, "modo": modo, "aviso": "YouTube no abrió la subida: " + err, "pieza": pieza}
    if not upload_url:
        return {"ok": False, "modo": modo, "aviso": "YouTube no devolvió la URL de subida.", "pieza": pieza}
    # 2) mandar los bytes
    req2 = urllib.request.Request(upload_url, data=video_bytes, method="PUT",
                                  headers={"Content-Type": mime, "Content-Length": str(len(video_bytes))})
    try:
        with urllib.request.urlopen(req2, timeout=900) as r:
            res = json.load(r)
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", "replace")[:300]
        _registrar({**base, "resultado": "error", "error": err})
        return {"ok": False, "modo": modo, "aviso": "YouTube rechazó el video: " + err, "pieza": pieza}
    vid = res.get("id")
    estado = (res.get("status") or {}).get("privacyStatus")
    link = f"https://www.youtube.com/watch?v={vid}" if vid else None
    _registrar({**base, "resultado": "SUBIDO", "id": vid, "privacidad": estado, "link": link, "pieza": pieza})
    aviso = {"private": "Subido como PRIVADO: revisalo y publicalo desde YouTube Studio.",
             "public": "Subido y PÚBLICO.", "unlisted": "Subido como no listado."}.get(estado, f"Subido ({estado}).")
    if status.get("publishAt"):
        aviso = f"Subido y programado: YouTube lo publica solo el {fecha[:16].replace('T', ' ')}."
    return {"ok": True, "modo": modo, "id": vid, "link": link, "privacidad": estado, "pieza": pieza, "aviso": aviso}
