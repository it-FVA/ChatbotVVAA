"""
publicar_ui.py — Publicar desde el chatbot (24/9, rehecho 24/9 noche).

Dos lugares, un solo formulario:
  1. recuadro(usuario, pieza, key)  → debajo de la respuesta del bot, cuando esa respuesta es una
     pieza (lo decide el bot con la herramienta proponer_publicacion). Viene precompletado: texto, canal, fecha, título y
     una búsqueda en el banco de imágenes. La persona ajusta y aprieta Enviar sin salir del chat.
  2. render(usuario)                → la pestaña "Publicar" del sidebar, como respaldo para piezas
     que no nacen de una conversación.

Una pieza = título (opcional), texto, imagen (del banco, por URL o archivo), canal, fecha (opcional).
(28/9) Si hay "texto sobre la imagen" y el canal es Instagram o Facebook, el recuadro muestra la foto
con la frase encima (imagen.py) y publica ESA imagen: se sube a la biblioteca de WordPress para tener
URL pública y esa URL viaja a la red o a la cola. "Publicar así" destildado → va la foto sola.
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
    "privado": ("🟠", "privado: sube el video como privado; vos lo publicás desde YouTube Studio"),
    "real": ("🔴", "REAL: publica de verdad"),
}
CANALES = ["WordPress", "Instagram", "Facebook", "YouTube"]
CLAVE = {"WordPress": "wordpress", "Instagram": "instagram", "Facebook": "facebook", "YouTube": "youtube"}
# (16/10, Franco) nombres visibles: la entrada en WordPress se llama "Blogpost"; el "Newsletter" es el mail a la comunidad.
CANAL_TXT = {"wordpress": "Blogpost", "instagram": "Instagram", "facebook": "facebook".capitalize(), "youtube": "YouTube", "newsletter": "Newsletter"}


def canal_txt(c):
    return CANAL_TXT.get((c or "").lower(), c or "")


def _lista(clave, defecto):
    return [u.strip() for u in str(st.secrets.get(clave, defecto)).split(",") if u.strip()]


def roles(usuario):
    """(13/10, reunión + pedido de Franco) Tres niveles, acumulativos:
    - CREADOR DE CONTENIDO (todos): chat, arma piezas en simulado, elige fecha y hora y las manda a
      aprobación; sigue su estado en "Mis publicaciones".
    - APROBADOR / ADMIN (secret APROBADORES): panel admin: aprueba (puede cambiar fecha y hora), rechaza
      con nota, ve la cola y el registro completo.
    - PUBLICACIÓN DIRECTA (secret PUBLICACION_DIRECTA; por defecto = los aprobadores): publica de verdad
      desde el recuadro sin pasar por aprobación (bypass).
    Se cambian en secrets sin tocar código."""
    aprob = _lista("APROBADORES", "julian,franco,beto")
    directa = _lista("PUBLICACION_DIRECTA", ",".join(aprob))
    aprueba = usuario in aprob
    return {"crea": True, "aprueba": aprueba, "publica": usuario in directa,
            "nombre": "aprobador / admin" if aprueba else "creador de contenido",
            "aprobadores": aprob, "publicadores": directa}


def _cfg(usuario=None):
    """La configuración que ve esta persona: quien no publica en real tiene todos los canales en simulado."""
    cfg = publicar.Config(st.secrets)
    if usuario and not roles(usuario)["publica"]:
        for a in ("modo_wp", "modo_ig", "modo_fb", "modo_yt"):
            if getattr(cfg, a) != "apagado":
                setattr(cfg, a, "simulado")
    return cfg


def _con_zona(fecha):
    """La fecha del recuadro es hora Argentina sin zona; en la base va con -03:00 (29/9: se guardaba como UTC)."""
    if fecha and len(fecha) >= 16 and fecha[-6] not in "+-" and not fecha.endswith("Z"):
        return fecha + ZONA_HORARIA
    return fecha


def _hook_registro(usuario):
    def _f(entrada):
        pieza = entrada.get("pieza") or {}
        db.registrar_publicacion(
            usuario=usuario, canal=entrada.get("canal", ""), modo=entrada.get("modo", ""),
            titulo=(pieza.get("title") or entrada.get("titulo") or CONTEXTO_REGISTRO.get("titulo") or "")[:200],
            texto=(pieza.get("content") or pieza.get("caption") or pieza.get("message") or pieza.get("description") or "")[:5000],
            imagen_url=pieza.get("image_url") or entrada.get("url"),
            fecha_programada=_con_zona(pieza.get("date") or pieza.get("fecha_programada") or CONTEXTO_REGISTRO.get("fecha")),
            estado="prueba" if entrada.get("modo") == "simulado" else str(entrada.get("resultado", ""))[:60],
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
    elif modo == "privado":
        a = "Se sube el video a YouTube **como privado**. No lo ve nadie hasta que vos lo publiques desde YouTube Studio."
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
        if fecha_iso and canal == "YouTube":
            a = f"**Modo REAL:** se sube ahora y YouTube lo publica solo el {fecha_iso[:16].replace('T', ' ')}."
    if canal == "YouTube" and modo in ("privado", "real"):
        a += " (Hasta que Google audite el proyecto, YouTube deja los videos subidos por API en privado: se publican desde YouTube Studio.)"
    if fecha_iso and _va_a_la_cola(canal, modo):
        a = (f"**Queda en la cola** para el {fecha_iso[:16].replace('T', ' ')}: no se manda ahora. Ese día sale sola por {canal} "
             f"con el modo que tenga el canal en ese momento (hoy **{modo}**" + (": se arma y se muestra, no se publica" if modo == "simulado" else "") + ").")
    return a


# (5/10) Formato de la pieza → etiqueta con que subir_banco.py marca cada imagen del banco.
# Julián carga el banco en carpetas FB / IG / Stories con las medidas en el nombre; el script las
# traduce a estas tres palabras. Si el recuadro ya tiene elegido un formato (selector "Formato"),
# se usa ese; si no, el que corresponde al canal.
FORMATO_POR_CANAL = {"Facebook": "cuadrado", "Instagram": "vertical"}


def _formato_busqueda(canal, key):
    f = st.session_state.get(f"pub_{key}_fmt")          # misma clave que el selector "Formato" del recuadro (k("fmt"))
    return f if f in ("cuadrado", "vertical", "historia") else FORMATO_POR_CANAL.get(canal)


def _banco(cfg, consulta, key, formato=None):
    """Busca en el banco y cachea por recuadro, para no pegarle a WordPress en cada redibujo.
    Con `formato`, primero busca las imágenes etiquetadas con ese formato (consulta + formato);
    si no hay, cae a la búsqueda sin formato, y después a las recientes."""
    cache = st.session_state.setdefault("banco_cache", {})
    k = f"{key}|{consulta.strip().lower()}|{formato or ''}"
    if k not in cache:
        try:
            res = []
            if formato and formato not in consulta.lower():
                res = publicar.buscar_imagenes_banco(cfg, f"{consulta.strip()} {formato}".strip(), n=6)
                res = [r for r in res if formato in (r.get("titulo") or "").lower()]   # solo las del formato pedido
            if not res and consulta.strip():
                res = publicar.buscar_imagenes_banco(cfg, consulta, n=6)
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


# (28/9) Texto sobre imagen: la pieza de redes es la foto del banco con la frase encima.
# imagen.componer_imagen lo arma (Pillow); acá se cachea por contenido para no recomponer
# en cada redibujo del formulario, y se decide qué imagen viaja a Instagram/Facebook.
def _componer(fuente, texto_imagen, firma, formato, tipografia=None, posicion="centro", alineacion="centro",
              logo=None, posicion_logo="abajo derecha", peso="normal"):
    """fuente: bytes o URL. Devuelve bytes JPEG con la frase encima, o None si falla."""
    import hashlib
    import imagen
    h = hashlib.md5(fuente).hexdigest() if isinstance(fuente, (bytes, bytearray)) else str(fuente)
    clave = f"{h}|{texto_imagen}|{firma}|{formato}|{tipografia}|{posicion}|{alineacion}|{logo}|{posicion_logo}|{peso}"
    cache = st.session_state.setdefault("compuesta_cache", {})
    if clave not in cache:
        try:
            cache[clave] = imagen.componer_imagen(fuente, texto_imagen, firma=firma, formato=formato,
                                                  tipografia=tipografia, posicion=posicion, alineacion=alineacion, peso=peso,
                                                  logo=logo, posicion_logo=posicion_logo)
        except Exception as e:
            cache[clave] = None
            st.warning(f"No pude componer la imagen: {e}")
    return cache[clave]


def _sin_firma_repetida(texto_imagen, firma):
    """Si el bot ya puso '— Br. David' al final del texto de la imagen, no lo duplicamos."""
    t = (texto_imagen or "").rstrip()
    f = (firma or "").strip()
    if f and t.endswith(f):
        t = t[: -len(f)].rstrip(" \n—-–")
    return t


def _enviar(cfg, usuario, canal, titulo, texto, archivo, imagen_url, fecha_iso, texto_imagen="", video=None, compuesta=None, formato=None,
            aprobacion=False, video_url=None):
    """Ejecuta la publicación según el switch. Devuelve (res, imagen_url_final).
    aprobacion=True (13/10): no publica; sube la imagen y deja la pieza 'a_aprobar' para el panel.
    video_url (16/10): pieza de video (un recorte que ya está en WordPress): reel/historia en Instagram,
    video en Facebook, short en YouTube. Sin imagen ni composición."""
    imagen_id = None
    if canal in ("Instagram", "Facebook"):
        texto = _texto_plano(texto)
    CONTEXTO_REGISTRO.update(titulo=titulo, texto_imagen=texto_imagen, fecha=fecha_iso)
    if compuesta is not None and canal in ("Instagram", "Facebook"):
        # La imagen compuesta tiene que estar en internet para IG/FB: va a la biblioteca de WP.
        nombre = f"pieza-{datetime.date.today().isoformat()}-{(titulo or texto)[:40]}".strip()
        nombre = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in nombre).strip("-") + ".jpg"
        import hashlib
        subidas = st.session_state.setdefault("compuesta_subidas", {})   # md5 → url (29/9: 3 intentos = 3 copias en WP)
        h = hashlib.md5(compuesta).hexdigest()
        if h in subidas:
            res_img = {"url": subidas[h]}
        else:
            with st.spinner("Subiendo la imagen con la frase a la biblioteca de WordPress…"):
                res_img = publicar.subir_imagen_wordpress(cfg, compuesta, nombre, titulo=titulo or texto[:60],
                                                          quien=usuario, pieza=titulo or texto[:60],
                                                          etiquetas=["pieza-compuesta"])
            if res_img.get("url"):
                subidas[h] = res_img["url"]
        if res_img.get("url"):
            imagen_url = res_img["url"]
            archivo = None   # ya no hace falta subir la cruda
        else:
            st.warning((res_img.get("aviso") or "No se pudo subir la imagen compuesta.")
                       + " Se publica la foto sin la frase encima."
                       + (" (Para que funcione, WordPress tiene que estar en modo borrador o real.)" if res_img.get("modo") in ("apagado", "simulado") else ""))
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
    modo = cfg.resumen()[CLAVE[canal]]
    if aprobacion:
        try:
            pid = db.proponer_publicacion(usuario, CLAVE[canal], modo, titulo, texto, imagen_url,
                                          (fecha_iso + ZONA_HORARIA) if fecha_iso else None,
                                          extra={"texto_imagen": texto_imagen or None, "formato": formato or None,
                                                 "video_url": video_url or None})
        except Exception as e:
            return {"ok": False, "modo": "aprobacion", "aviso": f"No pude guardar la pieza para aprobación: {e}"}, imagen_url
        if not pid:
            return {"ok": False, "modo": "aprobacion", "aviso": "No pude guardar la pieza para aprobación (¿falta Supabase en los secrets?)."}, imagen_url
        quien = ", ".join(roles(usuario)["aprobadores"]) or "un aprobador"
        return {"ok": True, "modo": "aprobacion", "id": pid,
                "aviso": f"Quedó pendiente de aprobación ({quien}). Si la aprueban, sale por {canal}"
                         + (f" el {fecha_iso[:16].replace('T', ' ')}" if fecha_iso else " en la próxima corrida de la cola")
                         + ". Podés ver el estado en «Mis piezas enviadas», en la barra lateral.",
                "pieza": {"image_url": imagen_url, "caption" if canal == "Instagram" else "message": texto, "fecha_programada": fecha_iso}}, imagen_url
    # (25/9) Cola: si hay fecha y el canal no programa solo (Instagram siempre; Facebook fuera de
    # modo real), la pieza NO se manda ahora: queda 'pendiente' y procesar_cola.py la saca ese día
    # con el modo que tenga el canal en ese momento.
    if fecha_iso and _va_a_la_cola(canal, modo):
        try:
            pid = db.encolar_publicacion(usuario, CLAVE[canal], modo, titulo, texto, imagen_url,
                                         fecha_iso + ZONA_HORARIA, extra={"texto_imagen": texto_imagen or None,
                                                                          "formato": formato or None,
                                                                          "video_url": video_url or None})
        except Exception as e:
            return {"ok": False, "modo": modo, "aviso": f"No pude guardar la pieza en la cola: {e}"}, imagen_url
        if not pid:
            return {"ok": False, "modo": modo, "aviso": "No pude guardar la pieza en la cola (¿falta Supabase en los secrets?)."}, imagen_url
        cuando = fecha_iso[:16].replace("T", " ")
        return {"ok": True, "modo": modo, "encolada": True, "id": pid,
                "aviso": f"Quedó en la cola para el {cuando}. Ese día sale sola por {canal}, con el modo que tenga el canal en ese momento (hoy: {modo}). "
                         "Podés cancelarla desde «Piezas en cola» en la barra lateral.",
                "pieza": {"image_url": imagen_url, "caption" if canal == "Instagram" else "message": texto, "fecha_programada": fecha_iso}}, imagen_url
    with st.spinner("Armando la pieza…"):
        if video_url and canal == "Instagram":
            res = publicar.publicar_instagram_video(cfg, video_url, texto, quien=usuario, historia=(formato == "historia"))
        elif video_url and canal == "Facebook":
            res = publicar.publicar_facebook_video(cfg, video_url, texto, quien=usuario, fecha=fecha_iso, titulo=titulo.strip())
        elif video_url and canal == "YouTube":
            datos, err = (None, None)
            if cfg.modo_yt in ("privado", "real"):
                datos, err = publicar.bajar_bytes(video_url)
            if err:
                res = {"ok": False, "modo": cfg.modo_yt, "aviso": f"No pude bajar el recorte de WordPress: {err}"}
            else:
                res = publicar.publicar_youtube(cfg, datos or b"", titulo.strip(), texto, quien=usuario, fecha=fecha_iso,
                                                nombre_archivo=video_url.rsplit("/", 1)[-1] or "clip.mp4")
        elif canal == "WordPress":
            res = publicar.publicar_wordpress(cfg, titulo.strip(), publicar.html_video(video_url, texto) if video_url else texto,
                                              imagen_id=imagen_id, quien=usuario, fecha=fecha_iso)
        elif canal == "Instagram":
            res = publicar.publicar_instagram(cfg, imagen_url or "", texto, quien=usuario,
                                              historia=(formato == "historia"))
        elif canal == "YouTube":
            res = publicar.publicar_youtube(cfg, video.getvalue() if video is not None else b"", titulo.strip(), texto,
                                            quien=usuario, fecha=fecha_iso,
                                            nombre_archivo=(video.name if video is not None else "video.mp4"))
        else:
            res = publicar.publicar_facebook(cfg, imagen_url, texto, quien=usuario, fecha=fecha_iso)
    return res, imagen_url


ZONA_HORARIA = "-03:00"   # Argentina; las fechas del recuadro son hora local


def _va_a_la_cola(canal, modo):
    if modo in ("apagado",):
        return False
    if canal == "Instagram":
        return True                      # la API de Instagram no programa
    if canal == "Facebook":
        return modo != "real"            # en real programa Facebook mismo
    return False                         # WordPress y YouTube programan nativo (o el video no se puede guardar en cola)                         # WordPress programa nativo (borrador con fecha / future)


ESTADO_TXT = {"a_aprobar": "⏳ pendiente de aprobación", "pendiente": "✅ aprobada · programada", "rechazada": "✖ rechazada",
              "publicada": "📣 publicada", "simulada": "👁 simulada", "error": "⚠ error", "cancelada": "✖ cancelada",
              "subida": "🖼 imagen subida", "draft": "📝 borrador en WordPress", "programada": "🗓 programada",
              "PUBLICADO": "📣 publicada", "borrador": "📝 borrador", "prueba": "🧪 prueba (simulado)",
              "lista": "✉️ lista para enviar (pegar en Perfit)"}
NO_SON_PIEZAS = ("subida", "prueba", "borrador", "simulada", "simulado")   # fuera del registro del panel


def _fecha(v):
    v = str(v or "")
    return v[:16].replace("T", " ") if v else ""


def _fila_publicacion(p, mostrar_usuario=False, pref=""):
    """Una pieza del registro, en un recuadro: estado, canal, texto, fechas y quién hizo qué."""
    res = p.get("resultado") or {}
    est = p.get("estado") or ""
    with st.container(border=True):
        c1, c2 = st.columns([1, 4])
        if res.get("video_url"):
            c1.video(res["video_url"])
        elif p.get("imagen_url"):
            c1.image(p["imagen_url"], use_container_width=True)
        cab = f"**{ESTADO_TXT.get(est, est)}** · {canal_txt(p.get('canal'))} · creada {_fecha(p.get('creado'))}"
        if mostrar_usuario:
            cab += f" · por **{p.get('usuario')}**"
        c2.markdown(cab)
        if p.get("titulo"):
            c2.markdown(f"**{p['titulo']}**")
        if p.get("canal") == "newsletter":
            c2.caption("Newsletter · plantilla " + str((res.get("pieza") or {}).get("plantilla") or res.get("plantilla") or "mensual"))
            if p.get("texto"):
                c2.download_button("⬇️ Descargar HTML", data=(p["texto"] or "").encode("utf-8"),
                                   file_name=f"newsletter-{str(p.get('creado', ''))[:10]}.html", mime="text/html", key=f"dl_{pref}{p['id']}")
        elif p.get("texto"):
            c2.caption((p["texto"] or "")[:220] + ("…" if len(p.get("texto") or "") > 220 else ""))
        detalle = []
        if p.get("fecha_programada"):
            detalle.append(f"sale el {_fecha(p['fecha_programada'])}")
        if res.get("aprobada_por"):
            detalle.append(f"aprobó **{res['aprobada_por']}** ({_fecha(res.get('aprobada_en'))})")
        if res.get("rechazada_por"):
            detalle.append(f"rechazó **{res['rechazada_por']}** ({_fecha(res.get('rechazada_en'))})")
        if res.get("nota"):
            detalle.append(f"nota: _{res['nota']}_")
        if res.get("cancelada_por"):
            detalle.append(f"canceló **{res['cancelada_por']}**")
        if est in ("publicada", "PUBLICADO") and (res.get("ultimo") or {}).get("permalink"):
            detalle.append(f"[ver publicación ↗]({res['ultimo']['permalink']})")
        if est == "error":
            detalle.append(f"error: {str((res.get('ultimo') or {}).get('aviso', ''))[:120]}")
        if detalle:
            c2.markdown(" · ".join(detalle))


def _mis_recortes(usuario, todos=False):
    """(16/10, pedido de Franco) Los recortes que pidió la persona (desde las tarjetas del chat o pidiéndoselo al bot),
    con estado, link y botón para publicar. todos=True (Panel admin → Clips): los de todo el equipo, con quién lo pidió
    y «Reintentar» en los que fallaron."""
    try:
        filas = db.listar_clips(100)
        if not todos:
            filas = [c for c in filas if c.get("pedido_por") in (usuario, "bot")]
    except Exception as e:
        st.error(f"No pude leer los recortes: {e}")
        return
    if not filas:
        st.caption(("Todavía no se pidió ningún recorte." if todos else "Todavía no pediste ningún recorte.")
                   + " Se piden desde los botones «✂️ Pedir el recorte» / «📱 Pedir en vertical» "
                   "debajo de cada video en el chat, o diciéndole al bot «pedime ese tramo en vertical».")
        return
    st.caption("Los recortes tardan unos 15 minutos. Cuando están listos aparece el link y el botón para publicar. "
               "Borrá los que no vayas a usar: cada uno ocupa entre 5 y 50 MB en WordPress.")
    _EST = {"listo": "✅ listo", "pedido": "⏳ en proceso", "error": "⚠ error"}
    cfg = publicar.Config(st.secrets)
    for c in filas:
        with st.container(border=True):
            c1, c2 = st.columns([1, 3])
            if c.get("estado") == "listo" and c.get("url"):
                c1.video(c["url"])
            fmt = "📱 vertical" if c.get("formato") == "vertical" else "🎬 horizontal"
            estado_txt = _EST.get(c.get("estado"), c.get("estado"))
            regenerando = c.get("estado") == "pedido" and bool(c.get("srt_editado")) and bool(c.get("url"))
            if regenerando:   # (19/10) ya había un video listo y se pidió rehacerlo con los subtítulos corregidos
                estado_txt = "⏳ regenerando con subtítulos corregidos"
            c2.markdown(f"**{(c.get('titulo') or c['video_id'])[:90]}**  \n"
                        f"{_fecha(c.get('creado'))} · {fmt} · {mmss_(c['inicio_ms'])}–{mmss_(c['fin_ms'])} · {estado_txt}"
                        + (f" · pidió **{c.get('pedido_por') or '—'}**" if todos else ""))
            if c.get("nota"):
                c2.caption(c["nota"][:160])
            if c.get("estado") == "error" and c.get("error"):
                c2.caption(c["error"][:160])
                if todos and c2.button("↻ Reintentar", key=f"rec_re_{c['id']}"):
                    db.actualizar_clip(c["id"], {"estado": "pedido", "error": None})
                    st.rerun()
            # (16/10, Franco) Borrar: saca el archivo de WordPress y el registro. Avisa si una publicación lo usa.
            if c.get("estado") in ("error", "pedido") or not c.get("url"):
                if c2.button("🗑 Borrar", key=f"rec_del_{c['id']}", help="Saca este pedido de la lista."):
                    if c.get("url"):   # (19/10) estaba regenerándose: el video anterior sigue en WordPress, se borra también
                        publicar.borrar_media_por_url(cfg, c["url"], quien=usuario)
                    db.borrar_clip(c["id"])
                    st.rerun()
            if c.get("estado") == "listo" and c.get("url"):
                b1, b2, b3, b4 = c2.columns([1.2, 1, 1, 1.2])
                b1.link_button("Abrir el recorte ↗", c["url"])
                usados = []
                try:
                    usados = db.publicaciones_con_video(c["url"])
                except Exception:
                    pass
                conf = b4.checkbox("confirmo", key=f"rec_conf_{c['id']}", help="Marcá para habilitar Borrar." + (" OJO: este recorte está en una publicación." if usados else ""))
                if usados:
                    c2.caption("⚠ Este recorte está usado en: " + ", ".join(f"{u.get('canal')} ({u.get('estado')})" for u in usados[:4])
                               + ". Si lo borrás, un blogpost que lo tenga embebido se queda sin video; Instagram, Facebook y YouTube ya tienen su copia.")
                if b3.button("🗑 Borrar", key=f"rec_del_{c['id']}", disabled=not conf):
                    ok, aviso = publicar.borrar_media_por_url(cfg, c["url"], quien=usuario)
                    if ok:
                        db.borrar_clip(c["id"])
                        st.toast("Recorte borrado (archivo y registro).")
                        st.rerun()
                    else:
                        st.error(aviso)
                if b2.button("📣 Publicar", key=f"rec_pub_{c['id']}"):
                    st.session_state["pieza_video"] = {"video_url": c["url"], "video_formato": c.get("formato"), "titulo": (c.get("titulo") or "")[:100],
                                                       "texto": "", "canal": "instagram" if c.get("formato") == "vertical" else "",
                                                       "video_id": c["video_id"], "miniatura": f"https://img.youtube.com/vi/{c['video_id']}/hqdefault.jpg"}
                    st.session_state.pop("retomar", None)
                    st.session_state["vista"] = "publicar"
                    st.rerun()
                if c.get("formato") == "vertical":
                    _editor_subtitulos(c, usuario)


def _editor_subtitulos(c, usuario):
    """(19/10, pregunta de Julián en la reunión: "¿y si la transcripción entendió mal una palabra?") En un recorte vertical
    listo, «✏️ Editar subtítulos» muestra las líneas tal como se quemaron (clips.srt: texto y tiempos de cada una), una caja
    por línea. «Regenerar» guarda el SRT corregido en clips.srt_editado y vuelve el pedido a 'pedido': la cola de la nube lo
    corta de nuevo con esos subtítulos, sube el video nuevo y borra el anterior de WordPress (~15 min)."""
    import recortar_clip as rc
    srt = c.get("srt_editado") or c.get("srt") or ""
    if not srt.strip():
        st.caption("✏️ Este recorte se hizo antes de que guardáramos los subtítulos, así que no se pueden editar. "
                   "Si hace falta corregirlos, borralo y pedilo de nuevo.")
        return
    key = f"rec_edit_{c['id']}"
    abierto = st.session_state.get(key, False)
    if st.button("✏️ Editar subtítulos" if not abierto else "Cerrar sin cambios", key=f"{key}_btn",
                 help="Corregí lo que la transcripción automática entendió mal y pedí el video de nuevo."):
        st.session_state[key] = not abierto
        st.rerun()
    if not abierto:
        return
    lineas = rc.leer_srt(srt)
    st.caption("Una caja por línea, con el momento en que aparece. Corregí el texto; si dejás una línea vacía, se saca. "
               "Los tiempos no se cambian desde acá.")
    nuevas = []
    for i, l in enumerate(lineas):
        t0, t1 = l["inicio"][3:8], l["fin"][3:8]   # HH:MM:SS,mmm → MM:SS
        texto = st.text_input(f"{t0} → {t1}", value=l["texto"], key=f"{key}_{i}", max_chars=80)
        nuevas.append({"inicio": l["inicio"], "fin": l["fin"], "texto": texto})
    nuevo_srt = rc.armar_srt_de_lineas(nuevas)
    cambio = nuevo_srt.strip() != srt.strip()
    if not nuevo_srt.strip():
        st.warning("Quedaron todas las líneas vacías: el video saldría sin subtítulos. Dejá al menos una.")
    if st.button("🔁 Regenerar con estos subtítulos", key=f"{key}_go", type="primary", disabled=not (cambio and nuevo_srt.strip()),
                 help="Vuelve a cortar el video con los subtítulos corregidos. Tarda unos 15 minutos, como cualquier recorte."):
        hoy = datetime.date.today().strftime("%d/%m")
        db.actualizar_clip(c["id"], {"srt_editado": nuevo_srt, "estado": "pedido", "error": None,
                                     "nota": f"Subtítulos corregidos por {usuario} el {hoy}. El video anterior se reemplaza cuando termine."})
        st.session_state[key] = False
        st.toast("Listo, en unos 15 minutos el recorte aparece con los subtítulos corregidos.")
        st.rerun()
    if not cambio:
        st.caption("Todavía no cambiaste nada.")


def mmss_(ms):
    ms = int(ms or 0)
    return f"{ms // 60000:02d}:{ms // 1000 % 60:02d}"


def mis_publicaciones(usuario):
    """(13/10) Pantalla "Mis publicaciones", para todos: lo que creé y en qué estado está.
    (16/10, UX) Con solapas por estado; «Mis recortes» es una pantalla aparte (botón de la barra)."""
    rol = roles(usuario)
    if st.session_state.get("mis_filtro") == "🎬 mis recortes":
        st.markdown("### 🎬 Mis recortes")
        _mis_recortes(usuario)
        return
    st.markdown("### 📋 Mis publicaciones")
    st.caption(f"Tu rol: **{rol['nombre']}**" + (" · con publicación directa" if rol["publica"] else "")
               + ". Acá quedan todas las piezas que mandaste: pendientes, aprobadas, rechazadas y publicadas.")
    try:
        mias = db.listar_mias(usuario)
    except Exception as e:
        st.error(f"No pude leer tus piezas: {e}")
        return
    mias = [p for p in mias if p.get("estado") != "subida"]     # las subidas de imagen no son piezas
    if not mias:
        st.caption("Todavía no mandaste ninguna pieza.")
        return
    grupos = {"Pendientes": ("a_aprobar",), "Aprobadas": ("pendiente", "programada"),
              "Publicadas": ("publicada", "PUBLICADO", "draft", "lista"), "Borradores": ("borrador",),
              "Rechazadas": ("rechazada", "cancelada"), "Pruebas": ("prueba", "simulada", "simulado")}
    nombres = ["Todas"] + list(grupos)
    conteo = {n: (len(mias) if n == "Todas" else len([p for p in mias if p.get("estado") in grupos[n]])) for n in nombres}
    solapas = st.tabs([f"{n} ({conteo[n]})" for n in nombres])
    for nombre, solapa in zip(nombres, solapas):
        with solapa:
            _lista_piezas([p for p in mias if nombre == "Todas" or p.get("estado") in grupos[nombre]], usuario, nombre)


def _lista_piezas(mias, usuario, pref):
    """Las piezas de una solapa, con Retomar (borradores) y Eliminar (lo que se puede)."""
    if not mias:
        st.caption("Nada acá por ahora.")
    for p in mias:
        _fila_publicacion(p, pref=pref)
        est = p.get("estado")
        c1, c2, _ = st.columns([1, 1, 4])
        if est == "borrador" and c1.button("✏️ Retomar", key=f"ret_{pref}_{p['id']}"):
            if p.get("canal") == "newsletter":
                import newsletter_ui
                pz = (p.get("resultado") or {}).get("pieza") or {}
                newsletter_ui.cargar(pz.get("plantilla") or "mensual", pz.get("datos") or {}, p["id"])
                st.session_state["vista"] = "newsletter"
            else:
                st.session_state["retomar"] = p
                st.session_state["vista"] = "publicar"
            st.rerun()
        if est in db.ELIMINABLES and c2.button("🗑 Eliminar", key=f"del_{pref}_{p['id']}"):
            if db.eliminar_publicacion(p["id"], usuario):
                st.rerun()
            else:
                st.warning("Esa pieza no se puede eliminar.")


def mis_propuestas_sidebar(usuario):
    """(13/10) Lo que esta persona mandó a aprobación y en qué estado está."""
    try:
        mias = db.listar_mis_propuestas(usuario)
    except Exception:
        return
    if not mias:
        return
    with st.expander(f"📨 Mis piezas enviadas ({len(mias)})"):
        for p in mias:
            est = p.get("estado") or ""
            nota = (p.get("resultado") or {}).get("nota")
            st.markdown(f"{ESTADO_TXT.get(est, est)} · {canal_txt(p.get('canal'))} · {(p.get('titulo') or p.get('texto') or '')[:40]}"
                        + (f"  \n_{nota}_" if nota else ""))


def panel_aprobacion(usuario):
    """(13/10) Panel admin de los aprobadores: para aprobar · en cola · registro completo."""
    st.markdown("### 🛠 Panel admin")
    rol = roles(usuario)
    if not rol["aprueba"]:
        st.warning("Esta pantalla es para los aprobadores.")
        return
    try:
        pend = db.listar_a_aprobar()
    except Exception as e:
        st.error(f"No pude leer las piezas: {e}")
        return
    t1, t2, t3, t4, t5 = st.tabs([f"⏳ Para aprobar ({len(pend)})", "🗓 En cola", "📒 Registro", "🗑 Papelera", "🎬 Clips"])
    with t5:
        # (15/10) Clips exactos pedidos desde el chat. (16/10, UX) Mismas tarjetas que «Mis recortes», para todo el equipo.
        st.caption("Recortes pedidos desde el chat por todo el equipo. Los corta la nube cada 15 minutos desde los originales en Drive.")
        _mis_recortes(usuario, todos=True)
    with t4:
        # (15/10) Conversaciones borradas por cualquier usuario: se pueden restaurar durante 30 días.
        st.caption(f"Conversaciones que alguien borró. Se restauran desde acá durante {db.PAPELERA_DIAS} días; después se borran de verdad.")
        try:
            pap = db.listar_papelera()
        except Exception as e:
            pap = []
            st.caption(f"(sin acceso: {e})")
        if not pap:
            st.caption("La papelera está vacía.")
        for c in pap:
            c1, c2 = st.columns([4, 1])
            c1.markdown(f"**{c.get('titulo') or '(sin título)'}** · {c.get('usuario')} · borrada {_fecha(c.get('borrada'))} · última actividad {_fecha(c.get('actualizado'))}")
            if c2.button("↩ Restaurar", key=f"rest_{c['id']}"):
                db.restaurar_conversacion(c["id"])
                st.success("Restaurada: vuelve a aparecer en la lista de esa persona.")
                st.rerun()
    with t2:
        try:
            cola = db.listar_pendientes()
        except Exception:
            cola = []
        if not cola:
            st.caption("No hay piezas en cola.")
        for p in cola:
            _fila_publicacion(p, mostrar_usuario=True)
            if st.button("Cancelar", key=f"adm_cancel_{p['id']}"):
                db.cancelar_publicacion(p["id"], usuario)
                st.rerun()
    with t3:
        st.caption("Quién creó cada pieza, quién la aprobó o rechazó, y qué pasó. Las últimas 60.")
        try:
            for p in db.listar_registro():
                if p.get("estado") not in NO_SON_PIEZAS:
                    _fila_publicacion(p, mostrar_usuario=True)
        except Exception as e:
            st.caption(f"(sin registro: {e})")
    if not pend:
        t1.caption("No hay piezas esperando aprobación.")
        return
    cfg_real = publicar.Config(st.secrets)
    r = cfg_real.resumen()
    for p in pend:
        pid = p["id"]
        res = p.get("resultado") or {}
        canal = p.get("canal") or ""
        if canal == "newsletter":
            # (15/10) El newsletter no sale por la cola: aprobar = dejar el HTML listo para pegar en Perfit.
            import streamlit.components.v1 as _components
            with t1.container(border=True):
                st.markdown(f"**✉️ Newsletter** · propuso **{res.get('propuesta_por') or p.get('usuario')}** · "
                            f"{str(p.get('creado', ''))[:16].replace('T', ' ')} · **{p.get('titulo') or ''}**")
                _components.html(p.get("texto") or "", height=600, scrolling=True)
                nota = st.text_input("Nota (si rechazás, decí por qué)", key=f"apr_n_{pid}")
                b1, b2, b3 = st.columns(3)
                if b1.button("✅ Aprobar (queda listo para Perfit)", type="primary", key=f"apr_ok_{pid}"):
                    db.actualizar_publicacion(pid, {"estado": "lista", "resultado": dict(res, aprobada_por=usuario,
                                                    aprobada_en=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"))})
                    st.success("Aprobado. El HTML queda en «Mis publicaciones» de quien lo propuso y en el Registro, para descargar y pegar en Perfit.")
                    st.rerun()
                if b2.button("✖ Rechazar", key=f"apr_no_{pid}"):
                    db.rechazar_publicacion(pid, usuario, nota, res)
                    st.rerun()
                b3.download_button("⬇️ Descargar HTML", data=(p.get("texto") or "").encode("utf-8"),
                                   file_name=f"newsletter-{str(p.get('creado', ''))[:10]}.html", mime="text/html", key=f"apr_dl_{pid}")
            continue
        with t1.container(border=True):
            c1, c2 = st.columns([1, 2])
            if p.get("imagen_url"):
                c1.image(p["imagen_url"], use_container_width=True)
            c2.markdown(f"**{canal}** · propuso **{res.get('propuesta_por') or p.get('usuario')}** · "
                        f"{str(p.get('creado', ''))[:16].replace('T', ' ')}"
                        + (f" · formato {res['formato']}" if res.get("formato") else ""))
            if p.get("titulo"):
                c2.markdown(f"#### {p['titulo']}")
            c2.text(p.get("texto") or "")
            if res.get("texto_imagen"):
                c2.caption(f"Sobre la imagen: «{res['texto_imagen']}»")
            fp = str(p.get("fecha_programada") or "")
            c2.caption("Fecha y hora que pidió: " + (fp[:16].replace("T", " ") if fp else "cuanto antes")
                       + f" · el canal hoy está en modo **{r.get(canal, '?')}** · podés cambiarla antes de aprobar")
            try:
                f0 = datetime.date.fromisoformat(fp[:10]) if fp else datetime.date.today()
                h0 = datetime.time(int(fp[11:13]), int(fp[14:16])) if fp else (datetime.datetime.now() + datetime.timedelta(minutes=20)).time().replace(second=0, microsecond=0)
            except Exception:
                f0, h0 = datetime.date.today(), datetime.time(9, 0)
            d1, d2, d3 = st.columns([1, 1, 2])
            fecha = d1.date_input("Sale el", value=f0, key=f"apr_f_{pid}")
            hora = d2.time_input("a las", value=h0, key=f"apr_h_{pid}")
            nota = d3.text_input("Nota (si rechazás, decí por qué)", key=f"apr_n_{pid}")
            b1, b2 = st.columns(2)
            if b1.button("✅ Aprobar y programar", type="primary", key=f"apr_ok_{pid}"):
                fecha_iso = f"{fecha.isoformat()}T{hora.strftime('%H:%M:%S')}{ZONA_HORARIA}"
                db.aprobar_publicacion(pid, usuario, fecha_iso, r.get(canal, ""), res)
                st.success("Aprobada. Sale por la cola en esa fecha (la cola corre cada 15 min).")
                st.rerun()
            if b2.button("✖ Rechazar", key=f"apr_no_{pid}"):
                db.rechazar_publicacion(pid, usuario, nota, res)
                st.info("Rechazada. Quien la propuso lo ve en «Mis piezas enviadas».")
                st.rerun()


def piezas_en_cola_sidebar(usuario):
    """Expander en la barra lateral con las pendientes y un botón para cancelar cada una."""
    try:
        pend = db.listar_pendientes()
    except Exception:
        return
    if not pend:
        return
    with st.expander(f"🗓 Piezas en cola ({len(pend)})"):
        for p in pend:
            f = str(p.get("fecha_programada") or "")[:16].replace("T", " ")
            st.markdown(f"**{f}** · {canal_txt(p.get('canal'))} · {(p.get('titulo') or p.get('texto') or '')[:40]}")
            if st.button("Cancelar", key=f"cancel_{p['id']}"):
                db.cancelar_publicacion(p["id"], usuario)
                st.rerun()


def _mostrar_resultado(res, canal, modo, titulo, texto, archivo, imagen_url, fecha_iso, texto_imagen="", compuesta=None, video_url=None):
    if res.get("ok"):
        st.success(res.get("aviso", "Listo."))
    else:
        st.error(res.get("aviso", "No se pudo."))
    if res.get("link_editar"):
        st.markdown(f"[Abrir el borrador en WordPress ↗]({res['link_editar']})")
    if res.get("link") and canal == "YouTube":
        st.markdown(f"[Ver el video en YouTube ↗]({res['link']})")
    if res.get("permalink") and canal in ("Instagram", "Facebook"):
        st.markdown(f"[Ver la publicación ↗]({res['permalink']})")
    if modo == "simulado" or res.get("pieza"):
        with st.container(border=True):
            st.markdown(f"**Así quedaría en {canal}:**")
            if video_url:
                st.video(video_url)
            elif compuesta is not None:
                st.image(compuesta, width=360)
            elif archivo is not None:
                st.image(archivo.getvalue(), width=360)
            elif imagen_url:
                st.image(imagen_url, width=360)
            if texto_imagen and compuesta is None:
                st.caption(f"Sobre la imagen: «{texto_imagen}»")
            if canal == "WordPress":
                st.markdown(f"#### {titulo}")
                if video_url:
                    st.caption("(el recorte va acá, al principio de la entrada)")
                st.markdown(texto, unsafe_allow_html=True)
            else:
                st.text(texto)
            if fecha_iso:
                st.caption(f"Fecha pedida: {fecha_iso[:16].replace('T', ' ')}")


def formulario(usuario, key, pieza=None, compacto=False):
    """El formulario de publicar. `pieza` (de la herramienta proponer_publicacion) lo precompleta.
    `key` distingue cada instancia (uno por mensaje del bot, o 'tab')."""
    cfg = _cfg(usuario)
    cfg_real = publicar.Config(st.secrets)      # los modos reales de cada canal (para mandar a aprobación)
    rol = roles(usuario)
    publicar.REGISTRAR_EXTRA = _hook_registro(usuario)
    r = cfg.resumen()
    pieza = pieza or {}
    k = lambda s: f"pub_{key}_{s}"
    # (13/10) Borrador retomado: los selectores se precargan vía session_state una sola vez por borrador.
    borrador_id = pieza.get("_pid")
    if borrador_id and st.session_state.get(k("borrador_cargado")) != borrador_id:
        st.session_state[k("borrador_cargado")] = borrador_id
        for campo in ("fmt", "logo", "plogo", "tipo", "peso", "pos", "ali", "url", "firma", "busq"):
            if pieza.get(campo) is not None:
                st.session_state[k(campo)] = pieza[campo]
        st.session_state[k("prog")] = bool(pieza.get("fecha"))
        if pieza.get("fecha"):
            try:
                st.session_state[k("fecha")] = datetime.date.fromisoformat(pieza["fecha"])
                hh, mm = (pieza.get("hora") or "09:00").split(":")
                st.session_state[k("hora")] = datetime.time(int(hh), int(mm))
            except Exception:
                pass
        for campo in ("titulo", "timg", "texto"):
            st.session_state.pop(k(campo), None)
    if borrador_id:
        st.info("📝 Estás retomando un borrador. Al guardar se actualiza el mismo; al enviarlo o mandarlo a aprobación, el borrador se elimina.")

    # (16/10, revisión de UX) El formulario en tres pasos: "qué" abierto, "foto y diseño" plegado (sus
    # valores por defecto igual se aplican), "cuándo y enviar" abierto con un solo botón principal.
    texto_imagen = ""
    with st.expander("1 · Qué se publica", expanded=True):
        # (16/10) Pieza de video: un recorte exacto que ya está en WordPress. Va a Instagram (reel o historia),
        # Facebook (video) o YouTube (short). Sin imagen ni composición.
        video_url = (pieza.get("video_url") or "").strip() or None
        # Canal: precompletado solo si la persona lo dijo; si no, hay que elegirlo
        # (15/10) Nombres que distinguen la entrada en la web del newsletter (que tiene su propio editor).
        _NOMBRE = {"WordPress": "🌐 Blogpost (entrada en la web, WordPress)", "Instagram": "📸 Instagram", "Facebook": "📘 Facebook", "YouTube": "▶️ YouTube"}
        if video_url:
            st.video(video_url)
            st.caption("🎬 Recorte exacto" + (f" · {pieza['video_formato']}" if pieza.get("video_formato") else "") + ". Se publica tal cual está.")
            _canales = ["WordPress", "Instagram", "Facebook", "YouTube"]
            idx = {"wordpress": 0, "instagram": 1, "facebook": 2, "youtube": 3}.get(pieza.get("canal") or "", None)
            canal = st.radio("Canal", _canales, horizontal=True, index=idx, key=k("canal"), format_func=lambda c: _NOMBRE.get(c, c))
            # (16/10, punto 2) El recorte también va al newsletter: como bloque "Un recorte para ver", con la miniatura
            # del video original y el link al mp4 (el mail no reproduce video).
            if st.button("✉️ Llevar al newsletter", key=k("al_nl"), help="Abre el editor de Newsletter con el recorte cargado como bloque de video (imagen + link)."):
                import newsletter_ui
                datos = {"video": {"titulo": (pieza.get("titulo") or "")[:120], "texto": "", "imagen_url": pieza.get("miniatura") or "", "url": video_url}}
                newsletter_ui.cargar("mensual", datos, None)
                st.session_state.pop("pieza_video", None)
                st.session_state["vista"] = "newsletter"
                st.rerun()
        else:
            idx = {"wordpress": 0, "instagram": 1, "facebook": 2, "youtube": 3}.get(pieza.get("canal") or "", None)
            canal = st.radio("Canal", CANALES, horizontal=True, index=idx, key=k("canal"), format_func=lambda c: _NOMBRE.get(c, c))
            st.caption("Para el email a la comunidad usá «✉️ Newsletter» en la barra lateral: tiene sus plantillas y su vista previa.")
        if canal is None:
            st.caption("Elegí el canal para ver qué va a pasar al enviar.")
            modo = "apagado"
        else:
            modo = r[CLAVE[canal]]
            icono, txt = MODO_TXT.get(modo, ("⚫", modo))
            st.caption(f"{icono} {canal} en modo **{modo}** — {txt}")

        # Título y texto
        titulo = st.text_input("Título" + (" (obligatorio)" if canal in ("WordPress", "YouTube") else " (opcional, para el registro)"),
                               value=pieza.get("titulo", ""), key=k("titulo"))
        texto = st.text_area("Texto de la pieza" + (" (el caption)" if canal in ("Instagram", "Facebook") else " (la descripción del video)" if canal == "YouTube" else ""),
                             value=pieza.get("texto", ""), height=160 if compacto else 220, key=k("texto"),
                             placeholder="Escribí la pieza o pedísela al bot en el chat. En WordPress podés usar HTML simple.")

    _t2 = "2 · Formato del video" if video_url else "2 · Foto y diseño (frase encima, logo, tipografía)"
    with st.expander(_t2, expanded=bool(video_url)):
        if not video_url and (pieza.get("texto_imagen") or not compacto):
            texto_imagen = st.text_input("Texto sobre la imagen (para el diseño; no se publica como caption)",
                                         value=pieza.get("texto_imagen", ""), key=k("timg"))
        # YouTube: el archivo de video (no hay banco de videos)
        video = None
        imagen_url = None
        archivo = None
        compuesta = None
        formato = None
        if video_url:
            # (16/10) Pieza de video: sin imagen. En Instagram se elige reel (feed + Reels) o historia (24 h).
            if canal == "Instagram":
                formato = st.selectbox("Formato en Instagram", ["reel", "historia"], key=k("vfmt"),
                                       index=0 if (pieza.get("vfmt") or "reel") == "reel" else 1,
                                       help="Reel: sale en el feed y en Reels, con caption. Historia: dura 24 h y no lleva caption.")
                if formato == "historia":
                    st.caption("📱 Historia con video: dura 24 h y no lleva caption (Instagram no lo permite por API). El texto queda solo en el registro.")
                if pieza.get("video_formato") == "horizontal":
                    st.caption("Este recorte es horizontal. En Instagram se ve mejor el vertical (pedilo desde la misma tarjeta del chat).")
            elif canal == "YouTube":
                st.caption("Va al canal como video" + (" corto (short)" if pieza.get("video_formato") == "vertical" else "") + ". Título obligatorio.")
            elif canal == "WordPress":
                st.caption("🌐 Blogpost: el recorte va al principio de la entrada y el texto de abajo es el cuerpo. Título obligatorio.")
        elif canal == "YouTube":
            video = st.file_uploader("Video (mp4, mov)", type=["mp4", "mov", "m4v", "webm"], key=k("video"))
        if video_url:
            pass
        else:
          # Imagen: banco primero; URL o archivo como excepción
          st.markdown("**Imagen**" + (" (opcional en YouTube: queda solo en el registro)" if canal == "YouTube" else ""))
          cb1, cb2 = st.columns([4, 1])
          consulta = cb1.text_input("Buscar en el banco de imágenes", value=pieza.get("imagen_busqueda", ""), key=k("busq"),
                                    placeholder="ej. amanecer montaña calma", label_visibility="collapsed")
          formato_b = _formato_busqueda(canal, key)
          if cb2.button("Buscar", key=k("buscar_btn"), width="stretch"):
              st.session_state.get("banco_cache", {}).pop(f"{key}|{consulta.strip().lower()}|{formato_b or ''}", None)
          candidatas = _banco(cfg, consulta, key, formato_b)
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

          # (28/9) La frase encima de la foto: vista previa y elección de publicar así.
          # (8/10) El formato se elige aunque la foto vaya sola: antes, al destildar «Publicar así»
          # se perdía y una historia salía al feed (prueba real de Julián). Tipografía, posición y
          # alineación del texto, también pedidas por Julián.
          compuesta = None
          formato = None
          fuente = archivo.getvalue() if archivo is not None else imagen_url
          if canal in ("Instagram", "Facebook") and fuente:
              import imagen as _im
              con_frase = bool(texto_imagen.strip())
              st.markdown("**Con la frase encima**" if con_frase else "**Formato y logo**")
              cf1, cf2, cf3 = st.columns([2, 1, 1])
              firma = cf1.text_input("Firma", value=pieza.get("firma") or "— Br. David", key=k("firma")) if con_frase else ""
              # (13/10) arranca en el formato con el que se buscó en el banco; si no, al elegir cambia la lista
              # de candidatas y la foto elegida pasa a ser otra (visto en la prueba del circuito de aprobación).
              _fmts = ["cuadrado", "vertical", "historia"]
              formato = cf2.selectbox("Formato", _fmts, key=k("fmt"),
                                      index=_fmts.index(FORMATO_POR_CANAL.get(canal, "cuadrado")),
                                      help="«historia» en Instagram publica una HISTORIA (24 h, sin caption; la frase va en la imagen).")
              usar = cf3.checkbox("Publicar así", value=True, key=k("usar_comp"),
                                  help="Si lo destildás, se publica la foto sola y el texto queda solo en el registro.") if con_frase else True
              # (13/10) Logo con tamaño estándar por formato; se elige cuál y en qué esquina.
              cl1, cl2 = st.columns(2)
              logo = cl1.selectbox("Logo", list(_im.LOGOS), key=k("logo"),
                                   help="Los que Julián subió a WordPress (13/10). El tamaño es estándar por formato.")
              posicion_logo = cl2.selectbox("Posición del logo", list(_im.POSICIONES_LOGO), key=k("plogo"),
                                            disabled=(logo == "Sin logo"))
              con_logo = logo != "Sin logo"
              if canal == "Instagram" and formato == "historia":
                  st.caption("📱 Historia de Instagram: dura 24 h y no lleva caption (Instagram no lo permite por API). "
                             "El texto de la pieza queda solo en el registro."
                             + ("" if (con_frase or con_logo) and usar else " La foto sale tal cual; si no es vertical 9:16, Instagram la recorta."))
              if con_frase:
                  cd1, cd2, cd3, cd4 = st.columns(4)
                  tipografia = cd1.selectbox("Tipografía", list(_im.TIPOGRAFIAS), key=k("tipo"),
                                             help="Raleway es la de la Fundación (15/10). Lora: serif. Lato: sans.")
                  peso = cd2.selectbox("Peso", list(_im.PESOS), key=k("peso"), help="Fina, normal o negrita (Lato no tiene variantes).")
                  posicion = cd3.selectbox("Posición del texto", list(_im.POSICIONES), key=k("pos"))
                  alineacion = cd4.selectbox("Alineación", list(_im.ALINEACIONES), key=k("ali"))
              else:
                  tipografia, peso, posicion, alineacion = _im.TIPOGRAFIA_DEFAULT, "normal", "centro", "centro"
              if con_frase or con_logo:
                  compuesta = _componer(fuente, _sin_firma_repetida(texto_imagen.strip(), firma) if con_frase else "",
                                        firma.strip(), formato, tipografia, posicion, alineacion,
                                        logo if con_logo else None, posicion_logo, peso)
                  if compuesta is not None:
                      st.image(compuesta, width=360)
                      if not usar:
                          compuesta = None

    with st.expander("3 · Cuándo y enviar", expanded=True):
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

        # (16/10, UX) Vista chica de lo que sale, para no tener que abrir el paso 2.
        _mini = compuesta if compuesta is not None else (archivo.getvalue() if archivo is not None else imagen_url)
        if _mini is not None and not video_url:
            st.image(_mini, width=140)
        if canal is not None:
            st.caption(_aviso(canal, modo, fecha_iso))
        confirmar = st.checkbox("Entiendo que esto publica de verdad", key=k("conf")) if modo == "real" else True

        # (13/10) Quien no publica en real ve el envío simulado y, al lado, "Enviar a aprobación".
        modo_real = cfg_real.resumen()[CLAVE[canal]] if canal else "apagado"
        puede_proponer = (canal in ("WordPress", "Instagram", "Facebook") and not rol["publica"]
                          and modo_real in ("real", "borrador"))
        # (16/10, UX) Un solo botón principal según el rol; los otros, secundarios.
        if puede_proponer:
            st.caption("Creador de contenido: lo mandás a aprobación y lo revisa " + (", ".join(rol["aprobadores"]) or "un aprobador")
                       + ". «Ver simulado» solo muestra cómo quedaría.")
            _cols = st.columns([2, 1.2, 1.4])
            proponer = _cols[0].button("📨 Enviar a aprobación", type="primary", key=k("aprob"), width="stretch")
            enviar = _cols[1].button("👁 Ver simulado", key=k("enviar"), width="stretch", disabled=(canal is None or modo == "apagado"))
            cb_bor = _cols[2]
        else:
            _cols = st.columns([2, 1.4])
            enviar = _cols[0].button(f"Enviar a {canal or '…'}" + (" (simulado)" if modo == "simulado" and canal else ""),
                                     type="primary", key=k("enviar"), width="stretch",
                                     disabled=(canal is None or modo == "apagado" or not confirmar))
            proponer = False
            cb_bor = _cols[1]
        # (13/10) Borrador: guarda todo lo del formulario sin mandar nada; se retoma desde "Mis publicaciones".
        if cb_bor.button("💾 Guardar borrador", key=k("borrador"), disabled=(canal is None), width="stretch"):
            datos = {"canal": CLAVE.get(canal, ""), "titulo": titulo, "texto": texto, "texto_imagen": texto_imagen,
                     "video_url": video_url, "video_formato": pieza.get("video_formato"), "vfmt": formato if video_url else None,
                     "url": imagen_url or "", "busq": st.session_state.get(k("busq"), ""),
                     "firma": st.session_state.get(k("firma")), "fmt": formato, "logo": st.session_state.get(k("logo")),
                     "plogo": st.session_state.get(k("plogo")), "tipo": st.session_state.get(k("tipo")),
                     "peso": st.session_state.get(k("peso")),
                     "pos": st.session_state.get(k("pos")), "ali": st.session_state.get(k("ali")),
                     "fecha": fecha_iso[:10] if fecha_iso else None, "hora": fecha_iso[11:16] if fecha_iso else None}
            pid = db.guardar_borrador(usuario, CLAVE[canal], titulo, texto, imagen_url or None,
                                      (fecha_iso + ZONA_HORARIA) if fecha_iso else None, datos, pid=borrador_id)
            if pid:
                st.success("Guardado como borrador. Lo retomás desde «Mis publicaciones», filtro Borradores.")
            else:
                st.error("No pude guardar el borrador (¿falta Supabase en los secrets?).")
        if (enviar or proponer) and borrador_id:
            try:
                db._req("DELETE", f"?id=eq.{borrador_id}&estado=eq.borrador", tabla="publicaciones")
            except Exception:
                pass
            st.session_state.pop("retomar", None)
        if enviar or proponer:
            if not texto.strip():
                st.error("Falta el texto de la pieza.")
                return
            if canal in ("WordPress", "YouTube") and not titulo.strip():
                st.error(f"En {canal} hace falta un título.")
                return
            if canal == "YouTube" and video is None and not video_url and modo != "simulado":
                st.error("Falta el archivo de video.")
                return
            if proponer:
                res, imagen_url = _enviar(cfg_real, usuario, canal, titulo, texto, archivo, imagen_url, fecha_iso, texto_imagen,
                                          video=video, compuesta=compuesta, formato=formato, aprobacion=True, video_url=video_url)
                _mostrar_resultado(res, canal, "simulado", titulo, texto if canal == "WordPress" else _texto_plano(texto),
                                   archivo, imagen_url, fecha_iso, texto_imagen, compuesta=compuesta, video_url=video_url)
                return
            res, imagen_url = _enviar(cfg, usuario, canal, titulo, texto, archivo, imagen_url, fecha_iso, texto_imagen,
                                      video=video, compuesta=compuesta,
                                      formato=formato, video_url=video_url)
            _mostrar_resultado(res, canal, modo, titulo, texto if canal == "WordPress" else _texto_plano(texto),
                               archivo, imagen_url, fecha_iso, texto_imagen, compuesta=compuesta, video_url=video_url)


def recuadro(usuario, pieza, key, abierto=True):
    """Debajo de una respuesta del bot que es una pieza."""
    etiqueta = "📤 Publicar esta pieza"
    if pieza.get("canal"):
        etiqueta += f" · {canal_txt(pieza['canal'])}"
    if pieza.get("fecha"):
        etiqueta += f" · {pieza['fecha']}" + (f" {pieza['hora']}" if pieza.get("hora") else "")
    with st.expander(etiqueta, expanded=abierto):
        if pieza.get("canal") == "newsletter":
            # (15/10) El newsletter se arma en su editor; el texto del bot entra como reflexión / encuadre.
            st.caption("Esta pieza es un newsletter. Se arma en el editor de Newsletter, con sus bloques y la vista previa.")
            if st.button("✉️ Abrir en el editor de Newsletter", type="primary", key=f"pub_{key}_nl"):
                import newsletter_ui
                nl = newsletter_ui  # noqa
                datos = {"asunto": pieza.get("titulo") or "", "reflexion": pieza.get("texto") or ""}
                nl.cargar("mensual", datos, None)
                st.session_state["vista"] = "newsletter"
                st.rerun()
            return
        formulario(usuario, key, pieza=pieza, compacto=True)


def _pieza_de_borrador(p):
    """Convierte una fila 'borrador' en el dict `pieza` que entiende formulario()."""
    d = dict(((p.get("resultado") or {}).get("pieza") or {}))
    d["_pid"] = p["id"]
    d.setdefault("canal", p.get("canal"))
    d.setdefault("titulo", p.get("titulo") or "")
    d.setdefault("texto", p.get("texto") or "")
    d.setdefault("url", p.get("imagen_url") or "")
    d["imagen_busqueda"] = d.get("busq") or ""
    return d


def render(usuario):
    """La pestaña 'Publicar' (respaldo)."""
    cfg = _cfg(usuario)
    r = cfg.resumen()
    st.markdown("### 📤 Publicar una pieza")
    st.caption("Lo normal es publicar desde el chat, debajo de la respuesta del bot. Esta pantalla es para piezas que no salen de una conversación.")
    with st.container(border=True):
        cols = st.columns(4)
        for col, nombre in zip(cols, CANALES):
            modo = r[CLAVE[nombre]]
            icono, txt = MODO_TXT.get(modo, ("⚫", modo))
            col.markdown(f"**{nombre}** {icono}  \n<small>{txt}</small>", unsafe_allow_html=True)
    ret = st.session_state.get("retomar")
    pv = st.session_state.get("pieza_video")     # (16/10) «Publicar» desde la tarjeta de un recorte en el chat
    if pv:
        st.info("🎬 Recorte listo para publicar. Elegí el canal, escribí el texto y mandalo (o a aprobación).")
    formulario(usuario, "tab", pieza=_pieza_de_borrador(ret) if ret else (pv or None))
    with st.expander("Registro: quién hizo qué (últimas 15 acciones)"):
        try:
            for p in db.listar_publicaciones(limite=15):
                st.markdown(f"- {str(p.get('creado', ''))[:16].replace('T', ' ')} · **{canal_txt(p.get('canal'))}** · {p.get('modo')} · "
                            f"{(p.get('titulo') or '')[:60]} · {p.get('usuario')} · {p.get('estado')}")
        except Exception as e:
            st.caption(f"(sin registro: {e})")
