"""(8/11, Franco) metricas_wordpress.py y las rutas de «Conectar con WordPress.com» con WordPress.com simulado (monkeypatch sobre
metricas_wordpress._http). Sin red, sin claves. Lo que NO se pudo confirmar contra WordPress.com real queda dicho en el docstring del módulo."""
import json, time, urllib.parse

import pytest

import metricas_wordpress as mw
from test_metricas import Cfg, mundo, pub, hace   # noqa: F401  (mundo es una fixture: Supabase simulada)

TOKEN = "WPCOM-TOKEN-SECRETO"
CLIENT_SECRET = "WPCOM-CLIENT-SECRET"
CODIGO = "CODIGO-DE-UN-SOLO-USO"


class CfgWP(Cfg):
    wpcom_client_id, wpcom_client_secret = "12345", CLIENT_SECRET


def sim(monkeypatch, respuestas):
    visto = []

    def http(url, method="GET", headers=None, data=None):
        visto.append((url, method, headers, data))
        for clave, resp in respuestas:
            if clave in url:
                return resp(url) if callable(resp) else resp
        return None, {"error": "not_found", "message": "no simulado"}
    monkeypatch.setattr(mw, "_http", http)
    return visto


RESUMEN = ({"date": "2026-11-08", "period": "day", "views": 2400, "visitors": 900, "likes": 31, "reblogs": 0, "comments": 7, "followers": 120}, None)
TOP = ({"summary": {"postviews": [{"id": 11, "title": "Gratitud en casa", "views": 300}, {"id": 12, "title": "Otra", "views": 120}]}}, None)
REFS = ({"summary": {"groups": [{"group": "google", "name": "Google Search", "total": 410}, {"group": "facebook.com", "name": "Facebook", "total": 80}]}}, None)
CLICS = ({"summary": {"groups": [{"name": "instagram.com", "total": 25}]}}, None)
TODO = [("/stats/summary", RESUMEN), ("/stats/top-posts", TOP), ("/stats/referrers", REFS), ("/stats/clicks", CLICS)]


# ---------------- autorización ----------------
def test_url_de_autorizacion():
    u = mw.url_autorizacion(CfgWP(), "https://api.test/admin/metricas/wordpress/callback", "EL-STATE")
    p = urllib.parse.urlparse(u)
    q = urllib.parse.parse_qs(p.query)
    assert f"{p.scheme}://{p.netloc}{p.path}" == "https://public-api.wordpress.com/oauth2/authorize"
    assert q["client_id"] == ["12345"] and q["response_type"] == ["code"] and q["state"] == ["EL-STATE"]
    assert q["redirect_uri"] == ["https://api.test/admin/metricas/wordpress/callback"] and q["blog"] == ["viviragradecidos.org"]
    assert CLIENT_SECRET not in u


def test_canjear_codigo_ok(monkeypatch):
    visto = sim(monkeypatch, [("/oauth2/token", ({"access_token": TOKEN, "blog_id": "777", "blog_url": "https://viviragradecidos.org", "scope": "global", "token_type": "bearer"}, None))])
    tok, err = mw.canjear_codigo(CfgWP(), CODIGO, "https://api.test/cb")
    assert err is None and tok == {"access_token": TOKEN, "blog_id": "777", "blog_url": "https://viviragradecidos.org", "scope": "global"}
    url, metodo, _, data = visto[0]
    assert metodo == "POST" and url == mw.URL_TOKEN
    cuerpo = urllib.parse.parse_qs(data.decode())
    assert cuerpo["grant_type"] == ["authorization_code"] and cuerpo["code"] == [CODIGO] and cuerpo["client_secret"] == [CLIENT_SECRET]


def test_canjear_codigo_con_error(monkeypatch):
    sim(monkeypatch, [("/oauth2/token", (None, {"error": "invalid_grant", "error_description": f"Code {CODIGO} ya usado, secreto {CLIENT_SECRET}"}))])
    tok, err = mw.canjear_codigo(CfgWP(), CODIGO, "https://api.test/cb")
    assert tok is None and err.startswith("WordPress.com no aceptó la autorización")
    assert CODIGO not in err and CLIENT_SECRET not in err
    # sin app registrada o sin código: ni siquiera se llama
    assert mw.canjear_codigo(Cfg(), CODIGO, "x")[1] == mw.TEXTO_SIN_APP
    assert mw.canjear_codigo(CfgWP(), "", "x")[0] is None


# ---------------- lectura ----------------
def test_insights_sitio(monkeypatch):
    visto = sim(monkeypatch, TODO)
    d = mw.insights_sitio(TOKEN, "viviragradecidos.org", 28)
    assert (d["visitas"], d["visitantes"], d["me_gusta"], d["comentarios"]) == (2400, 900, 31, 7) and d["errores"] == []
    assert d["crudo"]["top_posts"] == [{"titulo": "Gratitud en casa", "vistas": 300}, {"titulo": "Otra", "vistas": 120}]
    assert d["crudo"]["referentes"][0] == {"nombre": "Google Search", "vistas": 410} and d["crudo"]["clics"] == [{"nombre": "instagram.com", "vistas": 25}]
    assert d["crudo"]["periodo_dias"] == 28
    assert all(h[2]["Authorization"] == f"Bearer {TOKEN}" for h in visto)
    assert "/sites/viviragradecidos.org/stats/summary?period=day&num=28" in visto[0][0]
    assert TOKEN not in json.dumps(d) and all(TOKEN not in h[0] for h in visto)           # el token va en el encabezado, no en la URL ni en el resultado


def test_insights_sitio_top_sin_resumir_y_secundarios_que_fallan(monkeypatch):
    por_dia = ({"days": {"2026-11-07": {"postviews": [{"id": 1, "title": "A", "views": 5}]},
                         "2026-11-08": {"postviews": [{"id": 1, "title": "A", "views": 4}, {"id": 2, "title": "B", "views": 2}]}}}, None)
    sim(monkeypatch, [("/stats/summary", RESUMEN), ("/stats/top-posts", por_dia), ("/stats/referrers", (None, {"error": "boom", "message": f"falló con {TOKEN}"}))])
    d = mw.insights_sitio(TOKEN, "viviragradecidos.org")
    assert d["crudo"]["top_posts"] == [{"titulo": "A", "vistas": 9}, {"titulo": "B", "vistas": 2}]
    assert "referentes" not in d["crudo"] and d["visitas"] == 2400                          # lo principal igual llega, sin inventar lo que falló
    assert any(e.startswith("WordPress.com no dio de dónde llegan") for e in d["errores"]) and TOKEN not in json.dumps(d)


def test_insights_sitio_token_invalido_y_sin_token(monkeypatch):
    sim(monkeypatch, [("/stats/", (None, {"error": "invalid_token", "message": "The OAuth2 token is invalid."}))])
    d = mw.insights_sitio(TOKEN, "viviragradecidos.org")
    assert d["errores"] == [mw.TEXTO_TOKEN_INVALIDO] and "visitas" not in d and mw.es_error_de_conexion(d["errores"][0])
    assert mw.insights_sitio("", "x")["errores"] == [mw.TEXTO_SIN_TOKEN] and mw.es_error_de_conexion(mw.TEXTO_SIN_TOKEN)


def test_insights_entrada(monkeypatch):
    visto = sim(monkeypatch, [("/stats/post/99", ({"views": 321, "fields": ["views"]}, None))])
    d = mw.insights_entrada(TOKEN, "viviragradecidos.org", 99, 60)
    assert d["visitas"] == 321 and d["errores"] == [] and d["crudo"]["post_id"] == "99" and "/stats/post/99?fields=views" in visto[0][0]
    assert mw.insights_entrada(TOKEN, "x", "")["errores"] == ["La pieza no tiene el id de la entrada de WordPress."]
    sim(monkeypatch, [("/stats/post/", (None, {"error": "unknown_post", "message": "Unknown post"}))])
    e = mw.insights_entrada(TOKEN, "viviragradecidos.org", 5)
    assert "visitas" not in e and e["errores"][0].startswith("WordPress.com no dio las vistas de la entrada")


# ---------------- token guardado ----------------
def test_token_guardado(mundo):
    assert mw.token_guardado() is None
    reg = mw.guardar_token({"access_token": TOKEN, "blog_id": "7", "blog_url": "https://viviragradecidos.org"}, "franco")
    assert "access_token" not in reg and reg["por"] == "franco" and reg["autorizado_en"]
    assert mundo["config"]["wpcom_token"]["access_token"] == TOKEN and mw.token_guardado()["blog_id"] == "7"
    mw.borrar_token("franco")
    assert mw.token_guardado() is None


# ---------------- rutas ----------------
@pytest.fixture
def con_app(mundo, monkeypatch):
    import api.metricas_rutas as mr
    monkeypatch.setattr(mr, "_config", lambda: CfgWP())
    monkeypatch.setenv("WEB_URL", "https://web.test")
    monkeypatch.setenv("API_URL_PUBLICA", "https://api.test")
    return mundo


def _state_de(resp):
    return urllib.parse.parse_qs(urllib.parse.urlparse(resp.headers["location"]).query)["state"][0]


def test_autorizar_redirige_con_state_firmado(logueado, con_app):
    r = logueado.get("/admin/metricas/wordpress/autorizar", follow_redirects=False)
    assert r.status_code == 302
    u = urllib.parse.urlparse(r.headers["location"])
    q = urllib.parse.parse_qs(u.query)
    assert f"{u.scheme}://{u.netloc}{u.path}" == mw.URL_AUTORIZAR and q["client_id"] == ["12345"]
    assert q["redirect_uri"] == ["https://api.test/admin/metricas/wordpress/callback"]
    from api import auth
    assert auth.leer_estado(q["state"][0], "wpcom", 600)["u"] == "franco"
    assert CLIENT_SECRET not in r.headers["location"]


def test_autorizar_sin_app_vuelve_a_la_web_con_el_motivo(logueado, mundo, monkeypatch):
    monkeypatch.setenv("WEB_URL", "https://web.test")
    r = logueado.get("/admin/metricas/wordpress/autorizar", follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"].startswith("https://web.test/aprobacion/metricas?wordpress=error&motivo=")


def test_autorizar_solo_admins(cliente, con_app):
    assert cliente.get("/admin/metricas/wordpress/autorizar", follow_redirects=False).status_code == 401
    assert cliente.delete("/admin/metricas/wordpress").status_code == 401


def test_callback_state_invalido(cliente, con_app, monkeypatch):
    llamado = []
    monkeypatch.setattr(mw, "canjear_codigo", lambda *a: llamado.append(a) or (None, "no debería"))
    for state in ("", "basura", "x.y.z"):
        r = cliente.get("/admin/metricas/wordpress/callback", params={"code": CODIGO, "state": state}, follow_redirects=False)
        assert r.status_code == 400
    from api import auth
    otro_proposito = auth.firmar_estado({"u": "franco"}, "otra-cosa")           # firmado por nosotros, pero para otro uso
    r = cliente.get("/admin/metricas/wordpress/callback", params={"code": CODIGO, "state": otro_proposito}, follow_redirects=False)
    assert r.status_code == 400
    assert not llamado and "wpcom_token" not in con_app["config"]


def test_callback_state_vencido(cliente, con_app, monkeypatch):
    from api import auth
    s = auth.firmar_estado({"u": "franco"}, "wpcom")
    real = time.time
    monkeypatch.setattr(time, "time", lambda: real() + 11 * 60)
    r = cliente.get("/admin/metricas/wordpress/callback", params={"code": CODIGO, "state": s}, follow_redirects=False)
    assert r.status_code == 400


def test_callback_ok_guarda_y_redirige(logueado, con_app, monkeypatch):
    state = _state_de(logueado.get("/admin/metricas/wordpress/autorizar", follow_redirects=False))
    visto = sim(monkeypatch, [("/oauth2/token", ({"access_token": TOKEN, "blog_id": "777", "blog_url": "https://viviragradecidos.org", "scope": "global"}, None))])
    logueado.cookies.clear()                                # el callback no depende de la cookie: lo autoriza el state
    r = logueado.get("/admin/metricas/wordpress/callback", params={"code": CODIGO, "state": state}, follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "https://web.test/aprobacion/metricas?wordpress=ok"
    g = con_app["config"]["wpcom_token"]
    assert g["access_token"] == TOKEN and g["blog_id"] == "777" and g["por"] == "franco"
    assert urllib.parse.parse_qs(visto[0][3].decode())["redirect_uri"] == ["https://api.test/admin/metricas/wordpress/callback"]
    quien, accion, usuario, detalle = con_app["cambios"][-1]
    assert (quien, accion, usuario) == ("franco", "config", "wpcom_token") and TOKEN not in json.dumps(detalle)


def test_callback_con_error_de_wordpress(logueado, con_app, monkeypatch):
    state = _state_de(logueado.get("/admin/metricas/wordpress/autorizar", follow_redirects=False))
    r = logueado.get("/admin/metricas/wordpress/callback", params={"error": "access_denied", "state": state}, follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"].startswith("https://web.test/aprobacion/metricas?wordpress=error&motivo=")
    sim(monkeypatch, [("/oauth2/token", (None, {"error": "invalid_grant", "error_description": "malo"}))])
    r = logueado.get("/admin/metricas/wordpress/callback", params={"code": CODIGO, "state": state}, follow_redirects=False)
    assert "wordpress=error" in r.headers["location"] and "wpcom_token" not in con_app["config"] and CODIGO not in r.headers["location"]


def test_desconectar(logueado, con_app):
    con_app["config"]["wpcom_token"] = {"access_token": TOKEN, "blog_id": "7"}
    assert logueado.delete("/admin/metricas/wordpress").json() == {"ok": True}
    assert mw.token_guardado() is None and con_app["cambios"][-1][1:3] == ("config", "wpcom_token")


# ---------------- canales y captura ----------------
def _sitio(logueado):
    return {c["clave"]: c for c in logueado.get("/admin/metricas/canales").json()["canales"]}["sitio"]


def test_canal_sitio_estados(logueado, con_app, monkeypatch):
    import api.metricas_rutas as mr
    s = _sitio(logueado)                                     # con app y sin token
    assert s["api"] == "pendiente" and s["nota_api"] == "Falta conectar con WordPress.com (un clic)" and s["conectado"] is False
    assert s["conectar_url"] == "/admin/metricas/wordpress/autorizar"
    con_app["config"]["wpcom_token"] = {"access_token": TOKEN, "blog_id": "7"}      # conectado, todavía sin captura
    s = _sitio(logueado)
    assert s["api"] == "pendiente" and s["conectado"] is True and "Actualizar" in s["nota_api"]
    con_app["filas"].append({"id": "w1", "ambito": "canal", "ref": "sitio", "canal": "sitio", "fuente": "api", "capturado": hace(0, 1),
                             "datos": {"visitas": 5, "crudo": {}, "errores": []}})
    s = _sitio(logueado)
    assert s["api"] == "disponible" and s["conectado"] is True and s["ultima"]["datos"]["visitas"] == 5
    con_app["filas"].append({"id": "w2", "ambito": "canal", "ref": "sitio", "canal": "sitio", "fuente": "api", "capturado": hace(0),
                             "datos": {"crudo": {}, "errores": [mw.TEXTO_TOKEN_INVALIDO]}})
    s = _sitio(logueado)
    assert s["api"] == "error" and s["nota_api"] == mw.TEXTO_TOKEN_INVALIDO and s["conectar_url"]
    monkeypatch.setattr(mr, "_config", lambda: Cfg())                               # sin app y sin token: como hasta hoy
    con_app["config"].clear()
    s = _sitio(logueado)
    assert s["api"] == "no_hay" and s["conectar_url"] is None and s["conectado"] is False and "WordPress.com pide autorizar" in s["nota_api"]


def test_actualizar_suma_el_sitio(logueado, con_app, monkeypatch):
    con_app["config"]["wpcom_token"] = {"access_token": TOKEN, "blog_id": "7"}
    con_app["pubs"].append(pub(30, "wordpress", "publicada", 3, id=99, link="https://viviragradecidos.org/x"))     # entrada real publicada
    con_app["pubs"].append(pub(31, "wordpress", "borrador", 3, id=98))                                              # borrador: no se pide
    pedidos = []

    def entrada(token, site, post_id, dias=28):
        pedidos.append((token, site, post_id))
        return {"visitas": 321, "crudo": {}, "errores": []}
    monkeypatch.setattr(mw, "insights_sitio", lambda token, site, dias=28: {"visitas": 2400, "visitantes": 900, "crudo": {}, "errores": []})
    monkeypatch.setattr(mw, "insights_entrada", entrada)
    import metricas_meta, metricas_youtube
    monkeypatch.setattr(metricas_meta, "insights_cuenta_instagram", lambda cfg, dias=28: {"alcance": 1, "crudo": {}, "errores": []})
    monkeypatch.setattr(metricas_meta, "insights_pieza_instagram", lambda *a, **k: {"alcance": 1, "crudo": {}, "errores": []})
    monkeypatch.setattr(metricas_meta, "insights_pagina_facebook", lambda cfg, dias=28: {"seguidores": 1, "crudo": {}, "errores": []})
    monkeypatch.setattr(metricas_meta, "insights_posteo_facebook", lambda *a: {"vistas": 1, "crudo": {}, "errores": []})
    monkeypatch.setattr(metricas_youtube, "insights_canal_youtube", lambda cfg, dias=28: {"vistas": 1, "crudo": {}, "errores": []})
    d = logueado.post("/admin/metricas/actualizar").json()
    assert d["sitio"] == {"ok": True, "piezas": 1, "error": None}
    assert pedidos == [(TOKEN, "viviragradecidos.org", "99")]
    assert any(f["ambito"] == "canal" and f["ref"] == "sitio" and f["fuente"] == "api" for f in con_app["filas"])
    assert any(f["ambito"] == "pieza" and f["ref"] == "pub-30" and f["datos"]["visitas"] == 321 for f in con_app["filas"])
    assert _sitio(logueado)["api"] == "disponible"


def test_actualizar_sitio_sin_conexion_y_con_token_vencido(logueado, con_app, monkeypatch):
    assert logueado.post("/admin/metricas/actualizar").json()["sitio"]["error"] == mw.TEXTO_SIN_TOKEN
    con_app["config"]["wpcom_token"] = {"access_token": TOKEN, "blog_id": "7"}
    sim(monkeypatch, [("/stats/", (None, {"error": "invalid_token", "message": "The OAuth2 token is invalid."}))])
    d = logueado.post("/admin/metricas/actualizar")
    assert d.status_code == 200 and d.json()["sitio"] == {"ok": False, "piezas": 0, "error": mw.TEXTO_TOKEN_INVALIDO}
    assert TOKEN not in d.text
    assert _sitio(logueado)["api"] == "error"
