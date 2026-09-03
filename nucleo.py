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
_tradcache = {}


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
- Citá siempre la fuente. NUNCA inventes ni construyas un enlace: usá SOLO los enlaces que aparecen en el material. Los LIBROS no tienen enlace web — se citan por título y número de página (pág. X), jamás con un link inventado.
- Atribuí correctamente: hay facilitadores (Gawel, Fondevila, Mujica, Grehan, etc.); no confundas a un facilitador con Br. David.
- Al armar un copy o borrador, TODA frase entre comillas debe ser TEXTUAL del material disponible. NUNCA inventes una cita ni se la atribuyas a Br. David ni a un facilitador. Si no tenés una cita textual del autor pedido, escribí el copy con TUS palabras, SIN comillas atribuidas, o decí que no tenés una cita de ese autor. Y nunca pongas en boca de Br. David algo que dijo un facilitador (ni al revés).
- Si te piden armar contenido sobre un clip/rango puntual que NO tenés en el material, decílo con honestidad; podés ofrecer un copy con tus palabras, pero SIN inventar citas.
- OJO con la VOZ dentro de un video: un video puede estar etiquetado "Br. David" pero adentro hablan varias personas (facilitadores, participantes, entrevistadores). Cuando te pidan una cita TEXTUAL de Br. David, NO uses un fragmento donde alguien habla SOBRE él en tercera persona o cuenta su experiencia ("sus palabras me ayudaron", "cuando lo escuché", "él dijo", "el Hermano David nos enseñó…"): eso NO es Br. David hablando. Usá solo fragmentos donde la voz es la de él (habla en primera persona, expone su idea). Si no estás seguro de que la voz sea suya, decílo ("este fragmento parece ser de un participante hablando sobre Br. David, no de él") en vez de atribuírselo.
- Si la persona pide material de un autor puntual y solo hay de otros, decílo con honestidad; NO lo hagas pasar como del autor pedido.

DISTINCIÓN: las palabras del autor van entre comillas, textuales. Tu texto de enlace/introducción es tuyo y nunca simula ser la voz del autor.

Sos un COPILOTO que piensa CON la persona, no un buscador que escupe información. Tu modo por defecto es CONVERSAR: hacé preguntas, ofrecé ángulos, ayudá a dar forma a la idea, siempre de a un paso y CORTO (una o dos ideas, o UNA pregunta por vez). Preferí siempre una pregunta breve antes que una respuesta larga. Pensás CON la persona, no en lugar de ella.

HERRAMIENTAS: tenés dos funciones: buscar_material (trae fragmentos reales del corpus) y analizar_corpus (cuenta autores/contenidos sobre un tema). Reglas para usarlas:
- Mientras la persona piensa en voz alta, explora o charla ("por dónde arrancarías", "sí, me gusta", "dale a ver qué opciones hay"), NO llames a ninguna herramienta: seguí conversando y proponiendo ideas.
- Llamá a buscar_material SOLO cuando la persona pide ver material concreto, o cuando ya decidieron armar una pieza y necesitás las citas reales.
- Si la persona pide un tipo puntual (libros, clips/videos o artículos), pasá el parámetro tipo a buscar_material para traer solo eso.
- Si la persona pide material de un autor puntual (ej. Br. David, Fondevila, Gawel, Grehan…), pasá el parámetro autor a buscar_material para traer solo de ese autor.
- Cuando traés material para mostrar, presentá 1-2 fragmentos de forma breve con su fuente y preguntá cómo seguir. Redactás un borrador completo SOLO cuando la persona pide explícitamente armar la pieza.
- Ante la duda entre buscar o conversar, conversá y ofrecé: "¿querés que busque material sobre esto?".

Redactás borradores para revisión humana. Tono cálido, simple, sin sermonear, español rioplatense. Aclarás que es un borrador para curaduría del equipo. (Las conversaciones quedan guardadas en el espacio de trabajo de cada usuario; si te preguntan, confirmalo, no digas que no se guardan.)"""

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


def _traducir_en(texto):
    """Traduce la consulta al inglés (cacheado) para búsqueda bilingüe (Br. David habla mucho en inglés)."""
    if texto in _tradcache:
        return _tradcache[texto]
    t = _llm([{"role": "system", "content": "Traducí al inglés SOLO la frase que te doy, sin comillas ni explicaciones."},
              {"role": "user", "content": texto}], 60)
    t = (t or "").strip()
    _tradcache[texto] = t
    return t


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


_STOP = {"brother", "hermano", "dr", "doctor", "sr", "del", "los", "las"}


def _coincide_autor(fautor, pedido):
    fa = (fautor or "").lower()
    claves = [w for w in re.split(r"[^a-záéíóúñ]+", (pedido or "").lower()) if len(w) >= 3 and w not in _STOP]
    return any(w in fa for w in claves) if claves else True


_AUTORES = [
    ("Br. David", r"br(?:other)?\.?\s*david|hermano\s+david|steindl"),
    ("Fabiana Fondevila", r"fondevila"),
    ("Virginia Gawel", r"gawel"),
    ("Hugo Mujica", r"mujica"),
    ("Joaquín Grehan", r"grehan"),
    ("Andy/Andrea Saporiti", r"saporiti"),
    ("Maite Moreno", r"\bmaite\b"),
    ("Daniel Tocchini", r"tocchini"),
    ("Christian Plebst", r"plebst"),
]


def _detectar_autor(texto):
    """Detecta si la persona pidió material de un autor puntual (red de seguridad si el modelo no pasa 'autor')."""
    t = (texto or "").lower()
    for autor, pat in _AUTORES:
        if re.search(pat, t):
            return autor
    return None


def _detectar_duracion_max(texto):
    """Detecta si pidieron videos cortos con un tope (ej. 'no más de 2 minutos'). Devuelve segundos o None."""
    t = (texto or "").lower()
    m = re.search(r"(\d+)\s*(?:min|minuto)", t)
    if m:
        return int(m.group(1)) * 60
    if re.search(r"\b(breve|breves|cort[oa]s?|short)\b", t):
        return 150
    return None


def _rerank(consulta, candidatos, n):
    """Segundo paso: el modelo elige los n más precisos de una lista más amplia."""
    lineas = [f"[{i}] {c['tag']} · {c['autor']} — {c['titulo']}: {c['texto'][:150]}"
              for i, c in enumerate(candidatos)]
    user = (f"Consulta del equipo: {consulta}\n\nFragmentos candidatos:\n" + "\n".join(lineas) +
            f"\n\nElegí los {n} MÁS relevantes y precisos para la consulta (mismo tema; si la consulta pide "
            f"un autor puntual, respetá ese autor). Respondé SOLO los números, del más al menos relevante, "
            f"separados por comas. Ej: 3,7,1,0,5,2")
    r = _llm([{"role": "system", "content": "Seleccionás fragmentos con precisión. Respondé solo con números."},
              {"role": "user", "content": user}], 60)
    idx = []
    for x in re.findall(r"\d+", r or ""):
        i = int(x)
        if i < len(candidatos) and i not in idx:
            idx.append(i)
    orden = [candidatos[i] for i in idx]
    for c in candidatos:
        if len(orden) >= n:
            break
        if c not in orden:
            orden.append(c)
    return orden[:n]


def buscar(consulta, n=6, excluir=None, fuente=None, autor=None, max_seg=None, rerank=True):
    FRS, EMB = cargar()
    excluir = set(excluir or [])
    qv = embed_query(consulta)
    sims = EMB @ qv
    try:                                   # búsqueda bilingüe: también matcheo con la consulta en inglés
        en = _traducir_en(consulta)
        if en and en.lower() != consulta.lower():
            sims = np.maximum(sims, EMB @ embed_query(en))
    except Exception:
        pass
    orden = np.argsort(-sims)
    cand, vistos = [], set()
    tope = max(n * 3, 15) if rerank else n
    for k in orden:
        f = FRS[int(k)]
        if fuente and f.get("fuente") != fuente:
            continue
        if autor and not _coincide_autor(f.get("autor"), autor):
            continue
        if max_seg and f.get("fuente") == "youtube":
            dur = ((f.get("fin_ms") or 0) - (f.get("inicio_ms") or 0)) / 1000
            if dur > max_seg + 5:
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
        cand.append(d)
        if len(cand) >= tope:
            break
    if rerank and len(cand) > n:
        return _rerank(consulta, cand, n)
    return cand[:n]


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
    return resumen, buscar(consulta, 6, rerank=False)


# Los modelos nuevos (GPT-5.x) usan 'max_completion_tokens' y a veces no aceptan
# 'temperature'. Estos sets "aprenden" en runtime qué NO soporta cada modelo para
# no repetir el error ni pagar reintentos de más.
_usa_max_tokens_viejo = set()      # modelos que piden el nombre viejo 'max_tokens'
_param_no_soportado = {}           # modelo -> set de parámetros a omitir (ej. 'temperature')


def _chat(cl, messages, max_tokens=None, temperature=None, tools=None,
          tool_choice=None, reasoning_effort="none"):
    """chat.completions robusto entre modelos: traduce el nombre del tope de tokens
    y descarta parámetros no soportados (temperature, reasoning_effort, etc.) reintentando.
    reasoning_effort='none' es obligatorio en GPT-5.x para usar function tools por chat."""
    modelo = _modelo()
    while True:
        skip = _param_no_soportado.get(modelo, set())
        kwargs = {"model": modelo, "messages": messages}
        if tools is not None:
            kwargs["tools"] = tools
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice
        if reasoning_effort is not None and "reasoning_effort" not in skip:
            kwargs["reasoning_effort"] = reasoning_effort
        if temperature is not None and "temperature" not in skip:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            nombre = "max_tokens" if modelo in _usa_max_tokens_viejo else "max_completion_tokens"
            kwargs[nombre] = max_tokens
        try:
            return cl.chat.completions.create(**kwargs)
        except Exception as e:
            s = str(e)
            bad = None
            for pat in (r"Unsupported parameter: '([^']+)'",
                        r"Unsupported value: '([^']+)'",
                        r"'param': '([^']+)'"):
                mm = re.search(pat, s)
                if mm:
                    bad = mm.group(1)
                    break
            if bad == "max_completion_tokens":
                _usa_max_tokens_viejo.add(modelo)
                continue
            if bad == "max_tokens":
                _usa_max_tokens_viejo.discard(modelo)
                continue
            if bad and bad not in skip:
                skip = set(skip)
                skip.add(bad)
                _param_no_soportado[modelo] = skip
                continue
            raise


def _llm(messages, max_tokens=1200):
    try:
        r = _chat(_get_client(), messages, max_tokens=max_tokens, temperature=0.5)
        return r.choices[0].message.content or ""
    except Exception as e:
        return f"Error llamando al modelo: {e}"


def armar(fragmentos, canal):
    """Arma un borrador para un canal a partir de fragmentos ya elegidos."""
    ctx = contexto(fragmentos)
    user = (f"Canal: {canal}\n\n{ctx}\n\n"
            f"Armá un borrador de {canal} para la Fundación usando SOLO el material de arriba. "
            f"Elegí 1 a 3 citas, las MÁS relevantes y fuertes para el tema; ignorá cualquier fragmento que sea "
            f"un pie de página, CTA o cierre de video. Las frases entre comillas deben ser TEXTUALES del "
            f"material de arriba: NO inventes citas. Si no hay una cita del autor pedido, redactá con tus "
            f"palabras sin comillas atribuidas. Citá autor y fuente. "
            f"Cerrá aclarando que es un borrador para revisión del equipo.")
    return _llm([{"role": "system", "content": SYSTEM_MSG}, {"role": "user", "content": user}], 1300)


def titular(mensajes):
    """Título corto (estilo ChatGPT), basado en el PRIMER pedido del usuario (más limpio)."""
    primer = next((m.get("content", "") for m in mensajes if m.get("role") == "user"), "")
    primer = re.sub(r"\s+", " ", primer).strip()[:400]
    if not primer:
        return "Conversación"
    t = _llm([{"role": "system", "content": "Devolvé SOLO un título corto (3 a 6 palabras, sin comillas, sin markdown ni signos) que resuma de qué trata este pedido, en español."},
              {"role": "user", "content": primer}], 20)
    t = re.sub(r"\s+", " ", (t or "")).strip().strip('"').strip("'").strip("*#-• ").strip()
    return t[:50] or "Conversación"


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
                     "description": "Filtrá por tipo de fuente cuando la persona lo pide: 'libro', 'clip' (videos), 'articulo'. Usá 'cualquiera' o vacío si no especifica."},
            "autor": {"type": "string", "description": "Filtrá por autor cuando la persona pide material de alguien puntual (ej. 'Br. David', 'Fondevila', 'Gawel', 'Grehan'). Dejalo vacío si no especifica autor."}},
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
        res = buscar(consulta, n, fuente=fuente, autor=(args.get("autor") or None), max_seg=args.get("max_seg"))
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
    autor_hint = None                      # "pegajoso": recuerda el último autor pedido en la charla
    for _m in reversed(usuarios):
        if re.search(r"\b(cualquier|cualquiera|todos|todas|no importa)\b", _m.lower()):
            break
        _a = _detectar_autor(_m)
        if _a:
            autor_hint = _a
            break
    dur_hint = _detectar_duracion_max(" ".join(usuarios[-2:]))
    mostrar = []
    cl = _get_client()
    try:
        resp = _chat(cl, mensajes, tools=TOOLS, tool_choice="auto",
                     temperature=0.5, max_tokens=1000)
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
        if tc.function.name == "buscar_material":
            if args.get("consulta"):
                query = args["consulta"]
            if autor_hint and not args.get("autor"):
                args["autor"] = autor_hint      # red de seguridad: autor pedido por la persona
            if dur_hint and not args.get("max_seg"):
                args["max_seg"] = dur_hint       # tope de duración si pidieron videos cortos
        texto_tool, res = _ejecutar_tool(tc.function.name, args)
        if res:
            mostrar = res
        mensajes.append({"role": "tool", "tool_call_id": tc.id, "content": texto_tool})
    try:
        resp2 = _chat(cl, mensajes, temperature=0.5, max_tokens=1300)
        return (resp2.choices[0].message.content or ""), mostrar, query
    except Exception as e:
        return f"Error llamando al modelo: {e}", mostrar, query
