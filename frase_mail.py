"""
frase_mail.py — La Frase del día por mail, en tandas, con el custom trigger de Perfit (26/10, decisión de Beto:
«usar el disparador de 200 por hora aunque sea provisorio, mientras se elige la herramienta nueva»).
Cómo encaja con lo que ya existe:
  - programar_frases.py deja, para cada día con la frase asignada y el canal «mail» prendido, UNA pieza en la cola
    (tabla publicaciones, canal 'mail') con fecha = el día anterior a la hora `frase_mail_inicio` (15:00 por defecto):
    a 200 por hora, la lista de 3.140 lleva ~16 horas, así que arrancando a las 15:00 a las 7:00 la tienen todos.
  - procesar_cola.py, cuando esa pieza vence, llama a `iniciar`: baja la lista de Perfit (o, en simulado, usa la lista
    de prueba de config) y deja un renglón por destinatario en `frase_envios` (estado 'pendiente'); la pieza pasa a
    'enviando'.
  - En cada pasada (cada 15 minutos) `avanzar` manda hasta 50 eventos (= 200 por hora). Si Perfit responde 429, para
    y sigue en la pasada siguiente. Cuando no queda nada pendiente, la pieza pasa a 'publicada' (real) o 'simulada'.
  - `enviar_prueba` manda la frase de un día a unos mails sueltos, ya mismo (la primera prueba del equipo).
Lo que recibe la automation de Perfit en el contexto del evento (para armar la plantilla del mail):
  frase, autor, imagen_url (la foto con la frase encima, 1080×1080, ya en WordPress), fecha (AAAA-MM-DD), fecha_texto
  («lunes 27 de octubre»), pie (hashtags), link (el sitio).
"""
import datetime
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

POR_CORRIDA = 50                 # 4 pasadas por hora × 50 = los 200 por hora de Perfit
INICIO_DEFECTO = "15:00"         # hora Argentina del día ANTERIOR en que arranca el envío
ZONA = datetime.timezone(datetime.timedelta(hours=-3))
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def fecha_texto(fecha, con_anio=False):
    d = datetime.date.fromisoformat(str(fecha)[:10])
    return f"{DIAS[d.weekday()]} {d.day} de {MESES[d.month - 1]}" + (f" de {d.year}" if con_anio else "")


def contexto_de(frase, fecha, imagen_url, pie=None, link=None):
    """Lo que viaja en el evento del trigger y usa la plantilla del mail en Perfit. Mantiene los nombres que ya usa el
    Automation de agosto (distribucion/newsletter/plantilla-myperfit.html: ${frase} ${autor} ${fuente} ${url} ${fecha}, con
    la fecha larga) y suma imagen_url, fecha_iso, fecha_texto, pie y link."""
    sitio = link or os.environ.get("DOMINIO_WEB") or "https://viviragradecidos.org"
    return {"frase": (frase.get("texto") or "").strip(), "autor": (frase.get("autor") or "").strip() or "Br. David",
            "fuente": (frase.get("fuente") or "").strip() if isinstance(frase.get("fuente"), str) else "",
            "url": sitio, "link": sitio, "imagen_url": imagen_url or "",
            "fecha": fecha_texto(fecha, con_anio=True), "fecha_iso": str(fecha)[:10], "fecha_texto": fecha_texto(fecha),
            "pie": pie or ""}


def _emails_prueba(db):
    lista = db.obtener_config("frase_mail_prueba") or []
    return [e.strip().lower() for e in lista if isinstance(e, str) and "@" in e]


def destinatarios(db, perfit, modo):
    """En real: los contactos activos de la lista de la Frase del día en Perfit. En simulado/apagado: la lista de prueba.
    Devuelve (emails, de_donde)."""
    if modo == "real":
        lista = perfit.lista_frase()
        if not lista:
            raise RuntimeError(f"No encontré la lista «{os.environ.get('PERFIT_LISTA_FRASE')}» en Perfit.")
        emails = [c["email"] for c in perfit.contactos_de_lista(lista["id"], estado="active")]
        return emails, f"lista «{lista.get('name')}» de Perfit ({len(emails)} activos)"
    emails = _emails_prueba(db)
    return emails, f"lista de prueba de config ({len(emails)})" + (" · modo " + modo)


def iniciar(p, db, perfit):
    """La pieza 'mail' venció: arma la lista de destinatarios en frase_envios y deja la pieza en 'enviando'.
    Devuelve el dict que espera procesar_cola: {"ok", "modo", "aviso", "estado_cola": "enviando"}."""
    m = perfit.modo()
    if m == "apagado":
        return {"ok": False, "modo": m, "aviso": "PUBLICAR_MAIL está apagado: no se manda nada."}
    faltan = perfit.configurado()
    if m == "real" and faltan:
        return {"ok": False, "modo": m, "aviso": "Faltan variables de Perfit: " + ", ".join(faltan)}
    try:
        emails, de_donde = destinatarios(db, perfit, m)
    except Exception as e:
        return {"ok": False, "modo": m, "aviso": f"no pude leer los destinatarios: {e}"}
    if not emails:
        return {"ok": False, "modo": m, "aviso": "sin destinatarios: " + de_donde}
    fecha = ((p.get("resultado") or {}).get("frase_del_dia") or str(p.get("fecha_programada") or "")[:10])
    db.crear_envios_frase(p["id"], fecha, emails)
    return {"ok": True, "modo": m, "estado_cola": "enviando",
            "aviso": f"{len(emails)} destinatarios ({de_donde}); se mandan de a {POR_CORRIDA} por pasada"}


def avanzar(db, perfit, max_por_corrida=POR_CORRIDA, piezas=None):
    """Manda la siguiente tanda de las piezas 'mail' en 'enviando'. Devuelve un resumen por pieza."""
    m = perfit.modo()
    piezas = piezas if piezas is not None else db.publicaciones_por_estado("enviando", canal="mail")
    resumen = []
    cupo = max_por_corrida
    for p in piezas:
        pid = p["id"]
        res = p.get("resultado") or {}
        frase = db.obtener_frase(res.get("frase_id")) if res.get("frase_id") else None
        ctx = contexto_de(frase or {"texto": res.get("texto_imagen"), "autor": res.get("autor")},
                          res.get("frase_del_dia") or str(p.get("fecha_programada") or "")[:10],
                          p.get("imagen_url"), pie=db.obtener_config("frase_pie"))
        enviados = errores = 0
        limite = False
        if cupo > 0:
            for fila in db.envios_pendientes(pid, cupo):
                if m == "real":
                    r = perfit.disparar(fila["email"], ctx)
                else:
                    r = {"ok": True, "estado": "enviado", "aviso": f"simulado: no se mandó ({m})"}
                if r["estado"] == "limite":
                    limite = True
                    break
                db.actualizar_envio(fila["id"], {"estado": "enviado" if r["ok"] else "error",
                                                 "enviado_en": db._ahora_iso() if r["ok"] else None,
                                                 "error": None if r["ok"] else r["aviso"][:300]})
                cupo -= 1
                if r["ok"]:
                    enviados += 1
                else:
                    errores += 1
        conteo = db.resumen_envios(pid)
        campos = {"resultado": dict(res, envios=conteo, ultimo=f"tanda: {enviados} enviados, {errores} errores"
                                    + (" · Perfit pidió esperar (429)" if limite else ""))}
        if not conteo.get("pendiente"):
            campos["estado"] = "publicada" if m == "real" and conteo.get("enviado") else "simulada"
            campos["procesado_en"] = db._ahora_iso()
        db.actualizar_publicacion(pid, campos)
        resumen.append({"id": pid, "enviados": enviados, "errores": errores, "quedan": conteo.get("pendiente", 0),
                        "limite": limite, "estado": campos.get("estado", "enviando")})
        if limite:
            break
    return resumen


def enviar_prueba(frase, fecha, imagen_url, emails, db, perfit, pie=None):
    """Manda la frase a esos mails ahora mismo (prueba del equipo). Respeta el modo: en simulado no manda, solo registra."""
    m = perfit.modo()
    if m == "apagado":
        return {"ok": False, "modo": m, "aviso": "PUBLICAR_MAIL está apagado.", "resultados": []}
    faltan = [k for k in perfit.configurado() if k != "PERFIT_LISTA_FRASE"]   # para la prueba no hace falta la lista
    if m == "real" and faltan:
        return {"ok": False, "modo": m, "aviso": "Faltan variables de Perfit: " + ", ".join(faltan), "resultados": []}
    ctx = contexto_de(frase, fecha, imagen_url, pie=pie)
    emails = [e.strip().lower() for e in emails if e and "@" in e][:LIMITE_PRUEBA]
    ids = db.crear_envios_frase(None, str(fecha)[:10], emails, prueba=True)
    resultados = []
    for fila in ids:
        r = perfit.disparar(fila["email"], ctx) if m == "real" else {"ok": True, "estado": "enviado", "aviso": f"simulado ({m}): no se mandó"}
        db.actualizar_envio(fila["id"], {"estado": "enviado" if r["ok"] else "error",
                                         "enviado_en": db._ahora_iso() if r["ok"] else None,
                                         "error": None if r["ok"] else r["aviso"][:300]})
        resultados.append({"email": fila["email"], "ok": r["ok"], "aviso": r["aviso"]})
        if r["estado"] == "limite":
            break
    ok = sum(1 for x in resultados if x["ok"])
    return {"ok": ok > 0, "modo": m, "aviso": f"{ok} de {len(emails)} enviados" + ("" if m == "real" else f" (modo {m}: no salió ningún mail)"),
            "contexto": ctx, "resultados": resultados}


LIMITE_PRUEBA = 30


def main(argv=None):
    """`python frase_mail.py` = una tanda (lo llama procesar_cola al final de cada pasada)."""
    from procesar_cola import _cargar_config_local
    _cargar_config_local()
    import db, perfit
    if not db.disponible():
        print("frase por mail: sin Supabase, nada que hacer.")
        return 1
    r = avanzar(db, perfit)
    if not r:
        print(f"frase por mail: nada en envío (modo {perfit.modo()})")
    for x in r:
        print(f"frase por mail: pieza {x['id']} → {x['enviados']} enviados, {x['errores']} errores, quedan {x['quedan']}"
              + (" · 429" if x["limite"] else "") + f" · {x['estado']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
