"""Pruebas de api/salud.py sin red: _get (HTTP), la llamada a OpenAI y db.* se reemplazan con mocks."""
import json, time, datetime as dt

import pytest

import db
import api.salud as salud

AHORA = dt.datetime.now(dt.timezone.utc)


def _iso(d):
    return d.isoformat(timespec="seconds")


def _respuestas(mapa):
    """Un _get falso: busca la primera clave contenida en la URL; devuelve (estado, cuerpo, ms)."""
    llamadas = []

    def _get(url, headers=None, timeout=8, method="GET", data=None):
        llamadas.append(url)
        for clave, (st, cuerpo) in mapa.items():
            if clave in url:
                return st, cuerpo if isinstance(cuerpo, str) else json.dumps(cuerpo), 12
        return 0, "URLError: sin mock para " + url, 5
    _get.llamadas = llamadas
    return _get


def _corrida(hace_min, conclusion="success", status="completed"):
    return {"workflow_runs": [{"status": status, "conclusion": conclusion, "event": "schedule", "html_url": "https://github.com/x",
                               "run_started_at": _iso(AHORA - dt.timedelta(minutes=hace_min)), "updated_at": _iso(AHORA)}]}


@pytest.fixture
def mundo(monkeypatch):
    """Todo sano: Supabase, OpenAI, WordPress, Meta (IG vence en 30 días; FB sin vencimiento), Google, GitHub, web."""
    salud._CACHE.clear()
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "k")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("WP_SITE", "viviragradecidos.org")
    monkeypatch.setenv("WP_USER", "admin")
    monkeypatch.setenv("WP_APP_PASSWORD", "abcd")
    monkeypatch.setenv("META_IG_TOKEN", "IGABtoken")
    monkeypatch.setenv("META_IG_TOKEN_VENCE", (AHORA + dt.timedelta(days=30)).date().isoformat())
    monkeypatch.setenv("META_FB_PAGE_TOKEN", "FBTOKEN")
    monkeypatch.setenv("DRIVE_TOKEN_JSON", json.dumps({"client_id": "c", "client_secret": "s", "refresh_token": "r", "scopes": ["drive.readonly"]}))
    monkeypatch.setenv("YOUTUBE_TOKEN_JSON", json.dumps({"client_id": "c", "client_secret": "s", "refresh_token": "r2"}))
    monkeypatch.setenv("CORS_ORIGENES", "https://chatbot-vvaa.vercel.app")
    monkeypatch.delenv("SALUD_TOKEN", raising=False)
    vence_ig = int((AHORA + dt.timedelta(days=30)).timestamp())
    mapa = {
        "viviragradecidos.org/wp-json/wp/v2/users/me": (200, {"slug": "admin", "roles": ["administrator"]}),
        "viviragradecidos.org/wp-json/": (200, {"name": "Vivir Agradecidos"}),
        "graph.instagram.com/v21.0/me": (200, {"id": "396", "username": "vivir.agradecidos"}),
        "input_token=EAAIGTOKEN": (200, {"data": {"is_valid": True, "expires_at": vence_ig, "type": "USER", "scopes": ["instagram_basic"]}}),
        "input_token=FBTOKEN": (200, {"data": {"is_valid": True, "expires_at": 0, "type": "PAGE", "scopes": ["pages_manage_posts"]}}),
        "oauth2.googleapis.com/token": (200, {"access_token": "ya29", "scope": "drive"}),
        "workflows/cola.yml/runs": (200, _corrida(10)),
        "workflows/recortar_pendientes.yml/runs": (200, _corrida(20)),
        "chatbot-vvaa.vercel.app": (200, "<html>"),
    }
    monkeypatch.setattr(salud, "_get", _respuestas(mapa))
    monkeypatch.setattr(salud, "_openai_modelo", lambda modelo: {"id": modelo})
    historial, guardadas = [], []
    config = {"frase_activa": True, "frase_imagen": "https://foto.jpg"}
    hoy = salud._hoy_argentina()
    frases = {hoy.isoformat(): {"fecha": hoy.isoformat(), "texto": "La gratitud es la llave", "autor": "Br. David", "estado": "programada"},
              (hoy + dt.timedelta(days=1)).isoformat(): {"fecha": (hoy + dt.timedelta(days=1)).isoformat(), "texto": "Mañana", "autor": "X", "estado": "programada"}}
    monkeypatch.setattr(db, "_req", lambda method, params="", body=None, tabla="conversaciones": [])
    monkeypatch.setattr(db, "listar_pendientes", lambda vencidas=False, limite=50: [])
    monkeypatch.setattr(db, "clips_pedidos_antes", lambda iso: [])
    monkeypatch.setattr(db, "obtener_config", lambda clave, defecto=None: config.get(clave, defecto))
    monkeypatch.setattr(db, "frase_del_dia", lambda fecha: frases.get(str(fecha)))
    monkeypatch.setattr(db, "listar_salud", lambda limite=100: list(historial))
    monkeypatch.setattr(db, "guardar_salud", lambda estado, detalle: guardadas.append({"estado": estado, "detalle": detalle}) or [])
    return {"mapa": mapa, "config": config, "frases": frases, "historial": historial, "guardadas": guardadas}


def _estados(informe):
    return {c["nombre"]: c["estado"] for c in informe["chequeos"]}


def test_salud_compatible(cliente):
    d = cliente.get("/salud").json()
    for k in ("ok", "corpus_fragmentos", "corpus_cargado", "supabase", "modelo", "login_google", "google_client_id", "dominio_fva"):
        assert k in d
    assert d["version"] and d["arranque"] and d["vectores"] == "local"


def test_servicios_solo_admin(cliente, mundo, monkeypatch):
    assert cliente.get("/salud/servicios").status_code == 401
    assert cliente.get("/salud/historial").status_code == 401
    cliente.post("/login", json={"usuario": "lizzie", "clave": "clave-lizzie"})      # no es admin
    assert cliente.get("/salud/servicios").status_code == 403
    # token de monitoreo: sin SALUD_TOKEN configurado no vale; con él, sí (query o cabecera)
    assert cliente.get("/salud/servicios?token=abc").status_code == 403
    monkeypatch.setenv("SALUD_TOKEN", "abc")
    assert cliente.get("/salud/servicios?token=otro&guardar=0").status_code == 403
    r = cliente.get("/salud/servicios?token=abc&guardar=0")
    assert r.status_code == 200 and r.json()["consultado_por"] == "monitor"
    assert cliente.get("/salud/servicios?guardar=0", headers={"X-Salud-Token": "abc"}).status_code == 200


def test_todo_sano(logueado, mundo):
    r = logueado.get("/salud/servicios")
    assert r.status_code == 200, r.text
    d = r.json()
    est = _estados(d)
    assert len(d["chequeos"]) == len(salud.CHEQUEOS)
    # el corpus no está cargado en los tests: la fila api avisa; todo lo demás ok
    assert est.pop("api") == "aviso"
    assert set(est.values()) == {"ok"}, est
    assert d["estado"] == "aviso" and d["consultado_por"] == "franco"
    ig = next(c for c in d["chequeos"] if c["nombre"] == "instagram")
    assert "@vivir.agradecidos" in ig["detalle"] and "Vence el" in ig["detalle"] and ig["vence"]
    fb = next(c for c in d["chequeos"] if c["nombre"] == "facebook")
    assert "sin vencimiento" in fb["detalle"]
    fr = next(c for c in d["chequeos"] if c["nombre"] == "frase_del_dia")
    assert "La gratitud es la llave" in fr["detalle"] and fr["hoy"]["con_foto"] is False
    mem = next(c for c in d["chequeos"] if c["nombre"] == "memoria")
    assert mem["rss_mb"] > 0 and mem["limite_mb"] == 512
    # se guardó una fila resumida en salud_historial
    assert len(mundo["guardadas"]) == 1
    g = mundo["guardadas"][0]
    assert g["estado"] == "aviso" and {c["nombre"] for c in g["detalle"]["chequeos"]} == set(est) | {"api"}


def test_meta_por_vencer_y_vencido(mundo, monkeypatch):
    """Un token de Facebook Login (EAA…) en META_IG_TOKEN va por debug_token, como el de la página."""
    monkeypatch.setenv("META_IG_TOKEN", "EAAIGTOKEN")
    salud._CACHE.clear()
    assert salud._chequear_instagram()["estado"] == "ok"
    pronto = int((AHORA + dt.timedelta(days=5)).timestamp())
    mundo["mapa"]["input_token=EAAIGTOKEN"] = (200, {"data": {"is_valid": True, "expires_at": pronto, "type": "USER", "scopes": []}})
    salud._CACHE.clear()
    r = salud._chequear_instagram()
    assert r["estado"] == "aviso" and "Vence en" in r["que_hacer"]
    mundo["mapa"]["input_token=EAAIGTOKEN"] = (200, {"data": {"is_valid": False}})
    salud._CACHE.clear()
    assert salud._chequear_instagram()["estado"] == "error"
    mundo["mapa"]["input_token=EAAIGTOKEN"] = (400, {"error": {"message": "Invalid OAuth access token."}})
    salud._CACHE.clear()
    r = salud._chequear_instagram()
    assert r["estado"] == "error" and "Invalid OAuth" in r["detalle"]
    monkeypatch.delenv("META_IG_TOKEN")
    assert salud._chequear_instagram()["estado"] == "aviso"


def test_instagram_login(mundo, monkeypatch):
    """Token IG… (Instagram Login, el de producción): /me para la validez, META_IG_TOKEN_VENCE para el vencimiento."""
    salud._CACHE.clear()
    assert salud._chequear_instagram()["estado"] == "ok"
    monkeypatch.setenv("META_IG_TOKEN_VENCE", (AHORA + dt.timedelta(days=3)).date().isoformat())
    salud._CACHE.clear()
    r = salud._chequear_instagram()
    assert r["estado"] == "aviso" and "Vence en" in r["que_hacer"]
    monkeypatch.setenv("META_IG_TOKEN_VENCE", "2026-01-01")
    salud._CACHE.clear()
    assert salud._chequear_instagram()["estado"] == "error"
    monkeypatch.delenv("META_IG_TOKEN_VENCE")
    salud._CACHE.clear()
    r = salud._chequear_instagram()
    assert r["estado"] == "aviso" and "META_IG_TOKEN_VENCE" in r["que_hacer"]
    mundo["mapa"]["graph.instagram.com/v21.0/me"] = (400, {"error": {"message": "Invalid OAuth access token - Cannot parse access token", "type": "OAuthException"}})
    salud._CACHE.clear()
    r = salud._chequear_instagram()
    assert r["estado"] == "error" and "Cannot parse" in r["detalle"]


def test_cache_openai_y_meta(mundo):
    salud._CACHE.clear()
    a = salud._chequear_openai()
    b = salud._chequear_openai()
    assert a["estado"] == "ok" and b.get("cacheado") is True
    salud._chequear_facebook()
    n = len(salud._get.llamadas)
    assert salud._chequear_facebook()["cacheado"] is True and len(salud._get.llamadas) == n


def test_openai_falla(mundo, monkeypatch):
    salud._CACHE.clear()

    def _rompe(modelo):
        raise RuntimeError("Error code: 401 - Incorrect API key provided")
    monkeypatch.setattr(salud, "_openai_modelo", _rompe)
    r = salud._chequear_openai()
    assert r["estado"] == "error" and "clave" in r["que_hacer"]
    monkeypatch.delenv("OPENAI_API_KEY")
    assert "Falta" in salud._chequear_openai()["detalle"]


def test_google_rechaza(mundo):
    mundo["mapa"]["oauth2.googleapis.com/token"] = (400, {"error": "invalid_grant", "error_description": "Token has been expired or revoked."})
    salud._CACHE.clear()
    r = salud._chequear_drive()
    assert r["estado"] == "error" and "autorizar_drive.py" in r["que_hacer"] and "invalid_grant" in r["detalle"]
    r = salud._chequear_youtube()
    assert r["estado"] == "error" and "autorizar_youtube.py" in r["que_hacer"]


def test_wordpress(mundo, monkeypatch):
    assert salud._chequear_wordpress()["estado"] == "ok"
    mundo["mapa"]["viviragradecidos.org/wp-json/wp/v2/users/me"] = (401, {"code": "rest_not_logged_in"})
    r = salud._chequear_wordpress()
    assert r["estado"] == "error" and "Application Passwords" in r["que_hacer"]
    monkeypatch.delenv("WP_APP_PASSWORD")
    assert salud._chequear_wordpress()["estado"] == "aviso"
    mundo["mapa"]["viviragradecidos.org/wp-json/"] = (503, "mantenimiento")
    assert salud._chequear_wordpress()["estado"] == "error"


def test_cola_vieja_fallida_y_piezas(mundo, monkeypatch):
    mundo["mapa"]["workflows/cola.yml/runs"] = (200, _corrida(90))
    salud._CACHE.clear()
    r = salud._chequear_cola()
    assert r["estado"] == "aviso" and "hace 90 min" in r["detalle"] and r["pendientes_vencidas"] == 0
    mundo["mapa"]["workflows/cola.yml/runs"] = (200, _corrida(5, conclusion="failure"))
    salud._CACHE.clear()
    r = salud._chequear_cola()
    assert r["estado"] == "aviso" and "failure" in r["detalle"] and "log" in r["que_hacer"]
    mundo["mapa"]["workflows/cola.yml/runs"] = (200, _corrida(3, status="in_progress", conclusion=None))
    salud._CACHE.clear()
    assert salud._chequear_cola()["estado"] == "ok"
    # corrida reciente y OK pero una pieza pendiente que debía salir hace 2 h
    mundo["mapa"]["workflows/cola.yml/runs"] = (200, _corrida(4))
    salud._CACHE.clear()
    monkeypatch.setattr(db, "listar_pendientes", lambda vencidas=False, limite=50: [{"id": "p1", "fecha_programada": _iso(AHORA - dt.timedelta(hours=2))},
                                                                                  {"id": "p2", "fecha_programada": _iso(AHORA - dt.timedelta(minutes=5))}])
    r = salud._chequear_cola()
    assert r["estado"] == "aviso" and r["pendientes_vencidas"] == 1 and "120 min" in r["detalle"]
    # GitHub sin acceso (límite de 60/h): aviso, no error
    mundo["mapa"]["workflows/cola.yml/runs"] = (403, "rate limit exceeded")
    salud._CACHE.clear()
    assert "No pude leer GitHub" in salud._chequear_cola()["detalle"]


def test_recortes_pedidos_viejos(mundo, monkeypatch):
    monkeypatch.setattr(db, "clips_pedidos_antes", lambda iso: [{"id": "c1", "titulo": "Charla sobre la gratitud", "video_id": "abc"}])
    r = salud._chequear_recortes()
    assert r["estado"] == "aviso" and r["clips_pedidos_viejos"] == 1 and "Charla sobre la gratitud" in r["detalle"]


def test_frase_del_dia(mundo):
    mundo["config"]["frase_activa"] = False
    assert salud._chequear_frase()["estado"] == "ok"
    mundo["config"]["frase_activa"] = True
    mundo["config"]["frase_imagen"] = ""
    r = salud._chequear_frase()
    assert r["estado"] == "aviso" and "foto por defecto" in r["detalle"]
    mundo["config"]["frase_imagen"] = "https://foto.jpg"
    mundo["frases"].clear()
    r = salud._chequear_frase()
    assert r["estado"] == "aviso" and "hoy no tiene frase" in r["detalle"] and "mañana no tiene frase" in r["detalle"]


def test_web_y_memoria(mundo, monkeypatch):
    assert salud._chequear_web()["estado"] == "ok"
    mundo["mapa"]["chatbot-vvaa.vercel.app"] = (500, "boom")
    assert salud._chequear_web()["estado"] == "error"
    monkeypatch.setenv("CORS_ORIGENES", "")
    assert salud._chequear_web()["estado"] == "aviso"
    monkeypatch.setenv("MEMORIA_LIMITE_MB", "1")
    assert salud._chequear_memoria()["estado"] == "error"
    monkeypatch.setattr(salud, "_rss_mb", lambda: 420.0)
    monkeypatch.setenv("MEMORIA_LIMITE_MB", "512")
    r = salud._chequear_memoria()
    assert r["estado"] == "aviso" and r["porcentaje"] == 82


def test_supabase_sin_credenciales(mundo, monkeypatch):
    monkeypatch.delenv("SUPABASE_URL")
    assert salud._chequear_supabase()["estado"] == "error"


def test_chequeo_que_se_cuelga(mundo, monkeypatch):
    def _lento():
        raise TimeoutError("se colgó")
    monkeypatch.setattr(salud, "CHEQUEOS", [_lento, salud._chequear_memoria])
    inf = salud.correr()
    assert inf["estado"] == "error" and inf["chequeos"][0]["estado"] == "error" and inf["chequeos"][0]["nombre"] == "_lento"


def test_desde_cuando(mundo):
    """El «desde» es la corrida más vieja de la racha actual con el mismo estado."""
    ahora = salud._iso(AHORA)
    informe = {"creado": ahora, "chequeos": [{"nombre": "openai", "estado": "error"}, {"nombre": "web", "estado": "ok"}, {"nombre": "drive", "estado": "aviso"}]}
    historial = [
        {"creado": "2026-10-22T09:00:00+00:00", "detalle": {"chequeos": [{"nombre": "openai", "estado": "error"}, {"nombre": "drive", "estado": "ok"}]}},
        {"creado": "2026-10-22T08:00:00+00:00", "detalle": {"chequeos": [{"nombre": "openai", "estado": "error"}]}},
        {"creado": "2026-10-22T07:00:00+00:00", "detalle": {"chequeos": [{"nombre": "openai", "estado": "ok"}]}},
        {"creado": "2026-10-22T06:00:00+00:00", "detalle": {"chequeos": [{"nombre": "openai", "estado": "error"}]}},
    ]
    salud.desde_cuando(informe, historial)
    assert informe["chequeos"][0]["desde"] == "2026-10-22T08:00:00+00:00"
    assert "desde" not in informe["chequeos"][1]
    assert informe["chequeos"][2]["desde"] == ahora          # drive estaba ok en la corrida anterior: empieza ahora


def test_historial_endpoint(logueado, mundo):
    mundo["historial"].append({"id": 1, "creado": "2026-10-22T05:00:00+00:00", "estado": "ok", "detalle": {}})
    r = logueado.get("/salud/historial?limite=5")
    assert r.status_code == 200 and r.json()[0]["id"] == 1
    r = logueado.get("/salud/servicios").json()
    api = next(c for c in r["chequeos"] if c["nombre"] == "api")
    assert api["estado"] == "aviso" and api["desde"] == r["creado"]       # la fila previa (detalle {}) no tenía 'api' en aviso: la racha empieza ahora
