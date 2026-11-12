"""
metricas_perfit.py — Los números del mail (Newsletter y Frase del día), leídos de Perfit (8/11, Franco: «sumar el mail a Métricas»).
Contrato: web/maquetas/metricas-contrato.md. Misma forma que metricas_wordpress.py y metricas_youtube.py.

SOLO HTTP contra Perfit (por perfit._req, que lleva la clave en «Authorization: Bearer» y no imprime nada) más un conteo sin HTTP de la
tabla frase_envios. Cada función devuelve el dict NORMALIZADO del contrato:

    {"enviados", "aperturas", "clics", …   (enteros; la clave está SOLO si Perfit dio el número: nunca un 0 inventado),
     "crudo": {lo que devolvió, chico},
     "errores": [textos en castellano: qué no se pudo traer y por qué]}

  insights_cuenta_mail(fuente_env, dias=28)       la cuenta: suma de las campañas lanzadas en el período (enviados, aperturas, clics, rebotes, bajas,
                                                  tasa_apertura y tasa_clics) + hasta 20 campañas en el crudo
  insights_campana_mail(fuente_env, campaign_id)  una campaña de Perfit: enviados, aperturas, clics, compartidos (+ resto en el crudo)
  insights_frase_mail(db, publicacion_id)         una pieza «mail» de la Frase del día: cuántos envíos salieron y cuántos fallaron (registro de la app)
  hay_clave(fuente_env)                           ¿hay PERFIT_API_KEY y PERFIT_CUENTA?

`fuente_env` es un dict como os.environ (PERFIT_API_KEY, PERFIT_CUENTA). La clave nunca va en `crudo` ni en `errores`.

Endpoints CONFIRMADOS EN VIVO el 8/11 (workflow «perfit-probar», herramientas/perfit_probar.py; GET con «Authorization: Bearer», base
https://api.myperfit.com/v2/{cuenta}):
  · GET /campaigns?limit&offset&sortby=id&sortdir=desc
        → {success, paging{offset, limit, results, total, next}, data:[{id, name, description, tags, type, state, launchMode, launchDate,
           archived, created, lastModified, recipients, thumbnail, metrics{sent, sentP, bounced, bouncedP, opened, openedP, clicked, clickedP,
           conversions, conversionsAmount}}]}
  · GET /campaigns/{id}/metrics
        → {success, data:{recipients, sent, sentP, delivered, deliveredP, opened, openedP, openedT, viewsOnline, clicked, clickedP, clickedT,
           ctor, bounced, bouncedP, bouncedHard, bouncedSoft, complained, unsubscribed, unsubscribedP, shared, sharedOpened}}
  · /campaigns/{id}/stats y /campaigns/{id}/report NO existen (404): no se usan.

SIN CONFIRMAR (la probe solo imprime claves y tipos, no valores):
  · El formato de `launchDate` (se lee como fecha ISO 8601; si no se entiende, esa campaña no se cuenta y queda anotado en `errores`).
  · Si los porcentajes (`openedP`, `clickedP`) vienen de 0 a 100 o de 0 a 1: se guardan tal cual los da Perfit, sin convertir. Los de la cuenta son
    el promedio de los de cada campaña pesado por sus envíos (no se recalculan a partir de aperturas / enviados).
  · Si `paging.next` es una dirección o un número: no se usa; se pagina por `offset` hasta cubrir el período, juntar 100 campañas o agotar `total`.
  · MÉTRICAS DE LAS AUTOMATIONS (/automations): la Frase del día NO es una campaña, la manda una automation por custom trigger. La probe pidió
    GET /automations?limit=3 pero no se confirmó (ni se vio) qué trae para aperturas y clics; por eso la Frase del día cuenta solo los envíos
    de nuestro registro (frase_envios), que son lo que la app mandó a Perfit y no lo que Perfit entregó, abrió o tocó.
  · Los newsletters armados en la app NO se mandan por la API: el HTML se pega a mano en Perfit (newsletter.py), así que no hay id de campaña por
    pieza. Entran a la cuenta cuando se lanzan en Perfit, pero no se atan a una pieza.
"""
import datetime as dt
import urllib.error

import perfit

MAX_CAMPANAS = 100         # tope de campañas que se leen de Perfit en un pedido de cuenta
MAX_EN_CRUDO = 20          # cuántas campañas van en el crudo
PAGINA = 50

TEXTO_SIN_CLAVE = "No hay conexión con Perfit configurada."
TEXTO_CLAVE_RECHAZADA = "Perfit rechazó la clave"
TEXTO_SIN_RESPUESTA = "Perfit no respondió"
FUENTE_REGISTRO = "registro de la app"


def hay_clave(fuente_env):
    f = fuente_env if fuente_env is not None else {}
    return bool((f.get("PERFIT_API_KEY") or "").strip() and (f.get("PERFIT_CUENTA") or "").strip())


def es_error_de_clave(texto):
    t = str(texto)
    return t.startswith(TEXTO_CLAVE_RECHAZADA) or t.startswith(TEXTO_SIN_CLAVE)


def _limpiar(texto, fuente_env):
    t = str(texto)
    for k in ("PERFIT_API_KEY",):
        s = (fuente_env or {}).get(k) or ""
        if s.strip():
            t = t.replace(s.strip(), "***")
    return t


def _pedir(ruta, fuente_env):
    """(respuesta, None) o (None, texto de error en castellano). Traduce los errores de perfit._req; no filtra la clave."""
    try:
        return perfit._req("GET", ruta, fuente=fuente_env, timeout=30), None
    except (RuntimeError, urllib.error.URLError, OSError, TimeoutError, ValueError) as e:
        return None, _traducir(e, fuente_env)


def _traducir(e, fuente_env):
    """El texto en castellano de un error de perfit._req (la clave nunca sale)."""
    if isinstance(e, RuntimeError):
        m = str(e)
        if " 401 " in m or " 403 " in m:
            return f"{TEXTO_CLAVE_RECHAZADA}: revisá PERFIT_API_KEY y PERFIT_CUENTA."
        if " 404 " in m:
            return "Perfit no encontró lo que se pidió (¿ya no existe?)."
        if " 429 " in m:
            return "Perfit pidió esperar un rato antes de volver a preguntar."
        return _limpiar(f"Perfit respondió con un error: {m}", fuente_env)[:200]
    if isinstance(e, ValueError) and not isinstance(e, urllib.error.URLError):
        return "Perfit devolvió algo que no se entiende."
    return f"{TEXTO_SIN_RESPUESTA}: no pude conectarme."


def _salida(normal, crudo, errores):
    out = {k: v for k, v in normal.items() if v is not None}
    out["crudo"] = crudo
    out["errores"] = errores
    return out


def _num(v):
    """Entero o float tal cual lo dio Perfit; None si no hay número (nunca un 0 inventado)."""
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return v
    try:
        x = float(str(v).strip())
        return int(x) if x == int(x) else x
    except ValueError:
        return None


def _entero(v):
    n = _num(v)
    return None if n is None else int(n)


def _fecha(valor):
    if not valor:
        return None
    try:
        d = dt.datetime.fromisoformat(str(valor).strip().replace("Z", "+00:00").replace(" ", "T", 1))
        return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def _campana_en_crudo(c, m):
    return {"id": c.get("id"), "nombre": str(c.get("name") or "")[:120], "fecha": c.get("launchDate"),
            "enviados": _entero(m.get("sent")), "aperturas": _entero(m.get("opened")), "clics": _entero(m.get("clicked")),
            "rebotes": _entero(m.get("bounced")), "bajas": _entero(m.get("unsubscribed"))}


def _promedio_pesado(pares):
    """Promedio de los porcentajes de Perfit pesado por envíos; None si no hay ninguno."""
    pares = [(p, w) for p, w in pares if p is not None and w]
    total = sum(w for _, w in pares)
    return round(sum(p * w for p, w in pares) / total, 2) if total else None


def insights_cuenta_mail(fuente_env, dias=28, ahora=None):
    """La cuenta de Perfit en los últimos `dias` días: suma de las campañas con `launchDate` dentro del período."""
    if not hay_clave(fuente_env):
        return _salida({}, {}, [TEXTO_SIN_CLAVE])
    ahora = ahora or dt.datetime.now(dt.timezone.utc)
    desde = ahora - dt.timedelta(days=dias)
    errores, crudo = [], {"periodo_dias": dias}
    dentro, vistas, sin_fecha, offset, total = [], 0, 0, 0, None
    while vistas < MAX_CAMPANAS:
        r, err = _pedir(f"/campaigns?limit={PAGINA}&offset={offset}&sortby=id&sortdir=desc", fuente_env)
        if r is None:
            errores.append(err)
            if not dentro:
                return _salida({}, crudo, errores)
            break
        datos = [c for c in (r.get("data") or []) if isinstance(c, dict)] if isinstance(r, dict) else []
        pag = (r.get("paging") or {}) if isinstance(r, dict) else {}
        total = _entero(pag.get("total")) if total is None else total
        if not datos:
            break
        todas_viejas = True
        for c in datos:
            vistas += 1
            if not c.get("launchDate"):
                continue                                    # borrador o programada: todavía no salió
            f = _fecha(c["launchDate"])
            if f is None:
                sin_fecha += 1
                continue
            if f >= desde:
                todas_viejas = False
                if f <= ahora:
                    dentro.append((f, c))
            if vistas >= MAX_CAMPANAS:
                break
        offset += len(datos)
        if todas_viejas or (total is not None and offset >= total) or not pag.get("next"):
            break
    if sin_fecha:
        errores.append(f"Perfit dio {sin_fecha} {'campaña' if sin_fecha == 1 else 'campañas'} con una fecha que no se entiende: no se cuentan.")
    dentro.sort(key=lambda x: x[0], reverse=True)
    mets = [(c, c.get("metrics") if isinstance(c.get("metrics"), dict) else {}) for _, c in dentro]

    def suma(clave):
        vals = [_entero(m.get(clave)) for _, m in mets]
        vals = [v for v in vals if v is not None]
        return sum(vals) if vals else None

    normal = {"enviados": suma("sent"), "aperturas": suma("opened"), "clics": suma("clicked"), "rebotes": suma("bounced"), "bajas": suma("unsubscribed"),
              "tasa_apertura": _promedio_pesado([(_num(m.get("openedP")), _entero(m.get("sent"))) for _, m in mets]),
              "tasa_clics": _promedio_pesado([(_num(m.get("clickedP")), _entero(m.get("sent"))) for _, m in mets])}
    if not dentro and not errores:
        normal.update(enviados=0, aperturas=0, clics=0)     # una suma de cero campañas es un cero verdadero: en el período no se mandó nada
    crudo["campanas_en_periodo"] = len(dentro)
    crudo["campanas"] = [_campana_en_crudo(c, m) for c, m in mets[:MAX_EN_CRUDO]]
    return _salida(normal, crudo, errores)


def insights_campana_mail(fuente_env, campaign_id):
    """Una campaña de Perfit (GET /campaigns/{id}/metrics). `entregados` va en el crudo, junto con el resto."""
    if not hay_clave(fuente_env):
        return _salida({}, {}, [TEXTO_SIN_CLAVE])
    if not campaign_id:
        return _salida({}, {}, ["La pieza no tiene el id de la campaña de Perfit."])
    r, err = _pedir(f"/campaigns/{str(campaign_id).strip()}/metrics", fuente_env)
    crudo = {"campana_id": str(campaign_id)}
    if r is None:
        return _salida({}, crudo, [err])
    d = r.get("data") if isinstance(r, dict) and isinstance(r.get("data"), dict) else {}
    if not d:
        return _salida({}, crudo, ["Perfit no dio los números de la campaña."])
    for k in ("recipients", "delivered", "bounced", "complained", "unsubscribed", "viewsOnline", "ctor", "openedP", "clickedP"):
        if _num(d.get(k)) is not None:
            crudo[k] = _num(d[k])
    return _salida({"enviados": _entero(d.get("sent")), "aperturas": _entero(d.get("opened")), "clics": _entero(d.get("clicked")),
                    "compartidos": _entero(d.get("shared"))}, crudo, [])


def contactos_lista_frase(fuente_env):
    """(12/11, Franco: «el objetivo es ganar gente propia») Los contactos activos de la lista de la Frase del día en Perfit
    (PERFIT_LISTA_FRASE, id o nombre): (n, None), (None, texto de error) o (None, None) si la lista no está configurada.
    Usa perfit.lista_frase (GET /lists/{id}, o GET /lists?q= si es un nombre) y lee `activeContacts`."""
    if not hay_clave(fuente_env):
        return None, TEXTO_SIN_CLAVE
    if not ((fuente_env or {}).get("PERFIT_LISTA_FRASE") or "").strip():
        return None, None
    try:
        lista = perfit.lista_frase(fuente_env)
    except (RuntimeError, urllib.error.URLError, OSError, TimeoutError, ValueError) as e:
        return None, "No pude leer la lista de la Frase del día: " + _traducir(e, fuente_env)
    if not isinstance(lista, dict):
        return None, "Perfit no encontró la lista de la Frase del día."
    n = _entero(lista.get("activeContacts"))
    if n is None:
        return None, "Perfit no dio cuántos contactos tiene la lista de la Frase del día."
    return n, None


def insights_frase_mail(db, publicacion_id):
    """La Frase del día de un día: no es una campaña de Perfit, así que el número sale de nuestro registro (frase_envios, sin HTTP):
    `enviados` = los que la app mandó a Perfit sin error, `errores_envio` (en el crudo) = los que fallaron. No dice cuántos abrieron."""
    crudo = {"fuente": FUENTE_REGISTRO}
    try:
        c = db.resumen_envios(str(publicacion_id), prueba=False) or {}
    except Exception as e:
        return _salida({}, crudo, [f"No pude leer el registro de envíos: {type(e).__name__}"])
    if not c.get("total"):
        return _salida({}, crudo, ["No hay envíos registrados de esta pieza."])
    crudo.update(errores_envio=int(c.get("error") or 0), pendientes=int(c.get("pendiente") or 0))
    return _salida({"enviados": int(c.get("enviado") or 0)}, crudo, [])
