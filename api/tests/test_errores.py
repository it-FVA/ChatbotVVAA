"""Manejo de errores: handler global de la API y db._req ante cortes de red."""
import socket
import urllib.error

import pytest
from fastapi.testclient import TestClient

import db
from api.main import app


@app.get("/_prueba_error", include_in_schema=False)   # fuera del OpenAPI: web/openapi.json se genera sin las pruebas
def _prueba_error(tipo: str = "x"):
    if tipo == "db":
        raise RuntimeError("Supabase 503: caído")
    raise ValueError("secreto interno")


def test_excepcion_no_prevista_devuelve_json_legible_sin_filtrar_el_mensaje(caplog):
    c = TestClient(app, raise_server_exceptions=False)
    r = c.get("/_prueba_error")
    assert r.status_code == 500 and "ValueError" in r.json()["detail"] and "secreto interno" not in r.json()["detail"]
    assert any("Error no controlado" in x.message for x in caplog.records)
    assert "base de datos" in c.get("/_prueba_error?tipo=db").json()["detail"]


@pytest.mark.parametrize("error", [urllib.error.URLError("sin red"), socket.timeout("timed out"), ConnectionResetError("reset")])
def test_req_convierte_cortes_de_red_en_runtimeerror(monkeypatch, error):
    monkeypatch.setattr(db, "_cfg", lambda: ("https://x.supabase.co", "k"))

    def boom(*a, **k):
        raise error
    monkeypatch.setattr(db.urllib.request, "urlopen", boom)
    with pytest.raises(RuntimeError, match="Supabase sin conexión"):
        db._req("GET", "?x=1")
