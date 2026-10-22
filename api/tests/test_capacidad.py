"""(22/10) Bloque «capacidad» de /salud/servicios: uso vs. límite del plan por proveedor, umbral configurable, justificación."""
import datetime as dt

import pytest

import db
import api.salud as salud

AHORA = dt.datetime.now(dt.timezone.utc)


@pytest.fixture
def datos(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "k")
    monkeypatch.setenv("CORS_ORIGENES", "https://chatbot-vvaa.vercel.app")
    monkeypatch.delenv("MEMORIA_LIMITE_MB", raising=False)
    config = {"openai_precios": {"gpt-5.6-sol": {"entrada": 4.0, "salida": 20.0, "cache": 0.4, "fuente": "docs 21/10"}}}
    estado = {"config": config, "base_bytes": 120 * 2 ** 20, "arranques": {24: 1, 168: 4}, "rss": 300.0, "guardadas": []}
    hoy = salud._hoy_argentina()
    uso = [{"creado": f"{hoy.isoformat()}T10:00:00Z", "modelo": "gpt-5.6-sol", "tokens_entrada": 1_000_000, "tokens_salida": 100_000, "tokens_cache": 0},
           {"creado": f"{hoy.isoformat()}T11:00:00Z", "modelo": "text-embedding-3-small", "tokens_entrada": 50_000, "tokens_salida": 0, "tokens_cache": 0}]
    servicios = [{"nombre": "Supabase", "proveedor": "Supabase", "plan": "Free", "costo_mensual_usd": 0, "confirmado": True, "activo": True},
                 {"nombre": "Render", "proveedor": "Render", "plan": "Free", "costo_mensual_usd": 0, "confirmado": True, "activo": True}]
    monkeypatch.setattr(db, "obtener_config", lambda clave, defecto=None: config.get(clave, defecto))
    monkeypatch.setattr(db, "guardar_config", lambda clave, valor, usuario=None: config.__setitem__(clave, valor))
    monkeypatch.setattr(db, "tamano_base", lambda: {"bytes": estado["base_bytes"], "tablas": {"fragmentos_emb": {"filas": 26448, "bytes": 90 * 2 ** 20}, "conversaciones": {"filas": 91, "bytes": 2 ** 20}}})
    monkeypatch.setattr(db, "contar_arranques", lambda horas=24: estado["arranques"].get(horas, 0))
    monkeypatch.setattr(db, "listar_servicios", lambda solo_activos=False: list(servicios))
    monkeypatch.setattr(db, "uso_openai", lambda dias=28, desde=None, hasta=None: list(uso))
    monkeypatch.setattr(db, "listar_salud", lambda limite=100: [])
    monkeypatch.setattr(db, "guardar_salud", lambda e, d: estado["guardadas"].append((e, d)) or [])
    monkeypatch.setattr(salud, "_rss_mb", lambda: estado["rss"])
    return estado


def _por(items, proveedor):
    return next(i for i in items if i["proveedor"] == proveedor)


def test_capacidad_todo_bajo_umbral(datos):
    items = salud.capacidad()
    assert {i["proveedor"] for i in items} == {"supabase", "render", "vercel", "openai"}
    sb = _por(items, "supabase")
    assert sb["uso"] == 120.0 and sb["limite"] == 500 and sb["porcentaje"] == 24 and sb["estado"] == "ok" and sb["referencia"] is False
    assert sb["plan"] == "Free" and sb["costo_mensual_usd"] == 0 and sb["tablas"]["fragmentos_emb"]["filas"] == 26448
    assert "supabase.com/pricing" in sb["fuente_limite"]
    rd = _por(items, "render")
    assert rd["uso"] == 300 and rd["limite"] == 512 and rd["porcentaje"] == 59 and rd["estado"] == "ok" and rd["arranques_24h"] == 1
    vc = _por(items, "vercel")
    assert vc["estado"] == "sin_dato" and vc["medido"] is False and vc["referencia"] is True and vc["limite"] == 100
    oa = _por(items, "openai")
    # 1M entrada × 4 + 0.1M salida × 20 = 4 + 2 = US$ 6; el embedding no tiene precio cargado
    assert oa["uso"] == 6.0 and oa["limite"] is None and oa["estado"] == "ok" and "text-embedding-3-small" in oa["modelos_sin_precio"]
    assert "No hay presupuesto" in oa["justificacion"] and oa["tokens"]["llamadas"] == 2


def test_capacidad_umbral_y_aviso(datos):
    datos["base_bytes"] = 380 * 2 ** 20            # 76 % > 70
    datos["rss"] = 450.0                            # 88 %
    datos["config"]["presupuesto_openai_usd"] = 8   # 6 de 8 = 75 %
    items = salud.capacidad()
    sb, rd, oa = _por(items, "supabase"), _por(items, "render"), _por(items, "openai")
    assert sb["estado"] == "aviso" and "Conviene pasar a plan pago" in sb["justificacion"] and "76 %" in sb["justificacion"]
    assert rd["estado"] == "aviso" and "88 %" in rd["justificacion"]
    assert oa["estado"] == "aviso" and oa["porcentaje"] == 75
    assert items[0]["estado"] == "aviso"           # el peor primero
    # umbral configurable: con 90 % todo vuelve a ok salvo render (88 < 90 también ok)
    datos["config"]["umbrales_planes"] = {"default": 90}
    items = salud.capacidad()
    assert all(i["estado"] == "ok" for i in items if i["proveedor"] != "vercel")
    datos["config"]["umbrales_planes"] = {"default": 90, "render": 50}
    assert _por(salud.capacidad(), "render")["estado"] == "aviso" and _por(salud.capacidad(), "render")["umbral"] == 50
    # al 100 % es error
    datos["base_bytes"] = 600 * 2 ** 20
    assert _por(salud.capacidad(), "supabase")["estado"] == "error"


def test_capacidad_arranques_frios(datos):
    datos["arranques"] = {24: 7, 168: 20}
    rd = _por(salud.capacidad(), "render")
    assert rd["estado"] == "aviso" and "7 veces en 24 h" in rd["justificacion"] and rd["arranques_7d"] == 20


def test_capacidad_supabase_caida(datos, monkeypatch):
    def _rompe():
        raise RuntimeError("Supabase rpc/tamano_base 503")
    monkeypatch.setattr(db, "tamano_base", _rompe)
    sb = _por(salud.capacidad(), "supabase")
    assert sb["estado"] == "error" and "pausada" in sb["justificacion"]


def test_capacidad_vercel_manual(datos):
    datos["config"]["vercel_uso_manual"] = {"gb": 80, "fecha": "2026-10-22T10:00:00+00:00", "por": "franco"}
    vc = _por(salud.capacidad(), "vercel")
    assert vc["uso"] == 80 and vc["porcentaje"] == 80 and vc["estado"] == "aviso" and vc["medido"] is False
    assert "a mano" in vc["justificacion"] and "franco" in vc["justificacion"]


def test_endpoints_capacidad(logueado, datos, monkeypatch):
    r = logueado.get("/salud/capacidad")
    assert r.status_code == 200 and len(r.json()["capacidad"]) == 4
    r = logueado.put("/salud/capacidad/config", json={"umbrales_planes": {"default": 75}, "presupuesto_openai_usd": 10, "vercel_uso_manual_gb": 12.5})
    assert r.status_code == 200, r.text
    assert datos["config"]["umbrales_planes"] == {"default": 75} and datos["config"]["presupuesto_openai_usd"] == 10
    assert datos["config"]["vercel_uso_manual"]["gb"] == 12.5 and datos["config"]["vercel_uso_manual"]["por"] == "franco"
    assert logueado.put("/salud/capacidad/config", json={"umbrales_planes": {"default": 150}}).status_code == 400
    assert logueado.put("/salud/capacidad/config", json={}).status_code == 400
    # /salud/servicios trae el bloque y guarda su resumen en el historial
    monkeypatch.setattr(salud, "CHEQUEOS", [salud._chequear_memoria])
    r = logueado.get("/salud/servicios")
    d = r.json()
    assert len(d["capacidad"]) == 4 and datos["guardadas"][-1][1]["capacidad"][0]["nombre"]
    oa = _por(d["capacidad"], "openai")
    assert oa["estado"] == "ok"


def test_capacidad_solo_admin(cliente, datos):
    assert cliente.get("/salud/capacidad").status_code == 401
    cliente.post("/login", json={"usuario": "lizzie", "clave": "clave-lizzie"})
    assert cliente.get("/salud/capacidad").status_code == 403
    assert cliente.put("/salud/capacidad/config", json={"presupuesto_openai_usd": 1}).status_code == 403


def test_desde_cuando_capacidad_salta_arranques():
    informe = {"creado": "2026-10-22T12:00:00+00:00", "capacidad": [{"nombre": "Supabase", "estado": "aviso"}]}
    historial = [{"creado": "2026-10-22T11:30:00+00:00", "estado": "arranque", "detalle": {"version": "x"}},
                 {"creado": "2026-10-22T11:00:00+00:00", "estado": "aviso", "detalle": {"capacidad": [{"nombre": "Supabase", "estado": "aviso"}]}},
                 {"creado": "2026-10-22T10:00:00+00:00", "estado": "ok", "detalle": {"capacidad": [{"nombre": "Supabase", "estado": "ok"}]}}]
    salud.desde_cuando(informe, historial, "capacidad")
    assert informe["capacidad"][0]["desde"] == "2026-10-22T11:00:00+00:00"
