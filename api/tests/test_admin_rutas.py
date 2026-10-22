"""(22/10) Endpoints de Administración de la web (api/admin_rutas.py): resumen, uso, costos, servicios y configuración,
con una Supabase simulada (monkeypatch sobre db). El cálculo del costo es el de publicar_ui._costo."""
import datetime as dt

import pytest

import db
import api.admin_rutas as ar
import api.cuentas as cuentas

AHORA = dt.datetime.now(dt.timezone.utc)
HOY = ar._hoy_argentina()


def _iso(d):
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture
def mundo(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "k")
    precios = {"gpt-5.6-sol": {"entrada": 4.0, "salida": 20.0, "cache": 0.4, "fuente": "docs 21/10"}}
    config = {"openai_precios": precios, "frase_canales": ["instagram"]}
    hace = lambda h: _iso(AHORA - dt.timedelta(hours=h))
    # 2 llamadas de franco (US$ 4 + 2 = 6 la primera; 0,2 la segunda), 1 de lizzie sin precio, 1 del sistema
    uso = [{"creado": hace(2), "usuario": "franco", "modelo": "gpt-5.6-sol", "que": "chat", "tokens_entrada": 1_000_000, "tokens_salida": 100_000, "tokens_cache": 0},
           {"creado": hace(30), "usuario": "franco", "modelo": "gpt-5.6-sol", "que": "auxiliar", "tokens_entrada": 50_000, "tokens_salida": 0, "tokens_cache": 0},
           {"creado": hace(3), "usuario": "lizzie", "modelo": "text-embedding-3-small", "que": "embedding", "tokens_entrada": 10_000, "tokens_salida": 0, "tokens_cache": 0},
           {"creado": hace(4), "usuario": None, "modelo": "gpt-5.6-sol", "que": "auxiliar", "tokens_entrada": 100_000, "tokens_salida": 0, "tokens_cache": 100_000}]
    # el mes pasado: una llamada de US$ 2
    mes_pasado = (HOY.replace(day=1) - dt.timedelta(days=3))
    uso_viejo = [{"creado": f"{mes_pasado.isoformat()}T12:00:00Z", "usuario": "beto", "modelo": "gpt-5.6-sol", "que": "chat", "tokens_entrada": 500_000, "tokens_salida": 0, "tokens_cache": 0}]
    actividad = {"conversaciones": [{"id": "c1", "usuario": "franco", "titulo": "Sobre la gratitud", "creado": hace(5), "actualizado": hace(2), "n_mensajes": 3},
                                    {"id": "c2", "usuario": "lizzie", "titulo": "Newsletter", "creado": hace(40), "actualizado": hace(3), "n_mensajes": 1},
                                    {"id": "c3", "usuario": "frase_del_dia", "titulo": "bot", "creado": hace(1), "actualizado": hace(1), "n_mensajes": 1}],
                 "publicaciones": [{"id": 1, "usuario": "franco", "canal": "instagram", "modo": "simulado", "estado": "a_aprobar", "titulo": "Pieza", "creado": hace(6)}],
                 "clips": [{"id": "k1", "pedido_por": "julian", "formato": "vertical", "estado": "listo", "titulo": "Recorte", "creado": hace(7)}]}
    usuarios = [{"usuario": "franco", "nombre": "Franco", "rol": "admin", "activo": True, "ultimo_login": hace(1)},
                {"usuario": "lizzie", "nombre": "Lizzie", "rol": "creador", "activo": True, "ultimo_login": None},
                {"usuario": "beto", "nombre": "Beto", "rol": "admin", "activo": True, "ultimo_login": None},
                {"usuario": "amalia", "nombre": None, "rol": "creador", "activo": False, "ultimo_login": None}]
    servicios = [{"id": "s1", "nombre": "Render (fva-api)", "proveedor": "Render", "plan": "Free", "costo_mensual_usd": 0, "confirmado": True, "activo": True},
                 {"id": "s2", "nombre": "Hostinger VPS", "proveedor": "Hostinger", "plan": "KVM 1", "costo_mensual_usd": 7.99, "confirmado": False, "activo": True},
                 {"id": "s3", "nombre": "Viejo", "proveedor": "x", "plan": None, "costo_mensual_usd": 50, "confirmado": True, "activo": False}]
    historial = [{"creado": _iso(AHORA - dt.timedelta(minutes=5)), "estado": "arranque", "detalle": {"version": "x"}},
                 {"creado": _iso(AHORA - dt.timedelta(minutes=20)), "estado": "aviso",
                  "detalle": {"chequeos": [{"nombre": "supabase", "estado": "ok", "detalle": "ok"}, {"nombre": "instagram", "estado": "aviso", "detalle": "vence"},
                                           {"nombre": "web", "estado": "error", "detalle": "500"}],
                              "capacidad": [{"nombre": "Supabase", "estado": "aviso", "porcentaje": 76}, {"nombre": "Render (API)", "estado": "ok"}]}}]
    estado = {"config": config, "uso": uso, "uso_viejo": uso_viejo, "actividad": actividad, "usuarios": usuarios, "servicios": servicios,
              "historial": historial, "cambios": [], "guardados": [], "borrados": []}

    def _uso_openai(dias=28, desde=None, hasta=None):
        filas = list(uso)
        if desde and desde[:10] <= mes_pasado.isoformat():
            filas = filas + list(uso_viejo)
        if hasta:
            filas = [f for f in filas if f["creado"] < hasta]
        if desde:
            filas = [f for f in filas if f["creado"] >= desde]
        return filas

    def _guardar_servicio(datos, usuario=None):
        estado["guardados"].append((dict(datos), usuario))
        if datos.get("id"):
            for s in servicios:
                if s["id"] == datos["id"]:
                    s.update(datos)
                    return [dict(s)]
        nuevo = dict(datos, id="s-nuevo")
        servicios.append(nuevo)
        return [nuevo]

    monkeypatch.setattr(db, "obtener_config", lambda clave, defecto=None: config.get(clave, defecto))
    monkeypatch.setattr(db, "guardar_config", lambda clave, valor, usuario=None: config.__setitem__(clave, valor))
    monkeypatch.setattr(db, "uso_openai", _uso_openai)
    monkeypatch.setattr(db, "uso_actividad", lambda dias=28: {k: list(v) for k, v in actividad.items()})
    monkeypatch.setattr(db, "uso_ultima_vez", lambda: {"franco": hace(2), "lizzie": hace(3), "beto": hace(500)})
    monkeypatch.setattr(db, "listar_usuarios", lambda limite=500: [dict(u) for u in usuarios])
    monkeypatch.setattr(db, "listar_servicios", lambda solo_activos=False: [dict(s) for s in servicios if s["activo"] or not solo_activos])
    monkeypatch.setattr(db, "guardar_servicio", _guardar_servicio)
    monkeypatch.setattr(db, "borrar_servicio", lambda sid: estado["borrados"].append(sid) or [])
    monkeypatch.setattr(db, "listar_salud", lambda limite=100: list(historial))
    monkeypatch.setattr(db, "registrar_cambio_usuario", lambda quien, accion, usuario=None, detalle=None: estado["cambios"].append((quien, accion, usuario, detalle)))
    # la tabla config con quién y cuándo (admin_rutas._filas_config usa db._req); cualquier otra tabla, vacía
    monkeypatch.setattr(db, "_req", lambda metodo, q, cuerpo=None, tabla=None, **kw: [{"clave": k, "valor": v, "actualizado": "2026-10-21T20:00:00+00:00", "por": "franco"} for k, v in config.items()] if tabla == "config" else [])
    monkeypatch.setattr(db, "usuario_por_nombre", lambda u: None)      # el login sigue por secrets (conftest)
    cuentas.olvidar()
    return estado


# ---------------- cálculo ----------------
def test_calcular_costos_misma_formula_que_streamlit(mundo):
    r = ar.calcular_costos(mundo["uso"], mundo["config"]["openai_precios"])
    # franco: 1M×4 + 0.1M×20 = 6 ; 50k×4/1M = 0.2 → 6.2. sistema: (100k−100k)×4 + 100k×0.4 = 0.04. lizzie: sin precio.
    assert r["total_usd"] == pytest.approx(6.24)
    assert r["modelos_sin_precio"] == ["text-embedding-3-small"] and r["llamadas"] == 4 and r["personas"] == 3
    franco = r["por_persona"][0]
    assert franco["usuario"] == "franco" and franco["usd"] == pytest.approx(6.2) and franco["chats"] == 1 and franco["usd_por_chat"] == pytest.approx(6.2)
    assert franco["parte"] == pytest.approx(6.2 / 6.24, abs=1e-3)
    sistema = next(p for p in r["por_persona"] if p["usuario"] == "(sistema)")
    assert sistema["usd"] == pytest.approx(0.04) and sistema["tokens_cache"] == 100_000
    modelos = {(m["modelo"], m["que"]): m for m in r["por_modelo"]}
    assert modelos[("gpt-5.6-sol", "chat")]["usd"] == pytest.approx(6.0) and modelos[("text-embedding-3-small", "embedding")]["con_precio"] is False
    assert sum(d["usd"] for d in r["por_dia"]) == pytest.approx(6.24)


def test_periodo():
    p = ar.periodo(None, None)
    assert p["tipo"] == "dias" and p["dias"] == 28 and p["hasta"] is None
    p = ar.periodo(None, "2026-09")
    assert p["desde"] == "2026-09-01T03:00:00Z" and p["hasta"] == "2026-10-01T03:00:00Z" and p["texto"] == "septiembre 2026"
    with pytest.raises(Exception):
        ar.periodo(None, "2026-13")
    with pytest.raises(Exception):
        ar.periodo(0, None)


# ---------------- endpoints ----------------
def test_solo_admins(cliente, mundo):
    for ruta in ("/admin/resumen", "/admin/uso", "/admin/costos", "/admin/servicios", "/admin/config"):
        assert cliente.get(ruta).status_code == 401
    cliente.post("/login", json={"usuario": "lizzie", "clave": "clave-lizzie"})
    for ruta in ("/admin/resumen", "/admin/uso", "/admin/costos", "/admin/servicios", "/admin/config"):
        assert cliente.get(ruta).status_code == 403
    assert cliente.put("/admin/config", json={"cambios": {"frase_activa": True}}).status_code == 403
    assert cliente.put("/admin/servicios", json={"nombre": "x"}).status_code == 403


def test_resumen(logueado, mundo):
    d = logueado.get("/admin/resumen").json()
    s = d["salud"]
    assert s["estado"] == "aviso" and s["errores"] == 1 and s["avisos"] == 1 and s["chequeos"] == 3 and s["arranques_24h"] == 1
    assert [m["nombre"] for m in s["mal"]] == ["instagram", "web"] and s["capacidad_mal"][0]["nombre"] == "Supabase"
    c = d["costo"]
    assert c["openai_usd"] == pytest.approx(6.24) and c["fijo_usd"] == 7.99 and c["total_usd"] == pytest.approx(14.23)
    assert c["sin_confirmar"] == ["Hostinger VPS"] and c["servicios_activos"] == 2
    assert c["anterior"]["openai_usd"] == pytest.approx(2.0) and c["anterior"]["total_usd"] == pytest.approx(9.99)
    assert c["presupuesto_usd"] is None and "text-embedding-3-small" in c["modelos_sin_precio"]


def test_resumen_sin_corridas(logueado, mundo):
    mundo["historial"].clear()
    s = logueado.get("/admin/resumen").json()["salud"]
    assert s["estado"] == "sin_dato" and "Salud" in s["detalle"]


def test_uso(logueado, mundo):
    d = logueado.get("/admin/uso?dias=7").json()
    r = d["resumen"]
    # frase_del_dia no cuenta; julián aparece aunque no esté en la tabla; amalia aparece aunque no hizo nada
    assert r["conversaciones"] == 2 and r["piezas"] == 1 and r["recortes"] == 1 and r["personas_activas"] == 3
    personas = {p["usuario"]: p for p in d["personas"]}
    # gratefulness viene de la lista de secrets (conftest), mientras conviven las dos listas
    assert set(personas) == {"franco", "lizzie", "beto", "amalia", "julian", "gratefulness"} and r["personas_total"] == 6
    assert personas["franco"]["conversaciones"] == 1 and personas["franco"]["mensajes"] == 3 and personas["franco"]["piezas"] == 1
    assert personas["franco"]["costo_usd"] == pytest.approx(6.2) and personas["franco"]["lo_ultimo"]["texto"] == "Sobre la gratitud"
    assert personas["julian"]["recortes"] == 1 and personas["julian"]["en_tabla"] is False and personas["julian"]["lo_ultimo"]["tipo"] == "recorte"
    assert personas["amalia"]["conversaciones"] == 0 and personas["amalia"]["activo"] is False
    assert set(d["sin_actividad"]) == {"beto", "amalia", "gratefulness"}
    assert d["personas"][0]["usuario"] == "franco"              # ordenado por última vez
    assert sum(s["total"] for s in d["por_semana"]) == 2 and d["ultimas"]["conversaciones"][0]["titulo"] == "Sobre la gratitud"


def test_uso_por_mes_recorta(logueado, mundo):
    mes_pasado = (HOY.replace(day=1) - dt.timedelta(days=1)).strftime("%Y-%m")
    d = logueado.get(f"/admin/uso?mes={mes_pasado}").json()
    assert d["periodo"]["tipo"] == "mes" and d["resumen"]["conversaciones"] == 0 and d["resumen"]["piezas"] == 0
    assert all(p["conversaciones"] == 0 for p in d["personas"])


def test_costos(logueado, mundo):
    d = logueado.get("/admin/costos?dias=28").json()
    assert d["total_usd"] == pytest.approx(6.24) and d["periodo"]["dias"] == 28 and d["registro_desde"] == "2026-10-21"
    assert len(d["meses"]) == 6 and d["meses"][0]["mes"] == HOY.strftime("%Y-%m") and d["meses"][0]["usd"] == pytest.approx(6.24)
    assert d["meses"][1]["usd"] == pytest.approx(2.0) and d["meses"][1]["quien_mas"]["usuario"] == "beto"
    assert d["meses"][5]["usd"] == 0 and d["meses"][5]["llamadas"] == 0
    assert "gpt-5.6-sol" in d["precios"] and "gpt-5.6-sol" in d["avisos_precios"]
    assert logueado.get("/admin/costos?mes=2026-1").status_code == 400


def test_servicios_listar_guardar_borrar(logueado, mundo):
    d = logueado.get("/admin/servicios").json()
    assert len(d["servicios"]) == 3 and d["fijo_usd"] == 7.99 and d["fijo_confirmado_usd"] == 0 and d["openai_mes_usd"] == pytest.approx(6.24)
    assert d["total_mes_usd"] == pytest.approx(14.23) and d["sin_confirmar"] == ["Hostinger VPS"]
    r = logueado.put("/admin/servicios", json={"nombre": " Prueba ", "proveedor": "x", "costo_mensual_usd": 3.5, "confirmado": False, "desde": "2026-10-22"})
    assert r.status_code == 200, r.text
    assert r.json()["servicio"]["id"] == "s-nuevo" and r.json()["servicio"]["nombre"] == "Prueba"
    assert mundo["cambios"][-1][1] == "servicio_alta" and mundo["cambios"][-1][2] == "Prueba" and mundo["guardados"][-1][1] == "franco"
    r = logueado.put("/admin/servicios", json={"id": "s-nuevo", "nombre": "Prueba", "costo_mensual_usd": 4, "confirmado": True})
    assert r.status_code == 200 and mundo["cambios"][-1][1] == "servicio_editar"
    assert logueado.put("/admin/servicios", json={"nombre": "  "}).status_code == 400
    assert logueado.put("/admin/servicios", json={"nombre": "x", "costo_mensual_usd": -1}).status_code == 400
    assert logueado.put("/admin/servicios", json={"nombre": "x", "desde": "22/10/2026"}).status_code == 400
    assert logueado.delete("/admin/servicios/s-nuevo").status_code == 200
    assert mundo["borrados"] == ["s-nuevo"] and mundo["cambios"][-1][1] == "servicio_baja"
    assert logueado.delete("/admin/servicios/no-existe").status_code == 404


def test_config_leer_y_guardar(logueado, mundo):
    d = logueado.get("/admin/config").json()
    assert d["valores"]["openai_precios"]["por"] == "franco" and "frase_activa" in d["explicaciones"]
    assert d["frase_canales_posibles"]["instagram"] and "gpt-5.6-sol" in d["modelos_vistos"]
    cambios = {"presupuesto_openai_usd": 25, "umbrales_planes": {"default": 75, "render": 60}, "frase_activa": True, "frase_hora": "08:30",
               "frase_canales": ["facebook", "instagram"], "frase_imagen": "https://x/y.jpg", "frase_pie": " #Hola ", "vercel_uso_manual": {"gb": 12.5},
               "openai_precios": {"gpt-5.6-sol": {"entrada": "4", "salida": 20, "cache": 0.4, "fuente": "docs", "fecha": "2026-10-22"}}}
    r = logueado.put("/admin/config", json={"cambios": cambios})
    assert r.status_code == 200, r.text
    c = mundo["config"]
    assert c["presupuesto_openai_usd"] == 25 and c["umbrales_planes"] == {"default": 75.0, "render": 60.0} and c["frase_activa"] is True
    assert c["frase_hora"] == "08:30" and c["frase_canales"] == ["instagram", "facebook"] and c["frase_pie"] == "#Hola"
    assert c["vercel_uso_manual"]["gb"] == 12.5 and c["vercel_uso_manual"]["por"] == "franco"
    assert c["openai_precios"]["gpt-5.6-sol"]["entrada"] == 4.0 and c["openai_precios"]["gpt-5.6-sol"]["fecha"] == "2026-10-22"
    registro = [x for x in mundo["cambios"] if x[1] == "config"]
    assert len(registro) == 9 and all(x[0] == "franco" for x in registro)
    hora = next(x for x in registro if x[2] == "frase_hora")
    assert hora[3] == {"de": None, "a": "08:30"}


@pytest.mark.parametrize("cambios", [
    {"frase_hora": "25:00"}, {"frase_canales": ["tiktok"]}, {"frase_canales": []}, {"frase_imagen": "foto.jpg"}, {"frase_activa": "si"},
    {"presupuesto_openai_usd": -1}, {"umbrales_planes": {"default": 150}}, {"vercel_uso_manual": {"gb": -3}},
    {"openai_precios": {"m": {"entrada": 1, "salida": 2}}},            # sin fuente
    {"openai_precios": {"m": {"entrada": 1, "fuente": "x"}}},          # sin salida
    {"clips_estilo": {}}, {"otra_clave": 1}, {},
])
def test_config_rechaza_lo_invalido(logueado, mundo, cambios):
    r = logueado.put("/admin/config", json={"cambios": cambios})
    assert r.status_code == 400, r.text
    assert not [x for x in mundo["cambios"] if x[1] == "config"]


def test_sin_supabase(logueado, monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    assert logueado.get("/admin/resumen").json()["sin_supabase"] is True
    assert logueado.get("/admin/uso").json()["sin_supabase"] is True
    assert logueado.get("/admin/servicios").json()["servicios"] == []
    assert logueado.put("/admin/config", json={"cambios": {"frase_activa": True}}).status_code == 503
