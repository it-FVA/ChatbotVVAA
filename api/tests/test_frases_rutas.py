"""Pruebas de api/frases_rutas.py sin Supabase: la tabla frases es una lista en memoria (monkeypatch de db.*)."""
import copy, datetime
import pytest

import db
import programar_frases as pf
import api.frases_rutas as fr

HOY = datetime.date(2026, 10, 22)
D = lambda n: (HOY + datetime.timedelta(days=n)).isoformat()


def _f(i, **k):
    base = {"id": f"f{i}", "texto": f"Frase {i}", "autor": "Br. David" if i % 2 else "Otra", "origen": "sheet", "validada": True, "fecha": None,
            "imagen_url": None, "estado": "programada", "publicacion_id": None, "orden": i, "fuente": None, "tema": None, "creado": None,
            "ultima_publicada": None, "veces_publicada": 0, "piezas": None}
    base.update(k)
    return base


FILAS = [_f(1, fecha=D(0)), _f(2, fecha=D(1)), _f(3, fecha=D(2), estado="saltada"), _f(4, fecha=D(3), publicacion_id="p9"),
         _f(5), _f(6), _f(7, validada=False), _f(8, fecha=D(-5), estado="publicada", ultima_publicada="2026-10-17T10:00:00", veces_publicada=1)]


@pytest.fixture
def tabla(monkeypatch):
    filas = copy.deepcopy(FILAS)
    config = {"frase_activa": False, "frase_imagen": "https://x/fondo.jpg"}
    monkeypatch.setattr(pf, "hoy_argentina", lambda: HOY)
    monkeypatch.setattr(db, "disponible", lambda: True)
    monkeypatch.setattr(db, "obtener_config", lambda k, d=None: config.get(k, d))
    monkeypatch.setattr(db, "guardar_config", lambda k, v, u=None: config.__setitem__(k, v))
    monkeypatch.setattr(db, "obtener_frase", lambda fid: next((dict(f) for f in filas if f["id"] == fid), None))
    monkeypatch.setattr(db, "frase_del_dia", lambda fecha: next((dict(f) for f in filas if f["fecha"] == str(fecha)[:10]), None))

    def _listar(desde=None, hasta=None, limite=2000):
        out = [dict(f) for f in filas if f["fecha"] and (not desde or f["fecha"] >= str(desde)) and (not hasta or f["fecha"] <= str(hasta))]
        return sorted(out, key=lambda f: f["fecha"])
    monkeypatch.setattr(db, "listar_frases", _listar)
    monkeypatch.setattr(db, "frases_sin_fecha", lambda solo_validadas=True, limite=2000: [dict(f) for f in filas if not f["fecha"] and (f["validada"] or not solo_validadas)])
    monkeypatch.setattr(db, "frases_pendientes_validacion", lambda limite=2000: [dict(f) for f in filas if not f["validada"]])

    def _actualizar(fid, campos):
        for f in filas:
            if f["id"] == fid:
                f.update(campos)
    monkeypatch.setattr(db, "actualizar_frase", _actualizar)

    def _mover(fid, fecha):
        if fecha and any(f["fecha"] == fecha for f in filas):
            return False
        _actualizar(fid, {"fecha": fecha})
        return True
    monkeypatch.setattr(db, "mover_frase", _mover)

    def _intercambiar(a, b):
        fa, fb = db.obtener_frase(a)["fecha"], db.obtener_frase(b)["fecha"]
        _actualizar(a, {"fecha": None}); _actualizar(b, {"fecha": fa}); _actualizar(a, {"fecha": fb})
        return True
    monkeypatch.setattr(db, "intercambiar_frases", _intercambiar)
    monkeypatch.setattr(db, "resumen_frases", lambda: {"total": len(filas), "validadas": sum(f["validada"] for f in filas), "con_fecha": sum(bool(f["fecha"]) for f in filas),
                                                        "publicadas": 1, "sin_fecha_validadas": 2, "pendientes_validar": 1})
    monkeypatch.setattr(db, "obtener_publicacion", lambda pid: {"id": pid, "estado": "pendiente", "fecha_programada": D(3) + "T07:00:00-03:00", "resultado": {}})
    monkeypatch.setattr(db, "candidatas_rotacion", lambda hoy: [dict(f) for f in filas if f["validada"] and (not f["fecha"] or f["fecha"] < hoy) and not (f["fecha"] and f["publicacion_id"])])
    monkeypatch.setattr(db, "fechas_ocupadas", lambda a, b: {f["fecha"] for f in filas if f["fecha"] and a <= f["fecha"] <= b})

    def _upsert(lote, on_conflict="texto"):
        for fila in lote:
            _actualizar(fila["id"], {k: v for k, v in fila.items() if k != "actualizado"})
        return len(lote)
    monkeypatch.setattr(db, "upsert_frases", _upsert)
    creadas = []
    monkeypatch.setattr(db, "crear_frase", lambda texto, autor, **k: (creadas.append(texto), filas.append(_f(90 + len(creadas), texto=texto, autor=autor or None)), filas[-1]["id"])[2])
    return filas


def test_solo_aprobadores(cliente, tabla):
    assert cliente.get("/frases/resumen").status_code == 401
    cliente.post("/login", json={"usuario": "lizzie", "clave": "clave-lizzie"})
    assert cliente.get("/frases/resumen").status_code == 403
    assert cliente.get("/frases/proximas").status_code == 403


def test_resumen_proximas_backlog_mes(logueado, tabla):
    r = logueado.get("/frases/resumen").json()
    assert r["disponible"] and r["admin"] and r["activa"] is False and r["conteos"]["programadas"] == 4
    assert r["manana"]["frase"]["id"] == "f2" and r["frases_nuevas_hasta"] == D(3 + 2) and r["avisos"] == []
    p = logueado.get("/frases/proximas?dias=5").json()
    assert [x["frase"]["id"] if x["frase"] else None for x in p] == ["f1", "f2", "f3", "f4", None]
    assert p[2]["frase"]["estado"] == "saltada" and p[3]["frase"]["cerrada"]
    b = logueado.get("/frases/backlog").json()
    assert [x["id"] for x in b["sin_dia"]] == ["f5", "f6"] and [x["id"] for x in b["pendientes"]] == ["f7"]
    assert logueado.get("/frases/backlog?q=frase 5").json()["sin_dia_total"] == 1
    m = logueado.get(f"/frases/mes/{HOY.year}/{HOY.month}").json()
    assert m["dias"] == 31 and D(0) in m["frases"] and m["hoy"] == D(0)
    assert logueado.get("/frases/mes/2026/13").status_code == 400
    d = logueado.get(f"/frases/dia/{D(3)}").json()
    assert d["frase"]["cerrada"] and d["cola"]["estado"] == "pendiente" and d["foto"]["url"] == "https://x/fondo.jpg"
    assert logueado.get(f"/frases/dia/{D(9)}").json()["frase"] is None


def test_mover_sacar_intercambiar(logueado, tabla):
    # mover a un día libre y volver
    assert logueado.post("/frases/f1/mover", json={"fecha": D(1)}).status_code == 409        # ocupado
    assert logueado.post("/frases/f1/mover", json={"fecha": D(-1)}).status_code == 400       # pasado
    assert logueado.post("/frases/f4/mover", json={"fecha": D(9)}).status_code == 409        # en la cola
    assert logueado.post("/frases/f7/mover", json={"fecha": D(9)}).status_code == 409        # no validada
    r = logueado.post("/frases/f1/mover", json={"fecha": D(9)})
    assert r.status_code == 200 and r.json()["frase"]["fecha"] == D(9)
    assert logueado.post("/frases/f1/mover", json={"fecha": D(0)}).json()["frase"]["fecha"] == D(0)
    # asignar una sin día (y una saltada movida vuelve a programada)
    assert logueado.post("/frases/f5/mover", json={"fecha": D(9)}).json()["frase"]["fecha"] == D(9)
    assert logueado.post("/frases/f3/mover", json={"fecha": D(10)}).json()["frase"]["estado"] == "programada"
    # intercambiar y deshacer
    r = logueado.post("/frases/intercambiar", json={"id_a": "f1", "id_b": "f2"}).json()
    assert r["a"]["fecha"] == D(1) and r["b"]["fecha"] == D(0)
    r = logueado.post("/frases/intercambiar", json={"id_a": "f1", "id_b": "f2"}).json()
    assert r["a"]["fecha"] == D(0) and r["b"]["fecha"] == D(1)
    assert logueado.post("/frases/intercambiar", json={"id_a": "f1", "id_b": "f4"}).status_code == 409
    assert logueado.post("/frases/intercambiar", json={"id_a": "f6", "id_b": "f7"}).status_code == 409
    # cambiar por otra = intercambiar con una sin día
    r = logueado.post("/frases/intercambiar", json={"id_a": "f2", "id_b": "f6"}).json()
    assert r["a"]["fecha"] is None and r["b"]["fecha"] == D(1)
    # sacar
    r = logueado.post("/frases/f6/sacar")
    assert r.status_code == 200 and r.json()["frase"]["fecha"] is None
    assert logueado.post("/frases/f4/sacar").status_code == 409


def test_editar_crear_repartir_vaciar_activa(logueado, tabla):
    r = logueado.patch("/frases/f1", json={"texto": "  Nueva  ", "autor": " "})
    assert r.status_code == 200 and r.json()["frase"]["texto"] == "Nueva" and r.json()["frase"]["autor"] is None
    assert logueado.patch("/frases/f1", json={"texto": " "}).status_code == 400
    assert logueado.patch("/frases/f1", json={}).status_code == 400
    assert logueado.patch("/frases/f4", json={"texto": "x"}).status_code == 409
    assert logueado.patch("/frases/f1", json={"imagen_url": "foto.jpg"}).status_code == 400
    assert logueado.patch("/frases/f1", json={"imagen_url": "https://x/a.jpg"}).json()["frase"]["imagen_url"] == "https://x/a.jpg"
    assert logueado.patch("/frases/f1", json={"quitar_imagen": True}).json()["frase"]["imagen_url"] is None
    assert logueado.patch("/frases/f1", json={"estado": "saltada"}).json()["frase"]["estado"] == "saltada"
    assert logueado.patch("/frases/f5", json={"estado": "saltada"}).status_code == 409
    assert logueado.patch("/frases/f1", json={"estado": "otro"}).status_code == 400
    r = logueado.post("/frases", json={"texto": "Agradecer es vivir", "autor": "Br. David"})
    assert r.status_code == 201 and r.json()["frase"]["texto"] == "Agradecer es vivir" and r.json()["frase"]["fecha"] is None
    assert logueado.post("/frases", json={"texto": " "}).status_code == 400
    # repartir: las sin día (f5, f6, la nueva) + la publicada f8 (rotación) desde mañana, sin pisar ocupadas (D1..D3)
    r = logueado.post("/frases/repartir", json={"modo": "orden", "desde": D(1)}).json()
    assert r["cantidad"] == 4 and r["desde"] == D(1) and r["hasta"] == D(7)
    fechas = {f["id"]: f["fecha"] for f in tabla}
    assert fechas["f5"] == D(4) and fechas["f6"] == D(5) and fechas["f8"] == D(7) and fechas["f2"] == D(1)
    assert logueado.post("/frases/repartir", json={"desde": D(-2)}).status_code == 400
    # vaciar: las programadas/saltadas sin cola vuelven a sin día; f4 (en cola) queda
    assert logueado.post("/frases/vaciar", json={"confirmo": False}).status_code == 400
    r = logueado.post("/frases/vaciar", json={"confirmo": True}).json()
    assert r["cantidad"] == 7 and next(f for f in tabla if f["id"] == "f4")["fecha"] == D(3)
    # interruptor: solo admins (franco lo es por ADMINS default)
    r = logueado.put("/frases/activa", json={"activa": True})
    assert r.status_code == 200 and logueado.get("/frases/resumen").json()["activa"] is True
    logueado.put("/frases/activa", json={"activa": False})


def test_previa(logueado, tabla, monkeypatch):
    monkeypatch.setattr(pf, "componer", lambda f, foto, estilo=None: b"\xff\xd8jpg")
    r = logueado.get("/frases/f1/previa.jpg")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg" and r.content.startswith(b"\xff\xd8")
    monkeypatch.setattr(db, "obtener_config", lambda k, d=None: None)
    monkeypatch.setattr(fr, "_cfg", lambda: (None, type("P", (), {"buscar_imagenes_banco": staticmethod(lambda *a, **k: [])})))
    assert logueado.get("/frases/f1/previa.jpg").status_code == 404
