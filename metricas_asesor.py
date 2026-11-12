"""
metricas_asesor.py — El asesor de campañas de la pestaña Métricas (8/11, Franco; pedido de Beto). Antes metricas_resumen.py: el botón
«¿Cómo le fue?» es ahora un caso particular de un asesor con el que se conversa. Contrato: web/maquetas/metricas-contrato.md
(«Agregado del 8/11 (Franco, 12:30): el asesor de campañas»).

  responder(mensajes, periodo, usuario, cfg)       el asesor (8/11: nombra las piezas; 12/11: la apertura arranca con un veredicto, hasta 300 palabras): contesta la conversación (los últimos 12 mensajes) sabiendo todo lo que la
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
MAX_NOMBRADAS = 15          # piezas por lista nombrada (programadas, en aprobación, publicadas de la semana) y por campaña
DIAS_SEMANA = 7             # «esta semana»: las publicadas de los últimos 7 días se nombran
LIMITE_PALABRAS = 250       # respuestas a preguntas libres
LIMITE_APERTURA = 300       # el mensaje de apertura: veredicto + gente propia + campañas + falta + sugerencia (12/11, Franco; antes 350)
MAX_TOP_FRASE = 3           # de la Frase del día automática solo se nombran las de más alcance (12/11, Franco)
SIN_IA = "El resumen con IA no está disponible ahora"
CLAVE_FRASE = "frase_del_dia"
HECHAS = tuple(metricas.GRUPOS_HECHAS) + ("saliendo",)      # «saliendo» (mail en tandas) cuenta como hecha (12/11, Franco)
# Claves de números que no están en CLAVES_NORMALIZADAS pero que el contexto muestra si vienen (12/11, Franco)
ETIQUETA_EXTRA = {"enviados_frase": "enviados de la Frase del día", "lista_contactos": "contactos en la lista", "minutos_vistos": "minutos vistos"}
ETIQUETA_TASA = {"alcance_sobre_seguidores": "alcance = {} de los seguidores", "interacciones_sobre_alcance": "interacciones = {} del alcance",
                 "aperturas_sobre_enviados": "aperturas = {} de los enviados", "clics_sobre_enviados": "clics = {} de los enviados"}

SISTEMA = ("Sos el asesor de campañas del equipo de la Fundación Vivir Agradecidos y le hablás a la dirección (Beto). Español rioplatense, "
           "tono cálido y claro, sin jerga (no digas «API», «endpoint» ni «token»: decí «desde la plataforma» o «anotado a mano»). Usá SOLO los "
           "datos de abajo: no inventes números, fechas ni causas, y decí de dónde sale cada número. NO hables de lo que no figura: si algo no "
           "está en los datos (títulos de borradores, por ejemplo) no lo menciones ni te quejes de no tenerlo; lo único que se pide cargar es "
           "lo de «LO QUE FALTA CARGAR». "
           "EL OBJETIVO es ganar gente propia: suscriptores de mail y de WhatsApp. Instagram, Facebook y YouTube son canales prestados: "
           "sirven para que nos encuentren, y se juzgan por cuánto empujan hacia la gente propia. "
           "COMPARÁ con el período anterior cuando exista, diciendo el signo y el tamaño del cambio («subió 24 %»); si no hay período "
           "anterior, decilo una sola vez y no compares. Para decir si algo es poco o mucho usá las tasas (alcance sobre seguidores, "
           "aperturas sobre enviados, etc.) y no compares números absolutos entre canales de escala distinta. "
           "ESTADOS: «saliendo» es un mail que está saliendo en tandas (decí «está saliendo en tandas», nunca «programada»; cuenta como "
           "hecha). «cancelada» se cortó a propósito: decí «cancelada a propósito», no es un fallo. «no salió» es solo lo rechazado o con "
           "error: nombrá cuál. Las de prueba y las canceladas no llegaron a nadie: no les atribuyas alcance. "
           "NOMBRÁ LAS PIEZAS hechas por personas con título, canal, día y hora y de quién son, tal como figuran en los datos. "
           "«Frase del día (automática)» la arma la plataforma sola: contala en UNA línea con los totales que figuran y la de más alcance; "
           "nunca la enumeres día por día. Si no hay métricas, igual respondé y decí qué habría que cargar. Las sugerencias se apoyan en "
           "la guía de canales. Respondés únicamente con JSON válido.")


class ResumenNoDisponible(Exception):
    """Falta la clave de OpenAI."""


def _dia(iso):
    d = metricas._fecha(iso)
    return d.astimezone(metricas.ZONA_AR).strftime("%d/%m").lstrip("0") if d else "?"


def _cuando(iso, ahora=None):
    """«mañana 10:00 (9/11)», «hoy 15:30 (8/11)», «ayer 09:00 (7/11)» o «12/11 10:00»: día relativo, hora y fecha en hora Argentina."""
    d = metricas._fecha(iso)
    if not d:
        return "sin fecha"
    ar = d.astimezone(metricas.ZONA_AR)
    hoy = (ahora or dt.datetime.now(metricas.ZONA_AR)).astimezone(metricas.ZONA_AR).date()
    rel = {0: "hoy", 1: "mañana", -1: "ayer", 2: "pasado mañana"}.get((ar.date() - hoy).days)
    fecha = f"{ar.day}/{ar.month}"
    return f"{rel} {ar:%H:%M} ({fecha})" if rel else f"{fecha} {ar:%H:%M}"


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
    return ", ".join([f"{k} {d[k]}" for k in metricas.CLAVES_NORMALIZADAS if k in d]
                     + [f"{t} {d[k]}" for k, t in ETIQUETA_EXTRA.items() if _es_num(d.get(k))])


def _es_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _grupo(p):
    """El grupo de la pieza para el asesor: «cancelada» (a propósito) aunque metricas.py todavía la junte con no_salio (12/11, Franco)."""
    if (p.get("estado") or "").strip().lower() == "cancelada":
        return "cancelada"
    return p.get("estado_grupo")


def _dicho(p):
    """Cómo se dice el estado de una pieza (12/11, Franco): saliendo ≠ programada, cancelada ≠ fallo, no_salio nombra la causa."""
    g = _grupo(p)
    if g == "saliendo":
        return "está saliendo en tandas"
    if g == "cancelada":
        return "cancelada a propósito"
    if g == "no_salio":
        causa = {"rechazada": "rechazada", "error": "con error"}.get((p.get("estado") or "").strip().lower())
        return f"no salió ({causa})" if causa else "no salió"
    return {"en_aprobacion": "en aprobación"}.get(g, g)


def _linea_pieza(p):
    m = p.get("metricas")
    if m:
        origen = "desde la plataforma" if m.get("fuente") == "api" else "anotado a mano"
        mt = f"{_nums(m)} (fuente: {origen}, {_dia(m.get('capturado'))})"
    else:
        mt = "sin métricas"
    return (f"- {_dia(p.get('fecha'))} · {p.get('canal_texto')} · {p.get('formato') or 'formato sin dato'} · «{p.get('titulo') or 'sin título'}» "
            f"· {_dicho(p)}" + (f" · de {p['usuario']}" if p.get("usuario") else "") + f" · {mt}")


def totales_de(camp):
    """Suma de los números de las piezas de una campaña: {clave: total} (solo las claves que alguna pieza tiene)."""
    t = {}
    for p in camp["piezas"]:
        for k, v in (p.get("metricas") or {}).items():
            if k in metricas.CLAVES_NORMALIZADAS and _es_num(v):
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
    sin = sum(1 for p in camp["piezas"] if _grupo(p) == "publicada" and not p.get("metricas") and p["canal"] in con_dato)
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
NOMBRE_GRUPO = {"publicada": "publicadas", "programada": "programadas", "en_aprobacion": "en aprobación", "saliendo": "saliendo en tandas"}


def _linea_nombrada(p, con_hora):
    quien = f", de {p['usuario']}" if p.get("usuario") else ""
    cuando = _cuando(p.get("fecha")) if con_hora else _dia(p.get("fecha"))
    extra = f", {_dicho(p)}" if _grupo(p) in ("no_salio", "saliendo") else ""
    return f"- «{p.get('titulo') or 'sin título'}» ({p.get('canal_texto')}, {cuando}{quien}{extra})"


def _lista_nombrada(titulo, piezas, con_hora):
    if not piezas:
        return []
    extra = f" (y {len(piezas) - MAX_NOMBRADAS} más)" if len(piezas) > MAX_NOMBRADAS else ""
    return [f"{titulo}{extra}:"] + [_linea_nombrada(p, con_hora) for p in piezas[:MAX_NOMBRADAS]]


def _por_fecha(piezas, grupo, reverso=False):
    return sorted((p for p in piezas if _grupo(p) == grupo), key=lambda p: p.get("fecha") or "", reverse=reverso)


def _cuenta_hechas(piezas):
    n = {}
    for p in piezas:
        g = _grupo(p)
        n[g] = n.get(g, 0) + 1
    return n


def _bloque_frase(c, ahora):
    """La Frase del día automática en pocas líneas (12/11, Franco: «enumera las 14 una por una, es ruido»): totales por canal y formato,
    en cuántos días salió, las 3 de más alcance y lo que está saliendo o no salió. Nunca pieza por pieza."""
    piezas = c["piezas"]
    n = _cuenta_hechas(piezas)
    pub = _por_fecha(piezas, "publicada")
    cab = (f"### {c['nombre']} (la arma la plataforma sola, no un equipo) · {sum(n.get(g, 0) for g in HECHAS)} piezas hechas en el período ("
           + (", ".join(f"{n[g]} {NOMBRE_GRUPO[g]}" for g in HECHAS if n.get(g)) or "ninguna") + ")")
    por = {}
    for p in pub:
        k = (p.get("canal_texto") or "?") + (f", {p['formato']}" if p.get("formato") else "")
        por[k] = por.get(k, 0) + 1
    out = [cab]
    if por:
        out.append("Publicadas por canal: " + "; ".join(f"{k}: {v}" for k, v in sorted(por.items())))
    dias = sorted({d.astimezone(metricas.ZONA_AR).date() for d in (metricas._fecha(p.get("fecha")) for p in pub) if d})
    if dias:
        corrido = (dias[-1] - dias[0]).days + 1
        sin = corrido - len(dias)
        out.append(f"Salió en {len(dias)} de {corrido} días corridos entre el {dias[0].day}/{dias[0].month} y el {dias[-1].day}/{dias[-1].month}"
                   + (" (todos los días)" if not sin else f" (sin pieza en {sin} {'día' if sin == 1 else 'días'})"))
    out.append("Suma de métricas: " + (_nums(totales_de(c)) or "ninguna cargada"))
    con = sorted((p for p in pub if _es_num((p.get("metricas") or {}).get("alcance"))), key=lambda p: p["metricas"]["alcance"], reverse=True)[:MAX_TOP_FRASE]
    if con:
        out.append(f"Las {len(con)} de más alcance (solo estas se nombran):")
        out += [_linea_pieza(p) for p in con]
    out += _lista_nombrada("Saliendo en tandas ahora", _por_fecha(piezas, "saliendo"), True)
    for g, t in (("programada", "Programadas"), ("en_aprobacion", "En aprobación")):
        if n.get(g):
            out.append(f"{t}: {n[g]} (no se nombran una por una)")
    out += _lista_nombrada("No salieron (rechazadas o con error)", _por_fecha(piezas, "no_salio"), False)
    if n.get("cancelada"):
        out.append(f"Canceladas a propósito (no es un fallo): {n['cancelada']}")
    return "\n".join(out)


def _bloque_campana(c, tope=MAX_PIEZAS_CAMPANA, ahora=None):
    """Una campaña para el modelo: cabecera, descripción si viene, suma de métricas, las piezas NOMBRADAS (programadas, en aprobación y
    saliendo con título, canal, fecha/hora y quién; publicadas de la última semana; las que no salieron y las canceladas) y el detalle
    con sus números. Los borradores y las pruebas NO entran (8/11 y 12/11, Franco: no son trabajo hecho y el modelo se quejaba de no ver
    sus títulos). La Frase del día va resumida (`_bloque_frase`)."""
    ahora = ahora or metricas._ahora()
    if c.get("id") == CLAVE_FRASE:
        return _bloque_frase(c, ahora)
    n = _cuenta_hechas(c["piezas"])
    hechas = sum(n.get(g, 0) for g in HECHAS)
    est = ", ".join(f"{n[g]} {NOMBRE_GRUPO[g]}" for g in HECHAS if n.get(g)) or "sin piezas"
    por = {}
    for p in c["piezas"]:
        if _grupo(p) in HECHAS:
            d = por.setdefault(p.get("canal_texto"), {})
            d[_grupo(p)] = d.get(_grupo(p), 0) + 1
    canales = "; ".join(f"{k}: " + ", ".join(f"{v} {NOMBRE_GRUPO[g]}" for g, v in d.items()) for k, d in por.items())
    cab = (f"### {c['nombre']}" + (f" (de {c['dueno']})" if c.get("dueno") else "") + f" · {hechas} piezas hechas en el período ({est})"
           + (f" · del {_dia(c['primera'])} al {_dia(c['ultima'])}" if c.get("primera") else "") + (f" · por canal: {canales}" if canales else ""))
    desc = c.get("descripcion")
    desc = [f"De qué trata: {desc.strip()[:400]}"] if isinstance(desc, str) and desc.strip() else []
    hechas_p = sorted((p for p in c["piezas"] if _grupo(p) in HECHAS), key=lambda p: p.get("fecha") or "", reverse=True)
    desde = metricas._iso(ahora - dt.timedelta(days=DIAS_SEMANA))
    semana = [p for p in hechas_p if _grupo(p) == "publicada" and (p.get("fecha") or "") >= desde]
    nombradas = (_lista_nombrada("Programadas", _por_fecha(c["piezas"], "programada"), True)
                 + _lista_nombrada("Saliendo en tandas ahora (ya cuentan como hechas, no están programadas)", _por_fecha(c["piezas"], "saliendo"), True)
                 + _lista_nombrada("En aprobación", _por_fecha(c["piezas"], "en_aprobacion"), True)
                 + _lista_nombrada(f"Publicadas en los últimos {DIAS_SEMANA} días", semana, False)
                 + _lista_nombrada("No salieron (rechazadas o con error)", _por_fecha(c["piezas"], "no_salio"), False)
                 + _lista_nombrada("Canceladas a propósito (no es un fallo)", _por_fecha(c["piezas"], "cancelada"), False))
    return "\n".join([cab] + desc + ["Suma de métricas: " + (_nums(totales_de(c)) or "ninguna cargada")] + nombradas
                     + (["Detalle de piezas con sus números:"] if hechas_p[:tope] else []) + [_linea_pieza(p) for p in hechas_p[:tope]])


# ---- canales: período anterior, tasas, gente propia (12/11, Franco) ----
def _pct(v):
    """0.31 → «31 %», 0.035 → «3,5 %» (la tasa viene como fracción)."""
    x = v * 100
    return (f"{x:.0f}" if abs(x) >= 10 else f"{x:.1f}".replace(".", ",")) + " %"


def _tasas(c):
    t = c.get("tasas")
    if not isinstance(t, dict):
        return ""
    out = [ETIQUETA_TASA[k].format(_pct(t[k])) for k in ETIQUETA_TASA if _es_num(t.get(k))]
    if _es_num(t.get("visitas_por_dia")):
        out.append(f"{round(t['visitas_por_dia'])} visitas por día")
    return "; ".join(out)


def _datos(fila):
    d = (fila or {}).get("datos") if isinstance(fila, dict) else None
    return d if isinstance(d, dict) else {}


def _anterior_de(c):
    a = c.get("anterior")
    return a if isinstance(a, dict) and _nums(_datos(a)) else None


def _cambio(nuevo, viejo):
    """«+24 %» o None si no hay con qué comparar."""
    if not (_es_num(nuevo) and _es_num(viejo)) or not viejo:
        return None
    d = (nuevo - viejo) / abs(viejo) * 100
    return f"{'+' if d >= 0 else '−'}{abs(d):.0f} %"


def _bloque_canales(canales):
    out = []
    for c in canales["canales"]:
        l = f"- {c['texto']} (conexión: {c['api']}" + (f"; {c['nota_api']}" if c.get("nota_api") else "") + ")"
        if c.get("ultima") and _nums(_datos(c["ultima"])):
            u = c["ultima"]
            l += f" · desde la plataforma: {_nums(u['datos'])} (período {u.get('periodo_desde')} a {u.get('periodo_hasta')}, {_dia(u.get('capturado'))})"
        a = _anterior_de(c)
        if a:
            l += f" · período anterior: {_nums(a['datos'])} (período {a.get('periodo_desde')} a {a.get('periodo_hasta')})"
        t = _tasas(c)
        if t:
            l += f" · tasas: {t}"
        if c.get("manual") and _nums(_datos(c["manual"])):
            m = c["manual"]
            l += f" · anotado a mano por {m.get('por')}: {_nums(m['datos'])} (período {m.get('periodo_desde')} a {m.get('periodo_hasta')})"
        out.append(l)
    return "\n".join(out)


def _cambios(canales, tope=6):
    """Los cambios contra el período anterior, CALCULADOS acá (no por el modelo), de mayor a menor."""
    cs = []
    for c in canales["canales"]:
        a, d = _anterior_de(c), _datos(c.get("ultima"))
        if not a:
            continue
        for k in list(metricas.CLAVES_NORMALIZADAS) + list(ETIQUETA_EXTRA):
            ch = _cambio(d.get(k), _datos(a).get(k))
            if ch:
                viejo = _datos(a)[k]
                cs.append((abs(d[k] - viejo) / abs(viejo), f"{c['texto']}, {ETIQUETA_EXTRA.get(k, k.replace('_', ' '))}: de {viejo} a {d[k]} ({ch})"))
    return [t for _, t in sorted(cs, reverse=True)[:tope]]


def _gente_propia(canales):
    """La lista de mail y WhatsApp con su variación (todo de los datos). Sin nada: la frase para decir que no se mide."""
    por = {c["clave"]: c for c in canales["canales"]}
    out = []
    mail = por.get("mail") or {}
    lista = _datos(mail.get("ultima")).get("lista_contactos")
    if _es_num(lista):
        l = f"Lista de mail: {lista} contactos (desde la plataforma, {_dia((mail.get('ultima') or {}).get('capturado'))})"
        antes = _datos(_anterior_de(mail)).get("lista_contactos")
        ch = _cambio(lista, antes)
        out.append(l + (f"; en el período anterior eran {antes} ({ch}, {'+' if lista >= antes else '−'}{abs(lista - antes)} contactos)" if ch
                        else "; sin período anterior de la lista"))
    wa = por.get("whatsapp") or {}
    manual = _nums(_datos(wa.get("manual")))
    nums = manual or _nums(_datos(wa.get("ultima")))
    if nums:
        out.append(f"WhatsApp: {nums}" + (f" (anotado a mano por {wa['manual'].get('por')})" if manual else ""))
    return out or ["No hay ningún dato de la lista de mail ni de WhatsApp (decir «todavía no medimos la lista»)."]


def _falta_cargar(canales, piezas):
    """Lo que de verdad falta cargar, calculado: canales sin ningún número y canales con piezas hechas sin métricas."""
    sin = [c["texto"] for c in canales["canales"] if not _nums(_datos(c.get("ultima"))) and not _nums(_datos(c.get("manual")))]
    falto = fuentes_y_falto({"piezas": [p for p in piezas if _grupo(p) in HECHAS]})[1]
    return ([f"Canales sin ningún número (ni de la plataforma ni a mano): {', '.join(sin)}"] if sin else []) + falto


def contexto(data, canales, extra=None, limite=LIMITE_PALABRAS):
    """El system prompt completo: reglas + hoy + totales + gente propia + cambios + campañas + canales (con período anterior y tasas)
    + qué falta cargar + guía (+ `extra`)."""
    todas = data["campanas"] + [data["sueltas"]]
    piezas = [p for c in todas for p in c["piezas"]]
    usados = list(dict.fromkeys(p["canal"] for p in piezas)) or ["instagram", "facebook"]
    hoy = dt.datetime.now(metricas.ZONA_AR).strftime("%d/%m/%Y")
    n = _cuenta_hechas(piezas)
    try:
        from api.admin_rutas import SERVICIO
    except Exception:
        SERVICIO = {CLAVE_FRASE, "bot", "cola"}
    hechas = [p for p in piezas if _grupo(p) in HECHAS]
    auto = sum(1 for p in hechas if p.get("usuario") in SERVICIO)
    camps = sorted(data["campanas"], key=lambda c: c["ultima"] or "", reverse=True)[:MAX_CAMPANAS]
    cambios = _cambios(canales)
    hay_anterior = any(_anterior_de(c) for c in canales["canales"])
    partes = [SISTEMA + f" Máximo {limite} palabras.", f"Hoy es {hoy} (hora Argentina). Período mirado: {data['periodo']['texto']}.",
              f"Totales del período: {len(hechas)} piezas hechas ({', '.join(f'{n[g]} {NOMBRE_GRUPO[g]}' for g in HECHAS if n.get(g)) or 'ninguna'}): "
              f"{len(hechas) - auto} hechas por personas y {auto} automáticas. "
              f"Aparte: {n.get('no_salio', 0)} no salieron (rechazadas o con error), {n.get('cancelada', 0)} canceladas a propósito (no es un fallo).",
              "GENTE PROPIA (el objetivo):\n" + "\n".join(_gente_propia(canales)),
              ("CAMBIOS CONTRA EL PERÍODO ANTERIOR (calculados, de mayor a menor):\n" + "\n".join(f"- {t}" for t in cambios)) if cambios else
              ("PERÍODO ANTERIOR: no hay cambios comparables en los números que hay." if hay_anterior else
               "PERÍODO ANTERIOR: todavía no hay (decilo una sola vez y no compares)."),
              "CAMPAÑAS:\n" + ("\n\n".join(_bloque_campana(c) for c in camps) or "(no hay campañas con piezas)"),
              "PIEZAS SIN CAMPAÑA:\n" + _bloque_campana(data["sueltas"]),
              "CANALES (números de cada cuenta):\n" + _bloque_canales(canales),
              "LO QUE FALTA CARGAR (calculado):\n" + ("\n".join(f"- {x}" for x in _falta_cargar(canales, piezas)) or "- nada")]
    if extra:
        partes.append(extra)
    partes.append("GUÍA DE CANALES de la Fundación (criterio de qué se espera de cada formato):\n" + (tramos_guia(usados) or "(no disponible)"))
    partes.append('Devolvé SOLO un JSON con: "texto" (markdown corto, hasta ' + str(limite) + ' palabras), "fuentes" (lista de textos: de dónde sale cada número), '
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
def responder(mensajes, periodo, usuario, cfg=None, extra=None, alcance=None, limite=LIMITE_PALABRAS):
    """Contesta la conversación (`mensajes` = [{rol: usuario|asesor, texto}], la última del usuario). `periodo` es el dict de
    api.admin_rutas.periodo(). `extra` agrega contexto al system prompt y `alcance` (una campaña) limita fuentes y faltantes a ella.
    Devuelve {texto, fuentes, falto, modelo}. Levanta ResumenNoDisponible, ValueError (sin pregunta) o RuntimeError (falló el modelo)."""
    if not os.environ.get("OPENAI_API_KEY"):
        raise ResumenNoDisponible(SIN_IA)
    preguntas = _preguntas(mensajes)
    data = metricas.campanas(periodo)
    canales = metricas.canales_estado(cfg) if cfg is not None else {"canales": []}
    msgs = [{"role": "system", "content": contexto(data, canales, extra, limite)}] + preguntas
    import nucleo
    tok = nucleo.USUARIO.set(usuario)                 # el uso de OpenAI queda a nombre de quien preguntó
    try:
        r = nucleo._chat(nucleo._get_client(), msgs, max_tokens=1800, temperature=0.4)    # registra el uso con que='auxiliar'
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


def _extras(fila):
    d = _datos(fila)
    return {k: d[k] for k in ETIQUETA_EXTRA if _es_num(d.get(k))}


def huella(dias, cfg):
    """(8/11, Franco) Una firma de lo que la apertura resume: campañas (nombre y piezas con su estado y fecha) y los números de cada
    canal. Si cambia (se borró una campaña, salió una pieza, se leyeron números nuevos), la apertura guardada quedó vieja."""
    import hashlib, json
    from api.admin_rutas import periodo            # recién acá: la cola no carga FastAPI
    per = periodo(dias, None)
    data = metricas.campanas(per)
    camps = [(c["id"], c["nombre"], c.get("descripcion"), sorted((p["id"], p["estado"], p["fecha"]) for p in c["piezas"]))
             for c in data["campanas"] + [data["sueltas"]]]
    # (12/11, Franco) también cambian la lista de contactos, el período anterior, las tasas y los números extra de cada canal
    canales = [(c["clave"], metricas._numeros(c.get("ultima")), metricas._numeros(c.get("manual")),
                _extras(c.get("ultima")), _extras(c.get("manual")), _extras(c.get("anterior")), metricas._numeros(c.get("anterior")), c.get("tasas"))
               for c in metricas.canales_estado(cfg)["canales"]]
    return hashlib.sha1(json.dumps([camps, canales], sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]


def apertura(dias, usuario, cfg, forzar=False):
    """El mensaje con que el asesor recibe al abrir la pestaña. Se reutiliza la última guardada mientras sea de hoy (hora Argentina) Y los
    datos no hayan cambiado (`huella`); si cambió algo (8/11, Franco: «la carpeta Dios no está más y la apertura la sigue nombrando»)
    o se pide `forzar`, se arma de nuevo. {texto, fuentes, falto, capturado, nuevo}."""
    ya = db.ultimas_metricas("resumen", refs=["apertura"], fuente="ia").get(("apertura", "ia"))
    cap = metricas._fecha(ya.get("capturado")) if ya else None
    firma = huella(dias, cfg)
    d = (ya or {}).get("datos") or {}
    if (not forzar and cap and cap.astimezone(metricas.ZONA_AR).date() == dt.datetime.now(metricas.ZONA_AR).date()
            and d.get("huella") == firma):
        return {"texto": d.get("texto") or "", "fuentes": d.get("fuentes") or [], "falto": d.get("falto") or [], "capturado": ya["capturado"], "nuevo": False}
    from api.admin_rutas import periodo
    per = periodo(dias, None)
    pregunta = ("Armá el mensaje de apertura de hoy, en markdown corto y con ESTA estructura, en este orden: "
                "(1) «**En una línea:**» un veredicto de hasta 3 líneas sobre cómo viene la semana y el mes: qué salió hecho por personas, qué "
                "salió solo (automático) y el número que más cambió contra el período anterior, si hay. "
                "(2) «**Gente propia:**» una línea con la lista de mail y su variación, y WhatsApp si hay dato; si no hay nada, "
                "«todavía no medimos la lista». "
                "(3) «**Campañas:**» una línea por campaña hecha por personas, NOMBRANDO lo publicado esta semana, lo programado (título, canal, "
                "día y hora, de quién) y lo que está en aprobación; lo que está saliendo en tandas se dice así, no «programada»; la Frase del día "
                "automática en UNA sola línea con sus totales y la de más alcance, nunca día por día. "
                "(4) «**Falta cargar:**» una línea, solo con lo que figura en LO QUE FALTA CARGAR. "
                "(5) «**Sugerencia:**» una, concreta. No comentes datos que no figuran. "
                f"Hasta {LIMITE_APERTURA} palabras.")
    r = responder([{"rol": "usuario", "texto": pregunta}], per, usuario, cfg, limite=LIMITE_APERTURA)
    fila = _guardar("apertura", per, dict(r, dias=per["dias"], huella=firma))
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
