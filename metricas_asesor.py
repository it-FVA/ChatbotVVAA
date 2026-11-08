"""
metricas_asesor.py — El asesor de campañas de la pestaña Métricas (8/11, Franco; pedido de Beto). Antes metricas_resumen.py: el botón
«¿Cómo le fue?» es ahora un caso particular de un asesor con el que se conversa. Contrato: web/maquetas/metricas-contrato.md
(«Agregado del 8/11 (Franco, 12:30): el asesor de campañas»).

  responder(mensajes, periodo, usuario, cfg)       el asesor: contesta la conversación (los últimos 12 mensajes) sabiendo todo lo que la
                                                   pestaña muestra. Devuelve {texto, fuentes, falto, modelo}
  apertura(dias, usuario, cfg)                     el mensaje proactivo al abrir la pestaña: UNA vez por día (hora Argentina), guardado
                                                   como ambito='resumen', ref='apertura'; si ya hay uno de hoy no llama al modelo
  resumen_campana(ref, dias, usuario, cfg)         POST /resumen: la pregunta fija «¿Cómo le fue a la campaña X?» al mismo asesor
  ultimo(ref)                                      el último resumen guardado de una campaña (o de 'apertura'), o None

El system prompt lleva la salida compactada de metricas.campanas(periodo) y de metricas.canales_estado(cfg), la fecha de hoy y la guía
de canales de Beto (fuentes/guia_canales.md) recortada a los canales usados + «Los tres errores» + «Resumen». La conversación no se guarda
(vive en la pantalla). Nada inventado: `fuentes` y `falto` los CALCULA este módulo de los datos (el modelo pide su versión, pero solo se
aprovecha su `texto` y, si agrega algo, su `falto`). El uso de OpenAI queda en uso_openai con que='auxiliar' (nucleo._chat lo registra) y
`usuario` = quien preguntó. Sin OPENAI_API_KEY: ResumenNoDisponible (la ruta responde 503).
"""
import os, re, json, datetime as dt

import db
import metricas

GUIA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fuentes", "guia_canales.md")
TITULOS_GUIA = ["Las dos preguntas que ordenan todo", "Instagram", "Facebook", "YouTube", "Newsletter", "WhatsApp", "Sitio web",
                "Ecos y el podcast", "Los que no, y por qué", "Los tres errores que conviene evitar", "Resumen"]
TRAMO_DE_CANAL = {"instagram": "Instagram", "facebook": "Facebook", "youtube": "YouTube", "mail": "Newsletter", "newsletter": "Newsletter",
                  "whatsapp": "WhatsApp", "wordpress": "Sitio web", "home": "Sitio web"}
MAX_TRAMO = 2200            # caracteres por tramo de la guía
MAX_MENSAJES = 12           # de la conversación, los últimos
MAX_CAMPANAS = 15           # campañas que entran al system prompt (las de `ultima` más reciente)
MAX_PIEZAS_CAMPANA = 40     # piezas por campaña (las más recientes)
SIN_IA = "El resumen con IA no está disponible ahora"

SISTEMA = ("Sos el asesor de campañas del equipo de la Fundación Vivir Agradecidos. Conocés las campañas, sus piezas, los números que hay "
           "(desde la plataforma o anotados a mano) y la guía de canales. Español rioplatense, tono cálido y claro, sin jerga (no digas «API», "
           "«endpoint» ni «token»: decí «desde la plataforma» o «anotado a mano»). Usá SOLO los datos de abajo: no inventes números, fechas ni "
           "causas. Decí siempre de dónde sale cada número y qué faltó. Comparás contra algo (otra campaña, otro canal, el período anterior) "
           "cuando se pueda, sin exagerar. Las piezas en estado «prueba» o «no_salio» no llegaron a nadie: no les atribuyas alcance. Si no hay "
           "métricas, igual respondé: resumí lo hecho y decí qué habría que cargar. Las sugerencias se apoyan en la guía de canales. "
           "Máximo 250 palabras. Respondés únicamente con JSON válido.")


class ResumenNoDisponible(Exception):
    """Falta la clave de OpenAI."""


def _dia(iso):
    d = metricas._fecha(iso)
    return d.astimezone(metricas.ZONA_AR).strftime("%d/%m").lstrip("0") if d else "?"


def tramos_guia(canales_usados, texto=None):
    """La guía de canales recortada: los tramos de los canales usados + «Los tres errores» + «Resumen»."""
    if texto is None:
        try:
            texto = open(GUIA, encoding="utf-8").read()
        except OSError:
            return ""
    tramos, actual = {}, None
    for linea in texto.splitlines():
        t = linea.strip()
        if actual != "Resumen" and t in TITULOS_GUIA:
            actual = t
            tramos.setdefault(actual, [])
            continue
        if actual:
            tramos[actual].append(linea)
    quiero = [TRAMO_DE_CANAL[c] for c in canales_usados if c in TRAMO_DE_CANAL]
    orden = [t for t in TITULOS_GUIA if t in quiero and t in tramos] + ["Los tres errores que conviene evitar", "Resumen"]
    out = []
    for t in dict.fromkeys(orden):
        cuerpo = "\n".join(l for l in tramos.get(t, []) if l.strip())
        if cuerpo:
            out.append(f"## {t}\n{cuerpo[:MAX_TRAMO]}")
    return "\n\n".join(out)


def _nums(d):
    return ", ".join(f"{k} {d[k]}" for k in metricas.CLAVES_NORMALIZADAS if k in d)


def _linea_pieza(p):
    m = p.get("metricas")
    if m:
        origen = "desde la plataforma" if m.get("fuente") == "api" else "anotado a mano"
        mt = f"{_nums(m)} (fuente: {origen}, {_dia(m.get('capturado'))})"
    else:
        mt = "sin métricas"
    return (f"- {_dia(p.get('fecha'))} · {p.get('canal_texto')} · {p.get('formato') or 'formato sin dato'} · «{p.get('titulo') or 'sin título'}» "
            f"· {p.get('estado_grupo')} · {mt}")


def totales_de(camp):
    """Suma de los números de las piezas de una campaña: {clave: total} (solo las claves que alguna pieza tiene)."""
    t = {}
    for p in camp["piezas"]:
        for k, v in (p.get("metricas") or {}).items():
            if k in metricas.CLAVES_NORMALIZADAS:
                t[k] = t.get(k, 0) + v
    return t


def fuentes_y_falto(camp):
    """(fuentes, falto) calculados de las piezas de `camp` ({"piezas": [...]}), sin pasar por el modelo."""
    vistas = {}
    for p in camp["piezas"]:
        m = p.get("metricas")
        if m:
            k = (p["canal_texto"], m.get("fuente"))
            vistas[k] = max(vistas.get(k, ""), m.get("capturado") or "")
    fuentes = [f"{c} ({'desde la plataforma' if f == 'api' else 'anotado a mano'}, {_dia(cap)})" for (c, f), cap in sorted(vistas.items())]
    con_dato = {p["canal"] for p in camp["piezas"] if p.get("metricas")}
    falto = [f"{p['canal_texto']}: sin datos" for p in {p["canal"]: p for p in camp["piezas"]}.values() if p["canal"] not in con_dato]
    sin = sum(1 for p in camp["piezas"] if p["estado_grupo"] == "publicada" and not p.get("metricas") and p["canal"] in con_dato)
    if sin:
        falto.append(f"{sin} {'pieza publicada' if sin == 1 else 'piezas publicadas'} sin métricas")
    return fuentes, falto


def _buscar(data, ref):
    if ref == "sueltas":
        return data["sueltas"]
    return next((c for c in data["campanas"] if str(c["id"]) == str(ref)), None)


def _anterior(camp, data):
    """La campaña del mismo dueño cuya `ultima` es la inmediatamente anterior a la de ésta."""
    if not camp.get("dueno") or not camp.get("ultima"):
        return None
    cand = [c for c in data["campanas"] if c["dueno"] == camp["dueno"] and c["id"] != camp["id"] and c["ultima"] and c["ultima"] < camp["ultima"]]
    return max(cand, key=lambda c: c["ultima"]) if cand else None


# ---------------- el contexto del asesor ----------------
def _bloque_campana(c, tope=MAX_PIEZAS_CAMPANA):
    est = ", ".join(f"{n} {g}" for g, n in c["por_estado"].items() if n) or "sin piezas"
    canales = "; ".join(f"{k}: " + ", ".join(f"{n} {g}" for g, n in v.items() if n) for k, v in c["por_canal"].items())
    cab = (f"### {c['nombre']}" + (f" (de {c['dueno']})" if c.get("dueno") else "") + f" · {c['piezas_total']} piezas en el período ({est})"
           + (f" · del {_dia(c['primera'])} al {_dia(c['ultima'])}" if c.get("primera") else "") + (f" · por canal: {canales}" if canales else ""))
    piezas = sorted(c["piezas"], key=lambda p: p["fecha"] or "", reverse=True)[:tope]
    return "\n".join([cab, "Suma de métricas: " + (_nums(totales_de(c)) or "ninguna cargada")] + [_linea_pieza(p) for p in piezas])


def _bloque_canales(canales):
    out = []
    for c in canales["canales"]:
        l = f"- {c['texto']} (conexión: {c['api']}" + (f"; {c['nota_api']}" if c.get("nota_api") else "") + ")"
        if c.get("ultima") and _nums(c["ultima"]["datos"]):
            u = c["ultima"]
            l += f" · desde la plataforma: {_nums(u['datos'])} (período {u.get('periodo_desde')} a {u.get('periodo_hasta')}, {_dia(u.get('capturado'))})"
        if c.get("manual"):
            m = c["manual"]
            l += f" · anotado a mano por {m.get('por')}: {_nums(m['datos'])} (período {m.get('periodo_desde')} a {m.get('periodo_hasta')})"
        out.append(l)
    return "\n".join(out)


def contexto(data, canales, extra=None):
    """El system prompt completo: reglas + hoy + campañas + canales + guía (+ `extra`)."""
    todas = data["campanas"] + [data["sueltas"]]
    usados = list(dict.fromkeys(p["canal"] for c in todas for p in c["piezas"])) or ["instagram", "facebook"]
    hoy = dt.datetime.now(metricas.ZONA_AR).strftime("%d/%m/%Y")
    t = data["totales"]
    camps = sorted(data["campanas"], key=lambda c: c["ultima"] or "", reverse=True)[:MAX_CAMPANAS]
    partes = [SISTEMA, f"Hoy es {hoy} (hora Argentina). Período mirado: {data['periodo']['texto']}.",
              f"Totales del período: {t['piezas']} piezas ({', '.join(f'{t[g]} {g}' for g in metricas.GRUPOS if t[g]) or 'ninguna'}).",
              "CAMPAÑAS:\n" + ("\n\n".join(_bloque_campana(c) for c in camps) or "(no hay campañas con piezas)"),
              "PIEZAS SIN CAMPAÑA:\n" + _bloque_campana(data["sueltas"]),
              "CANALES (números de cada cuenta):\n" + _bloque_canales(canales)]
    if extra:
        partes.append(extra)
    partes.append("GUÍA DE CANALES de la Fundación (criterio de qué se espera de cada formato):\n" + (tramos_guia(usados) or "(no disponible)"))
    partes.append('Devolvé SOLO un JSON con: "texto" (markdown corto, hasta 250 palabras), "fuentes" (lista de textos: de dónde sale cada número), '
                  '"falto" (lista de textos: qué datos faltaron).')
    return "\n\n".join(partes)


def _json_del_modelo(t):
    m = re.search(r"\{.*\}", t or "", re.S)
    try:
        return json.loads(m.group(0)) if m else {}
    except ValueError:
        return {}


def _preguntas(mensajes):
    out = []
    for m in (mensajes or [])[-MAX_MENSAJES:]:
        texto = (m.get("texto") or "").strip()[:2000]
        if texto:
            out.append({"role": "user" if m.get("rol") == "usuario" else "assistant", "content": texto})
    if not out or out[-1]["role"] != "user":
        raise ValueError("Falta la pregunta.")
    return out


# ---------------- el asesor ----------------
def responder(mensajes, periodo, usuario, cfg=None, extra=None, alcance=None):
    """Contesta la conversación (`mensajes` = [{rol: usuario|asesor, texto}], la última del usuario). `periodo` es el dict de
    api.admin_rutas.periodo(). `extra` agrega contexto al system prompt y `alcance` (una campaña) limita fuentes y faltantes a ella.
    Devuelve {texto, fuentes, falto, modelo}. Levanta ResumenNoDisponible, ValueError (sin pregunta) o RuntimeError (falló el modelo)."""
    if not os.environ.get("OPENAI_API_KEY"):
        raise ResumenNoDisponible(SIN_IA)
    preguntas = _preguntas(mensajes)
    data = metricas.campanas(periodo)
    canales = metricas.canales_estado(cfg) if cfg is not None else {"canales": []}
    msgs = [{"role": "system", "content": contexto(data, canales, extra)}] + preguntas
    import nucleo
    tok = nucleo.USUARIO.set(usuario)                 # el uso de OpenAI queda a nombre de quien preguntó
    try:
        r = nucleo._chat(nucleo._get_client(), msgs, max_tokens=1500, temperature=0.4)    # registra el uso con que='auxiliar'
        bruto = r.choices[0].message.content or ""
    except Exception as e:
        raise RuntimeError(f"No pude responder: {str(e)[:160]}")
    finally:
        nucleo.USUARIO.reset(tok)
    j = _json_del_modelo(bruto)
    texto = (j.get("texto") or "").strip() if isinstance(j.get("texto"), str) else ""
    fuentes, falto = fuentes_y_falto(alcance if alcance is not None else {"piezas": [p for c in data["campanas"] + [data["sueltas"]] for p in c["piezas"]]})
    mas = [x for x in (j.get("falto") or []) if isinstance(x, str) and x.strip() and x not in falto] if isinstance(j.get("falto"), list) else []
    return {"texto": texto or bruto.strip(), "fuentes": fuentes, "falto": falto + mas[:3], "modelo": nucleo._modelo()}


def _publico(fila):
    d = fila.get("datos") or {}
    return {"ref": fila.get("ref"), "nombre": d.get("nombre"), "texto": d.get("texto") or "", "fuentes": d.get("fuentes") or [],
            "falto": d.get("falto") or [], "comparado_con": d.get("comparado_con"), "modelo": d.get("modelo") or "", "capturado": fila.get("capturado")}


def ultimo(ref):
    """El último resumen guardado de la campaña `ref`, en la forma de la respuesta; None si no hay."""
    f = db.ultimas_metricas("resumen", refs=[ref], fuente="ia").get((str(ref), "ia"))
    return _publico(f) if f else None


def _guardar(ref, per, datos):
    hoy = dt.datetime.now(metricas.ZONA_AR).date()
    return db.guardar_metrica({"ambito": "resumen", "ref": str(ref), "canal": None, "fuente": "ia", "datos": datos, "por": "ia",
                               "periodo_desde": (hoy - dt.timedelta(days=per["dias"])).isoformat(), "periodo_hasta": hoy.isoformat()})


def apertura(dias, usuario, cfg):
    """El mensaje con que el asesor recibe al abrir la pestaña. Una vez por día (hora Argentina): si la última guardada es de hoy se
    devuelve sin llamar al modelo. {texto, fuentes, falto, capturado, nuevo}."""
    ya = db.ultimas_metricas("resumen", refs=["apertura"], fuente="ia").get(("apertura", "ia"))
    cap = metricas._fecha(ya.get("capturado")) if ya else None
    if cap and cap.astimezone(metricas.ZONA_AR).date() == dt.datetime.now(metricas.ZONA_AR).date():
        d = ya.get("datos") or {}
        return {"texto": d.get("texto") or "", "fuentes": d.get("fuentes") or [], "falto": d.get("falto") or [], "capturado": ya["capturado"], "nuevo": False}
    from api.admin_rutas import periodo            # recién acá: la cola no carga FastAPI
    per = periodo(dias, None)
    pregunta = ("Armá el mensaje de apertura de hoy: qué pasó en los últimos 7 días, qué campaña se mueve, qué números faltan cargar y una "
                "sugerencia concreta. Que sea breve.")
    r = responder([{"rol": "usuario", "texto": pregunta}], per, usuario, cfg)
    fila = _guardar("apertura", per, dict(r, dias=per["dias"]))
    return {"texto": r["texto"], "fuentes": r["fuentes"], "falto": r["falto"],
            "capturado": (fila or {}).get("capturado") or metricas._iso(metricas._ahora()), "nuevo": True}


def resumen_campana(ref, dias, usuario, cfg=None):
    """POST /resumen: «¿Cómo le fue a la campaña X?» al mismo asesor, con las piezas de la campaña y la anterior del mismo dueño
    como contexto extra. Guarda la fila ambito='resumen' y devuelve {ref, nombre, texto, fuentes, falto, comparado_con, modelo, capturado}.
    Levanta ResumenNoDisponible, LookupError (no hay esa campaña) o RuntimeError."""
    if not os.environ.get("OPENAI_API_KEY"):
        raise ResumenNoDisponible(SIN_IA)
    from api.admin_rutas import periodo
    per = periodo(dias, None)
    data = metricas.campanas(per)
    camp = _buscar(data, ref)
    if camp is None:
        raise LookupError("No encuentro esa campaña con piezas en el período.")
    previa = _anterior(camp, data)
    if previa is None and ref != "sueltas" and per["dias"] < 365:       # la anterior puede estar más atrás que el período pedido
        largo = metricas.campanas(periodo(365, None))
        previa = _anterior(_buscar(largo, ref) or camp, largo)
    extra = f"CAMPAÑA DE LA PREGUNTA: {camp['nombre']}\n" + _bloque_campana(camp, MAX_PIEZAS_CAMPANA * 2)
    extra += ("\nCampaña anterior del mismo dueño: " + _bloque_campana(previa, 0)) if previa else "\nCampaña anterior del mismo dueño: no hay."
    r = responder([{"rol": "usuario", "texto": f"¿Cómo le fue a la campaña {camp['nombre']}?"}], per, usuario, cfg, extra=extra, alcance=camp)
    datos = {"texto": r["texto"], "fuentes": r["fuentes"], "falto": r["falto"], "comparado_con": previa["nombre"] if previa else None,
             "modelo": r["modelo"], "nombre": camp["nombre"], "dias": per["dias"]}
    fila = _guardar(ref, per, datos)
    return {"ref": str(ref), "nombre": camp["nombre"], "texto": r["texto"], "fuentes": r["fuentes"], "falto": r["falto"],
            "comparado_con": datos["comparado_con"], "modelo": r["modelo"],
            "capturado": (fila or {}).get("capturado") or metricas._iso(metricas._ahora())}
