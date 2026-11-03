"""
avisos.py — avisos al equipo cuando pasa algo que alguien tiene que mirar (2/11, pedido de Franco).
Hoy la plataforma no avisaba: Patricio mandó tres piezas a aprobación a las 19:46 y nadie se enteró hasta mirar la pantalla.

Qué avisa:
  - a los aprobadores (rol aprobador o admin, activos, con email) cuando llega una pieza a aprobación;
  - a quien hizo la pieza cuando se la aprueban o rechazan.

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
