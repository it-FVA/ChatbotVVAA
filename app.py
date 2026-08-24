"""
Asistente de contenido "Vivir Agradecidos" — versión Streamlit (para HF/Streamlit Cloud).
Misma lógica que el server local, pero:
  - Los embeddings (corpus y consulta) son de OpenAI -> app liviana, sin modelo local.
  - Acceso con contraseña (st.secrets["APP_PASSWORD"]).
Secrets necesarios en Streamlit Cloud:
  OPENAI_API_KEY, APP_PASSWORD   (opcional: ASISTENTE_MODELO)
"""
import os, json, re, html, base64
import numpy as np
import streamlit as st
from openai import OpenAI

st.set_page_config(page_title="Asistente · Vivir Agradecidos", page_icon="🌼", layout="centered")

# ---------------- Acceso con contraseña ----------------
def autorizar():
    if st.session_state.get("ok"):
        return True
    st.markdown("### 🌼 Asistente de contenido · Vivir Agradecidos")
    pw = st.text_input("Contraseña", type="password")
    if pw:
        if pw == st.secrets.get("APP_PASSWORD", ""):
            st.session_state["ok"] = True
            st.rerun()
        else:
            st.error("Contraseña incorrecta.")
    st.stop()

autorizar()

# ---------------- Config ----------------
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
MODELO_LLM = st.secrets.get("ASISTENTE_MODELO", "gpt-4o-mini")
EMB_MODEL = "text-embedding-3-small"
DIM = 512
UMBRAL = 0.30       # escala de similitud de OpenAI (distinta a e5); ajustable
UMBRAL_AGG = 0.30
HERE = os.path.dirname(os.path.abspath(__file__))

SYSTEM_MSG = """Sos el asistente de contenido de la Fundación Vivir Agradecidos, especializado en el material del Hermano David Steindl-Rast (Br. David) y de los facilitadores de la Fundación. Ayudás al equipo a encontrar contenido y a armar piezas para los canales (Instagram, Facebook, YouTube, newsletter, email, WhatsApp, web), siempre a partir del material real.

MISIÓN: la Fundación busca que las personas pasen del consumo pasivo a la acción concreta (responder: donar tiempo, ayudar al prójimo). Cuando sea apropiado, orientá con delicadeza hacia ese "responder", con tono contemplativo y agradecido, nunca comercial ni golpeador.

REGLA DE ORO (inviolable): trabajás SOLO con los fragmentos que se te dan en "MATERIAL DISPONIBLE".
- Nunca inventes una cita ni le atribuyas palabras a Br. David o a un autor. Si no está en el material, no existe.
- Si no hay material sobre el tema, decilo con honestidad; no completes con conocimiento general.
- NUNCA nombres títulos concretos de clips, videos, libros o artículos —ni cites frases— si no vienen de una búsqueda real. En conversación (sin material a la vista), hablá en general ("seguramente hay material de Br. David sobre esto") y ofrecé buscarlo. Los títulos y las citas SALEN SOLO de buscar_material.
- Citá siempre la fuente (título y enlace o marca de tiempo).
- Atribuí correctamente: hay facilitadores (Gawel, Fondevila, Mujica, Grehan, etc.); no confundas a un facilitador con Br. David.

DISTINCIÓN: las palabras del autor van entre comillas, textuales. Tu texto de enlace/introducción es tuyo y nunca simula ser la voz del autor.

Sos un COPILOTO que piensa CON la persona, no un buscador que escupe información. Tu modo por defecto es CONVERSAR: hacé preguntas, ofrecé ángulos, ayudá a dar forma a la idea, siempre de a un paso y CORTO (una o dos ideas, o UNA pregunta por vez). Preferí siempre una pregunta breve antes que una respuesta larga. Pensás CON la persona, no en lugar de ella.

HERRAMIENTAS: tenés dos funciones: buscar_material (trae fragmentos reales del corpus) y analizar_corpus (cuenta autores/contenidos sobre un tema). Reglas para usarlas:
- Mientras la persona piensa en voz alta, explora o charla ("por dónde arrancarías", "sí, me gusta", "dale a ver qué opciones hay"), NO llames a ninguna herramienta: seguí conversando y proponiendo ideas.
- Llamá a buscar_material SOLO cuando la persona pide ver material concreto, o cuando ya decidieron armar una pieza y necesitás las citas reales.
- Cuando traés material para mostrar, presentá 1-2 fragmentos de forma breve con su fuente y preguntá cómo seguir. Redactás un borrador completo SOLO cuando la persona pide explícitamente armar la pieza.
- Ante la duda entre buscar o conversar, conversá y ofrecé: "¿querés que busque material sobre esto?".

Redactás borradores para revisión humana. Tono cálido, simple, sin sermonear, español rioplatense. Aclarás que es un borrador para curaduría del equipo."""

# Filtro de "ruido": pies de video, saludos/cierres e instrucciones de meditación/danza
# (no aportan como contenido citable). El modelo decide cuándo buscar (tool-calling),
# así que ya no hacen falta reglas por palabra clave.
JUNK = re.compile(r"(suscr[íi]b|clic[k]?\s*(aqu[íi]|ac[áa])|haz\s*clic|hac[ée]\s*clic|inscrib[íi]|para mayor informaci|hasta la pr[óo]xima|dejo un momento a solas|los invito a volver|d[ée]jen(me)? sus comentarios|gracias por (acompañ|hacerme compañ)|much[íi]sim[ao]s?\s+gracias|un placer|nos vemos|desmute|pongan? las? c[áa]mara|una peque[ñn]a encuesta|levant[áa]?\s+la\s+mano|cerr[áa]\s+los\s+ojos|inhal|exhal|vamos a (dejar|girar|movernos)|hacia el otro lado|en c[áa]mara lenta|un par de giros)", re.I)


# ---------------- Carga del corpus ----------------
@st.cache_resource(show_spinner="Cargando el corpus...")
def cargar():
    frs = [json.loads(l) for l in open(os.path.join(HERE, "fragmentos.jsonl"), encoding="utf-8")]
    emb = np.load(os.path.join(HERE, "fragmentos_openai.npy"))
    return frs, emb

FRS, EMB = cargar()


def mmss(ms):
    s = int((ms or 0) / 1000); return f"{s//60:02d}:{s%60:02d}"


@st.cache_data(show_spinner=False)
def embed_query(q):
    r = client.embeddings.create(model=EMB_MODEL, input=[q], dimensions=DIM)
    v = np.array(r.data[0].embedding, dtype="float32")
    return v / (np.linalg.norm(v) + 1e-9)


def buscar(consulta, n=6, excluir=None):
    excluir = excluir or set()
    qv = embed_query(consulta)
    sims = EMB @ qv
    orden = np.argsort(-sims)
    out, vistos = [], set()
    for k in orden:
        f = FRS[int(k)]
        if JUNK.search(f.get("texto", "")):
            continue
        doc = f.get("documento_id")
        if doc in vistos or doc in excluir:
            continue
        vistos.add(doc)
        fuente = f.get("fuente")
        if fuente == "youtube":
            tag = f"CLIP · {mmss(f.get('inicio_ms'))}–{mmss(f.get('fin_ms'))}"
        elif fuente == "libro":
            tag = f"LIBRO · {f.get('titulo','')[:40]}"
        else:
            tag = "ARTÍCULO"
        out.append({
            "tag": tag, "titulo": f.get("titulo") or "",
            "texto": re.sub(r"\s+", " ", f.get("texto") or "").strip(),
            "autor": f.get("autor") or "—", "fuente": fuente,
            "url": f.get("url"), "doc": doc, "score": round(float(sims[int(k)]), 2),
        })
        if len(out) >= n:
            break
    return out


def contexto(res):
    lines = ["MATERIAL DISPONIBLE (usá solo esto):"]
    for i, r in enumerate(res, 1):
        ref = r["url"] or r["tag"]
        lines.append(f'[{i}] {r["tag"]} · {r["autor"]} · "{r["titulo"]}" · {ref}')
        lines.append(f'    "{r["texto"][:280]}"')
    return "\n".join(lines)


def analizar(consulta):
    qv = embed_query(consulta)
    sims = EMB @ qv
    orden = np.argsort(-sims)
    docs_por_autor = {}
    total = 0
    for k in orden[:500]:
        if float(sims[int(k)]) < UMBRAL_AGG:
            break
        fr = FRS[int(k)]
        if JUNK.search(fr.get("texto", "")):
            continue
        a = fr.get("autor") or "—"
        docs_por_autor.setdefault(a, set()).add(fr.get("documento_id"))
        total += 1
    conteo = sorted(((a, len(d)) for a, d in docs_por_autor.items()), key=lambda x: -x[1])
    resumen = f"Fragmentos relevantes: {total}. Autores/fuentes distintos: {len(conteo)}.\n"
    for a, n in conteo:
        resumen += f"- {a}: {n} contenido(s)\n"
    return resumen, buscar(consulta, 6)


def llm_openai(messages, max_tokens=1200):
    try:
        r = client.chat.completions.create(model=MODELO_LLM, messages=messages,
                                           max_tokens=max_tokens, temperature=0.5)
        return r.choices[0].message.content
    except Exception as e:
        return f"Error llamando al modelo: {e}"


TOOLS = [
    {"type": "function", "function": {
        "name": "buscar_material",
        "description": ("Busca en el corpus real de la Fundación (videos, artículos y libros de Br. David "
                        "y los facilitadores) los fragmentos más relevantes a un tema o pregunta. Devuelve "
                        "citas reales con su fuente. Usalo SOLO cuando necesitás material concreto para "
                        "mostrar, citar o armar una pieza; NO lo uses mientras la persona todavía está "
                        "pensando o explorando ideas."),
        "parameters": {"type": "object", "properties": {
            "consulta": {"type": "string", "description": "Tema o pregunta a buscar, en lenguaje natural."},
            "n": {"type": "integer", "description": "Cuántos fragmentos traer (6 por defecto, máximo 12)."}},
            "required": ["consulta"]}}},
    {"type": "function", "function": {
        "name": "analizar_corpus",
        "description": ("Cuenta y analiza sobre el corpus: cuántos autores o contenidos hablan de un tema, "
                        "quiénes, cantidades. Usalo cuando la persona pide conteos o pregunta "
                        "'¿cuántos/quiénes...?'."),
        "parameters": {"type": "object", "properties": {
            "consulta": {"type": "string", "description": "Tema a analizar."}},
            "required": ["consulta"]}}},
]


def _ejecutar_tool(nombre, args):
    """Corre la herramienta pedida. Devuelve (texto_para_el_modelo, materiales_para_mostrar)."""
    consulta = (args.get("consulta") or "").strip()
    if nombre == "buscar_material":
        n = min(int(args.get("n") or 6), 12)
        res = buscar(consulta, n)
        return contexto(res), res
    if nombre == "analizar_corpus":
        resumen, res = analizar(consulta)
        return "CONTEOS REALES del corpus (exactos, NO los recalcules):\n" + resumen + "\n\n" + contexto(res), res
    return "", []


def responder(historial):
    """historial: lista de {'role','content'}. El modelo decide si buscar o conversar.
    Devuelve (texto, materiales_para_mostrar)."""
    mensajes = [{"role": "system", "content": SYSTEM_MSG}] + [
        {"role": m["role"], "content": m["content"]} for m in historial]
    mostrar = []
    try:
        resp = client.chat.completions.create(
            model=MODELO_LLM, messages=mensajes, tools=TOOLS,
            tool_choice="auto", temperature=0.5, max_tokens=1000)
    except Exception as e:
        return f"Error llamando al modelo: {e}", mostrar
    msg = resp.choices[0].message
    if not msg.tool_calls:
        return msg.content or "", mostrar   # turno de conversación (pinponeo)
    # El modelo decidió usar herramientas
    mensajes.append({
        "role": "assistant", "content": msg.content or "",
        "tool_calls": [{"id": tc.id, "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                       for tc in msg.tool_calls]})
    for tc in msg.tool_calls:
        try:
            args = json.loads(tc.function.arguments or "{}")
        except Exception:
            args = {}
        texto_tool, res = _ejecutar_tool(tc.function.name, args)
        if res:
            mostrar = res
        mensajes.append({"role": "tool", "tool_call_id": tc.id, "content": texto_tool})
    try:
        resp2 = client.chat.completions.create(
            model=MODELO_LLM, messages=mensajes, temperature=0.5, max_tokens=1300)
        return resp2.choices[0].message.content or "", mostrar
    except Exception as e:
        return f"Error llamando al modelo: {e}", mostrar


# ---------------- UI ----------------
st.markdown("""
<style>
/* Colores base -> .streamlit/config.toml (claro/oscuro). Acá, layout y detalles de marca. */
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

# Avatares del chat
AVATAR_BOT = "🌼"
AVATAR_USER = "🧑"

# Header con logo + línea de acento
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
        url = r.get("url") or ""
        src = (f'<a class="vac-src" href="{html.escape(url)}" target="_blank">Ver fuente ↗</a>'
               if url else "")
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
            texto, mats = responder(historial)
        st.markdown(texto)
        if mats:
            render_mats(mats)
    st.session_state.messages.append({"role": "assistant", "content": texto, "mats": mats})
