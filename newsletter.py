"""
newsletter.py — Canal Newsletter (15/10). Plantillas del newsletter real de la Fundación, el HTML del
email (600 px, colores de la marca) y la redacción de los bloques con el bot a partir del corpus.

Formato leído de dos newsletters reales que mandó Julián (fva-transcripcion/analisis/newsletter-formato.md):
  - "mensual": cabecera con el mes · reflexión del mes (voz de Br. David) · 3 preguntas · un encuentro
    destacado con botón · agenda del mes (tarjetas) · recursos para profundizar · cierre.
  - "revivi": encuadre de un tema · tres episodios de Ecos (foto, título, presentación, link) · cierre.

El bot NO manda el email: deja el HTML aprobado para pegar en Perfit (o lo que lo reemplace).

Uso:
    datos = newsletter.vacio("mensual")          # dict con todos los campos
    datos = newsletter.redactar("mensual", "la confianza en la vida", datos)   # el bot completa los textos
    html  = newsletter.armar_html("mensual", datos)
"""
import json
import re
import html as _html

PLANTILLAS = {"mensual": "Mensual (reflexión + agenda + recursos)", "revivi": "Reviví (tres episodios de Ecos)"}

# Colores sacados del newsletter real
VERDE = "#1f4d3f"      # títulos
AMARILLO = "#f4b43c"   # botones
AZUL = "#1b2e6b"       # títulos del Reviví
GRIS = "#444444"
FUENTE = "Arial, Helvetica, sans-serif"

PLACEHOLDER = "https://viviragradecidos.org/wp-content/uploads/2026/10/1080x1920_brother_flores_naturaleza_.jpg"


def vacio(plantilla):
    """Todos los campos de la plantilla, vacíos (o con valores fijos de la Fundación)."""
    if plantilla == "revivi":
        return {"asunto": "", "encuadre": "", "intro": "Hoy reunimos tres episodios de Ecos para mirar ese territorio desde distintas perspectivas:",
                "episodios": [{"titulo": "", "texto": "", "imagen_url": "", "url": ""} for _ in range(3)],
                "cierre_destacado": "", "cierre": "Si te sirve este contenido, no dudes en compartirlo con alguien a quien le pueda hacer bien un momento de pausa.\n¡Que lo disfrutes!",
                "firma": "Con cariño,\nEquipo de Vivir Agradecidos"}
    return {"asunto": "", "mes": "", "cabecera_url": "",
            "reflexion": "", "preguntas": ["", "", ""],
            "encuentro": {"titulo": "UN ENCUENTRO VIVENCIAL", "frase": "", "imagen_url": "", "texto": "",
                          "boton_texto": "RESERVÁ TU LUGAR", "boton_url": ""},
            "agenda": [{"fecha_corta": "", "titulo": "", "descripcion": "", "fecha": "", "horario": "", "modalidad": "",
                        "facilitan": "", "boton_texto": "INSCRIBITE", "boton_url": "", "imagen_url": ""} for _ in range(3)],
            "recursos": {"imagen_url": "",
                         "lectura": {"titulo": "", "url": "", "de": "Brother David"},
                         "ecos": {"titulo": "", "url": "", "con": ""},
                         "meditacion": {"titulo": "", "url": "", "con": ""}},
            "cierre": "", "firma": "Gracias por ser parte de esta comunidad.\nFundación Vivir Agradecidos"}


# ----------------------------------------------------------------------------- HTML

def _e(t):
    return _html.escape(str(t or ""))


def _p(t, size=15, color=GRIS, bold=False, align="left", extra=""):
    t = _e(t).replace("\n", "<br>")
    w = "font-weight:bold;" if bold else ""
    return f'<p style="margin:0 0 14px 0;font-family:{FUENTE};font-size:{size}px;line-height:1.5;color:{color};text-align:{align};{w}{extra}">{t}</p>'


def _h(t, color=VERDE, size=22, align="center"):
    return f'<p style="margin:26px 0 8px 0;font-family:{FUENTE};font-size:{size}px;font-weight:bold;color:{color};text-align:{align};letter-spacing:.5px">{_e(t)}</p>'


def _boton(texto, url, align="left"):
    if not texto:
        return ""
    return (f'<table cellpadding="0" cellspacing="0" border="0" style="margin:10px 0 18px 0;{"margin-left:auto;margin-right:auto;" if align == "center" else ""}"><tr><td style="background:{AMARILLO};border-radius:22px;padding:11px 26px">'
            f'<a href="{_e(url or "#")}" style="font-family:{FUENTE};font-size:14px;font-weight:bold;color:{VERDE};text-decoration:none;letter-spacing:.5px">{_e(texto)}</a></td></tr></table>')


def _img(url, w=600, h=None, alt=""):
    if not url:
        return ""
    hh = f' height="{h}"' if h else ""
    return f'<img src="{_e(url)}" width="{w}"{hh} alt="{_e(alt)}" style="display:block;width:{w}px;max-width:100%;height:auto;border:0">'


def _sep(color=VERDE):
    return f'<hr style="border:0;border-top:2px solid {color};margin:22px 0">'


def _marco(cuerpo, asunto):
    return f'''<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>{_e(asunto)}</title></head>
<body style="margin:0;padding:0;background:#f3f3f3">
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f3f3f3"><tr><td align="center" style="padding:18px 8px">
<table width="600" cellpadding="0" cellspacing="0" border="0" style="width:600px;max-width:100%;background:#ffffff">
<tr><td style="padding:0 0 10px 0">{cuerpo}</td></tr>
<tr><td style="padding:18px 24px;border-top:1px solid #e5e5e5;font-family:{FUENTE};font-size:11px;color:#888;text-align:center">
© 2026 Vivir Agradecidos · Arenales 605, Vicente López, Argentina<br>
<a href="https://www.facebook.com/viviragradecidos" style="color:#888">Facebook</a> · <a href="https://www.instagram.com/viviragradecidos" style="color:#888">Instagram</a> · <a href="https://www.youtube.com/@viviragradecidos" style="color:#888">YouTube</a>
</td></tr>
</table></td></tr></table>
</body></html>'''


def _tarjeta_agenda(a, i):
    img = _img(a.get("imagen_url") or PLACEHOLDER, 280, alt=a.get("titulo", ""))
    datos = "".join(f'<p style="margin:0 0 4px 0;font-family:{FUENTE};font-size:13px;color:{GRIS}">{em} {_e(l)}: {_e(v)}</p>'
                    for em, l, v in (("📅", "Fecha", a.get("fecha")), ("🕙", "Horario", a.get("horario")),
                                     ("💻", "Modalidad", a.get("modalidad")), ("🌿", "Facilitan", a.get("facilitan"))) if v)
    texto = (f'<p style="margin:0 0 8px 0;font-family:{FUENTE};font-size:13px;color:{GRIS}">{_e(a.get("fecha_corta"))}</p>'
             f'<p style="margin:0 0 10px 0;font-family:{FUENTE};font-size:19px;font-weight:bold;color:#222">{_e(a.get("titulo"))}</p>'
             + _p(a.get("descripcion"), 14) + datos + _boton(a.get("boton_texto"), a.get("boton_url")))
    izq, der = (img, texto) if i % 2 == 0 else (texto, img)
    return (f'<table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 6px 0"><tr>'
            f'<td width="50%" valign="top" style="padding:10px 8px">{izq}</td><td width="50%" valign="top" style="padding:10px 8px">{der}</td></tr></table>'
            f'<hr style="border:0;border-top:1px solid {AMARILLO};margin:6px 0 10px 0">')


def armar_html(plantilla, d):
    """Devuelve el HTML completo del email."""
    if plantilla == "revivi":
        cuerpo = '<div style="padding:22px 28px 6px 28px">' + _p("Hola,", 15)
        cuerpo += _p(d.get("encuadre"), 15) + _p(d.get("intro"), 15)
        for ep in d.get("episodios") or []:
            if not (ep.get("titulo") or ep.get("texto")):
                continue
            img = _img(ep.get("imagen_url") or PLACEHOLDER, 260, alt=ep.get("titulo", ""))
            tit = f'<a href="{_e(ep.get("url") or "#")}" style="text-decoration:none"><p style="margin:0 0 12px 0;font-family:{FUENTE};font-size:20px;font-weight:bold;color:{AZUL};text-transform:uppercase">{_e(ep.get("titulo"))}</p></a>'
            cuerpo += (f'<table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:18px 0"><tr>'
                       f'<td width="52%" valign="top" style="padding-right:12px">{tit}{_p(ep.get("texto"), 14)}'
                       f'<a href="{_e(ep.get("url") or "#")}" style="font-family:{FUENTE};font-size:13px;color:{AZUL};font-weight:bold">Escuchar el episodio →</a></td>'
                       f'<td width="48%" valign="top">{img}</td></tr></table><hr style="border:0;border-top:1px solid {AZUL};margin:4px 0 14px 0">')
        cuerpo += _p(d.get("cierre_destacado"), 15, AZUL, bold=True, align="center", extra="text-transform:uppercase;")
        cuerpo += _p(d.get("cierre"), 15) + _p(d.get("firma"), 15) + "</div>"
        return _marco(cuerpo, d.get("asunto") or "Reviví")

    cuerpo = _img(d.get("cabecera_url"), 600, alt=d.get("mes", ""))
    cuerpo += '<div style="padding:22px 28px 6px 28px">' + _p("Hola,", 15) + _p(d.get("reflexion"), 15)
    pregs = [q for q in (d.get("preguntas") or []) if q]
    if pregs:
        cuerpo += _p("Te invitamos a hacer una pausa hoy y hacerte estas preguntas para la reflexión personal:", 15, VERDE, bold=True)
        cuerpo += "".join(_p("🌼 " + q, 15, GRIS, bold=True) for q in pregs)
    en = d.get("encuentro") or {}
    if en.get("frase") or en.get("texto"):
        cuerpo += _sep() + _h(en.get("titulo") or "UN ENCUENTRO VIVENCIAL") + _p(en.get("frase"), 17, VERDE, bold=True, align="center")
        cuerpo += _img(en.get("imagen_url"), 544, alt=en.get("titulo", "")) + _p(en.get("texto"), 15, align="center", extra="margin-top:12px;")
        cuerpo += _boton(en.get("boton_texto"), en.get("boton_url"), align="center")
    ag = [a for a in (d.get("agenda") or []) if a.get("titulo")]
    if ag:
        cuerpo += _sep() + _h(f"LA AGENDA DE {(d.get('mes') or '').upper()}".strip()) + _p("espacios para la práctica", 16, "#222", align="center")
        cuerpo += "".join(_tarjeta_agenda(a, i) for i, a in enumerate(ag))
    rc = d.get("recursos") or {}
    items = []
    for em, rot, k, lab in (("📖", "Lectura", "lectura", "de"), ("🎧", "Ecos (podcast)", "ecos", "con"), ("🧘", "Meditación guiada", "meditacion", "con")):
        it = rc.get(k) or {}
        if it.get("titulo"):
            quien = f", {lab} {_e(it.get(lab))}" if it.get(lab) else ""
            items.append(f'<p style="margin:0 0 14px 0;font-family:{FUENTE};font-size:15px;color:{GRIS}">{em} {rot}: <a href="{_e(it.get("url") or "#")}" style="color:{VERDE};font-weight:bold">{_e(it.get("titulo"))}</a>{quien}</p>')
    if items:
        cuerpo += _sep() + _img(rc.get("imagen_url"), 544, alt="Recursos para profundizar este mes") + _h("RECURSOS PARA PROFUNDIZAR ESTE MES", size=18) + "".join(items)
    cuerpo += _sep(AMARILLO) + _p(d.get("cierre"), 15, align="center") + _p(d.get("firma"), 15, VERDE, bold=True, align="center") + "</div>"
    return _marco(cuerpo, d.get("asunto") or f"Newsletter {d.get('mes', '')}")


# ----------------------------------------------------------------------------- redacción con el bot

def _json_del_modelo(t):
    m = re.search(r"\{.*\}", t, re.S)
    return json.loads(m.group(0)) if m else {}


def redactar(plantilla, tema, d, n_material=8):
    """Completa los textos de la plantilla a partir del corpus (busca material sobre el tema y pide al
    modelo los bloques en JSON). No toca fechas, horarios, links ni imágenes: eso lo carga la persona.
    Devuelve el dict `d` actualizado y la lista de materiales usados."""
    import nucleo
    mats = nucleo.buscar(tema, n=n_material)
    ctx = nucleo.contexto(mats)
    if plantilla == "revivi":
        mats_ecos = nucleo.buscar(tema + " Ecos podcast conversación", n=8, fuente="youtube")
        ctx = nucleo.contexto(mats_ecos) + "\n\n" + ctx
        pedido = ('Devolvé SOLO un JSON con: "asunto" (línea de asunto, con "Reviví:" adelante), "encuadre" (2 oraciones sobre el tema, '
                  'en segunda persona plural como el newsletter real), "episodios" (lista de 3: {"titulo": título del episodio de Ecos EN '
                  'MAYÚSCULAS tal como figura en el material, "texto": 2-3 oraciones que presentan al invitado y el tema, con el nombre del '
                  'invitado, "url": el link del material}), "cierre_destacado" (una frase en mayúsculas que resuma qué eligen según su '
                  'necesidad). Usá SOLO episodios de Ecos / videos que estén en el material; si hay menos de 3, devolvé los que haya.')
    else:
        pedido = ('Devolvé SOLO un JSON con: "asunto" (línea de asunto breve, como "Octubre: Una invitación a celebrar lo que es."), '
                  '"reflexion" (2 párrafos separados por \\n\\n: el primero plantea el tema desde la vida cotidiana; el segundo arranca con '
                  '"Brother David nos enseña que" y sintetiza su mirada SIN inventar citas; si usás una frase textual, va entre comillas y '
                  'tiene que estar en el material), "preguntas" (lista de 3 preguntas para la reflexión personal, en primera persona), '
                  '"encuentro_frase" (una invitación de una línea con 2-3 verbos en mayúsculas, como "Te invitamos a AGRADECER lo recibido, '
                  'CELEBRAR lo que es"), "lectura" ({"titulo", "url"}: un artículo o libro de Br. David del material), "ecos" ({"titulo", '
                  '"url", "con"}: un video o episodio del material, con el nombre de quien habla), "meditacion" ({"titulo", "url", "con"}: '
                  'una meditación o práctica del material si hay; si no, campos vacíos), "cierre" (una frase de deseo para el mes).')
    msgs = [{"role": "system", "content": "Redactás el newsletter mensual de la Fundación Vivir Agradecidos. Tono cálido, sereno, en segunda "
             "persona plural ('te invitamos', 'nos descubrimos'). Español rioplatense sin voseo forzado. No inventás citas, títulos ni links: "
             "solo lo que está en el material. Respondés únicamente con JSON válido."},
            {"role": "user", "content": f"Tema del newsletter: {tema}\n\n{ctx}\n\n{pedido}"}]
    j = _json_del_modelo(nucleo._llm(msgs, max_tokens=1800))
    if not j:
        return d, mats
    d = json.loads(json.dumps(d))
    if plantilla == "revivi":
        for k in ("asunto", "encuadre", "cierre_destacado"):
            if j.get(k):
                d[k] = j[k]
        eps = j.get("episodios") or []
        for i, ep in enumerate(eps[:3]):
            while len(d["episodios"]) <= i:
                d["episodios"].append({"titulo": "", "texto": "", "imagen_url": "", "url": ""})
            d["episodios"][i].update({"titulo": ep.get("titulo", ""), "texto": ep.get("texto", ""), "url": ep.get("url", "")})
        return d, mats
    for k in ("asunto", "reflexion", "cierre"):
        if j.get(k):
            d[k] = j[k]
    if j.get("preguntas"):
        d["preguntas"] = (list(j["preguntas"]) + ["", "", ""])[:3]
    if j.get("encuentro_frase"):
        d["encuentro"]["frase"] = j["encuentro_frase"]
    for k in ("lectura", "ecos", "meditacion"):
        if isinstance(j.get(k), dict):
            d["recursos"][k].update({kk: vv for kk, vv in j[k].items() if kk in d["recursos"][k]})
    return d, mats
