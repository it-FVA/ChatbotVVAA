"""
perfit.py — Cliente mínimo de Perfit (26/10, reunión: la Frase del día vuelve por mail con el disparador personalizado).
Dos cosas, nada más:
  1. Leer la lista de destinatarios desde la API de contactos (así no hay que exportar nada a mano: cuando Julián
     tenga la lista depurada, acá se lee tal cual está en Perfit).
  2. Disparar un evento del «custom trigger» por contacto: Perfit tiene una automation atada a la clave del evento
     (frase_del_dia) que manda el mail con los datos del contexto (frase, autor, imagen_url, fecha…).
Límite de Perfit: 200 eventos por hora; el que se pasa recibe 429 y se descarta. Por eso el envío va en tandas
(frase_mail.py) y a la lista de 3.140 le lleva ~16 horas.
Variables (todas secretas salvo el modo; se cargan en Render, en los secrets de GitHub Actions y en local):
  PUBLICAR_MAIL        apagado | simulado | real   (como PUBLICAR_INSTAGRAM; simulado = no manda nada, pero registra)
  PERFIT_API_KEY       API key de la cuenta (Perfit → Perfil → API key); va como «Authorization: Bearer …»
  PERFIT_CUENTA        nombre de la cuenta en Perfit (el «micuenta» de https://api.myperfit.com/v2/micuenta/…)
  PERFIT_TRIGGER_URL   la URL que da Perfit al activar Integraciones → Custom Triggers (lleva los ids adentro)
  PERFIT_TRIGGER_KEY   clave del evento (por defecto frase_del_dia_corpus: la del Automation que ya existe desde agosto)
  PERFIT_LISTA_FRASE   id (número) o nombre exacto de la lista de la Frase del día en Perfit
Fuente: developers.myperfit.com (Contacts API, Custom Triggers) y perfitapiv2.docs.apiary.io, leídos el 26/10/2026.
"""
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.myperfit.com/v2"
MODOS = ("apagado", "simulado", "real")
TRIGGER_KEY_DEFECTO = "frase_del_dia_corpus"   # la clave del Automation que ya existe en Perfit (distribucion/, agosto)
LIMITE_POR_HORA = 200            # documentado por Perfit (26/10/2026)
PAGINA = 500                     # contactos por pedido al listar (la API pagina con offset/limit)


def modo(fuente=None):
    f = fuente if fuente is not None else os.environ
    m = (f.get("PUBLICAR_MAIL") or "apagado").strip().lower()
    return m if m in MODOS else "apagado"


def configurado(fuente=None):
    """Qué falta para que el mail funcione de verdad: lista vacía = todo cargado."""
    f = fuente if fuente is not None else os.environ
    faltan = [k for k in ("PERFIT_API_KEY", "PERFIT_CUENTA", "PERFIT_TRIGGER_URL", "PERFIT_LISTA_FRASE") if not (f.get(k) or "").strip()]
    return faltan


def _req(metodo, ruta, datos=None, fuente=None, timeout=60):
    f = fuente if fuente is not None else os.environ
    key = (f.get("PERFIT_API_KEY") or "").strip()
    cuenta = (f.get("PERFIT_CUENTA") or "").strip()
    if not key or not cuenta:
        raise RuntimeError("Faltan PERFIT_API_KEY o PERFIT_CUENTA.")
    url = f"{API}/{cuenta}{ruta}"
    cuerpo = json.dumps(datos).encode() if datos is not None else None
    req = urllib.request.Request(url, data=cuerpo, method=metodo,
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                                          "Accept": "application/json", "User-Agent": "FVA chatbot (perfit.py)"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        cuerpo = e.read().decode("utf-8", "ignore")[:300]
        raise RuntimeError(f"Perfit {e.code} en {metodo} {ruta}: {cuerpo}")


# ---------------- Listas y contactos ----------------
def listas(q="", fuente=None, limite=100):
    """Las listas de la cuenta: [{id, name, activeContacts, totalContacts, ...}]."""
    out, offset = [], 0
    while True:
        r = _req("GET", f"/lists?{urllib.parse.urlencode({'q': q, 'offset': offset, 'limit': limite, 'sortby': 'name', 'sortdir': 'asc'})}", fuente=fuente)
        datos = r.get("data") or []
        out.extend(datos)
        pag = r.get("paging") or {}
        offset += len(datos)
        if not datos or offset >= int(pag.get("total") or 0):
            break
    return out


def lista_frase(fuente=None):
    """La lista de la Frase del día según PERFIT_LISTA_FRASE (id numérico o nombre exacto). Devuelve el dict de la lista o None."""
    f = fuente if fuente is not None else os.environ
    ref = (f.get("PERFIT_LISTA_FRASE") or "").strip()
    if not ref:
        return None
    if re.fullmatch(r"\d+", ref):
        r = _req("GET", f"/lists/{ref}", fuente=fuente)
        return r.get("data") or None
    for l in listas(q=ref, fuente=fuente):
        if (l.get("name") or "").strip().lower() == ref.lower():
            return l
    return None


def contactos_de_lista(lista_id, estado="active", fuente=None):
    """Los mails de una lista, filtrados por estado (active = suscriptos y entregables). Pagina de a PAGINA.
    Devuelve [{id, email}] (la API de listado solo da id y email)."""
    out, offset = [], 0
    while True:
        params = {"offset": offset, "limit": PAGINA, "filter[list]": lista_id, "sortby": "email", "sortdir": "asc"}
        if estado:
            params["filter[state]"] = estado
        r = _req("GET", "/contacts?" + urllib.parse.urlencode(params), fuente=fuente)
        datos = r.get("data") or []
        out.extend({"id": c.get("id"), "email": (c.get("email") or "").strip().lower()} for c in datos if c.get("email"))
        pag = r.get("paging") or {}
        offset += len(datos)
        if not datos or offset >= int(pag.get("total") or 0):
            break
    # sin repetidos, por si la lista los tiene
    vistos, unicos = set(), []
    for c in out:
        if c["email"] not in vistos:
            vistos.add(c["email"])
            unicos.append(c)
    return unicos


# ---------------- Custom trigger ----------------
def disparar(email, contexto, fuente=None, trigger_key=None, timeout=30):
    """Manda UN evento del custom trigger para ese contacto. Devuelve {"ok", "estado": enviado|limite|error, "aviso"}.
    'limite' = Perfit respondió 429 (ya se pasaron los 200 por hora): hay que parar y seguir en la próxima tanda."""
    f = fuente if fuente is not None else os.environ
    url = (f.get("PERFIT_TRIGGER_URL") or "").strip()
    if not url:
        return {"ok": False, "estado": "error", "aviso": "Falta PERFIT_TRIGGER_URL."}
    cuerpo = {"trigger_key": trigger_key or (f.get("PERFIT_TRIGGER_KEY") or TRIGGER_KEY_DEFECTO).strip(),
              "contact": email, "context": {k: ("" if v is None else str(v)) for k, v in (contexto or {}).items()}}
    req = urllib.request.Request(url, data=json.dumps(cuerpo).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": "FVA chatbot (perfit.py)"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return {"ok": True, "estado": "enviado", "aviso": f"HTTP {r.status}"}
    except urllib.error.HTTPError as e:
        if e.code == 429:
            return {"ok": False, "estado": "limite", "aviso": "Perfit: 429, límite de 200 por hora"}
        return {"ok": False, "estado": "error", "aviso": f"Perfit {e.code}: {e.read().decode('utf-8', 'ignore')[:200]}"}
    except Exception as e:
        return {"ok": False, "estado": "error", "aviso": f"sin conexión: {e}"}


def probar_conexion(fuente=None):
    """Para Salud y para la pantalla: qué está cargado y si la API responde. No manda nada."""
    f = fuente if fuente is not None else os.environ
    out = {"modo": modo(f), "faltan": configurado(f), "lista": None, "error": None, "api_ok": False, "listas": None}
    if "PERFIT_API_KEY" in out["faltan"] or "PERFIT_CUENTA" in out["faltan"]:
        return out
    try:
        # primero, ¿la API key sirve? (un pedido chico, aunque todavía no haya lista elegida)
        r = _req("GET", "/lists?limit=1", fuente=f)
        out["api_ok"] = bool(r.get("success", True))
        out["listas"] = int((r.get("paging") or {}).get("total") or 0)
        l = lista_frase(f)
        if l:
            out["lista"] = {"id": l.get("id"), "nombre": l.get("name"), "activos": l.get("activeContacts"), "total": l.get("totalContacts")}
        elif "PERFIT_LISTA_FRASE" not in out["faltan"]:
            out["error"] = f"No encontré en Perfit la lista «{f.get('PERFIT_LISTA_FRASE')}»."
    except Exception as e:
        out["error"] = str(e)[:300]
    return out
