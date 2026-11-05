"""Presencia y control de versión al guardar (5/11): la tabla presencia es una lista en memoria (monkeypatch de db._req)."""
import copy
from datetime import datetime, timezone, timedelta

import pytest

import db
import api.presencia_rutas as prr


def _iso(seg_atras):
    return (datetime.now(timezone.utc) - timedelta(seconds=seg_atras)).isoformat(timespec="seconds")


@pytest.fixture
def filas(monkeypatch):
    """presencia en memoria: entiende el upsert, la consulta por tipo/item/visto y el borrado."""
    tabla = []
    monkeypatch.setattr(db, "disponible", lambda: True)
    monkeypatch.setattr(prr, "_cache", {"t": 0.0, "nombres": {}})
    monkeypatch.setattr(db, "listar_usuarios", lambda limite=500: [{"usuario": "franco", "nombre": "Franco"}, {"usuario": "lizzie", "nombre": "Lizzie P."},
                                                                  {"usuario": "gratefulness", "nombre": None}])

    def req(method, params="", body=None, tabla="conversaciones", prefer=None):
        assert tabla == "presencia", tabla
        if method == "POST":
            tabla_mem = filas_mem
            clave = (body["tipo"], body["item_id"], body["usuario"])
            tabla_mem[:] = [f for f in tabla_mem if (f["tipo"], f["item_id"], f["usuario"]) != clave] + [dict(body)]
            return [body]
        if method == "GET":
            out = list(filas_mem)
            for parte in params.lstrip("?").split("&"):
                if parte.startswith(("tipo=eq.", "item_id=eq.", "visto=gte.")):
                    campo, resto = parte.split("=", 1)
                    op, val = resto.split(".", 1)
                    val = val.replace("%3A", ":").replace("%2B", "+")
                    out = [f for f in out if (f[campo] >= val if op == "gte" else f[campo] == val)]
            return out
        if method == "DELETE":
            antes = list(filas_mem)
            def borra(f):
                for parte in params.lstrip("?").split("&"):
                    campo, resto = parte.split("=", 1)
                    op, val = resto.split(".", 1)
                    val = val.replace("%3A", ":").replace("%2B", "+")
                    if op == "eq" and f[campo] != val:
                        return False
                    if op == "lt" and not f[campo] < val:
                        return False
                return True
            filas_mem[:] = [f for f in filas_mem if not borra(f)]
            return [f for f in antes if f not in filas_mem]
    filas_mem = tabla
    monkeypatch.setattr(db, "_req", req)
    return tabla


def test_latir_y_quienes_excluye_al_propio_y_a_los_viejos(filas):
    db.latir("pieza", "p1", "franco", "edita")
    db.latir("pieza", "p1", "lizzie", "mira")
    db.latir("pieza", "p2", "lizzie", "mira")            # otra pieza
    filas.append({"tipo": "pieza", "item_id": "p1", "usuario": "gratefulness", "modo": "edita", "visto": _iso(300)})   # ya no está
    assert [q["usuario"] for q in db.quienes("pieza", "p1", "franco")] == ["lizzie"]
    otros = db.quienes("pieza", "p1", "lizzie")
    assert [(q["usuario"], q["modo"]) for q in otros] == [("franco", "edita")] and otros[0]["hace_seg"] < 5
    assert db.quienes("recorte", "p1", "franco") == []
    db.latir("pieza", "p1", "lizzie", "edita")           # el mismo latido actualiza la fila (clave tipo, item, usuario)
    assert len([f for f in filas if f["usuario"] == "lizzie" and f["item_id"] == "p1"]) == 1
    db.salir("pieza", "p1", "lizzie")
    assert db.quienes("pieza", "p1", "franco") == []


def test_los_que_editan_van_primero_y_limpiar_borra_lo_viejo(filas):
    db.latir("pieza", "p1", "lizzie", "mira")
    filas.append({"tipo": "pieza", "item_id": "p1", "usuario": "gratefulness", "modo": "edita", "visto": _iso(5)})
    assert [q["usuario"] for q in db.quienes("pieza", "p1", "franco")] == ["gratefulness", "lizzie"]
    filas.append({"tipo": "pieza", "item_id": "p9", "usuario": "viejo", "modo": "mira", "visto": _iso(60 * 20)})
    db.limpiar_viejas(10)
    assert [f["usuario"] for f in filas if f["usuario"] == "viejo"] == [] and len(filas) == 2


def test_rutas_de_presencia(logueado, filas):
    r = logueado.post("/presencia/pieza/p1", json={"modo": "edita"})
    assert r.status_code == 200 and r.json() == {"presentes": []}          # solo estoy yo
    filas.append({"tipo": "pieza", "item_id": "p1", "usuario": "lizzie", "modo": "edita", "visto": _iso(8)})
    filas.append({"tipo": "pieza", "item_id": "p1", "usuario": "gratefulness", "modo": "mira", "visto": _iso(15)})
    pres = logueado.post("/presencia/pieza/p1", json={"modo": "mira"}).json()["presentes"]
    assert [(p["usuario"], p["nombre"], p["modo"]) for p in pres] == [("lizzie", "Lizzie P.", "edita"), ("gratefulness", "gratefulness", "mira")]
    assert logueado.post("/presencia/otra/p1", json={}).status_code == 400
    assert logueado.delete("/presencia/pieza/p1").status_code == 200
    assert not [f for f in filas if f["usuario"] == "franco"]


def test_presencia_pide_sesion(cliente):
    assert cliente.post("/presencia/pieza/p1", json={"modo": "mira"}).status_code == 401


def test_presencia_no_rompe_si_la_base_falla(logueado, monkeypatch):
    monkeypatch.setattr(db, "disponible", lambda: True)
    monkeypatch.setattr(db, "_req", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("Supabase 500")))
    assert logueado.post("/presencia/pieza/p1", json={"modo": "mira"}).json() == {"presentes": []}


# ---------------- Versión al guardar ----------------
def test_hace_texto():
    assert prr.hace_texto(_iso(1)) == "hace 1 segundo" and prr.hace_texto(_iso(40)) == "hace 40 segundos"
    assert prr.hace_texto(_iso(180)) == "hace 3 minutos" and prr.hace_texto(_iso(7300)) == "hace 2 horas"
    assert prr.hace_texto(None) == "hace un rato"


def test_conflicto_sin_version_o_igual_no_molesta():
    assert prr.conflicto(None, "2026-11-05T10:00:00+00:00", "lizzie", "franco") is None
    assert prr.conflicto("2026-11-05T10:00:00+00:00", "2026-11-05T10:00:00+00:00", "lizzie", "franco") is None
