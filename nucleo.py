"""
Cerebro compartido del asistente de contenido "Vivir Agradecidos".
Lo usan las dos UIs sin duplicar lógica:
  - app.py       -> UI Streamlit (online)
  - servidor.py  -> UI HTML (local, para demos)

Contiene: carga del corpus, búsqueda semántica (embeddings OpenAI), copiloto con
tool-calling, análisis/conteos, armado de borradores y los "locators" (página en
libros, segundo exacto en clips, frase resaltada en artículos).

Config por variables de entorno: OPENAI_API_KEY (obligatoria), ASISTENTE_MODELO (opcional).
"""
import os, json, re, urllib.parse
import numpy as np
from openai import OpenAI

HERE = os.path.dirname(os.path.abspath(__file__))
EMB_MODEL = "text-embedding-3-small"
DIM = 512
UMBRAL_AGG = 0.30

_client = None
_FRS = None
_EMB = None
_qcache = {}


def _get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    return _client


def _modelo():
    return os.environ.get("ASISTENTE_MODELO", "gpt-4o-mini")


def cargar():
    """Carga el corpus una sola vez (queda en memoria del proceso)."""
    global _FRS, _EMB
    if _FRS is None:
        _FRS = [json.loads(l) for l in open(os.path.join(HERE, "fragmentos.jsonl"), encoding="utf-8")]
        _EMB = np.load(os.path.join(HERE, "fragmentos_openai.npy"))
    return _FRS, _EMB


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
- Si la persona pide un tipo puntual (libros, clips/videos o artículos), pasá el parámetro tipo a buscar_material para traer solo eso.
- Cuando traés material para mostrar, presentá 1-2 fragmentos de forma breve con su fuente y preguntá cómo seguir. Redactás un borrador completo SOLO cuando la persona pide explícitamente armar la pieza.
- Ante la duda entre buscar o conversar, conversá y ofrecé: "¿querés que busque material sobre esto?".

Redactás borradores para revisión humana. Tono cálido, simple, sin sermonear, español rioplatense. Aclarás que es un borrador para curaduría del equipo."""

JUNK = re.compile(r"(suscr[íi]b|clic[k]?\s*(aqu[íi]|ac[áa])|haz\s*clic|hac[ée]\s*clic|inscrib[íi]|para mayor informaci|hasta la pr[óo]xima|dejo un momento a solas|los invito a volver|d[ée]jen(me)? sus comentarios|gracias por (acompañ|hacerme compañ)|much[íi]sim[ao]s?\s+gracias|un placer|nos vemos|desmute|pongan? las? c[áa]mara|una peque[ñn]a encuesta|levant[áa]?\s+la\s+mano|cerr[áa]\s+los\s+ojos|inhal|exhal|vamos a (dejar|girar|movernos)|hacia el otro lado|en c[áa]mara lenta|un par de giros)", re.I)


def _es_indice(t):
    """Detecta páginas de índice / tabla de contenido / datos de catálogo (no son citas reales)."""
    nums = len(re.findall(r"\b\d{1,3}\b", t))
    marc = len(re.findall(r"\b\d{1,3}\s*[-–.]", t))
    pal = max(len(t.split()), 1)
    return (nums >= 6 and nums / pal > 0.18) or marc >= 5


def mmss(ms):
    s = int((ms or 0) / 1000)
    return f"{s//60:02d}:{s%60:02d}"


def embed_query(q):
    if q in _qcache:
        return _qcache[q]
    r = _get_client().embeddings.create(model=EMB_MODEL, input=[q], dimensions=DIM)
    v = np.array(r.data[0].embedding, dtype="float32")
    v = v / (np.linalg.norm(v) + 1e-9)
    _qcache[q] = v
    return v


def link_fuente(r):
    """Enlace que salta al lugar exacto: clip -> segundo; artículo -> frase resaltada."""
    url = r.get("url") or ""
    if not url:
        return ""
    if r.get("fuente") == "youtube" and r.get("inicio_ms"):
        seg = int((r["inicio_ms"] or 0) / 1000)
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}t={seg}s"
    if r.get("fuente") == "web":
        snippet = " ".join((r.get("texto") or "").split()[:8]).strip(" ,.;:—\"'“”")
        if snippet:
            return url + "#:~:text=" + urllib.parse.quote(snippet)
    return url


def buscar(consulta, n=6, excluir=None, fuente=None):
    FRS, EMB = cargar()
    excluir = set(excluir or [])
    qv = embed_query(consulta)
    sims = EMB @ qv
    orden = np.argsort(-sims)
    out, vistos = [], set()
    for k in orden:
        f = FRS[int(k)]
        if fuente and f.get("fuente") != fuente:
            continue
        if JUNK.search(f.get("texto", "")) or _es_indice(f.get("texto", "")):
            continue
        doc = f.get("documento_id")
        if doc in vistos or doc in excluir:
            continue
        vistos.add(doc)
        fu = f.get("fuente")
        if fu == "youtube":
            tag = f"CLIP · {mmss(f.get('inicio_ms'))}–{mmss(f.get('fin_ms'))}"
        elif fu == "libro":
            tag = f"LIBRO · {f.get('titulo','')[:40]}"
            if f.get("pagina"):
                tag += f" · pág. {f['pagina']}"
        else:
            tag = "ARTÍCULO"
        d = {
            "tag": tag, "titulo": f.get("titulo") or "",
            "texto": re.sub(r"\s+", " ", f.get("texto") or "").strip(),
            "autor": f.get("autor") or "—", "fuente": fu,
            "url": f.get("url"), "doc": doc, "score": round(float(sims[int(k)]), 2),
            "inicio_ms": f.get("inicio_ms"), "pagina": f.get("pagina"),
        }
        d["ir"] = link_fuente(d)
        out.append(d)
        if len(out) >= n:
            break
    return out


def contexto(res):
    lines = ["MATERIAL DISPONIBLE (usá solo esto):"]
    for i, r in enumerate(res, 1):
        ref = r.get("ir") or r.get("url") or r["tag"]
        lines.append(f'[{i}] {r["tag"]} · {r["autor"]} · "{r["titulo"]}" · {ref}')
        lines.append(f'    "{r["texto"][:280]}"')
    return "\n".join(lines)


def analizar(consulta):
    FRS, EMB = cargar()
    qv = embed_query(consulta)
    sims = EMB @ qv
    orden = np.argsort(-sims)
    docs_por_autor = {}
    total = 0
    for k in orden[:500]:
        if float(sims[int(k)]) < UMBRAL_AGG:
            break
        fr = FRS[int(k)]
        if JUNK.search(fr.get("texto", "")) or _es_indice(fr.get("texto", "")):
            continue
        a = fr.get("autor") or "—"
        docs_por_autor.setdefault(a, set()).add(fr.get("documento_id"))
        total += 1
    conteo = sorted(((a, len(d)) for a, d in docs_por_autor.items()), key=lambda x: -x[1])
    resumen = f"Fragmentos relevantes: {total}. Autores/fuentes distintos: {len(conteo)}.\n"
    for a, n in conteo:
        resumen += f"- {a}: {n} contenido(s)\n"
    return resumen, buscar(consulta, 6)


def _llm(messages, max_tokens=1200):
    try:
        r = _get_client().chat.completions.create(
            model=_modelo(), messages=messages, max_tokens=max_tokens, temperature=0.5)
        return r.choices[0].message.content or ""
    except Exception as e:
        return f"Error llamando al modelo: {e}"


def armar(fragmentos, canal):
    """Arma un borrador para un canal a partir de fragmentos ya elegidos."""
    ctx = contexto(fragmentos)
    user = (f"Canal: {canal}\n\n{ctx}\n\n"
            f"Armá un borrador de {canal} para la Fundación usando SOLO el material de arriba. "
            f"Elegí 1 a 3 citas, las MÁS relevantes y fuertes para el tema; ignorá cualquier fragmento que sea "
            f"un pie de página, CTA o cierre de video. Citá textual, con autor y fuente. "
            f"Cerrá aclarando que es un borrador para revisión del equipo.")
    return _llm([{"role": "system", "content": SYSTEM_MSG}, {"role": "user", "content": user}], 1300)


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
            "n": {"type": "integer", "description": "Cuántos fragmentos traer (6 por defecto, máximo 12)."},
            "tipo": {"type": "string", "enum": ["libro", "clip", "articulo", "cualquiera"],
                     "description": "Filtrá por tipo de fuente cuando la persona lo pide: 'libro', 'clip' (videos), 'articulo'. Usá 'cualquiera' o vacío si no especifica."}},
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
    consulta = (args.get("consulta") or "").strip()
    if nombre == "buscar_material":
        n = min(int(args.get("n") or 6), 12)
        tipo = (args.get("tipo") or "").lower()
        fuente = {"libro": "libro", "clip": "youtube", "video": "youtube",
                  "articulo": "web", "artículo": "web", "web": "web"}.get(tipo)
        res = buscar(consulta, n, fuente=fuente)
        return contexto(res), res
    if nombre == "analizar_corpus":
        resumen, res = analizar(consulta)
        return "CONTEOS REALES del corpus (exactos, NO los recalcules):\n" + resumen + "\n\n" + contexto(res), res
    return "", []


def responder(historial):
    """historial: lista de {'role','content'}. El modelo decide si buscar o conversar.
    Devuelve (texto, materiales_para_mostrar, query_usada)."""
    mensajes = [{"role": "system", "content": SYSTEM_MSG}] + [
        {"role": m["role"], "content": m["content"]} for m in historial]
    usuarios = [m["content"] for m in historial if m["role"] == "user"]
    query = usuarios[-1] if usuarios else ""
    mostrar = []
    cl = _get_client()
    try:
        resp = cl.chat.completions.create(
            model=_modelo(), messages=mensajes, tools=TOOLS,
            tool_choice="auto", temperature=0.5, max_tokens=1000)
    except Exception as e:
        return f"Error llamando al modelo: {e}", mostrar, query
    msg = resp.choices[0].message
    if not msg.tool_calls:
        return (msg.content or ""), mostrar, query
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
        if tc.function.name == "buscar_material" and args.get("consulta"):
            query = args["consulta"]
        texto_tool, res = _ejecutar_tool(tc.function.name, args)
        if res:
            mostrar = res
        mensajes.append({"role": "tool", "tool_call_id": tc.id, "content": texto_tool})
    try:
        resp2 = cl.chat.completions.create(
            model=_modelo(), messages=mensajes, temperature=0.5, max_tokens=1300)
        return (resp2.choices[0].message.content or ""), mostrar, query
    except Exception as e:
        return f"Error llamando al modelo: {e}", mostrar, query
