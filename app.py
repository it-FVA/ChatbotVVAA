"""UI Streamlit (online) del asistente. Toda la lógica vive en nucleo.py (cerebro compartido)."""
import os, html, base64
import streamlit as st
import nucleo

st.set_page_config(page_title="Asistente · Vivir Agradecidos", page_icon="🌼", layout="centered")

# ---------------- Acceso con contraseña ----------------
if not st.session_state.get("ok"):
    st.markdown("### 🌼 Asistente de contenido · Vivir Agradecidos")
    pw = st.text_input("Contraseña", type="password")
    if pw:
        if pw == st.secrets.get("APP_PASSWORD", ""):
            st.session_state["ok"] = True
            st.rerun()
        else:
            st.error("Contraseña incorrecta.")
    st.stop()

# ---------------- Config: pasar secrets al entorno para el cerebro ----------------
os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
os.environ["ASISTENTE_MODELO"] = st.secrets.get("ASISTENTE_MODELO", "gpt-4o-mini")

HERE = os.path.dirname(os.path.abspath(__file__))


@st.cache_resource(show_spinner="Cargando el corpus…")
def _init():
    nucleo.cargar()
    return True
_init()

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
.vac-card { border:1px solid rgba(128,128,128,.28); border-radius:12px;
            padding:12px 15px; margin:9px 0; background:rgba(243,156,18,.05); }
.vac-top { display:flex; gap:10px; align-items:baseline; flex-wrap:wrap; margin-bottom:2px; }
.vac-tag { color:#F39C12; font-size:.7rem; font-weight:800; letter-spacing:.04em; text-transform:uppercase; }
.vac-autor { font-size:.8rem; opacity:.7; }
.vac-titulo { font-weight:700; font-size:.95rem; margin:1px 0 4px; }
.vac-quote { font-style:italic; opacity:.92; line-height:1.45; margin:0 0 8px; }
.vac-src { font-size:.82rem; color:#F39C12 !important; text-decoration:none; font-weight:700; }
.vac-src:hover { text-decoration:underline; }
</style>
""", unsafe_allow_html=True)

AVATAR_BOT = "🌼"
AVATAR_USER = "🧑"

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
st.caption("Búsqueda y armado fundados solo en el material real de la Fundación. Los borradores son para revisión del equipo.")

if "messages" not in st.session_state:
    st.session_state.messages = []


def render_mats(mats):
    for r in mats:
        tag = html.escape(r.get("tag") or "")
        autor = html.escape(r.get("autor") or "")
        titulo = html.escape(r.get("titulo") or "")
        texto = html.escape((r.get("texto") or "")[:300])
        href = r.get("ir") or ""
        src = (f'<a class="vac-src" href="{html.escape(href)}" target="_blank">Ver fuente ↗</a>'
               if href else "")
        st.markdown(
            f'<div class="vac-card"><div class="vac-top">'
            f'<span class="vac-tag">{tag}</span><span class="vac-autor">{autor}</span></div>'
            f'<div class="vac-titulo">{titulo}</div>'
            f'<div class="vac-quote">“{texto}”</div>{src}</div>',
            unsafe_allow_html=True)


for m in st.session_state.messages:
    rol = "user" if m["role"] == "user" else "assistant"
    with st.chat_message(rol, avatar=(AVATAR_USER if rol == "user" else AVATAR_BOT)):
        st.markdown(m["content"])
        if m.get("mats"):
            render_mats(m["mats"])

if prompt := st.chat_input("Escribí acá… (ej: 'estoy pensando una campaña sobre gratitud, ¿por dónde arrancarías?')"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar=AVATAR_USER):
        st.markdown(prompt)
    with st.chat_message("assistant", avatar=AVATAR_BOT):
        with st.spinner("Pensando…"):
            historial = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
            texto, mats, _ = nucleo.responder(historial)
        st.markdown(texto)
        if mats:
            render_mats(mats)
    st.session_state.messages.append({"role": "assistant", "content": texto, "mats": mats})
