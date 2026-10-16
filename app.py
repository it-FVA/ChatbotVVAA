"""UI Streamlit (online). Lógica en nucleo.py (cerebro) y guardado en db.py (Supabase)."""
import os, html, base64
import streamlit as st
import nucleo
import db

st.set_page_config(page_title="Asistente · Vivir Agradecidos", page_icon="🌼", layout="centered")


def _sec(k, d=""):
    return st.secrets.get(k, d)


# ---------------- Credenciales al entorno (para nucleo y db) ----------------
os.environ["OPENAI_API_KEY"] = _sec("OPENAI_API_KEY")
os.environ["ASISTENTE_MODELO"] = _sec("ASISTENTE_MODELO", "gpt-4o-mini")
os.environ["SUPABASE_URL"] = _sec("SUPABASE_URL")
os.environ["SUPABASE_KEY"] = _sec("SUPABASE_KEY")

# ---------------- Interruptores del buscador (ver ARQUITECTURA-BUSCADOR.md) ----------------
# Todos nacen apagados / con el valor de siempre. Se prenden desde los secrets de
# Streamlit Cloud, sin tocar código. Si no están en secrets, no cambia nada.
for _k, _d in (("BUSQUEDA_HIBRIDA", "0"), ("LIMPIEZA_EXTRA", "0"),
               ("RERANK_CANDIDATOS", "15"), ("RERANK_CHARS", "150"), ("CONTEXTO_CHARS", "1200"),
               ("DATOS_FIJOS_URL", ""),    # opcional: Sheet publicado; si está vacío, lee datos_fijos.md
               ("DISTINCIONES_URL", ""),  # opcional: pestaña Distinciones publicada como CSV; si falta, 7 de respaldo
               ("CONCEPTOS_URL", ""),      # opcional: pestaña Facetas publicada como CSV → expansión de consulta (5/10)
               ("EXPANSION_CONSULTA", "1")):  # "0" apaga la expansión aunque haya URL
    os.environ[_k] = str(_sec(_k, _d))

USUARIOS = dict(st.secrets.get("usuarios", {}))

# ---------------- Login por usuario ----------------
if not st.session_state.get("usuario"):
    st.markdown("### 🌼 Asistente de contenido · Vivir Agradecidos")
    u = st.text_input("Usuario")
    p = st.text_input("Contraseña", type="password")
    if st.button("Entrar"):
        if u in USUARIOS and str(USUARIOS[u]) == p:
            st.session_state.usuario = u
            st.session_state.messages = []
            st.session_state.conv_id = None
            st.session_state.conv_titulo = None
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos.")
    if not USUARIOS:
        st.caption("⚠ Falta configurar la lista de usuarios en los secrets ([usuarios]).")
    st.stop()

USUARIO = st.session_state.usuario

# (7/10) Idioma de la interfaz por usuario (pedido de Beto: comunidades inglesa y alemana).
# Se define en secrets, sección [idiomas] (usuario = "en" | "de"); sin entrada, español.
# El bot responde en el idioma en que le escriben igual; esto solo traduce los textos fijos
# de la pantalla y le avisa al bot de qué comunidad viene la persona.
_IDIOMAS_DEFAULT = {"gratefulness": "en", "dankbarleben": "de"}
IDIOMA = str(dict(st.secrets.get("idiomas", {})).get(USUARIO, _IDIOMAS_DEFAULT.get(USUARIO, "es"))).lower()
if IDIOMA not in ("es", "en", "de"):
    IDIOMA = "es"
_T = {
    "nueva": {"es": "➕ Nueva conversación", "en": "➕ New conversation", "de": "➕ Neues Gespräch"},
    "tus": {"es": "Tus conversaciones", "en": "Your conversations", "de": "Deine Gespräche"},
    "salir": {"es": "Salir", "en": "Log out", "de": "Abmelden"},
    "volver": {"es": "💬 Volver al chat", "en": "💬 Back to chat", "de": "💬 Zurück zum Chat"},
    "mis": {"es": "📋 Mis publicaciones", "en": "📋 My posts", "de": "📋 Meine Beiträge"},
    "newsletter": {"es": "✉️ Newsletter", "en": "✉️ Newsletter", "de": "✉️ Newsletter"},
    "renombrar": {"es": "Renombrar", "en": "Rename", "de": "Umbenennen"},
    "borrar": {"es": "🗑️ Borrar conversación", "en": "🗑️ Delete conversation", "de": "🗑️ Gespräch löschen"},
    "sub": {"es": "Búsqueda y armado fundados solo en el material real de la Fundación. Los borradores son para revisión del equipo.",
            "en": "Search and drafting grounded only in the Foundation's real material (Br. David and facilitators). Drafts are for the team's review. Quotes are shown in their original language.",
            "de": "Suche und Entwürfe gründen ausschließlich auf dem echten Material der Stiftung (Br. David und Begleiter). Entwürfe sind zur Durchsicht. Zitate erscheinen in ihrer Originalsprache."},
    "placeholder": {"es": "Escribí acá… (ej: 'estoy pensando una campaña sobre gratitud, ¿por dónde arrancarías?')",
                    "en": "Write here… (e.g. 'what does Br. David say about hope and expectation?')",
                    "de": "Hier schreiben… (z. B. 'Was sagt Bruder David über Dankbarkeit und Angst?')"},
    "pensando": {"es": "Pensando…", "en": "Thinking…", "de": "Denke nach…"},
}
def T(k):
    return _T[k].get(IDIOMA, _T[k]["es"])

st.session_state.setdefault("messages", [])
st.session_state.setdefault("conv_id", None)
st.session_state.setdefault("conv_titulo", None)

# ---------------- Pestaña "Publicar" (24/9): solo para los usuarios listados ----------------
# PUBLICAR_USUARIOS = "franco,julian" en secrets. Los switches por canal (PUBLICAR_WORDPRESS,
# PUBLICAR_INSTAGRAM, PUBLICAR_FACEBOOK) también viven en secrets; ver publicar.py.
# (13/10, reunión) Todos ven Publicar en simulado y pueden mandar a aprobación; APROBADORES aprueban;
# PUBLICAR_USUARIOS publican en real. Ver publicar_ui.roles().
import publicar_ui
PUEDE_PUBLICAR = True
ROL = publicar_ui.roles(USUARIO)
st.session_state.setdefault("vista", "chat")
st.session_state["_clipbtn"] = 0   # (15/10) claves únicas de los botones de clips, por corrida


@st.cache_resource(show_spinner="Cargando el corpus…")
def _init():
    nucleo.cargar()
    return True
_init()


# ---------------- Persistencia de conversaciones ----------------
def guardar():
    msgs = st.session_state.messages
    if not msgs or not db.disponible():
        return
    try:
        if st.session_state.conv_id:
            db.actualizar_conversacion(st.session_state.conv_id,
                                       st.session_state.conv_titulo or "Conversación", msgs)
        else:
            titulo = nucleo.titular(msgs)      # título sugerido automáticamente
            st.session_state.conv_titulo = titulo
            st.session_state.conv_id = db.crear_conversacion(USUARIO, titulo, msgs)
    except Exception as e:
        st.warning(f"No pude guardar la conversación: {e}")


def abrir(cid):
    conv = db.cargar_conversacion(cid)
    if conv:
        st.session_state.messages = db.normalizar(conv.get("mensajes"))
        st.session_state.conv_id = conv["id"]
        st.session_state.conv_titulo = conv.get("titulo")


# ---------------- Sidebar (estilo ChatGPT) ----------------
with st.sidebar:
    st.markdown(f"**👤 {USUARIO}**")
    # (24/9 noche) Publicar pasa dentro del chat: el bot propone el recuadro cuando la pieza está lista.
    # La pantalla "Publicar" suelta ya no se muestra; queda solo con ?vista=publicar en la dirección,
    # para cargar algo que no salió de una conversación.
    # (13/10) ?vista=... en la dirección se aplica una sola vez; después mandan los botones de la barra.
    if st.query_params.get("vista") in ("publicar", "aprobar", "mis", "newsletter") and not st.session_state.get("vista_qp"):
        st.session_state.vista = st.query_params.get("vista")
        st.session_state["vista_qp"] = True
    if st.session_state.vista in ("publicar", "aprobar", "mis", "newsletter"):
        if st.button(T("volver"), use_container_width=True):
            st.query_params.clear()
            st.session_state.vista = "chat"
            st.session_state.pop("retomar", None)
            st.session_state.pop("pieza_video", None)
            st.rerun()
    # (13/10) Roles: todos tienen "Mis publicaciones"; los aprobadores, además, el panel admin.
    if st.button(T("mis"), use_container_width=True):
        st.session_state.vista = "mis"
        st.rerun()
    # (15/10) Canal Newsletter: editor con plantillas, para todos (pasa por aprobación como cualquier pieza).
    if IDIOMA == "es" and st.button(T("newsletter"), use_container_width=True):
        st.session_state.vista = "newsletter"
        st.rerun()
    if ROL["aprueba"]:
        try:
            _n_apr = len(db.listar_a_aprobar())
        except Exception:
            _n_apr = 0
        if st.button(f"🛠 Panel admin · {_n_apr} para aprobar", use_container_width=True, type="primary" if _n_apr else "secondary"):
            st.session_state.vista = "aprobar"
            st.rerun()
    if st.button(T("nueva"), use_container_width=True, type="primary"):
        st.session_state.vista = "chat"
        st.session_state.messages = []
        st.session_state.conv_id = None
        st.session_state.conv_titulo = None
        st.rerun()

    st.divider()
    st.caption(T("tus"))
    if db.disponible():
        try:
            for c in db.listar_conversaciones(USUARIO)[:30]:
                cid = str(c["id"])
                titulo = c.get("titulo") or "Conversación"
                col_a, col_b = st.columns([5, 1], gap="small")
                if col_a.button(titulo[:32], key="open_" + cid, use_container_width=True):
                    abrir(c["id"])
                    st.rerun()
                with col_b.popover("⋮"):
                    nuevo = st.text_input("Renombrar", value=titulo, key="ren_" + cid,
                                          label_visibility="collapsed", placeholder="Nuevo nombre")
                    if st.button("✏️ Renombrar", key="renb_" + cid, use_container_width=True):
                        db.renombrar(c["id"], nuevo.strip() or titulo)
                        if st.session_state.conv_id == c["id"]:
                            st.session_state.conv_titulo = nuevo.strip() or titulo
                        st.rerun()
                    if st.button("🗑️ Borrar conversación", key="delb_" + cid, use_container_width=True):
                        db.borrar_conversacion(c["id"])
                        if st.session_state.conv_id == c["id"]:
                            st.session_state.messages = []
                            st.session_state.conv_id = None
                            st.session_state.conv_titulo = None
                        st.rerun()
        except Exception as e:
            st.caption(f"(no pude leer el historial: {e})")
    else:
        st.caption("(guardado desactivado: falta configurar Supabase)")
    st.divider()
    if st.button("Salir", use_container_width=True):
        for k in ("usuario", "messages", "conv_id", "conv_titulo"):
            st.session_state.pop(k, None)
        st.rerun()

# ---------------- Estilo de marca ----------------
st.markdown("""
<style>
.block-container { padding-top: 2.2rem; max-width: 820px; }
[data-testid="stChatMessage"] { border-radius: 14px; padding: .35rem .2rem; }
.vac-head { display:flex; align-items:center; gap:14px; margin:.1rem 0 .1rem; }
.vac-head img { width:60px; height:60px; }
.vac-h-t { font-size:1.55rem; font-weight:800; line-height:1.1; margin:0; }
.vac-h-s { font-size:.9rem; opacity:.6; margin:2px 0 0; }
.vac-rule { height:3px; border:none; margin:.55rem 0 .1rem;
            background:linear-gradient(90deg,#F39C12,rgba(243,156,18,0)); border-radius:3px; }
.vac-card { border:1px solid rgba(140,130,110,.28); border-left:3px solid #F39C12; border-radius:10px;
            padding:11px 14px; margin:9px 0; background:rgba(243,156,18,.055); }
.vac-top { display:flex; gap:10px; align-items:baseline; flex-wrap:wrap; margin-bottom:2px; }
.vac-tag { color:#d98a0f; font-size:.7rem; font-weight:800; letter-spacing:.04em; text-transform:uppercase; }
.vac-autor { font-size:.8rem; opacity:.7; }
.vac-titulo { font-weight:700; font-size:.95rem; margin:1px 0 4px; }
.vac-quote { font-style:italic; opacity:.92; line-height:1.45; margin:0 0 8px; }
.vac-trad { font-style:normal; opacity:.75; font-size:.92em; }
.vac-src { font-size:.82rem; color:#d98a0f !important; text-decoration:none; font-weight:700; }
.vac-src:hover { text-decoration:underline; }
</style>
""", unsafe_allow_html=True)

AVATAR_BOT = "🌼"
AVATAR_USER = "🧑"
HERE = os.path.dirname(os.path.abspath(__file__))

try:
    _logo64 = base64.b64encode(open(os.path.join(HERE, "logo.png"), "rb").read()).decode()
    _logo_html = f'<img src="data:image/png;base64,{_logo64}" alt="logo">'
except Exception:
    _logo_html = "🌼"
st.markdown(
    f'<div class="vac-head">{_logo_html}'
    '<div><p class="vac-h-t">Asistente de contenido</p>'
    '<p class="vac-h-s">Br. David · Vivir Agradecidos</p></div></div>'
    '<hr class="vac-rule">', unsafe_allow_html=True)
st.caption(T("sub"))

if st.session_state.vista == "publicar":
    publicar_ui.render(USUARIO)
    st.stop()
if st.session_state.vista == "mis":
    publicar_ui.mis_publicaciones(USUARIO)
    st.stop()
if st.session_state.vista == "newsletter":
    import newsletter_ui
    newsletter_ui.render(USUARIO)
    st.stop()
if st.session_state.vista == "aprobar":
    publicar_ui.panel_aprobacion(USUARIO)
    st.stop()


_TAGS = {"en": {"ARTÍCULO": "ARTICLE", "CLIP": "CLIP", "LIBRO": "BOOK", "pág.": "p."},
         "de": {"ARTÍCULO": "ARTIKEL", "CLIP": "CLIP", "LIBRO": "BUCH", "pág.": "S."}}
_VER = {"es": "Ver fuente ↗", "en": "View source ↗", "de": "Quelle öffnen ↗"}
_TRAD_LABEL = {"en": "translation", "de": "Übersetzung"}


def render_mats(mats, idioma="es"):
    """Tarjetas de fuentes. (8/10) Para las cuentas en inglés/alemán: etiquetas traducidas, título original
    + [traducción], y extracto original seguido de su traducción marcada (nucleo.traducir_tarjetas, una
    llamada por respuesta, cacheada). Si la traducción falla, la tarjeta queda en original."""
    trads = nucleo.traducir_tarjetas(mats, idioma) if idioma in ("en", "de") else []
    # (15/10) Clips exactos: para las tarjetas de video, "ver el recorte" si ya está, o pedirlo (horizontal / vertical).
    try:
        _clips = db.clips_de([r.get("doc") for r in mats if r.get("fuente") == "youtube" and r.get("inicio_ms") is not None])
    except Exception:
        _clips = []
    _por_tramo = {(c["video_id"], int(c["inicio_ms"]), int(c["fin_ms"]), c["formato"]): c for c in _clips}
    for n, r in enumerate(mats):
        tag = r.get("tag") or ""
        if idioma in _TAGS:
            for a, b in _TAGS[idioma].items():
                tag = tag.replace(a, b)
        tag = html.escape(tag)
        autor = html.escape(r.get("autor") or "")
        titulo = html.escape(r.get("titulo") or "")
        texto = html.escape((r.get("texto") or "")[:300])
        tr = trads[n] if n < len(trads) else {}
        if tr.get("titulo") and tr["titulo"].strip().lower() != (r.get("titulo") or "").strip().lower():
            titulo += f' <span class="vac-trad">[{html.escape(tr["titulo"])}]</span>'
        quote = f'<div class="vac-quote">“{texto}”</div>'
        if tr.get("texto") and tr["texto"].strip()[:60].lower() != (r.get("texto") or "").strip()[:60].lower():
            quote += (f'<div class="vac-quote vac-trad">({_TRAD_LABEL.get(idioma, "")}) '
                      f'{html.escape(tr["texto"][:400])}</div>')
        href = r.get("ir") or ""
        src = (f'<a class="vac-src" href="{html.escape(href)}" target="_blank">{_VER.get(idioma, _VER["es"])}</a>'
               if href else "")
        st.markdown(
            f'<div class="vac-card"><div class="vac-top">'
            f'<span class="vac-tag">{tag}</span><span class="vac-autor">{autor}</span></div>'
            f'<div class="vac-titulo">{titulo}</div>'
            f'{quote}{src}</div>',
            unsafe_allow_html=True)
        if IDIOMA == "es" and r.get("fuente") == "youtube" and r.get("inicio_ms") is not None and r.get("fin_ms"):
            _botones_clip(r, _por_tramo)


_CLIP_TXT = {"horizontal": "✂️ Pedir el recorte", "vertical": "📱 Pedir en vertical"}


def _botones_clip(r, por_tramo):
    """Debajo de una tarjeta de video: link al recorte exacto si existe, o botones para pedirlo.
    El pedido queda en la tabla clips; recortar_pendientes.yml (GitHub Actions, cada 15 min) lo corta
    desde el original en Drive y lo sube a WordPress."""
    vid, ini, fin = r.get("doc"), int(r["inicio_ms"]), int(r["fin_ms"])
    st.session_state["_clipbtn"] = st.session_state.get("_clipbtn", 0) + 1
    base = f"clip_{st.session_state['_clipbtn']}"
    cols = st.columns([1, 1, 1, 1])
    for i, formato in enumerate(("horizontal", "vertical")):
        c = por_tramo.get((vid, ini, fin, formato))
        if c and c.get("estado") == "listo" and c.get("url"):
            cols[i].markdown(f'<a class="vac-src" href="{html.escape(c["url"])}" target="_blank">'
                             f'{"🎬 Ver el recorte" if formato == "horizontal" else "📱 Ver en vertical"}</a>', unsafe_allow_html=True)
            # (16/10) Publicar el recorte: abre el formulario con el video cargado (Instagram reel/historia,
            # Facebook video, YouTube). Pasa por la misma aprobación y cola que las fotos.
            if PUEDE_PUBLICAR and cols[i + 2].button("📣 Publicar" + (" el vertical" if formato == "vertical" else " el recorte"),
                                                     key=f"{base}_pub_{formato}", help="Reel o historia en Instagram, video en Facebook o short en YouTube."):
                st.session_state["pieza_video"] = {"video_url": c["url"], "video_formato": formato, "titulo": (r.get("titulo") or "")[:100],
                                                   "texto": "", "canal": "instagram" if formato == "vertical" else "",
                                                   "video_id": vid, "miniatura": f"https://img.youtube.com/vi/{vid}/hqdefault.jpg"}
                st.session_state.pop("retomar", None)
                st.session_state["vista"] = "publicar"
                st.rerun()
        elif c and c.get("estado") == "pedido":
            cols[i].caption(("✂️" if formato == "horizontal" else "📱") + " recorte pedido · en unos minutos")
        elif c and c.get("estado") == "error":
            cols[i].caption(("✂️" if formato == "horizontal" else "📱") + " no se pudo recortar (ver Panel admin)")
        elif cols[i].button(_CLIP_TXT[formato], key=f"{base}_{formato}", help="Corta el tramo exacto desde el original en Drive y lo sube a la biblioteca de WordPress. Tarda unos minutos."):
            res = db.pedir_clip(vid, ini, fin, formato, r.get("titulo"), USUARIO)
            st.toast("Pedido. En unos minutos aparece «Ver el recorte» en esta tarjeta." if res else "No pude registrar el pedido.")
            st.rerun()


def publicar_en_chat(m, i, ultimo):
    """(24/9) Publicar desde adentro del chat: cuando el bot decide que la pieza está lista
    (herramienta proponer_publicacion), debajo de su respuesta aparece el recuadro precompletado
    con texto, título, canal, fecha e imágenes del banco. Si no es una pieza, no hay nada."""
    if PUEDE_PUBLICAR and m.get("pieza"):
        import publicar_ui
        publicar_ui.recuadro(USUARIO, m["pieza"], key=f"m{i}", abierto=ultimo)


_n = len(st.session_state.messages)
for i, m in enumerate(st.session_state.messages):
    rol = "user" if m.get("role") == "user" else "assistant"
    with st.chat_message(rol, avatar=(AVATAR_USER if rol == "user" else AVATAR_BOT)):
        st.markdown(m.get("content", ""))
        if m.get("mats"):
            render_mats(m["mats"], IDIOMA)
        if rol == "assistant":
            publicar_en_chat(m, i, ultimo=(i == _n - 1))

# (8/10) Dos pasos: primero el mensaje de la persona entra al historial y se redibuja (así se ve enseguida);
# después, si el último mensaje es de la persona y no tiene respuesta, se genera. Antes todo pasaba dentro
# del `if prompt`, y si la persona mandaba otro mensaje mientras el bot pensaba, Streamlit cortaba el script:
# quedaban dos mensajes seguidos sin respuesta, o el mismo duplicado (visto en la cuenta gratefulness el 8/10).
if prompt := st.chat_input(T("placeholder")):
    msgs = st.session_state.messages
    ultimo = msgs[-1] if msgs else None
    repetido = (ultimo and ultimo.get("role") == "user"
                and " ".join(ultimo.get("content", "").split()) == " ".join(prompt.split()))
    if not repetido:
        msgs.append({"role": "user", "content": prompt})
    st.rerun()

_msgs = st.session_state.messages
if _msgs and _msgs[-1].get("role") == "user":
    with st.chat_message("assistant", avatar=AVATAR_BOT):
        with st.spinner(T("pensando")):
            historial = [{"role": m.get("role", "user"), "content": m.get("content", ""),
                          "mats": m.get("mats")} for m in _msgs]
            nucleo.USUARIO_ACTUAL = USUARIO     # (16/10) firma los pedidos de recorte que hace el bot
            texto, mats, _, pieza = nucleo.responder_con_pieza(historial, idioma=(IDIOMA if IDIOMA != "es" else None))
        st.markdown(texto)
        if mats:
            render_mats(mats, IDIOMA)
    _msgs.append({"role": "assistant", "content": texto, "mats": mats, "pieza": pieza})
    guardar()
    st.rerun()          # vuelve a dibujar con el recuadro "Publicar esta pieza" bajo la respuesta nueva
