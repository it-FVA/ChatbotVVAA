"""
canales.py — El registro ÚNICO de los canales de publicación (3/11, revisión 5.2 punto 8).

Antes los canales estaban definidos en siete lugares (publicar.Config, programar_frases.CANALES_POSIBLES, chat_rutas.CANALES,
publicar_rutas.CANAL_TXT, las listas de la web…) y el despacho «qué función llama a cada canal» estaba escrito dos veces (la cola y
el envío directo) y ya divergían. Ahora todo sale de acá:

  - publicar.Config lee el modo de cada canal con `variable` y lo valida contra `modos`.
  - publicar.enviar_pieza(cfg, pieza, quien) despacha con `foto` / `video`: lo usan la cola, el envío directo y la aprobación.
  - api/chat_rutas y api/publicar_rutas sacan de acá los nombres, los formatos, qué va a la cola y qué pasa por aprobación.
  - programar_frases.CANALES_POSIBLES sale de SALIDAS_FRASE (por dónde sale la Frase del día).
  - La web recibe la lista por GET /yo (`canales`), GET /publicaciones/modos y GET /publicar/opciones; no tiene listas propias.

Para agregar un canal: una entrada en CANALES (y en SALIDAS_FRASE si la Frase del día sale por ahí), el conector en publicar.py
(o un módulo propio) y la variable PUBLICAR_<CANAL> en api/variables_entorno.py. Nada más: ni la cola, ni las rutas, ni la web.

Cada función `foto` / `video` recibe (cfg, pieza, quien, fecha):
  pieza  la fila de la tabla `publicaciones` (o un dict con las mismas claves: canal, titulo, texto, imagen_url, fecha_programada,
         resultado{video_url, formato, texto_imagen, autor…}),
  fecha  'AAAA-MM-DDTHH:MM:SS' en hora Argentina SOLO si la fecha programada está en el futuro (el proveedor programa solo);
         None si ya venció (la cola la publica ahora) o no tiene fecha.
Devuelven el dict del conector: {"ok", "modo", "aviso", …}.
"""
from dataclasses import dataclass, field
from typing import Callable, Optional

MODOS_WP = ("apagado", "simulado", "borrador", "real")
MODOS_RED = ("apagado", "simulado", "real")              # Instagram, Facebook, mail: real = lo ven los seguidores / llega el mail
MODOS_YT = ("apagado", "simulado", "privado", "real")    # (25/9) privado = sube el video como PRIVADO (se revisa en YouTube Studio)
MODOS_WA = ("apagado", "simulado")                      # (2/11) WhatsApp: prototipo; «real» todavía no existe (publicar.publicar_whatsapp)

CLAVES_WP = ("WP_SITE", "WP_USER", "WP_APP_PASSWORD")
CLAVES_IG = ("META_IG_TOKEN", "META_IG_USER_ID")
CLAVES_FB = ("META_FB_PAGE_ID", "META_FB_PAGE_TOKEN")
CLAVES_PERFIT = ("PERFIT_API_KEY", "PERFIT_CUENTA", "PERFIT_TRIGGER_URL", "PERFIT_LISTA_FRASE")


# ----------------------------------------------------------------------------- el despacho por canal
# (cada función importa publicar adentro: canales.py no puede importar publicar al cargarse porque publicar lo importa a él)

def _texto(p):
    return p.get("texto") or ""


def _extra(p):
    return p.get("resultado") or {}


def _historia(p):
    return _extra(p).get("formato") == "historia"


def _wordpress(cfg, p, quien, fecha):
    import publicar
    video_url = _extra(p).get("video_url")
    imagen = p.get("imagen_url")
    # la imagen ya está en la biblioteca: va como destacada (en simulado no se consulta a WordPress)
    imagen_id = publicar.media_id_por_url(cfg, imagen) if (imagen and cfg.modo("wordpress") in ("borrador", "real")) else None
    contenido = publicar.html_video(video_url, _texto(p)) if video_url else _texto(p)
    return publicar.publicar_wordpress(cfg, p.get("titulo") or "", contenido, imagen_id=imagen_id, quien=quien, fecha=fecha)


def _instagram(cfg, p, quien, fecha):
    import publicar
    return publicar.publicar_instagram(cfg, p.get("imagen_url") or "", _texto(p), quien=quien, historia=_historia(p))


def _instagram_video(cfg, p, quien, fecha):
    import publicar
    return publicar.publicar_instagram_video(cfg, _extra(p)["video_url"], _texto(p), quien=quien, historia=_historia(p))


def _facebook(cfg, p, quien, fecha):
    import publicar
    return publicar.publicar_facebook(cfg, p.get("imagen_url"), _texto(p), quien=quien, fecha=fecha)


def _facebook_video(cfg, p, quien, fecha):
    import publicar
    return publicar.publicar_facebook_video(cfg, _extra(p)["video_url"], _texto(p), quien=quien, fecha=fecha, titulo=p.get("titulo") or "")


def _instagram_carrusel(cfg, p, quien, fecha):
    import publicar
    return publicar.publicar_instagram_carrusel(cfg, _extra(p).get("imagenes") or [], _texto(p), quien=quien)


def _facebook_carrusel(cfg, p, quien, fecha):
    import publicar
    return publicar.publicar_facebook_fotos(cfg, _extra(p).get("imagenes") or [], _texto(p), quien=quien, fecha=fecha)


def _youtube(cfg, p, quien, fecha):
    """Sin video (solo pasa en «Ver simulado»): la ficha con bytes vacíos."""
    import publicar
    return publicar.publicar_youtube(cfg, b"", p.get("titulo") or "", _texto(p), quien=quien, fecha=fecha)


def _youtube_video(cfg, p, quien, fecha):
    import publicar
    video_url = _extra(p)["video_url"]
    datos, err = (b"", None)
    if cfg.modo("youtube") in ("privado", "real"):      # en simulado no hace falta bajar el recorte
        datos, err = publicar.bajar_bytes(video_url)
    if err:
        return {"ok": False, "modo": cfg.modo("youtube"), "aviso": f"No pude bajar el recorte de WordPress: {err}"}
    return publicar.publicar_youtube(cfg, datos or b"", p.get("titulo") or "", _texto(p), quien=quien, fecha=fecha,
                                     nombre_archivo=video_url.rsplit("/", 1)[-1] or "clip.mp4")


def _mail(cfg, p, quien, fecha):
    """(26/10) Frase del día por mail: arma la lista de destinatarios y la pieza queda 'enviando'; las tandas las manda
    frase_mail.avanzar al final de cada pasada de la cola (200 por hora, límite de Perfit)."""
    import db, frase_mail, perfit
    return frase_mail.iniciar(p, db, perfit)


def _whatsapp(cfg, p, quien, fecha):
    import publicar
    return publicar.publicar_whatsapp(cfg, p.get("imagen_url"), _texto(p), quien=quien)


def _home(cfg, p, quien, fecha):
    """(2/11) La Frase del día en la home del sitio: una entrada del tipo «frase» (texto + autor), la lista el widget de la home.
    Va con la fecha programada aunque ya haya vencido: la entrada queda fechada el día de la frase."""
    import publicar
    ex = _extra(p)
    return publicar.publicar_frase_home(cfg, ex.get("texto_imagen") or _texto(p), ex.get("autor"), fecha=p.get("fecha_programada"), quien=quien)


# ----------------------------------------------------------------------------- el registro

@dataclass(frozen=True)
class Canal:
    clave: str                      # el valor de publicaciones.canal
    nombre: str                     # cómo lo nombra la API y el asistente («WordPress»)
    texto: str                      # el nombre visible en la web («Blogpost», 16/10: la entrada es un blogpost; el newsletter es el mail)
    variable: str                   # PUBLICAR_* con el modo del canal
    modos: tuple                    # modos válidos; cualquier otro valor (o ausente) = apagado
    detalle: str = ""               # la línea de la tarjeta de Diseñar
    hereda: Optional[str] = None    # sin la variable, toma el modo de este otro canal (home → wordpress)
    claves: tuple = ()              # variables que tienen que estar cargadas para que el canal esté «configurado»
    formato: Optional[str] = None   # formato de foto que sugiere Diseñar (cuadrado | vertical)
    en_disenar: bool = False        # aparece en Diseñar (tarjeta) y en el menú «Canales»
    icono: str = "megafono"         # icono del menú (web/src/componentes/Iconos.tsx)
    requiere_titulo: bool = False
    acepta_aprobacion: bool = False  # «Enviar a aprobación» existe cuando el modo real es real o borrador
    cola: str = "nunca"             # con fecha: "siempre" va a la cola | "salvo_real" (en real programa el proveedor) | "nunca"
    frase: Optional[str] = None     # nombre en la Frase del día (None = la frase no sale por acá)
    foto: Optional[Callable] = field(default=None, compare=False)    # (cfg, pieza, quien, fecha) -> resultado
    video: Optional[Callable] = field(default=None, compare=False)   # idem con resultado.video_url; None = usa `foto`
    carrusel: Optional[Callable] = field(default=None, compare=False)  # (5/11, Franco) idem con resultado.imagenes (2 o más); None = usa `foto`

    def va_a_la_cola(self, modo):
        """¿Una pieza con fecha va a la cola (en vez de programarla el proveedor)?"""
        if modo == "apagado":
            return False
        return self.cola == "siempre" or (self.cola == "salvo_real" and modo != "real")

    def puede_proponer(self, modo_real):
        """«Enviar a aprobación» existe cuando el canal real está en real, borrador o privado (YouTube) (si no, no hay a dónde mandarla cuando la aprueben)."""
        return self.acepta_aprobacion and modo_real in ("real", "borrador", "privado")

    def para_web(self):
        return {"clave": self.clave, "nombre": self.nombre, "texto": self.texto, "detalle": self.detalle, "icono": self.icono,
                "en_disenar": self.en_disenar, "formato": self.formato, "requiere_titulo": self.requiere_titulo,
                "acepta_aprobacion": self.acepta_aprobacion, "frase": self.frase}


_LISTA = (
    Canal("wordpress", "WordPress", "Blogpost", "PUBLICAR_WORDPRESS", MODOS_WP, detalle="entrada en viviragradecidos.org", claves=CLAVES_WP,
          en_disenar=True, icono="casa", requiere_titulo=True, acepta_aprobacion=True, foto=_wordpress),
    Canal("instagram", "Instagram", "Instagram", "PUBLICAR_INSTAGRAM", MODOS_RED, detalle="foto con la frase, reel o historia", claves=CLAVES_IG,
          formato="vertical", en_disenar=True, icono="imagen", acepta_aprobacion=True, cola="siempre", frase="Instagram (posteo cuadrado)",
          foto=_instagram, video=_instagram_video, carrusel=_instagram_carrusel),
    Canal("facebook", "Facebook", "Facebook", "PUBLICAR_FACEBOOK", MODOS_RED, detalle="posteo en la página", claves=CLAVES_FB,
          formato="cuadrado", en_disenar=True, icono="megafono", acepta_aprobacion=True, cola="salvo_real", frase="Facebook (foto con texto)",
          foto=_facebook, video=_facebook_video, carrusel=_facebook_carrusel),
    Canal("youtube", "YouTube", "YouTube", "PUBLICAR_YOUTUBE", MODOS_YT, detalle="un recorte como video", claves=("YOUTUBE_TOKEN_JSON",),
          en_disenar=True, icono="pelicula", requiere_titulo=True, acepta_aprobacion=True, cola="siempre",   # (5/11) también pasa por aprobación; la cola lo sube a su hora
          foto=_youtube, video=_youtube_video),
    # (26/10) el mail de la frase por Perfit (perfit.py + frase_mail.py); el modo es PUBLICAR_MAIL
    Canal("mail", "Mail", "Mail (frase del día)", "PUBLICAR_MAIL", MODOS_RED, claves=CLAVES_PERFIT, icono="sobre",
          frase="Mail (Perfit, 200 por hora, arranca de madrugada o la tarde anterior)", foto=_mail),
    # (2/11) la frase en la home del sitio: sin PUBLICAR_HOME usa el modo de WordPress
    Canal("home", "Sitio web", "Sitio web (home)", "PUBLICAR_HOME", MODOS_WP, hereda="wordpress", claves=CLAVES_WP, icono="casa",
          frase="Sitio web (la frase en la home de viviragradecidos.org)", foto=_home),
    # (2/11) prototipo: solo simulado (no hay endpoint para la cuenta común de la fundación)
    Canal("whatsapp", "WhatsApp", "WhatsApp", "PUBLICAR_WHATSAPP", MODOS_WA, icono="celular",
          frase="WhatsApp (el grupo de la comunidad; por ahora solo simulado)", foto=_whatsapp),
    # el newsletter se arma en su editor y se pega en Perfit: no se publica desde la plataforma (queda 'lista')
    Canal("newsletter", "Newsletter", "Newsletter", "PUBLICAR_NEWSLETTER", ("apagado",), icono="enviar"),
)
CANALES = {c.clave: c for c in _LISTA}

# Por dónde sale la Frase del día (config `frase_canales`): cada salida es un canal más, opcionalmente, un formato.
# «historia» es Instagram con formato historia (1080×1920, 24 h); el resto es el canal tal cual.
SALIDAS_FRASE = {
    "historia": {"canal": "instagram", "formato": "historia", "nombre": "Instagram (historia, 1080×1920, 24 h)", "sufijo": " (historia)"},
    "instagram": {"canal": "instagram", "formato": "cuadrado", "nombre": CANALES["instagram"].frase, "sufijo": ""},
    "facebook": {"canal": "facebook", "formato": "cuadrado", "nombre": CANALES["facebook"].frase, "sufijo": ""},
    "mail": {"canal": "mail", "formato": "cuadrado", "nombre": CANALES["mail"].frase, "sufijo": " (mail)"},
    "home": {"canal": "home", "formato": None, "nombre": CANALES["home"].frase, "sufijo": " (home del sitio)"},
    "whatsapp": {"canal": "whatsapp", "formato": "cuadrado", "nombre": CANALES["whatsapp"].frase, "sufijo": " (WhatsApp)"},
}


def canal(clave):
    """El Canal o None (clave en cualquier capitalización)."""
    return CANALES.get((clave or "").strip().lower())


def de_disenar():
    """Los canales que se eligen en Diseñar (y en el menú), en orden."""
    return [c for c in _LISTA if c.en_disenar]


def nombres():
    """{clave: nombre de la API} de los canales de Diseñar (lo que era chat_rutas.CANALES)."""
    return {c.clave: c.nombre for c in de_disenar()}


def textos():
    """{clave: nombre visible} de todos (lo que era publicar_rutas.CANAL_TXT)."""
    return {c.clave: c.texto for c in _LISTA}


def formato_por_canal():
    return {c.clave: c.formato for c in _LISTA if c.formato}


def variables():
    """Las PUBLICAR_* de los canales que tienen conector (para --simular)."""
    return [c.variable for c in _LISTA if c.foto]


def canal_de_salida(salida):
    """Para la Frase del día: la salida (historia, mail…) → (clave del canal real, formato o None)."""
    s = SALIDAS_FRASE.get(salida)
    return (s["canal"], s["formato"]) if s else (None, None)


def para_web():
    return [c.para_web() for c in _LISTA]


# ----------------------------------------------------------------------------- el aviso de qué va a pasar al enviar
# (antes replicado en web/src/util/publicar.ts; la web lo recibe armado y solo reemplaza {cuando} por la fecha legible)

def aviso(clave, modo, con_fecha):
    """Una o dos frases sin markdown: qué pasa al apretar «Enviar» por este canal con este modo, con o sin fecha.
    Con fecha, el texto lleva «{cuando}» para que la web ponga la fecha.
    (5/11, QA visual) Mismo vocabulario que la web: «prueba» en vez de «simulado», «programada» en vez de «cola», sin «Modo REAL»."""
    c = canal(clave)
    nombre = c.nombre if c else clave
    if modo == "apagado":
        return f"{nombre} está apagado. No se puede hacer nada por este canal."
    if modo == "simulado":
        a = f"Se arma la pieza tal cual saldría en {nombre} y se muestra acá. No sale de verdad."
        if con_fecha and clave == "facebook":
            a += " (Cuando el canal esté en real, Facebook sí acepta programación.)"
    elif modo == "privado":
        a = "Se sube el video a YouTube como privado. No lo ve nadie hasta que lo publiques desde YouTube Studio."
    elif modo == "borrador":
        a = "Se crea la entrada en borrador en viviragradecidos.org. No se publica ni sale por newsletter hasta que la publiques desde WordPress."
        if con_fecha:
            a += " La fecha {cuando} queda guardada en el borrador."
    else:
        a = f"Se publica en {nombre} de verdad."
        if con_fecha and clave == "wordpress":
            a = "Se programa en WordPress para el {cuando} y sale sola ese día (y por newsletter)."
        if con_fecha and clave == "facebook":
            a = "Se programa en Facebook para el {cuando} (mínimo 10 minutos de anticipación)."
        if con_fecha and clave == "youtube":
            a = "Se sube ahora y YouTube lo publica solo el {cuando}."
    # (12/11) Google cerró la revisión: la API NO fuerza privado (probado con herramientas/youtube_probar.py: «unlisted» respetado).
    # Quedó sin el aviso «hasta que Google audite…» que venía de documentación de terceros desactualizada.
    if con_fecha and c and c.va_a_la_cola(modo):
        a = f"Queda programada para el {{cuando}}: no sale ahora. Ese día sale sola por {nombre}"
        a += " (el canal está en prueba: ese día se arma y se muestra, no sale de verdad)." if modo == "simulado" else "."
    return a
