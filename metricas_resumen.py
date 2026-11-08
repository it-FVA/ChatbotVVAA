"""
metricas_resumen.py — «¿Cómo le fue a esta campaña?»: el resumen con IA de Métricas (8/11, Franco; pedido de Beto).
Contrato: web/maquetas/metricas-contrato.md → «GET /resumen/{ref} y POST /resumen».

  generar(ref, dias, usuario)   arma el pedido, llama al modelo auxiliar (el mismo que usa newsletter.redactar), guarda la fila
                                ambito='resumen' (fuente 'ia') y devuelve {ref, nombre, texto, fuentes, falto, comparado_con, modelo, capturado}
  ultimo(ref)                   el último resumen guardado de esa campaña, o None

`ref` es el id de un proyecto (campaña) o 'sueltas' (las piezas que no están en ninguna campaña).

El pedido lleva: las piezas de la campaña en el período (canal, formato, fecha, título, estado) con sus métricas y de dónde sale cada
número; la campaña anterior del mismo dueño con sus totales, si hay; y la guía de canales de Beto (fuentes/guia_canales.md) recortada
a los tramos de los canales usados + «Los tres errores» + «Resumen», como criterio de qué se espera de cada formato.

Nada inventado: `fuentes`, `falto` y `comparado_con` los CALCULA este módulo a partir de los datos (el modelo pide su versión, pero
solo se aprovecha su `texto` y, si agrega algo, su `falto`). El uso de OpenAI queda en uso_openai con que='auxiliar' (nucleo._chat lo
registra) y `usuario` = quien pidió el resumen. Sin OPENAI_API_KEY: ResumenNoDisponible (la ruta responde 503).
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
MAX_PIEZAS = 60             # piezas que entran al pedido (las más recientes)
SIN_IA = "El resumen con IA no está disponible ahora"


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


def _linea_pieza(p):
    m = p.get("metricas")
    if m:
        nums = ", ".join(f"{k} {m[k]}" for k in metricas.CLAVES_NORMALIZADAS if k in m)
        origen = "desde la plataforma" if m.get("fuente") == "api" else "anotado a mano"
        mt = f"{nums} (fuente: {origen}, {_dia(m.get('capturado'))})"
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
    """(fuentes, falto) calculados de los datos de la campaña, sin pasar por el modelo."""
    vistas = {}
    for p in camp["piezas"]:
        m = p.get("metricas")
        if m:
            k = (p["canal_texto"], m.get("fuente"))
            if m.get("capturado") and m["capturado"] > vistas.get(k, ""):
                vistas[k] = m["capturado"]
            else:
                vistas.setdefault(k, m.get("capturado") or "")
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


def armar_pedido(camp, previa, guia):
    por_estado = ", ".join(f"{n} {g}" for g, n in camp["por_estado"].items() if n)
    piezas = sorted(camp["piezas"], key=lambda p: p["fecha"] or "", reverse=True)[:MAX_PIEZAS]
    partes = [f"Campaña: {camp['nombre']}" + (f" (de {camp['dueno']})" if camp.get("dueno") else ""),
              f"Piezas en el período: {camp['piezas_total']} ({por_estado or 'ninguna'})",
              "Piezas:\n" + ("\n".join(_linea_pieza(p) for p in piezas) or "- (ninguna)")]
    tot = totales_de(camp)
    partes.append("Suma de las métricas cargadas: " + (", ".join(f"{k} {v}" for k, v in tot.items()) or "ninguna (no hay números de ninguna fuente)"))
    if previa:
        pt = totales_de(previa)
        pe = ", ".join(f"{n} {g}" for g, n in previa["por_estado"].items() if n)
        partes.append(f"Campaña anterior del mismo dueño: {previa['nombre']} · {previa['piezas_total']} piezas ({pe}) · suma de métricas: "
                      + (", ".join(f"{k} {v}" for k, v in pt.items()) or "sin números"))
    else:
        partes.append("Campaña anterior del mismo dueño: no hay.")
    partes.append("Guía de canales de la Fundación (criterio de qué se espera de cada formato):\n" + (guia or "(no disponible)"))
    partes.append('Devolvé SOLO un JSON con: "texto" (markdown corto, hasta 250 palabras), "fuentes" (lista de textos: de dónde sale cada número), '
                  '"falto" (lista de textos: qué datos faltaron), "comparado_con" (nombre de la campaña anterior si la usaste, o null).')
    return "\n\n".join(partes)


SISTEMA = ("Resumís cómo le fue a una campaña de la Fundación Vivir Agradecidos para su equipo. Español rioplatense, tono cálido y claro, "
           "sin jerga (no digas «API», «endpoint» ni «token»: decí «desde la plataforma» o «anotado a mano»). Usá SOLO los datos del pedido: "
           "no inventes números, fechas ni causas. Decí siempre de dónde sale cada número y qué faltó. Las piezas en estado «prueba» o "
           "«no_salio» no llegaron a nadie: no les atribuyas alcance. Si no hay ninguna métrica, igual respondé: resumí lo hecho "
           "y decí qué habría que cargar para poder evaluar. Si hay campaña anterior, compará con ella sin exagerar. Cerrá con una o dos "
           "sugerencias para la próxima campaña apoyadas en la guía de canales. Máximo 250 palabras. Respondés únicamente con JSON válido.")


def _json_del_modelo(t):
    m = re.search(r"\{.*\}", t or "", re.S)
    try:
        return json.loads(m.group(0)) if m else {}
    except ValueError:
        return {}


def _publico(fila):
    d = fila.get("datos") or {}
    return {"ref": fila.get("ref"), "nombre": d.get("nombre"), "texto": d.get("texto") or "", "fuentes": d.get("fuentes") or [],
            "falto": d.get("falto") or [], "comparado_con": d.get("comparado_con"), "modelo": d.get("modelo") or "", "capturado": fila.get("capturado")}


def ultimo(ref):
    """El último resumen guardado de la campaña `ref`, en la forma de la respuesta; None si no hay."""
    f = db.ultimas_metricas("resumen", refs=[ref], fuente="ia").get((str(ref), "ia"))
    return _publico(f) if f else None


def generar(ref, dias, usuario):
    """Genera, guarda y devuelve el resumen de la campaña `ref` con los últimos `dias` días.
    Levanta ResumenNoDisponible (sin clave de OpenAI), LookupError (no hay esa campaña) o RuntimeError (falló el modelo)."""
    if not os.environ.get("OPENAI_API_KEY"):
        raise ResumenNoDisponible(SIN_IA)
    from api.admin_rutas import periodo            # recién acá: la cola no carga FastAPI
    per = periodo(dias, None)
    data = metricas.campanas(per)
    camp = _buscar(data, ref)
    if camp is None:
        raise LookupError("No encuentro esa campaña con piezas en el período.")
    previa = _anterior(camp, data)
    if previa is None and ref != "sueltas" and per["dias"] < 365:       # la anterior puede estar más atrás que el período pedido
        largo = metricas.campanas(periodo(365, None))
        previa = _anterior(_buscar(largo, ref) or camp, largo)
    usados = [p["canal"] for p in camp["piezas"]]
    pedido = armar_pedido(camp, previa, tramos_guia(list(dict.fromkeys(usados))))
    import nucleo
    msgs = [{"role": "system", "content": SISTEMA}, {"role": "user", "content": pedido}]
    tok = nucleo.USUARIO.set(usuario)                 # el uso de OpenAI queda a nombre de quien pidió
    try:
        r = nucleo._chat(nucleo._get_client(), msgs, max_tokens=1500, temperature=0.4)    # registra el uso con que='auxiliar'
        bruto = r.choices[0].message.content or ""
    except Exception as e:
        raise RuntimeError(f"No pude generar el resumen: {str(e)[:160]}")
    finally:
        nucleo.USUARIO.reset(tok)
    j = _json_del_modelo(bruto)
    texto = (j.get("texto") or "").strip() if isinstance(j.get("texto"), str) else ""
    texto = texto or bruto.strip()
    fuentes, falto = fuentes_y_falto(camp)
    extra = [x for x in (j.get("falto") or []) if isinstance(x, str) and x.strip() and x not in falto] if isinstance(j.get("falto"), list) else []
    modelo = nucleo._modelo()
    datos = {"texto": texto, "fuentes": fuentes, "falto": falto + extra[:3], "comparado_con": previa["nombre"] if previa else None,
             "modelo": modelo, "nombre": camp["nombre"], "dias": per["dias"]}
    hoy = dt.datetime.now(metricas.ZONA_AR).date()
    fila = db.guardar_metrica({"ambito": "resumen", "ref": str(ref), "canal": None, "fuente": "ia", "datos": datos, "por": "ia",
                               "periodo_desde": (hoy - dt.timedelta(days=per["dias"])).isoformat(), "periodo_hasta": hoy.isoformat()})
    return {"ref": str(ref), "nombre": camp["nombre"], "texto": texto, "fuentes": fuentes, "falto": datos["falto"],
            "comparado_con": datos["comparado_con"], "modelo": modelo, "capturado": (fila or {}).get("capturado") or metricas._iso(metricas._ahora())}
