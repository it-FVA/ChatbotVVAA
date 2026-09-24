"""
publicar_ui.py — La pestaña "Publicar" del chatbot (24/9).

Una pieza = título (opcional), texto, imagen (opcional), canal, fecha (opcional).
El botón hace lo que diga el switch de secrets.toml, y la pantalla dice siempre qué va a pasar:
    PUBLICAR_WORDPRESS = "borrador"   -> crea la entrada en borrador en viviragradecidos.org
    PUBLICAR_INSTAGRAM = "simulado"   -> arma el posteo y lo muestra; no lo manda
    PUBLICAR_FACEBOOK  = "simulado"   -> ídem (Facebook no está conectado todavía)
Ver el detalle de los modos en publicar.py y en fva-transcripcion/conectores/COMO-PROBAR.md.

Solo la ven los usuarios listados en PUBLICAR_USUARIOS (secrets; por defecto franco y julian).
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


def _cfg():
    return publicar.Config(st.secrets)


def _hook_registro(usuario):
    def _f(entrada):
        pieza = entrada.get("pieza") or {}
        db.registrar_publicacion(
            usuario=usuario, canal=entrada.get("canal", ""), modo=entrada.get("modo", ""),
            titulo=(pieza.get("title") or entrada.get("titulo") or "")[:200],
            texto=(pieza.get("content") or pieza.get("caption") or pieza.get("message") or "")[:5000],
            imagen_url=pieza.get("image_url") or entrada.get("url"),
            fecha_programada=pieza.get("date") or pieza.get("fecha_programada"),
            estado=str(entrada.get("resultado", ""))[:60],
            resultado={k: v for k, v in entrada.items() if k not in ("pieza",)})
    return _f


def render(usuario):
    cfg = _cfg()
    publicar.REGISTRAR_EXTRA = _hook_registro(usuario)
    r = cfg.resumen()

    st.markdown("### 📤 Publicar una pieza")
    st.caption("Nada sale sin que una persona apruebe. La pantalla te dice, antes de apretar, qué va a pasar en cada canal.")

    with st.container(border=True):
        cols = st.columns(3)
        for col, (nombre, clave) in zip(cols, (("WordPress", "wordpress"), ("Instagram", "instagram"), ("Facebook", "facebook"))):
            modo = r[clave]
            icono, txt = MODO_TXT.get(modo, ("⚫", modo))
            col.markdown(f"**{nombre}** {icono}  \n<small>{txt}</small>", unsafe_allow_html=True)

    canal = st.radio("Canal", ["WordPress", "Instagram", "Facebook"], horizontal=True, key="pub_canal")
    clave = {"WordPress": "wordpress", "Instagram": "instagram", "Facebook": "facebook"}[canal]
    modo = r[clave]

    titulo = st.text_input("Título" + (" (obligatorio en WordPress)" if canal == "WordPress" else " (opcional, solo para el registro)"))
    texto = st.text_area("Texto de la pieza", height=220,
                         placeholder="Pegá acá el texto que armaste con el asistente. En WordPress podés usar HTML simple (<p>, <strong>, <a>).")
    archivo = st.file_uploader("Imagen (opcional)", type=["jpg", "jpeg", "png", "webp"])
    url_imagen = st.text_input("…o pegá la URL de una imagen que ya está en el sitio (opcional)")

    c1, c2 = st.columns(2)
    programar = c1.checkbox("Programar para una fecha")
    fecha = hora = None
    if programar:
        fecha = c1.date_input("Día", value=datetime.date.today() + datetime.timedelta(days=1))
        hora = c2.time_input("Hora", value=datetime.time(9, 0))
    fecha_iso = f"{fecha.isoformat()}T{hora.strftime('%H:%M:%S')}" if programar else None

    # Qué va a pasar, dicho antes de apretar
    if modo == "apagado":
        aviso = f"{canal} está apagado. No se puede hacer nada por este canal."
    elif modo == "simulado":
        aviso = f"Se va a armar la pieza tal cual saldría en {canal} y se va a mostrar acá. **No se manda.**"
    elif modo == "borrador":
        aviso = "Se va a crear la entrada **en borrador** en viviragradecidos.org. No se publica ni sale por newsletter hasta que vos la publiques desde WordPress."
        if fecha_iso:
            aviso += f" La fecha {fecha_iso[:16].replace('T', ' ')} queda guardada en el borrador."
    else:
        aviso = f"**Modo REAL:** se publica en {canal} de verdad."
        if fecha_iso and canal == "WordPress":
            aviso = f"**Modo REAL:** se programa en WordPress para el {fecha_iso[:16].replace('T', ' ')} y sale sola ese día (y por newsletter)."
    if fecha_iso and canal != "WordPress":
        aviso += " ⚠ La programación en redes todavía no existe: la fecha queda anotada en el registro, nada más."
    st.info(aviso)

    if modo == "real":
        confirmar = st.checkbox("Entiendo que esto publica de verdad")
    else:
        confirmar = True

    if st.button(f"Enviar a {canal}", type="primary", disabled=(modo == "apagado" or not confirmar)):
        if not texto.strip():
            st.error("Falta el texto de la pieza.")
            return
        if canal == "WordPress" and not titulo.strip():
            st.error("En WordPress hace falta un título.")
            return

        # 1) imagen: si hay archivo, va a la biblioteca de medios de WordPress (cuando WP no está apagado/simulado)
        imagen_url = url_imagen.strip() or None
        imagen_id = None
        if archivo is not None:
            with st.spinner("Subiendo la imagen a la biblioteca de WordPress…"):
                res_img = publicar.subir_imagen_wordpress(cfg, archivo.getvalue(), archivo.name,
                                                          titulo=titulo or archivo.name, quien=usuario,
                                                          pieza=titulo or texto[:60])
            if res_img.get("url"):
                imagen_url, imagen_id = res_img["url"], res_img.get("id")
                st.success("Imagen subida a la biblioteca de medios.")
            elif res_img.get("aviso"):
                st.warning(res_img["aviso"] + " (para Instagram/Facebook la imagen tiene que estar en internet)")

        # 2) la pieza
        with st.spinner("Armando la pieza…"):
            if canal == "WordPress":
                res = publicar.publicar_wordpress(cfg, titulo.strip(), texto, imagen_id=imagen_id,
                                                  quien=usuario, fecha=fecha_iso)
            elif canal == "Instagram":
                res = publicar.publicar_instagram(cfg, imagen_url or "", texto, quien=usuario)
                if fecha_iso:
                    res["pieza"]["fecha_programada"] = fecha_iso
            else:
                res = publicar.publicar_facebook(cfg, imagen_url, texto, quien=usuario, fecha=fecha_iso)

        # 3) mostrar
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
                if canal == "WordPress":
                    st.markdown(f"#### {titulo}")
                    st.markdown(texto, unsafe_allow_html=True)
                else:
                    st.markdown(texto)
                if fecha_iso:
                    st.caption(f"Fecha pedida: {fecha_iso[:16].replace('T', ' ')}")

    with st.expander("Últimas piezas registradas"):
        try:
            for p in db.listar_publicaciones(limite=15):
                st.markdown(f"- {str(p.get('creado', ''))[:16].replace('T', ' ')} · **{p.get('canal')}** · {p.get('modo')} · "
                            f"{(p.get('titulo') or '')[:60]} · {p.get('usuario')} · {p.get('estado')}")
        except Exception as e:
            st.caption(f"(sin registro: {e})")
