"""
publicar_ui.py — Publicar desde el chatbot (24/9, rehecho 24/9 noche).

Dos lugares, un solo formulario:
  1. recuadro(usuario, pieza, key)  → debajo de la respuesta del bot, cuando esa respuesta es una
     pieza (lo decide el bot con la herramienta proponer_publicacion). Viene precompletado: texto, canal, fecha, título y
     una búsqueda en el banco de imágenes. La persona ajusta y aprieta Enviar sin salir del chat.
  2. render(usuario)                → la pestaña "Publicar" del sidebar, como respaldo para piezas
     que no nacen de una conversación.

Una pieza = título (opcional), texto, imagen (del banco, por URL o archivo), canal, fecha (opcional).
El botón hace lo que diga el switch de secrets.toml, y la pantalla dice siempre qué va a pasar:
    PUBLICAR_WORDPRESS = "borrador"   -> crea la entrada en borrador en viviragradecidos.org
    PUBLICAR_INSTAGRAM = "simulado"   -> arma el posteo y lo muestra; no lo manda
    PUBLICAR_FACEBOOK  = "simulado"   -> ídem
Banco de imágenes = biblioteca de medios de WordPress (ver publicar.buscar_imagenes_banco).
Solo lo ven los usuarios listados en PUBLICAR_USUARIOS (secrets; por defecto franco y julian).
Cada intento queda en la tabla `publicaciones` de Supabase (registro y semilla de la cola).
"""
import datetime
import streamlit as st
import publicar
import db

MODO_TXT = {
    "apagado": ("⚫", "apagado: este canal no está disponible"),
    "simulado": ("🟡", "simulado: arma la pieza y la muestra, NO la manda"),
    "borrador": ("🟠", "borrador: la crea en WordPress sin publicar; vos la publicás desde el panel"),
    "real": ("🔴", "REAL: publica de verdad"),
}
CANALES = ["WordPress", "Instagram", "Facebook"]
CLAVE = {"WordPress": "wordpress", "Instagram": "instagram", "Facebook": "facebook"}


def _cfg():
    return publicar.Config(st.secrets)


def _hook_registro(usuario):
    def _f(entrada):
        pieza = entrada.get("pieza") or {}
        db.registrar_publicacion(
            usuario=usuario, canal=entrada.get("canal", ""), modo=entrada.get("modo", ""),
            titulo=(pieza.get("title") or entrada.get("titulo") or CONTEXTO_REGISTRO.get("titulo") or "")[:200],
            texto=(pieza.get("content") or pieza.get("caption") or pieza.get("message") or "")[:5000],
            imagen_url=pieza.get("image_url") or entrada.get("url"),
            fecha_programada=pieza.get("date") or pieza.get("fecha_programada") or CONTEXTO_REGISTRO.get("fecha"),
            estado=str(entrada.get("resultado", ""))[:60],
            resultado=dict({k: v for k, v in entrada.items() if k not in ("pieza",)},
                           texto_imagen=CONTEXTO_REGISTRO.get("texto_imagen") or None))
    return _f


def _aviso(canal, modo, fecha_iso):
    if modo == "apagado":
        return f"{canal} está apagado. No se puede hacer nada por este canal."
    if modo == "simulado":
        a = f"Se arma la pieza tal cual saldría en {canal} y se muestra acá. **No se manda.**"
        if fecha_iso and canal == "Facebook":
            a += " (En modo real, Facebook sí acepta programación.)"
    elif modo == "borrador":
        a = "Se crea la entrada **en borrador** en viviragradecidos.org. No se publica ni sale por newsletter hasta que vos la publiques desde WordPress."
        if fecha_iso:
            a += f" La fecha {fecha_iso[:16].replace('T', ' ')} queda guardada en el borrador."
    else:
        a = f"**Modo REAL:** se publica en {canal} de verdad."
        if fecha_iso and canal == "WordPress":
            a = f"**Modo REAL:** se programa en WordPress para el {fecha_iso[:16].replace('T', ' ')} y sale sola ese día (y por newsletter)."
        if fecha_iso and canal == "Facebook":
            a = f"**Modo REAL:** se programa en Facebook para el {fecha_iso[:16].replace('T', ' ')} (mínimo 10 minutos de anticipación)."
    if fecha_iso and canal == "Instagram":
        a += " ⚠ Instagram no permite programar por API: la fecha queda anotada en el registro."
    return a


def _banco(cfg, consulta, key):
    """Busca en el banco y cachea por recuadro, para no pegarle a WordPress en cada redibujo."""
    cache = st.session_state.setdefault("banco_cache", {})
    k = f"{key}|{consulta.strip().lower()}"
    if k not in cache:
        try:
            res = publicar.buscar_imagenes_banco(cfg, consulta, n=6) if consulta.strip() else []
            if not res:
                res = publicar.imagenes_recientes_banco(cfg, n=6)
            cache[k] = res
        except Exception:
            cache[k] = []
    return cache[k]


def _texto_plano(t):
    """Red de seguridad para redes: saca markdown y links, deja texto pegable."""
    import re
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\1", t)          # [texto](url) -> texto
    t = re.sub(r"https?://\S+", "", t)                                   # urls sueltas
    t = re.sub(r"^\s{0,3}#{1,6}\s*", "", t, flags=re.M)                  # títulos
    t = re.sub(r"^\s*>\s?", "", t, flags=re.M)                            # citas
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)                              # negritas
    t = re.sub(r"(?<!\w)[_*](.+?)[_*](?!\w)", r"\1", t)                  # itálicas
    t = re.sub(r"^\s*[-*]\s+", "• ", t, flags=re.M)                       # viñetas
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


CONTEXTO_REGISTRO = {}   # título y texto_imagen del envío en curso, para el registro


def _enviar(cfg, usuario, canal, titulo, texto, archivo, imagen_url, fecha_iso, texto_imagen=""):
    """Ejecuta la publicación según el switch. Devuelve (res, imagen_url_final)."""
    imagen_id = None
    if canal in ("Instagram", "Facebook"):
        texto = _texto_plano(texto)
    CONTEXTO_REGISTRO.update(titulo=titulo, texto_imagen=texto_imagen, fecha=fecha_iso)
    if archivo is not None:
        with st.spinner("Subiendo la imagen a la biblioteca de WordPress…"):
            res_img = publicar.subir_imagen_wordpress(cfg, archivo.getvalue(), archivo.name,
                                                      titulo=titulo or archivo.name, quien=usuario,
                                                      pieza=titulo or texto[:60])
        if res_img.get("url"):
            imagen_url, imagen_id = res_img["url"], res_img.get("id")
            st.success("Imagen subida a la biblioteca de medios (ya queda en el banco).")
        elif res_img.get("aviso"):
            st.warning(res_img["aviso"] + " (para Instagram/Facebook la imagen tiene que estar en internet)")
    with st.spinner("Armando la pieza…"):
        if canal == "WordPress":
            res = publicar.publicar_wordpress(cfg, titulo.strip(), texto, imagen_id=imagen_id,
                                              quien=usuario, fecha=fecha_iso)
        elif canal == "Instagram":
            res = publicar.publicar_instagram(cfg, imagen_url or "", texto, quien=usuario)
            if fecha_iso and res.get("pieza") is not None:
                res["pieza"]["fecha_programada"] = fecha_iso
        else:
            res = publicar.publicar_facebook(cfg, imagen_url, texto, quien=usuario, fecha=fecha_iso)
    return res, imagen_url


def _mostrar_resultado(res, canal, modo, titulo, texto, archivo, imagen_url, fecha_iso, texto_imagen=""):
    if res.get("ok"):
        st.success(res.get("aviso", "Listo."))
    else:
        st.error(res.get("aviso", "No se pudo."))
    if res.get("link_editar"):
        st.markdown(f"[Abrir el borrador en WordPress ↗]({res['link_editar']})")
    if modo == "simulado" or res.get("pieza"):
        with st.container(border=True):
            st.markdown(f"**Así quedaría en {canal}:**")
            if archivo is not None:
                st.image(archivo.getvalue(), width=360)
            elif imagen_url:
                st.image(imagen_url, width=360)
            if texto_imagen:
                st.caption(f"Sobre la imagen: «{texto_imagen}»")
            if canal == "WordPress":
                st.markdown(f"#### {titulo}")
                st.markdown(texto, unsafe_allow_html=True)
            else:
                st.text(texto)
            if fecha_iso:
                st.caption(f"Fecha pedida: {fecha_iso[:16].replace('T', ' ')}")


def formulario(usuario, key, pieza=None, compacto=False):
    """El formulario de publicar. `pieza` (de la herramienta proponer_publicacion) lo precompleta.
    `key` distingue cada instancia (uno por mensaje del bot, o 'tab')."""
    cfg = _cfg()
    publicar.REGISTRAR_EXTRA = _hook_registro(usuario)
    r = cfg.resumen()
    pieza = pieza or {}
    k = lambda s: f"pub_{key}_{s}"

    # Canal: precompletado solo si la persona lo dijo; si no, hay que elegirlo
    idx = {"wordpress": 0, "instagram": 1, "facebook": 2}.get(pieza.get("canal") or "", None)
    canal = st.radio("Canal", CANALES, horizontal=True, index=idx, key=k("canal"))
    if canal is None:
        st.caption("Elegí el canal para ver qué va a pasar al enviar.")
        modo = "apagado"
    else:
        modo = r[CLAVE[canal]]
        icono, txt = MODO_TXT.get(modo, ("⚫", modo))
        st.caption(f"{icono} {canal} en modo **{modo}** — {txt}")

    # Título y texto
    titulo = st.text_input("Título" + (" (obligatorio en WordPress)" if canal == "WordPress" else " (opcional, para el registro)"),
                           value=pieza.get("titulo", ""), key=k("titulo"))
    texto_imagen = ""
    if pieza.get("texto_imagen") or not compacto:
        texto_imagen = st.text_input("Texto sobre la imagen (para el diseño; no se publica como caption)",
                                     value=pieza.get("texto_imagen", ""), key=k("timg"))
    texto = st.text_area("Texto de la pieza" + (" (el caption)" if canal in ("Instagram", "Facebook") else ""),
                         value=pieza.get("texto", ""), height=160 if compacto else 220, key=k("texto"),
                         placeholder="Escribí la pieza o pedísela al bot en el chat. En WordPress podés usar HTML simple.")

    # Imagen: banco primero; URL o archivo como excepción
    st.markdown("**Imagen**")
    cb1, cb2 = st.columns([4, 1])
    consulta = cb1.text_input("Buscar en el banco de imágenes", value=pieza.get("imagen_busqueda", ""), key=k("busq"),
                              placeholder="ej. amanecer montaña calma", label_visibility="collapsed")
    if cb2.button("Buscar", key=k("buscar_btn"), width="stretch"):
        st.session_state.get("banco_cache", {}).pop(f"{key}|{consulta.strip().lower()}", None)
    candidatas = _banco(cfg, consulta, key)
    imagen_url = None
    if candidatas:
        cols = st.columns(len(candidatas))
        for i, (c, img) in enumerate(zip(cols, candidatas)):
            c.image(img["miniatura"], width="stretch")
            c.caption((img["titulo"] or f"#{img['id']}")[:28])
        opciones = ["Sin imagen"] + [f"{i + 1}" for i in range(len(candidatas))]
        eleg = st.radio("Elegí una", opciones, horizontal=True, index=1 if pieza.get("imagen_busqueda") else 0,
                        key=k("eleg"), label_visibility="collapsed")
        if eleg != "Sin imagen":
            imagen_url = candidatas[int(eleg) - 1]["url"]
    else:
        st.caption("El banco no tiene nada para esa búsqueda todavía. Probá otras palabras, o cargá una excepción abajo.")
    with st.expander("Otra imagen (URL o archivo) — excepción", expanded=False):
        url_manual = st.text_input("URL de una imagen que ya está en internet", key=k("url"))
        archivo = st.file_uploader("…o subí un archivo (va al banco de WordPress)", type=["jpg", "jpeg", "png", "webp"], key=k("file"))
    if url_manual.strip():
        imagen_url = url_manual.strip()

    # Fecha
    c1, c2 = st.columns(2)
    programar = c1.checkbox("Programar para una fecha", value=bool(pieza.get("fecha")), key=k("prog"))
    fecha_iso = None
    if programar:
        try:
            f0 = datetime.date.fromisoformat(pieza["fecha"]) if pieza.get("fecha") else datetime.date.today() + datetime.timedelta(days=1)
        except Exception:
            f0 = datetime.date.today() + datetime.timedelta(days=1)
        try:
            hh, mm = (pieza.get("hora") or "09:00").split(":")
            h0 = datetime.time(int(hh), int(mm))
        except Exception:
            h0 = datetime.time(9, 0)
        fecha = c1.date_input("Día", value=f0, key=k("fecha"))
        hora = c2.time_input("Hora", value=h0, key=k("hora"))
        fecha_iso = f"{fecha.isoformat()}T{hora.strftime('%H:%M:%S')}"

    if canal is not None:
        st.info(_aviso(canal, modo, fecha_iso))
    confirmar = st.checkbox("Entiendo que esto publica de verdad", key=k("conf")) if modo == "real" else True

    if st.button(f"Enviar a {canal or '…'}", type="primary", key=k("enviar"), disabled=(canal is None or modo == "apagado" or not confirmar)):
        if not texto.strip():
            st.error("Falta el texto de la pieza.")
            return
        if canal == "WordPress" and not titulo.strip():
            st.error("En WordPress hace falta un título.")
            return
        res, imagen_url = _enviar(cfg, usuario, canal, titulo, texto, archivo, imagen_url, fecha_iso, texto_imagen)
        _mostrar_resultado(res, canal, modo, titulo, texto if canal == "WordPress" else _texto_plano(texto),
                           archivo, imagen_url, fecha_iso, texto_imagen)


def recuadro(usuario, pieza, key, abierto=True):
    """Debajo de una respuesta del bot que es una pieza."""
    etiqueta = "📤 Publicar esta pieza"
    if pieza.get("canal"):
        etiqueta += f" · {pieza['canal'].capitalize()}"
    if pieza.get("fecha"):
        etiqueta += f" · {pieza['fecha']}" + (f" {pieza['hora']}" if pieza.get("hora") else "")
    with st.expander(etiqueta, expanded=abierto):
        formulario(usuario, key, pieza=pieza, compacto=True)


def render(usuario):
    """La pestaña 'Publicar' (respaldo)."""
    cfg = _cfg()
    r = cfg.resumen()
    st.markdown("### 📤 Publicar una pieza")
    st.caption("Lo normal es publicar desde el chat, debajo de la respuesta del bot. Esta pantalla es para piezas que no salen de una conversación.")
    with st.container(border=True):
        cols = st.columns(3)
        for col, nombre in zip(cols, CANALES):
            modo = r[CLAVE[nombre]]
            icono, txt = MODO_TXT.get(modo, ("⚫", modo))
            col.markdown(f"**{nombre}** {icono}  \n<small>{txt}</small>", unsafe_allow_html=True)
    formulario(usuario, "tab")
    with st.expander("Últimas piezas registradas"):
        try:
            for p in db.listar_publicaciones(limite=15):
                st.markdown(f"- {str(p.get('creado', ''))[:16].replace('T', ' ')} · **{p.get('canal')}** · {p.get('modo')} · "
                            f"{(p.get('titulo') or '')[:60]} · {p.get('usuario')} · {p.get('estado')}")
        except Exception as e:
            st.caption(f"(sin registro: {e})")
