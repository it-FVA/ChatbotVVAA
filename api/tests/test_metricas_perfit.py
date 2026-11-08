"""(8/11, Franco) metricas_perfit.py y el mail dentro de Métricas, con Perfit simulado (monkeypatch sobre perfit._req). Sin red, sin claves.
Lo que NO se pudo confirmar contra Perfit real (formato de launchDate, escala de los porcentajes, automations) queda dicho en el módulo."""
import datetime as dt
import urllib.error

import pytest

import db
import metricas
import metricas_perfit as mp
import perfit
from test_metricas import Cfg, mundo, pub, hace, AHORA, iso   # noqa: F401  (mundo es una fixture: Supabase simulada)

CLAVE = "PERFIT-CLAVE-SECRETA"
ENV = {"PERFIT_API_KEY": CLAVE, "PERFIT_CUENTA": "viviragradecido"}


def camp(i, dias, enviados, abiertos, clics, **m):
    return {"id": i, "name": f"Newsletter {i}", "launchDate": iso(AHORA - dt.timedelta(days=dias)),
            "metrics": dict(sent=enviados, sentP=100, opened=abiertos, openedP=round(abiertos * 100 / enviados, 1), clicked=clics,
                            clickedP=round(clics * 100 / enviados, 1), bounced=3, unsubscribed=2, **m)}


def sim(monkeypatch, respuestas):
    """respuestas: lista de (fragmento de ruta, dict | Exception | callable)."""
    visto = []

    def req(metodo, ruta, datos=None, fuente=None, timeout=60):
        visto.append((metodo, ruta, fuente))
        for clave, resp in respuestas:
            if clave in ruta:
                if isinstance(resp, Exception):
                    raise resp
                return resp(ruta) if callable(resp) else resp
        raise RuntimeError(f"Perfit 404 en {metodo} {ruta}: no simulado")
    monkeypatch.setattr(perfit, "_req", req)
    return visto


@pytest.fixture(autouse=True)
def sin_clave_en_el_entorno(monkeypatch):
    monkeypatch.delenv("PERFIT_API_KEY", raising=False)
    monkeypatch.delenv("PERFIT_CUENTA", raising=False)


# ---------------- cuenta ----------------
def test_cuenta_con_dos_paginas_y_filtro_por_periodo(monkeypatch):
    monkeypatch.setattr(mp, "PAGINA", 2)
    pag1 = {"success": True, "paging": {"offset": 0, "limit": 2, "results": 2, "total": 5, "next": "x"},
            "data": [camp(5, 2, 1000, 400, 50), camp(4, 10, 500, 100, 10)]}
    pag2 = {"success": True, "paging": {"offset": 2, "limit": 2, "results": 2, "total": 5, "next": "y"},
            "data": [camp(3, 20, 500, 250, 25), camp(2, 40, 9999, 9999, 9999)]}       # la de 40 días queda fuera del período
    visto = sim(monkeypatch, [("offset=0", pag1), ("offset=2", pag2), ("offset=4", {"paging": {"total": 5, "next": None}, "data": [camp(1, 60, 1, 1, 1)]})])
    r = mp.insights_cuenta_mail(ENV, 28)
    assert r["errores"] == []
    assert (r["enviados"], r["aperturas"], r["clics"], r["rebotes"], r["bajas"]) == (2000, 750, 85, 9, 6)
    # los porcentajes son los de Perfit pesados por envíos: (40*1000 + 20*500 + 50*500) / 2000
    assert r["tasa_apertura"] == 37.5 and r["tasa_clics"] == 4.25
    assert r["crudo"]["campanas_en_periodo"] == 3
    assert [c["id"] for c in r["crudo"]["campanas"]] == [5, 4, 3]
    assert r["crudo"]["campanas"][0] == {"id": 5, "nombre": "Newsletter 5", "fecha": iso(AHORA - dt.timedelta(days=2)), "enviados": 1000,
                                         "aperturas": 400, "clics": 50, "rebotes": 3, "bajas": 2}
    assert len(visto) == 3 and all(f is ENV for _, _, f in visto)
    assert CLAVE not in str(r)


def test_cuenta_sin_campanas_en_el_periodo_es_cero_verdadero(monkeypatch):
    sim(monkeypatch, [("/campaigns", {"success": True, "paging": {"total": 1, "next": None}, "data": [camp(1, 90, 100, 10, 1)]})])
    r = mp.insights_cuenta_mail(ENV, 28)
    assert r["errores"] == [] and (r["enviados"], r["aperturas"], r["clics"]) == (0, 0, 0) and r["crudo"]["campanas"] == []
    assert "tasa_apertura" not in r


def test_cuenta_ignora_borradores_y_tope_de_20_en_el_crudo(monkeypatch):
    data = [dict(camp(i, 1, 10, 5, 1)) for i in range(1, 31)] + [{"id": 99, "name": "borrador", "launchDate": None, "metrics": {"sent": 5000}}]
    sim(monkeypatch, [("/campaigns", {"paging": {"total": 31, "next": None}, "data": data})])
    r = mp.insights_cuenta_mail(ENV, 28)
    assert r["enviados"] == 300 and len(r["crudo"]["campanas"]) == 20 and r["crudo"]["campanas_en_periodo"] == 30


def test_clave_rechazada_y_sin_respuesta_y_sin_clave(monkeypatch):
    sim(monkeypatch, [("/campaigns", RuntimeError(f"Perfit 401 en GET /campaigns: Bearer {CLAVE} invalid"))])
    r = mp.insights_cuenta_mail(ENV)
    assert r["errores"][0].startswith("Perfit rechazó la clave") and CLAVE not in str(r)
    assert not any(k in r for k in ("enviados", "aperturas", "clics"))
    sim(monkeypatch, [("/campaigns", urllib.error.URLError("timed out"))])
    assert mp.insights_cuenta_mail(ENV)["errores"][0].startswith("Perfit no respondió")
    visto = sim(monkeypatch, [])
    assert mp.insights_cuenta_mail({})["errores"] == ["No hay conexión con Perfit configurada."] and visto == []
    assert mp.insights_campana_mail({}, 7)["errores"] == ["No hay conexión con Perfit configurada."]


# ---------------- campaña por id ----------------
def test_campana_por_id(monkeypatch):
    visto = sim(monkeypatch, [("/campaigns/77/metrics", {"success": True, "data": {
        "recipients": 3000, "sent": 2900, "delivered": 2800, "opened": 900, "openedP": 32.1, "clicked": 120, "bounced": 100, "complained": 1,
        "unsubscribed": 7, "viewsOnline": 15, "ctor": 13.3, "shared": 4}})])
    r = mp.insights_campana_mail(ENV, 77)
    assert visto[0][1] == "/campaigns/77/metrics"
    assert (r["enviados"], r["aperturas"], r["clics"], r["compartidos"]) == (2900, 900, 120, 4)
    assert r["crudo"]["delivered"] == 2800 and r["crudo"]["bounced"] == 100 and r["crudo"]["complained"] == 1 and r["crudo"]["ctor"] == 13.3
    assert "entregados" not in r and r["errores"] == []


def test_campana_inexistente_y_sin_id(monkeypatch):
    sim(monkeypatch, [])
    assert "no encontró" in mp.insights_campana_mail(ENV, 5)["errores"][0]
    assert "id de la campaña" in mp.insights_campana_mail(ENV, None)["errores"][0]


# ---------------- Frase del día ----------------
def test_frase_mail_cuenta_los_envios(monkeypatch):
    class DB:
        def resumen_envios(self, pid, prueba=None):
            assert pid == "pub-9" and prueba is False
            return {"pendiente": 0, "enviado": 3100, "error": 40, "total": 3140}
    r = mp.insights_frase_mail(DB(), "pub-9")
    assert r["enviados"] == 3100 and r["crudo"] == {"fuente": "registro de la app", "errores_envio": 40, "pendientes": 0} and r["errores"] == []

    class Vacia:
        def resumen_envios(self, pid, prueba=None):
            return {"pendiente": 0, "enviado": 0, "error": 0, "total": 0}
    r = mp.insights_frase_mail(Vacia(), "pub-9")
    assert "enviados" not in r and r["errores"]


# ---------------- canales y actualizar ----------------
def _mail(logueado):
    return next(c for c in logueado.get("/admin/metricas/canales").json()["canales"] if c["clave"] == "mail")


def test_canal_mail_sin_clave_no_hay(logueado, mundo):
    m = _mail(logueado)
    assert m["api"] == "no_hay" and m["enlace"] == "https://app.myperfit.com/"


def test_canal_mail_pendiente_disponible_y_error(logueado, mundo, monkeypatch):
    monkeypatch.setenv("PERFIT_API_KEY", CLAVE)
    monkeypatch.setenv("PERFIT_CUENTA", "viviragradecido")
    assert _mail(logueado)["api"] == "pendiente"
    mundo["filas"].append({"id": "p1", "ambito": "canal", "ref": "mail", "canal": "mail", "fuente": "api", "capturado": hace(0),
                           "datos": {"enviados": 2000, "aperturas": 750, "clics": 85, "crudo": {}, "errores": []}})
    m = _mail(logueado)
    assert m["api"] == "disponible" and m["ultima"]["datos"]["enviados"] == 2000
    mundo["filas"].append({"id": "p2", "ambito": "canal", "ref": "mail", "canal": "mail", "fuente": "api", "capturado": hace(-1),
                           "datos": {"crudo": {}, "errores": ["Perfit rechazó la clave: revisá PERFIT_API_KEY y PERFIT_CUENTA."]}})
    m = _mail(logueado)
    assert m["api"] == "error" and "rechazó la clave" in m["nota_api"]


def test_actualizar_suma_el_mail(logueado, mundo, monkeypatch):
    monkeypatch.setenv("PERFIT_API_KEY", CLAVE)
    monkeypatch.setenv("PERFIT_CUENTA", "viviragradecido")
    mundo["pubs"].append(pub(40, "mail", "publicada", 3, frase_del_dia="2026-11-05"))
    mundo["pubs"].append(pub(41, "mail", "simulada", 3, modo="simulado"))                  # simulada: no se cuenta
    mundo["pubs"].append(pub(42, "newsletter", "publicada", 3))                              # newsletter: sin id de campaña, no se lee
    sim(monkeypatch, [("/campaigns", {"paging": {"total": 1, "next": None}, "data": [camp(8, 1, 1000, 300, 30)]})])
    monkeypatch.setattr(db, "resumen_envios", lambda pid, fecha=None, prueba=None: {"pendiente": 0, "enviado": 900, "error": 5, "total": 905})
    import metricas_meta, metricas_youtube
    monkeypatch.setattr(metricas_meta, "insights_cuenta_instagram", lambda cfg, dias=28: {"alcance": 1, "crudo": {}, "errores": []})
    monkeypatch.setattr(metricas_meta, "insights_pieza_instagram", lambda *a, **k: {"alcance": 1, "crudo": {}, "errores": []})
    monkeypatch.setattr(metricas_meta, "insights_pagina_facebook", lambda cfg, dias=28: {"seguidores": 1, "crudo": {}, "errores": []})
    monkeypatch.setattr(metricas_meta, "insights_posteo_facebook", lambda *a: {"vistas": 1, "crudo": {}, "errores": []})
    monkeypatch.setattr(metricas_youtube, "insights_canal_youtube", lambda cfg, dias=28: {"vistas": 1, "crudo": {}, "errores": []})
    r = logueado.post("/admin/metricas/actualizar")
    assert r.status_code == 200 and CLAVE not in r.text
    assert r.json()["mail"] == {"ok": True, "piezas": 1, "error": None}
    assert any(f["ambito"] == "canal" and f["ref"] == "mail" and f["datos"]["enviados"] == 1000 for f in mundo["filas"])
    piezas = [f for f in mundo["filas"] if f["ambito"] == "pieza" and f["canal"] == "mail"]
    assert [f["ref"] for f in piezas] == ["pub-40"] and piezas[0]["datos"]["enviados"] == 900 and piezas[0]["datos"]["crudo"]["errores_envio"] == 5
    assert _mail(logueado)["api"] == "disponible"


def test_actualizar_mail_con_clave_rechazada_y_sin_clave(logueado, mundo, monkeypatch):
    assert logueado.post("/admin/metricas/actualizar").json()["mail"] == {"ok": False, "piezas": 0, "error": "No hay conexión con Perfit configurada."}
    monkeypatch.setenv("PERFIT_API_KEY", CLAVE)
    monkeypatch.setenv("PERFIT_CUENTA", "viviragradecido")
    sim(monkeypatch, [("/campaigns", RuntimeError("Perfit 401 en GET /campaigns: no autorizado"))])
    r = logueado.post("/admin/metricas/actualizar")
    assert r.json()["mail"]["ok"] is False and r.json()["mail"]["error"].startswith("Perfit rechazó la clave") and CLAVE not in r.text
    assert _mail(logueado)["api"] == "error"
