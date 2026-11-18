"""
avisos.py — avisos al equipo cuando pasa algo que alguien tiene que mirar (2/11, pedido de Franco).
Hoy la plataforma no avisaba: Patricio mandó tres piezas a aprobación a las 19:46 y nadie se enteró hasta mirar la pantalla.

Qué avisa:
  - a los aprobadores (rol aprobador o admin, activos, con email) cuando llega una pieza a aprobación;
  - a quien hizo la pieza cuando se la aprueban, rechazan o cancelan.
(18/11, Franco: inventario de avisos) Además, desde la cola (procesar_cola.py / frase_mail.py), todos con el texto acá:
  - pieza_fallo: la cola no pudo publicar una pieza (primer error «se reintenta» y error definitivo tras 3 intentos): a quien la
    hizo y a los aprobadores. Antes una pieza aprobada podía fallar sin que nadie se enterara.
  - pieza_publicada: la cola la publicó de verdad (modo real): a quien la hizo, con el link. No para la Frase del día ni simuladas.
  - frases_pocas: el calendario de la Frase del día tiene 5 días o menos con frase (Slack, una vez por día).
  - token_ig_por_vencer: al token de Instagram le quedan 10 días o menos (Slack, una vez por día).
  - frase_mail_terminado: el envío por mail de la frase cerró con errores, o quedó incompleto al cierre del día (Slack).
  «Una vez por día» se lleva en config.avisos_diarios ({nombre: 'AAAA-MM-DD'}): una_vez_por_dia / marcar_avisado_hoy.

Por dónde (los dos son opcionales; sin configuración no hace nada y nunca rompe el pedido que lo llamó):
  - Slack: SLACK_WEBHOOK_URL (un «Incoming Webhook» del canal del equipo). Un mensaje por aviso.
  - Mail: SMTP_HOST, SMTP_PORT (587), SMTP_USER, SMTP_PASS, AVISOS_DESDE (remitente). Con Google Workspace:
    smtp.gmail.com + una contraseña de aplicación de la cuenta que manda.
  WEB_URL es el link a la plataforma en los avisos (default https://chatbot-vvaa.vercel.app).

Corre en un hilo aparte (no demora la respuesta de la API) y lo que pasa queda en el log del servidor.
"""
import json
import logging
import os
import smtplib
import threading
import urllib.request
from email.message import EmailMessage

log = logging.getLogger("avisos")

NOMBRE_CANAL = {"instagram": "Instagram", "facebook": "Facebook", "wordpress": "Blogpost", "youtube": "YouTube",
                "newsletter": "Newsletter", "mail": "Mail", "home": "Sitio web", "whatsapp": "WhatsApp"}


def web_url():
    return (os.environ.get("WEB_URL") or "https://chatbot-vvaa.vercel.app").rstrip("/")


def configurado():
    """Qué salidas están configuradas: {"slack": bool, "mail": bool}."""
    return {"slack": bool(os.environ.get("SLACK_WEBHOOK_URL")),
            "mail": bool(os.environ.get("SMTP_HOST") and os.environ.get("SMTP_USER") and os.environ.get("SMTP_PASS"))}


# ---------------- salidas ----------------
def _slack(texto):
    url = os.environ.get("SLACK_WEBHOOK_URL")
    if not url:
        return False
    req = urllib.request.Request(url, data=json.dumps({"text": texto}).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.status == 200


def _mail(destinatarios, asunto, texto):
    host, user, pw = os.environ.get("SMTP_HOST"), os.environ.get("SMTP_USER"), os.environ.get("SMTP_PASS")
    if not (host and user and pw) or not destinatarios:
        return False
    msg = EmailMessage()
    msg["From"] = os.environ.get("AVISOS_DESDE") or user
    msg["To"] = ", ".join(destinatarios)
    msg["Subject"] = asunto
    msg.set_content(texto)
    with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT") or 587), timeout=20) as s:
        s.starttls()
        s.login(user, pw)
        s.send_message(msg)
    return True


def _mandar(asunto, texto, emails):
    """Manda por las salidas configuradas. Devuelve {"slack": ok|None, "mail": ok|None}; los errores van al log."""
    out = {"slack": None, "mail": None}
    try:
        out["slack"] = _slack(f"*{asunto}*\n{texto}") if os.environ.get("SLACK_WEBHOOK_URL") else None
    except Exception as e:
        log.warning("aviso por Slack falló: %s", e)
        out["slack"] = False
    try:
        out["mail"] = _mail(emails, asunto, texto) if emails and configurado()["mail"] else None
    except Exception as e:
        log.warning("aviso por mail falló: %s", e)
        out["mail"] = False
    return out


def _en_hilo(fn, *a):
    t = threading.Thread(target=fn, args=a, daemon=True)
    t.start()
    return t


# ---------------- destinatarios ----------------
def _emails_aprobadores(db):
    try:
        return sorted({u["email"].strip().lower() for u in db.listar_usuarios()
                       if u.get("email") and u.get("activo", True) and u.get("rol") in ("aprobador", "admin")})
    except Exception as e:
        log.warning("no pude leer los aprobadores: %s", e)
        return []


def _email_de(db, usuario):
    try:
        for u in db.listar_usuarios():
            if u.get("usuario") == usuario and u.get("email"):
                return u["email"].strip().lower()
    except Exception as e:
        log.warning("no pude leer el email de %s: %s", usuario, e)
    return None


# ---------------- avisos ----------------
def pieza_a_aprobar(db, pid, usuario, canal, titulo, texto, formato=None, sincrono=False):
    """Llegó una pieza a aprobación: avisa a los aprobadores (Slack y/o mail)."""
    if not any(configurado().values()):
        return None
    nombre = NOMBRE_CANAL.get(canal, canal) + (f" · {formato}" if formato and formato != "cuadrado" else "")
    resumen = (titulo or texto or "").strip().replace("\n", " ")[:140]
    asunto = f"Pieza para aprobar: {nombre} — {usuario}"
    cuerpo = (f"{usuario} mandó una pieza de {nombre} a aprobación.\n"
              + (f"«{resumen}»\n" if resumen else "")
              + f"Revisarla: {web_url()}/aprobacion")
    emails = _emails_aprobadores(db)
    if sincrono:
        return _mandar(asunto, cuerpo, emails)
    return _en_hilo(_mandar, asunto, cuerpo, emails)


def pieza_cancelada(db, pieza, por, sincrono=False):
    """(18/11, Franco) Alguien bajó de la cola una pieza ya aprobada: avisa a quien la hizo (Slack y/o mail), como pieza_resuelta."""
    if not any(configurado().values()):
        return None
    canal = pieza.get("canal") or ""
    nombre = NOMBRE_CANAL.get(canal, canal)
    titulo = (pieza.get("titulo") or pieza.get("texto") or "").strip().replace("\n", " ")[:120]
    quien = pieza.get("usuario") or ""
    cuando = (pieza.get("fecha_programada") or "")[:16].replace("T", " ")
    asunto = f"Pieza cancelada: {nombre} — {quien}"
    cuerpo = (f"La canceló {por}." + (f" Iba a salir el {cuando}." if cuando else "") + (f"\n«{titulo}»" if titulo else "")
              + f"\nVerla en Mis publicaciones → Rechazadas: {web_url()}/publicaciones")
    emails = [e for e in [_email_de(db, quien)] if e]
    if sincrono:
        return _mandar(asunto, cuerpo, emails)
    return _en_hilo(_mandar, asunto, cuerpo, emails)


def pieza_resuelta(db, pieza, decision, por, nota=None, cuando=None, sincrono=False):
    """La aprobaron o rechazaron: avisa a quien la hizo (Slack y/o mail)."""
    if not any(configurado().values()):
        return None
    canal = pieza.get("canal") or ""
    nombre = NOMBRE_CANAL.get(canal, canal)
    titulo = (pieza.get("titulo") or pieza.get("texto") or "").strip().replace("\n", " ")[:120]
    quien = pieza.get("usuario") or ""
    if decision == "aprobada":
        asunto = f"Pieza aprobada: {nombre} — {quien}"
        cuerpo = (f"{por} aprobó la pieza de {nombre} de {quien}" + (f" «{titulo}»" if titulo else "") + "."
                  + (f" Sale el {cuando}." if cuando else "")
                  + f"\nVerla: {web_url()}/publicaciones")
    else:
        asunto = f"Pieza rechazada: {nombre} — {quien}"
        cuerpo = (f"{por} rechazó la pieza de {nombre} de {quien}" + (f" «{titulo}»" if titulo else "") + "."
                  + (f"\nNota: {nota}" if nota else "")
                  + f"\nVerla en Mis publicaciones → Rechazadas: {web_url()}/publicaciones")
    emails = [e for e in [_email_de(db, quien)] if e]
    if sincrono:
        return _mandar(asunto, cuerpo, emails)
    return _en_hilo(_mandar, asunto, cuerpo, emails)


# ---------------- avisos desde la cola (18/11, Franco) ----------------
TRELLO_TOKEN_IG = "https://trello.com/c/WVoR4cNK"      # tarjeta «Conectores»: cómo generar y dónde pegar el token de Instagram
FRASES_POCAS_DIAS = 5                                   # avisar cuando queden 5 días o menos con frase
TOKEN_IG_AVISO_DIAS = 10                                # avisar cuando falten 10 días o menos (la cola renueva sola a los 30)


def _hora_programada(pieza):
    return (pieza.get("fecha_programada") or "")[:16].replace("T", " ")


def _titulo_corto(pieza):
    return (pieza.get("titulo") or pieza.get("texto") or "").strip().replace("\n", " ")[:120]


def pieza_fallo(db, pieza, aviso, intentos, definitivo, sincrono=False):
    """La cola no pudo publicar la pieza. definitivo=True: agotó los 3 intentos y quedó en 'error'; si no, se reintenta en la
    próxima corrida (15 min). Avisa a quien la hizo y a los aprobadores (Slack y/o mail)."""
    if not any(configurado().values()):
        return None
    canal = pieza.get("canal") or ""
    nombre = NOMBRE_CANAL.get(canal, canal)
    quien = pieza.get("usuario") or ""
    cuando, titulo = _hora_programada(pieza), _titulo_corto(pieza)
    err = str(aviso or "sin detalle").strip().replace("\n", " ")[:300]
    if definitivo:
        asunto = f"Pieza NO salió: {nombre} — {quien}"
        cuerpo = (f"La cola no pudo publicar la pieza de {nombre} de {quien}" + (f" «{titulo}»" if titulo else "") + "."
                  + (f" Iba a salir el {cuando}." if cuando else "")
                  + f"\nFalló {intentos} veces y quedó en error: {err}"
                  + f"\nQué hacer: revisar el error, corregir la pieza y volver a mandarla (Mis publicaciones → Editar): {web_url()}/publicaciones")
    else:
        asunto = f"Pieza con error al publicar: {nombre} — {quien}"
        cuerpo = (f"La cola no pudo publicar la pieza de {nombre} de {quien}" + (f" «{titulo}»" if titulo else "") + "."
                  + (f" Iba a salir el {cuando}." if cuando else "")
                  + f"\nError (intento {intentos} de 3): {err}"
                  + "\nSe reintenta en la próxima corrida (15 min). Si falla tres veces queda en error y aviso de nuevo.")
    emails = sorted(set([e for e in [_email_de(db, quien)] if e] + _emails_aprobadores(db)))
    if sincrono:
        return _mandar(asunto, cuerpo, emails)
    return _en_hilo(_mandar, asunto, cuerpo, emails)


def link_publicado(res):
    """El link (o el id) con que el conector devolvió la publicación real: Instagram da permalink, WordPress link, Facebook/YouTube id."""
    res = res if isinstance(res, dict) else {}
    for k in ("permalink", "link", "url"):
        if res.get(k):
            return str(res[k])
    for k in ("id", "post_id", "video_id"):
        if res.get(k):
            return f"id {res[k]}"
    return None


def pieza_publicada(db, pieza, res, sincrono=False):
    """La cola publicó la pieza de verdad (modo real): avisa a quien la hizo con el link. Solo piezas de personas (procesar_cola
    no la llama para la Frase del día ni para las simuladas)."""
    if not any(configurado().values()):
        return None
    canal = pieza.get("canal") or ""
    nombre = NOMBRE_CANAL.get(canal, canal)
    quien = pieza.get("usuario") or ""
    titulo, link = _titulo_corto(pieza), link_publicado(res)
    asunto = f"Pieza publicada: {nombre} — {quien}"
    cuerpo = (f"Ya salió la pieza de {nombre} de {quien}" + (f" «{titulo}»" if titulo else "") + "."
              + (f"\nVerla: {link}" if link else "")
              + f"\nEn la plataforma: {web_url()}/publicaciones")
    emails = [e for e in [_email_de(db, quien)] if e]
    if sincrono:
        return _mandar(asunto, cuerpo, emails)
    return _en_hilo(_mandar, asunto, cuerpo, emails)


def frases_pocas(dias, ultima_fecha, sincrono=True):
    """Quedan `dias` días con frase asignada en el calendario (0 = mañana ya no tiene). Solo Slack."""
    if not os.environ.get("SLACK_WEBHOOK_URL"):
        return None
    asunto = ":calendar: La Frase del día se queda sin frases"
    if dias <= 0:
        cuerpo = "Mañana no tiene frase asignada: si no se carga hoy, mañana no sale la Frase del día."
    else:
        cuerpo = (f"Quedan {dias} día{'s' if dias != 1 else ''} con frase asignada (hasta el {ultima_fecha}). "
                  "Después de eso la Frase del día no sale.")
    cuerpo += f"\nAsignar frases: {web_url()}/frases (Calendario → Repartir, o día por día). Aviso una vez por día mientras siga así."
    return _mandar(asunto, cuerpo, []) if sincrono else _en_hilo(_mandar, asunto, cuerpo, [])


def token_ig_por_vencer(dias, vence, sincrono=True):
    """Al token de Instagram le quedan `dias` días (vence = fecha). La cola lo renueva sola cuando faltan menos de 30, así que
    llegar acá quiere decir que la renovación automática no está funcionando. Solo Slack."""
    if not os.environ.get("SLACK_WEBHOOK_URL"):
        return None
    cuando = vence.strftime("%d/%m/%Y") if hasattr(vence, "strftime") else str(vence)[:10]
    asunto = ":key: El token de Instagram está por vencer"
    if dias < 0:
        estado = f"Venció el {cuando}: Instagram y la Frase del día (historia) no salen hasta renovarlo."
    else:
        estado = f"Vence el {cuando} ({dias} día{'s' if dias != 1 else ''}). La renovación automática no lo renovó."
    cuerpo = (estado + f"\nCómo renovarlo: primero Administración → Instagram → «Renovar token» ({web_url()}/admin); si no alcanza, "
              f"generar uno nuevo y pegarlo donde dice la tarjeta {TRELLO_TOKEN_IG} (y la nota del 5/11 en HANDOFF). "
              "Aviso una vez por día mientras siga así.")
    return _mandar(asunto, cuerpo, []) if sincrono else _en_hilo(_mandar, asunto, cuerpo, [])


def frase_mail_terminado(pieza, conteo, incompleto=False, sincrono=True):
    """El envío por mail de la Frase del día cerró con errores (incompleto=False) o sigue con pendientes al cierre del día de la
    frase (incompleto=True). conteo = {enviado, error, pendiente, total}. Solo Slack."""
    if not os.environ.get("SLACK_WEBHOOK_URL"):
        return None
    res = pieza.get("resultado") or {}
    fecha = res.get("frase_del_dia") or str(pieza.get("fecha_programada") or "")[:10]
    env, err, pend = int(conteo.get("enviado") or 0), int(conteo.get("error") or 0), int(conteo.get("pendiente") or 0)
    asunto = (":email: El mail de la Frase del día quedó incompleto" if incompleto
              else ":email: El mail de la Frase del día terminó con errores")
    cuerpo = (f"Frase del {fecha}: {env} enviados, {err} con error, {pend} pendientes."
              + ("\nSe pasó el día de la frase y todavía hay pendientes: sigue mandando en tandas (200 por hora)." if incompleto else "")
              + (f"\nÚltima tanda: {res.get('ultimo')}" if res.get("ultimo") else "")
              + f"\nQué mirar: Perfit (automatización de la Frase del día) y la pieza en {web_url()}/frases (Mañana → mail).")
    return _mandar(asunto, cuerpo, []) if sincrono else _en_hilo(_mandar, asunto, cuerpo, [])


# ---------------- «una vez por día» (config.avisos_diarios) ----------------
CLAVE_DIARIOS = "avisos_diarios"


def una_vez_por_dia(db, nombre, hoy):
    """True si el aviso `nombre` todavía no se mandó hoy (hoy = 'AAAA-MM-DD'). No marca: marcar_avisado_hoy después de mandar."""
    try:
        d = db.obtener_config(CLAVE_DIARIOS, {}) or {}
        return d.get(nombre) != str(hoy)[:10]
    except Exception as e:
        log.warning("no pude leer %s: %s", CLAVE_DIARIOS, e)
        return False      # sin lectura no se avisa: mejor callar que repetir cada 15 minutos


def marcar_avisado_hoy(db, nombre, hoy):
    try:
        d = db.obtener_config(CLAVE_DIARIOS, {}) or {}
        d[nombre] = str(hoy)[:10]
        db.guardar_config(CLAVE_DIARIOS, d, usuario="cola")
    except Exception as e:
        log.warning("no pude guardar %s: %s", CLAVE_DIARIOS, e)
