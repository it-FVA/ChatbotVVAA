"""
vigilar_api.py — ¿Está viva la API? Avisa por Slack cuando se cae y cuando vuelve (17/11, pedido de Franco).

El 17/11 a las 12:00, en plena reunión, la app no conectaba con la API durante unos cinco minutos (la API se reinició a las
12:04) y nadie tenía forma de saberlo salvo mirando la pantalla. Esto corre en GitHub Actions (`vigilar_api.yml`, cada
10 min, y al final de cada corrida de la cola): hace GET /salud con tope de tiempo; si no responde «ok», lo reintenta una
vez más, y si sigue sin responder, la da por caída.

Para avisar una sola vez por caída (y no cada 10 minutos) guarda el estado en salud_historial: una fila estado='caida'
cuando se cae y una estado='vuelta' cuando vuelve. La última de esas filas es el estado anterior; solo se avisa cuando cambia.

Variables: API_URL (default https://fva-api.onrender.com), SLACK_WEBHOOK_URL, SUPABASE_URL + SUPABASE_KEY_COLA (rol «cola»,
con grant sobre salud_historial: migración 20261117_1300_salud_historial_grant_cola). Sin Supabase avisa igual, en cada corrida.
Uso: python vigilar_api.py           (sale con código 1 si la API está caída, así la corrida queda en rojo en GitHub)
"""
import json, os, sys, time, datetime as dt, urllib.request, urllib.error

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # consola de Windows
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
API_URL = (os.environ.get("API_URL") or "https://fva-api.onrender.com").rstrip("/")
TIMEOUT = int(os.environ.get("VIGIA_TIMEOUT") or 25)
ZONA = dt.timezone(dt.timedelta(hours=-3))


def _hora(iso=None):
    d = dt.datetime.fromisoformat(iso.replace("Z", "+00:00")) if iso else dt.datetime.now(dt.timezone.utc)
    return d.astimezone(ZONA).strftime("%d/%m %H:%M")


def probar(url=API_URL, intentos=2):
    """(True, detalle) si /salud responde ok; (False, qué pasó) si no. Entre intentos espera 20 s."""
    detalle = ""
    for i in range(intentos):
        t = time.time()
        try:
            with urllib.request.urlopen(urllib.request.Request(url + "/salud", headers={"User-Agent": "fva-vigia/1.0"}), timeout=TIMEOUT) as r:
                d = json.loads(r.read().decode("utf-8"))
            ms = int((time.time() - t) * 1000)
            if d.get("ok"):
                return True, f"responde en {ms} ms; corpus {d.get('corpus_fragmentos')}; arrancó {_hora(d['arranque']) if d.get('arranque') else '?'}"
            detalle = f"respondió sin ok: {str(d)[:150]}"
        except urllib.error.HTTPError as e:
            detalle = f"HTTP {e.code}"
        except Exception as e:  # noqa: BLE001
            detalle = f"{type(e).__name__}: {str(e)[:120] or 'sin respuesta'} ({int((time.time() - t) * 1000)} ms)"
        if i + 1 < intentos:
            time.sleep(20)
    return False, detalle


def estado_anterior(db):
    """La última fila caida/vuelta de salud_historial: ('caida'|'vuelta', creado) o (None, None)."""
    filas = db._req("GET", "?estado=in.(caida,vuelta)&select=estado,creado&order=creado.desc&limit=1", tabla="salud_historial") or []
    return (filas[0]["estado"], filas[0]["creado"]) if filas else (None, None)


def main():
    from procesar_cola import _cargar_config_local
    _cargar_config_local()
    import avisos
    viva, detalle = probar()
    print(("OK   " if viva else "CAÍDA") + f" {API_URL}: {detalle}")
    try:
        import db
        con_db = db.disponible()
    except Exception:  # noqa: BLE001
        con_db = False
    anterior, desde = (None, None)
    if con_db:
        try:
            anterior, desde = estado_anterior(db)
        except Exception as e:  # noqa: BLE001
            print(f"No pude leer salud_historial: {str(e)[:150]}")
            con_db = False
    web = avisos.web_url()
    if not viva and anterior != "caida":
        texto = (f"La API no responde desde las {_hora()} ({detalle}). La plataforma {web} muestra «No se pudo conectar con la API» "
                 f"hasta que vuelva.\nQué mirar: https://dashboard.render.com → fva-api → Events y Logs. Aviso de nuevo cuando vuelva.")
        _avisar(avisos, ":red_circle: Se cayó la API de la plataforma", texto)
        _guardar(db if con_db else None, "caida", {"detalle": detalle, "url": API_URL})
    elif viva and anterior == "caida":
        cuanto = ""
        if desde:
            mins = int((dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(desde.replace("Z", "+00:00"))).total_seconds() // 60)
            cuanto = f" Estuvo caída unos {mins} min (desde las {_hora(desde)})."
        _avisar(avisos, ":large_green_circle: Volvió la API de la plataforma", f"Responde de nuevo a las {_hora()} ({detalle}).{cuanto}")
        _guardar(db if con_db else None, "vuelta", {"detalle": detalle, "url": API_URL})
    elif not viva:
        print(f"Sigue caída (avisado a las {_hora(desde) if desde else '?'}); no repito el aviso.")
    return 0 if viva else 1


def _avisar(avisos, asunto, texto):
    if not os.environ.get("SLACK_WEBHOOK_URL"):
        print(f"(sin SLACK_WEBHOOK_URL) {asunto}: {texto}")
        return
    try:
        print("Slack:", avisos._slack(f"*{asunto}*\n{texto}"))
    except Exception as e:  # noqa: BLE001
        print(f"Slack falló: {str(e)[:150]}")


def _guardar(db, estado, detalle):
    if db is None:
        return
    try:
        db.guardar_salud(estado, detalle)
    except Exception as e:  # noqa: BLE001
        print(f"No pude guardar en salud_historial: {str(e)[:150]}")


if __name__ == "__main__":
    sys.exit(main())
