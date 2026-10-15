"""
newsletter_ui.py — Pantalla "✉️ Newsletter" (15/10). Editor de las dos plantillas con vista previa,
redacción con el bot, borrador, envío a aprobación y descarga del HTML.

Circuito: igual que cualquier pieza (ver publicar_ui.roles): quien no publica en real lo manda a
aprobación; el aprobador lo ve en el panel con la vista previa, lo aprueba (queda "lista": el HTML
listo para pegar en Perfit) o lo rechaza. El envío del email NO sale de acá.
"""
import datetime
import json

import streamlit as st
import streamlit.components.v1 as components

import db
import newsletter
import publicar_ui

ALTO_PREVIEW = 900


def _k(s):
    # Las claves llevan una "generación": al redactar, cargar o reiniciar se incrementa y los widgets
    # se crean de cero con los valores nuevos (Streamlit no actualiza un widget existente al cambiar `value`).
    return f"nl_{st.session_state.get('nl_gen', 0)}_{s}"


def _datos():
    """El newsletter en edición (session_state), creado vacío si no hay."""
    if "nl_datos" not in st.session_state:
        st.session_state["nl_datos"] = newsletter.vacio("mensual")
        st.session_state["nl_plantilla"] = "mensual"
        st.session_state["nl_pid"] = None
    return st.session_state["nl_datos"]


def cargar(plantilla, datos, pid=None):
    """Carga un newsletter en el editor (desde un borrador retomado o desde el chat)."""
    base = newsletter.vacio(plantilla)
    base.update(datos or {})
    st.session_state["nl_datos"] = base
    st.session_state["nl_plantilla"] = plantilla
    st.session_state["nl_pid"] = pid
    st.session_state["nl_gen"] = st.session_state.get("nl_gen", 0) + 1


def _campo(d, clave, etiqueta, alto=None, ayuda=None):
    v = st.text_area(etiqueta, value=d.get(clave) or "", key=_k(clave), height=alto, help=ayuda) if alto else \
        st.text_input(etiqueta, value=d.get(clave) or "", key=_k(clave), help=ayuda)
    d[clave] = v
    return v


def _editor_mensual(d):
    c1, c2 = st.columns([1, 2])
    d["mes"] = c1.text_input("Mes", value=d.get("mes") or "", key=_k("mes"), placeholder="Noviembre")
    d["asunto"] = c2.text_input("Asunto del email", value=d.get("asunto") or "", key=_k("asunto"))
    d["cabecera_url"] = st.text_input("Imagen de cabecera (URL del banco, 600×160)", value=d.get("cabecera_url") or "", key=_k("cab"))
    d["reflexion"] = st.text_area("Reflexión del mes (2 párrafos; el segundo arranca con «Brother David nos enseña que…»)",
                                  value=d.get("reflexion") or "", key=_k("ref"), height=180)
    st.markdown("**Preguntas para la reflexión personal**")
    pregs = list(d.get("preguntas") or ["", "", ""])
    for i in range(3):
        pregs[i] = st.text_input(f"Pregunta {i + 1}", value=pregs[i] if i < len(pregs) else "", key=_k(f"p{i}"), label_visibility="collapsed")
    d["preguntas"] = pregs
    with st.expander("Encuentro destacado", expanded=bool(d["encuentro"].get("frase"))):
        en = d["encuentro"]
        en["titulo"] = st.text_input("Título", value=en.get("titulo") or "", key=_k("en_t"))
        en["frase"] = st.text_input("Frase (con los verbos en mayúsculas)", value=en.get("frase") or "", key=_k("en_f"))
        en["imagen_url"] = st.text_input("Imagen (URL del banco)", value=en.get("imagen_url") or "", key=_k("en_i"))
        en["texto"] = st.text_area("Texto", value=en.get("texto") or "", key=_k("en_x"), height=90)
        b1, b2 = st.columns(2)
        en["boton_texto"] = b1.text_input("Texto del botón", value=en.get("boton_texto") or "", key=_k("en_bt"))
        en["boton_url"] = b2.text_input("Link del botón", value=en.get("boton_url") or "", key=_k("en_bu"))
    with st.expander("Agenda del mes", expanded=any(a.get("titulo") for a in d["agenda"])):
        n = st.number_input("Cantidad de actividades", 0, 6, value=max(1, len([a for a in d["agenda"] if a.get("titulo")]) or 3), key=_k("n_ag"))
        while len(d["agenda"]) < n:
            d["agenda"].append(newsletter.vacio("mensual")["agenda"][0])
        for i in range(int(n)):
            a = d["agenda"][i]
            st.markdown(f"**Actividad {i + 1}**")
            c1, c2 = st.columns(2)
            a["fecha_corta"] = c1.text_input("Fecha en chico", value=a.get("fecha_corta") or "", key=_k(f"a{i}_fc"), placeholder="Sábado 8 de noviembre")
            a["titulo"] = c2.text_input("Título", value=a.get("titulo") or "", key=_k(f"a{i}_t"))
            a["descripcion"] = st.text_input("Descripción (una línea)", value=a.get("descripcion") or "", key=_k(f"a{i}_d"))
            c1, c2, c3, c4 = st.columns(4)
            a["fecha"] = c1.text_input("📅 Fecha", value=a.get("fecha") or "", key=_k(f"a{i}_f"))
            a["horario"] = c2.text_input("🕙 Horario", value=a.get("horario") or "", key=_k(f"a{i}_h"))
            a["modalidad"] = c3.text_input("💻 Modalidad", value=a.get("modalidad") or "", key=_k(f"a{i}_m"))
            a["facilitan"] = c4.text_input("🌿 Facilitan", value=a.get("facilitan") or "", key=_k(f"a{i}_fa"))
            c1, c2, c3 = st.columns(3)
            a["boton_texto"] = c1.text_input("Botón", value=a.get("boton_texto") or "", key=_k(f"a{i}_bt"))
            a["boton_url"] = c2.text_input("Link", value=a.get("boton_url") or "", key=_k(f"a{i}_bu"))
            a["imagen_url"] = c3.text_input("Imagen (URL)", value=a.get("imagen_url") or "", key=_k(f"a{i}_i"))
        d["agenda"] = d["agenda"][:int(n)] if n else []
    with st.expander("Recursos para profundizar", expanded=bool(d["recursos"]["lectura"].get("titulo"))):
        rc = d["recursos"]
        rc["imagen_url"] = st.text_input("Imagen del bloque (URL)", value=rc.get("imagen_url") or "", key=_k("rc_i"))
        for k, rot, lab in (("lectura", "📖 Lectura", "de"), ("ecos", "🎧 Ecos (podcast)", "con"), ("meditacion", "🧘 Meditación guiada", "con")):
            c1, c2, c3 = st.columns([2, 2, 1])
            rc[k]["titulo"] = c1.text_input(f"{rot}: título", value=rc[k].get("titulo") or "", key=_k(f"{k}_t"))
            rc[k]["url"] = c2.text_input("link", value=rc[k].get("url") or "", key=_k(f"{k}_u"))
            rc[k][lab] = c3.text_input(lab, value=rc[k].get(lab) or "", key=_k(f"{k}_q"))
    d["cierre"] = st.text_input("Cierre (frase de deseo para el mes)", value=d.get("cierre") or "", key=_k("cierre"))
    d["firma"] = st.text_area("Firma", value=d.get("firma") or "", key=_k("firma"), height=70)


def _editor_revivi(d):
    d["asunto"] = st.text_input("Asunto del email", value=d.get("asunto") or "", key=_k("asunto"), placeholder="Reviví: …")
    d["encuadre"] = st.text_area("Encuadre del tema (2 oraciones)", value=d.get("encuadre") or "", key=_k("enc"), height=90)
    d["intro"] = st.text_input("Frase de introducción", value=d.get("intro") or "", key=_k("intro"))
    for i, ep in enumerate(d["episodios"]):
        with st.expander(f"Episodio {i + 1}" + (f" · {ep['titulo'][:40]}" if ep.get("titulo") else ""), expanded=not ep.get("titulo")):
            ep["titulo"] = st.text_input("Título (en mayúsculas)", value=ep.get("titulo") or "", key=_k(f"e{i}_t"))
            ep["texto"] = st.text_area("Presentación (2-3 oraciones, con el nombre del invitado)", value=ep.get("texto") or "", key=_k(f"e{i}_x"), height=90)
            c1, c2 = st.columns(2)
            ep["url"] = c1.text_input("Link al episodio", value=ep.get("url") or "", key=_k(f"e{i}_u"))
            ep["imagen_url"] = c2.text_input("Foto del invitado (URL del banco)", value=ep.get("imagen_url") or "", key=_k(f"e{i}_i"))
    d["cierre_destacado"] = st.text_input("Frase destacada de cierre (va en mayúsculas)", value=d.get("cierre_destacado") or "", key=_k("cd"))
    d["cierre"] = st.text_area("Cierre", value=d.get("cierre") or "", key=_k("cierre"), height=80)
    d["firma"] = st.text_area("Firma", value=d.get("firma") or "", key=_k("firma"), height=70)


def _limpiar_widgets():
    st.session_state["nl_gen"] = st.session_state.get("nl_gen", 0) + 1
    gen_viejo = f"nl_{st.session_state['nl_gen'] - 1}_"
    for k in list(st.session_state):
        if k.startswith(gen_viejo):
            del st.session_state[k]


def render(usuario):
    st.markdown("### ✉️ Newsletter (email a la comunidad)")
    st.caption("No es una entrada de la web: eso va por «🌐 WordPress» en el recuadro de publicar.")
    rol = publicar_ui.roles(usuario)
    d = _datos()
    plantilla = st.session_state.get("nl_plantilla", "mensual")
    st.caption("El newsletter real de la Fundación, bloque por bloque. El bot redacta los textos desde el material; "
               "la agenda, las fotos y los links los cargás vos. El email no sale de acá: el HTML aprobado se pega en Perfit.")

    c1, c2, c3 = st.columns([2, 3, 1])
    nueva = c1.selectbox("Plantilla", list(newsletter.PLANTILLAS), format_func=lambda p: newsletter.PLANTILLAS[p],
                         index=list(newsletter.PLANTILLAS).index(plantilla), key="nl_plantilla_sel")
    if nueva != plantilla:
        cargar(nueva, {}, None)
        _limpiar_widgets()
        st.rerun()
    tema = c2.text_input("Tema (para que el bot redacte los textos)", key="nl_tema",
                         placeholder="ej. la confianza en la vida · los vínculos familiares")
    if c3.button("✨ Redactar", type="primary", key="nl_redactar", disabled=not tema.strip()):
        with st.spinner("Buscando material y redactando…"):
            try:
                nuevo, mats = newsletter.redactar(plantilla, tema.strip(), d)
                st.session_state["nl_datos"] = nuevo
                st.session_state["nl_mats"] = mats
                _limpiar_widgets()
                st.rerun()
            except Exception as e:
                st.error(f"No pude redactar: {e}")
    if st.session_state.get("nl_mats"):
        with st.expander("Material que usó el bot"):
            for m in st.session_state["nl_mats"]:
                st.markdown(f"- **{m.get('titulo')}** · {m.get('autor')} · {m.get('tag')}" + (f" · [ver]({m['ir'] or m['url']})" if (m.get("ir") or m.get("url")) else ""))

    col_ed, col_pv = st.columns([1, 1])
    with col_ed:
        st.markdown("#### Contenido")
        if st.session_state.get("nl_pid"):
            st.info("📝 Estás retomando un borrador: al guardar se actualiza el mismo.")
        (_editor_revivi if plantilla == "revivi" else _editor_mensual)(d)
    html = newsletter.armar_html(plantilla, d)
    with col_pv:
        st.markdown("#### Vista previa")
        components.html(html, height=ALTO_PREVIEW, scrolling=True)

    st.markdown("---")
    titulo = d.get("asunto") or (f"Newsletter {d.get('mes')}" if d.get("mes") else "Newsletter")
    b1, b2, b3, b4 = st.columns(4)
    b1.download_button("⬇️ Descargar HTML", data=html.encode("utf-8"),
                       file_name=f"newsletter-{datetime.date.today().isoformat()}.html", mime="text/html", key=_k("dl"))
    if b2.button("💾 Guardar como borrador", key=_k("borrador")):
        pid = db.guardar_borrador(usuario, "newsletter", titulo, html, None, None,
                                  {"plantilla": plantilla, "datos": d}, pid=st.session_state.get("nl_pid"))
        if pid:
            st.session_state["nl_pid"] = pid
            st.success("Guardado como borrador. Lo retomás desde «Mis publicaciones».")
        else:
            st.error("No pude guardar (¿falta Supabase?).")
    if b3.button("📨 Enviar a aprobación", type="primary", key=_k("aprob")):
        pid = db.proponer_publicacion(usuario, "newsletter", "borrador", titulo, html, None, None,
                                      extra={"plantilla": plantilla, "datos": d})
        if pid:
            if st.session_state.get("nl_pid"):
                try:
                    db._req("DELETE", f"?id=eq.{st.session_state['nl_pid']}&estado=eq.borrador", tabla="publicaciones")
                except Exception:
                    pass
            quien = ", ".join(rol["aprobadores"]) or "un aprobador"
            st.success(f"Quedó pendiente de aprobación ({quien}). Cuando lo aprueben, el HTML queda listo para pegar en Perfit. "
                       "Lo seguís en «Mis publicaciones».")
            cargar("mensual", {}, None)
        else:
            st.error("No pude guardar la pieza para aprobación.")
    if b4.button("🗑 Empezar de nuevo", key=_k("reset")):
        cargar(plantilla, {}, None)
        _limpiar_widgets()
        st.rerun()
