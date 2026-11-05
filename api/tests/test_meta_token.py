"""(5/11) meta_token.py: el token de Instagram vive en config.meta_ig_token y se renueva solo. Sin red: HTTP y db con monkeypatch."""
import datetime as dt

import pytest

import db
import meta_token

AHORA = dt.datetime.now(dt.timezone.utc)


def _iso(d):
    return d.isoformat(timespec="seconds")


@pytest.fixture
def mundo(monkeypatch):
    meta_token._cache.update(t=0.0, v=None)
    monkeypatch.setenv("META_IG_TOKEN", "IGABsemilla")
    monkeypatch.delenv("META_IG_TOKEN_VENCE", raising=False)
    est = {"config": {}, "guardados": [], "http": []}
    monkeypatch.setattr(db, "disponible", lambda: True)
    monkeypatch.setattr(db, "obtener_config", lambda clave, defecto=None: est["config"].get(clave, defecto))
    monkeypatch.setattr(db, "guardar_config", lambda clave, valor, usuario=None: est["guardados"].append((clave, valor)) or est["config"].__setitem__(clave, valor))

    def _http(token):
        est["http"].append(token)
        return {"access_token": "IGABnuevo", "token_type": "bearer", "expires_in": 5183944}
    monkeypatch.setattr(meta_token, "_http_refresh", _http)
    return est


def test_lee_de_config(mundo):
    mundo["config"]["meta_ig_token"] = {"token": "IGABguardado", "vence": _iso(AHORA + dt.timedelta(days=50)), "renovado": _iso(AHORA)}
    assert meta_token.token_ig_vigente(usar_cache=False) == "IGABguardado"
    assert meta_token.info_token()["origen"] == "config"


def test_cae_al_entorno(mundo, monkeypatch):
    assert meta_token.token_ig_vigente(usar_cache=False) == "IGABsemilla"
    assert meta_token.info_token()["origen"] == "entorno"
    monkeypatch.setattr(db, "disponible", lambda: False)         # sin Supabase también
    assert meta_token.token_ig_vigente(usar_cache=False) == "IGABsemilla"


def test_config_ilegible_cae_al_entorno(mundo, monkeypatch):
    def _rompe(clave, defecto=None):
        raise RuntimeError("Supabase 500")
    monkeypatch.setattr(db, "obtener_config", _rompe)
    assert meta_token.token_ig_vigente(usar_cache=False) == "IGABsemilla"


def test_renueva_cuando_faltan_menos_de_30_dias(mundo):
    mundo["config"]["meta_ig_token"] = {"token": "IGABviejo", "vence": _iso(AHORA + dt.timedelta(days=20)), "renovado": _iso(AHORA - dt.timedelta(days=40))}
    r = meta_token.renovar_token_ig()
    assert r["renovado"] is True and mundo["http"] == ["IGABviejo"]
    clave, valor = mundo["guardados"][0]
    assert clave == "meta_ig_token" and valor["token"] == "IGABnuevo"
    vence = dt.datetime.fromisoformat(valor["vence"])
    assert 59 <= (vence - AHORA).days <= 60 and r["vence"] == valor["vence"]


def test_no_renueva_si_falta_mas(mundo):
    mundo["config"]["meta_ig_token"] = {"token": "IGABviejo", "vence": _iso(AHORA + dt.timedelta(days=45)), "renovado": _iso(AHORA)}
    r = meta_token.renovar_token_ig()
    assert r["renovado"] is False and mundo["http"] == [] and mundo["guardados"] == []


def test_renueva_si_el_vencimiento_no_se_conoce_o_se_fuerza(mundo):
    assert meta_token.renovar_token_ig()["renovado"] is True and mundo["http"] == ["IGABsemilla"]     # viene del entorno, sin fecha
    meta_token._cache.update(t=0.0, v=None)
    assert meta_token.renovar_token_ig()["renovado"] is False                                         # ahora vence en 60 días
    assert meta_token.renovar_token_ig(forzar=True)["renovado"] is True and mundo["http"][-1] == "IGABnuevo"


def test_falla_sin_romper(mundo, monkeypatch, capsys):
    mundo["config"]["meta_ig_token"] = {"token": "IGABviejo", "vence": _iso(AHORA + dt.timedelta(days=5)), "renovado": _iso(AHORA - dt.timedelta(days=55))}

    def _falla(token):
        raise RuntimeError("Meta 400: token inválido")
    monkeypatch.setattr(meta_token, "_http_refresh", _falla)
    r = meta_token.renovar_token_ig()
    assert r["renovado"] is False and "400" in r["motivo"] and mundo["guardados"] == []
    assert meta_token.token_ig_vigente(usar_cache=False) == "IGABviejo"
    salida = capsys.readouterr().out
    assert "NO pude renovarlo" in salida and "IGAB" not in salida


def test_no_imprime_el_token(mundo, capsys):
    meta_token.renovar_token_ig(forzar=True)
    assert "IGAB" not in capsys.readouterr().out


def test_config_usa_el_token_vigente(mundo, monkeypatch):
    import os, publicar
    mundo["config"]["meta_ig_token"] = {"token": "IGABguardado", "vence": _iso(AHORA + dt.timedelta(days=50))}
    meta_token._cache.update(t=0.0, v=None)
    assert publicar.Config(os.environ).ig_token == "IGABguardado"
    assert publicar.Config({"META_IG_TOKEN": "IGABotro"}).ig_token == "IGABotro"      # un dict explícito no consulta la base


def test_ruta_admin_fuerza_la_renovacion(mundo, logueado):
    r = logueado.post("/admin/instagram/renovar-token")
    assert r.status_code == 200 and r.json()["renovado"] is True and r.json()["vence"]
