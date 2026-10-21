"""Chat con streaming, sobre el cerebro (nucleo.py) sin modificarlo.

Qué hace: lo mismo que nucleo.responder_con_pieza (la función que usa app.py), paso por paso:
  1. arma los mensajes (system_msg, nota de idioma, material ya encontrado en la charla),
  2. primera llamada al modelo con las mismas herramientas (nucleo.TOOLS): buscar_material,
     proponer_publicacion, pedir_recorte, estado_recortes, analizar_corpus,
  3. ejecuta las herramientas con nucleo._ejecutar_tool (mismas redes de seguridad: autor pedido, duración),
  4. segunda llamada al modelo, PERO con stream=True: el texto sale a medida que llega.
y va emitiendo eventos: estado → fuentes (tarjetas) → pieza → texto (deltas) → fin.

NOTA DE MANTENIMIENTO: los pasos 1-3 están copiados de nucleo.responder_con_pieza (versión del 21/10) porque
en esta fase nucleo.py no se toca. Si esa función cambia, cambiar acá también; el plan (fase 2) prevé
compararlas con el set dorado y, después, que nucleo tenga su propia versión con streaming.

Variable global nucleo.USUARIO_ACTUAL (firma los recortes que pide el bot): en Streamlit hay un proceso por
persona; acá hay varias personas en el mismo proceso. Mientras siga siendo global, la ejecución de herramientas
va bajo un candado (una a la vez) para que un recorte pedido por Julián no quede firmado por Pato.
"""
import json, re, threading, logging

import nucleo
import db

log = logging.getLogger("api")
_CANDADO_TOOLS = threading.Lock()


# ---------------- Tarjetas (lo que hoy dibuja app.render_mats) ----------------
def _citadas(mats, texto):
    """Copia de app._citadas (16/10): qué tarjetas citó el bot (el título aparece en el texto)."""
    t = (texto or "").lower()
    out = set()
    for i, r in enumerate(mats):
        tit = (r.get("titulo") or "").strip().lower()
        if len(tit) >= 12 and tit[:40] in t:
            out.add(i)
    return out


def tarjetas(mats, idioma="es", texto=""):
    """Las fuentes como JSON para la interfaz: campos de nucleo + traducción (en/de) + estado de los recortes
    por tramo (horizontal/vertical, como los botones de app._botones_clip) + si fue citada en la respuesta."""
    mats = mats or []
    trads = []
    if idioma in ("en", "de"):
        try:
            trads = nucleo.traducir_tarjetas(mats, idioma)
        except Exception:
            trads = []
    clips = []
    try:
        clips = db.clips_de([r.get("doc") for r in mats if r.get("fuente") == "youtube" and r.get("inicio_ms") is not None])
    except Exception:
        clips = []
    por_tramo = {(c["video_id"], int(c["inicio_ms"]), int(c["fin_ms"]), c["formato"]): c for c in clips}
    cit = _citadas(mats, texto)
    out = []
    for n, r in enumerate(mats):
        t = {k: r.get(k) for k in ("tag", "titulo", "texto", "autor", "fuente", "url", "doc", "score",
                                   "inicio_ms", "fin_ms", "pagina", "ir")}
        t["citada"] = n in cit
        tr = trads[n] if n < len(trads) else {}
        t["traduccion"] = tr or None
        if r.get("fuente") == "youtube" and r.get("inicio_ms") is not None and r.get("fin_ms"):
            ini, fin = int(r["inicio_ms"]), int(r["fin_ms"])
            t["recortes"] = {f: ({"id": c["id"], "estado": c.get("estado"), "url": c.get("url"), "error": c.get("error")}
                                 if (c := por_tramo.get((r.get("doc"), ini, fin, f))) else None)
                             for f in ("horizontal", "vertical")}
        out.append(t)
    return out


# ---------------- Segunda llamada con streaming ----------------
def _chat_stream(cl, messages, max_tokens=None, temperature=None, reasoning_effort="none"):
    """Igual que nucleo._chat (mismos reintentos y misma memoria de parámetros no soportados, compartida
    con nucleo), pero con stream=True. Devuelve el iterador de chunks de OpenAI."""
    modelo = nucleo._modelo()
    while True:
        skip = nucleo._param_no_soportado.get(modelo, set())
        kwargs = {"model": modelo, "messages": messages, "stream": True}
        if reasoning_effort is not None and "reasoning_effort" not in skip:
            kwargs["reasoning_effort"] = reasoning_effort
        if temperature is not None and "temperature" not in skip:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            nombre = "max_tokens" if modelo in nucleo._usa_max_tokens_viejo else "max_completion_tokens"
            kwargs[nombre] = max_tokens
        try:
            return cl.chat.completions.create(**kwargs)
        except Exception as e:
            s = str(e)
            bad = None
            for pat in (r"Unsupported parameter: '([^']+)'", r"Unsupported value: '([^']+)'", r"'param': '([^']+)'"):
                mm = re.search(pat, s)
                if mm:
                    bad = mm.group(1)
                    break
            if bad == "max_completion_tokens":
                nucleo._usa_max_tokens_viejo.add(modelo)
                continue
            if bad == "max_tokens":
                nucleo._usa_max_tokens_viejo.discard(modelo)
                continue
            if bad and bad not in skip:
                skip = set(skip)
                skip.add(bad)
                nucleo._param_no_soportado[modelo] = skip
                continue
            raise


def _deltas(stream):
    for chunk in stream:
        try:
            d = chunk.choices[0].delta.content
        except (AttributeError, IndexError):
            d = None
        if d:
            yield d


# ---------------- El generador de eventos ----------------
def historial_de(mensajes):
    """Como app.py antes de llamar a nucleo: role, content y mats de cada mensaje guardado."""
    return [{"role": m.get("role", "user"), "content": m.get("content", ""), "mats": m.get("mats")}
            for m in (mensajes or [])]


def generar(historial, idioma=None, usuario=""):
    """Generador de eventos (nombre, datos). Réplica de nucleo.responder_con_pieza con la segunda llamada en streaming.
    idioma: 'en'/'de' agrega la nota de cuenta; None o 'es' no."""
    mensajes = [{"role": "system", "content": nucleo.system_msg()}] + [
        {"role": m["role"], "content": m["content"]} for m in historial]
    if idioma in nucleo._NOTA_IDIOMA:
        mensajes.insert(1, {"role": "system", "content": nucleo._NOTA_IDIOMA[idioma]})
    prev_mats = None
    for m in reversed(historial):
        if m.get("role") == "assistant" and m.get("mats"):
            prev_mats = m["mats"]
            break
    if prev_mats:
        try:
            ref = nucleo.contexto(prev_mats).replace(
                "MATERIAL DISPONIBLE (usá solo esto):",
                "MATERIAL YA ENCONTRADO en esta conversación (real, citalo tal cual "
                "sin volver a buscar si alcanza para lo que se pide):")
            mensajes.append({"role": "system", "content": ref})
        except Exception:
            pass
    usuarios = [m["content"] for m in historial if m["role"] == "user"]
    query = usuarios[-1] if usuarios else ""
    autor_hint = None
    for _m in reversed(usuarios):
        if re.search(r"\b(cualquier|cualquiera|todos|todas|no importa)\b", _m.lower()):
            break
        _a = nucleo._detectar_autor(_m)
        if _a:
            autor_hint = _a
            break
    dur_hint = nucleo._detectar_duracion_max(" ".join(usuarios[-2:]))
    mostrar, pieza = [], None
    cl = nucleo._get_client()
    yield "estado", {"texto": "pensando"}
    try:
        resp = nucleo._chat(cl, mensajes, tools=nucleo.TOOLS, tool_choice="auto", temperature=0.5, max_tokens=2500)
    except Exception as e:
        yield "texto", {"delta": f"Error llamando al modelo: {e}"}
        yield "fin", {"texto": f"Error llamando al modelo: {e}", "mats": [], "pieza": None, "query": query}
        return
    msg = resp.choices[0].message
    if not msg.tool_calls:
        texto = msg.content or ""
        yield "texto", {"delta": texto}
        yield "fin", {"texto": texto, "mats": [], "pieza": None, "query": query}
        return
    mensajes.append({"role": "assistant", "content": msg.content or "",
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
                args["autor"] = autor_hint
            if dur_hint and not args.get("max_seg"):
                args["max_seg"] = dur_hint
        yield "estado", {"texto": "buscando" if tc.function.name in ("buscar_material", "analizar_corpus") else "trabajando",
                         "herramienta": tc.function.name}
        with _CANDADO_TOOLS:
            nucleo.USUARIO_ACTUAL = usuario
            try:
                texto_tool, res = nucleo._ejecutar_tool(tc.function.name, args)
            finally:
                nucleo.USUARIO_ACTUAL = ""
        if isinstance(res, dict) and res.get("__pieza__"):
            pieza = res["__pieza__"]
        elif res:
            mostrar = res
        mensajes.append({"role": "tool", "tool_call_id": tc.id, "content": texto_tool})
    if mostrar:
        yield "fuentes", {"tarjetas": tarjetas(mostrar, idioma or "es")}
    if pieza:
        yield "pieza", pieza
    partes = []
    try:
        for d in _deltas(_chat_stream(cl, mensajes, temperature=0.5, max_tokens=1300)):
            partes.append(d)
            yield "texto", {"delta": d}
    except Exception as e:
        partes = [f"Error llamando al modelo: {e}"]
        yield "texto", {"delta": partes[0]}
    texto = "".join(partes)
    yield "fin", {"texto": texto, "mats": mostrar, "pieza": pieza, "query": query}


def responder(historial, idioma=None, usuario=""):
    """Sin streaming: consume el generador y devuelve lo mismo que nucleo.responder_con_pieza + los eventos."""
    fin = None
    for nombre, datos in generar(historial, idioma, usuario):
        if nombre == "fin":
            fin = datos
    return fin or {"texto": "", "mats": [], "pieza": None, "query": ""}
