"""Pruebas de api/recortes.py sin Supabase ni WordPress: la tabla clips es una lista en memoria (monkeypatch de db.*)."""
import copy
import pytest

import db
import publicar
import api.recortes as rec
import recortar_clip as rc

SRT = "1\n00:00:00,500 --> 00:00:02,000\nLa gratitud es la llave\n\n2\n00:00:02,100 --> 00:00:04,000\nde la alegría\n"
URL = "https://viviragradecidos.org/wp-content/uploads/2026/10/clip-abc-10-40-vertical.mp4"

FILAS = [
    {"id": "c1", "creado": "2026-10-20T10:00:00", "video_id": "abc123def", "inicio_ms": 10000, "fin_ms": 40000, "formato": "vertical",
     "titulo": "Charla sobre la gratitud", "pedido_por": "franco", "estado": "listo", "url": URL, "error": None,
     "procesado_en": None, "srt": SRT, "edicion": None, "nota": None, "estilo": None},
    {"id": "c2", "creado": "2026-10-20T11:00:00", "video_id": "abc123def", "inicio_ms": 10000, "fin_ms": 40000, "formato": "horizontal",
     "titulo": "Charla (horizontal)", "pedido_por": "lizzie", "estado": "listo", "url": URL.replace("-vertical", ""), "error": None,
     "procesado_en": None, "srt": None, "edicion": None, "nota": None, "estilo": None},
    {"id": "c3", "creado": "2026-10-20T12:00:00", "video_id": "xyz", "inicio_ms": 0, "fin_ms": 5000, "formato": "vertical",
     "titulo": "Fallido", "pedido_por": "lizzie", "estado": "error", "url": None, "error": "WordPress: 500",
     "procesado_en": None, "srt": None, "edicion": None, "nota": None, "estilo": None},
    {"id": "c4", "creado": "2026-10-20T13:00:00", "video_id": "abc123def", "inicio_ms": 50000, "fin_ms": 60000, "formato": "vertical",
     "titulo": "Del bot", "pedido_por": "bot", "estado": "pedido", "url": None, "error": None,
     "procesado_en": None, "srt": None, "edicion": None, "nota": None, "estilo": None},
]


@pytest.fixture
def tabla(monkeypatch):
    filas = copy.deepcopy(FILAS)
    cambios = []
    config = {}
    borrados_wp = []

    def _actualizar(cid, campos):
        cambios.append((cid, campos))
        for f in filas:
            if f["id"] == cid:
                f.update(campos)
        return [campos]

    monkeypatch.setattr(db, "disponible", lambda: True)
    monkeypatch.setattr(db, "listar_clips", lambda limite=60: list(filas))
    monkeypatch.setattr(db, "obtener_clip", lambda cid: next((copy.deepcopy(f) for f in filas if f["id"] == cid), None))
    monkeypatch.setattr(db, "actualizar_clip", _actualizar)
    def _borrar(cid):
        filas[:] = [f for f in filas if f["id"] != cid]

    monkeypatch.setattr(db, "borrar_clip", _borrar)
    monkeypatch.setattr(db, "publicaciones_con_video", lambda url: [{"id": 7, "canal": "wordpress", "estado": "publicada"}] if url == URL else [])
    monkeypatch.setattr(db, "obtener_config", lambda clave, defecto=None: config.get(clave, defecto))
    monkeypatch.setattr(db, "guardar_config", lambda clave, valor, usuario=None: config.__setitem__(clave, valor))
    monkeypatch.setattr(publicar, "borrar_media_por_url", lambda cfg, url, quien="": (borrados_wp.append(url) or True, "Archivo borrado de WordPress."))
    return {"filas": filas, "cambios": cambios, "config": config, "borrados_wp": borrados_wp}


def _login(cliente, usuario, clave):
    r = cliente.post("/login", json={"usuario": usuario, "clave": clave})
    assert r.status_code == 200, r.text
    return cliente


# ---------------- Lista ----------------
def test_mis_recortes(cliente, tabla):
    _login(cliente, "lizzie", "clave-lizzie")
    r = cliente.get("/recortes")
    assert r.status_code == 200
    ids = [c["id"] for c in r.json()]
    assert ids == ["c2", "c3", "c4"]              # los míos y los del bot; nunca el de franco
    c2 = r.json()[0]
    assert c2["propio"] and c2["puede_editar"] and c2["puede_borrar"]
    assert c2["miniatura"].endswith("abc123def/hqdefault.jpg") and c2["duracion_ms"] == 30000
    assert c2["estado_texto"] == "listo"
    assert r.json()[1]["puede_editar"] is False     # con error no se edita
    assert cliente.get("/recortes?todos=1").status_code == 403


def test_equipo_y_todos(cliente, tabla):
    _login(cliente, "lizzie", "clave-lizzie")
    eq = cliente.get("/recortes?equipo=1").json()
    assert [c["id"] for c in eq] == ["c1"]           # solo los LISTOS de otras personas
    assert eq[0]["propio"] is False and eq[0]["puede_editar"] is False and eq[0]["puede_borrar"] is False
    _login(cliente, "franco", "clave-franco")
    todos = cliente.get("/recortes?todos=1").json()
    assert [c["id"] for c in todos] == ["c1", "c2", "c3", "c4"]
    assert todos[1]["puede_editar"] and todos[1]["puede_borrar"]     # el aprobador puede con los ajenos
    assert [c["id"] for c in cliente.get("/recortes?todos=1&buscar=fallido").json()] == ["c3"]


def test_regenerando(cliente, tabla):
    tabla["filas"][0].update(estado="pedido", edicion={"srt": SRT})
    _login(cliente, "franco", "clave-franco")
    c = cliente.get("/recortes").json()[0]
    assert c["regenerando"] is True and c["estado_texto"] == "regenerando con los cambios"


# ---------------- Opciones, estilo por defecto, detalle ----------------
def test_opciones(logueado, tabla):
    d = logueado.get("/recortes/opciones").json()
    assert d["tipografias"] == list(rc.FUENTES_CLIPS) and d["posiciones"] == ["abajo", "centro", "arriba"]
    assert d["colores"]["amarillo de la marca"] == "F4B43C"
    assert d["fondos"]["sombra oscura"] == {"tipo": "caja", "color": "000000", "alpha": "90"}
    assert d["estilo_defecto"] == rc.ESTILO_DEFECTO and d["estilo_equipo"] is None
    assert d["limites"] == {"min_ms": 2000, "max_ms": 180000}


def test_estilo_defecto(cliente, tabla):
    _login(cliente, "lizzie", "clave-lizzie")
    assert cliente.get("/recortes/estilo-defecto").json() == {"estilo": rc.ESTILO_DEFECTO, "guardado": False}
    assert cliente.put("/recortes/estilo-defecto", json={"estilo": {"color": "crema"}}).status_code == 403
    _login(cliente, "franco", "clave-franco")
    r = cliente.put("/recortes/estilo-defecto", json={"estilo": {"color": "crema", "posicion": "centro", "tamano": "enorme"}})
    assert r.status_code == 200 and r.json()["estilo"]["color"] == "crema" and r.json()["estilo"]["tamano"] == "normal"
    assert tabla["config"]["clips_estilo"]["posicion"] == "centro"
    d = cliente.get("/recortes/estilo-defecto").json()
    assert d["guardado"] is True and d["estilo"]["color"] == "crema"
    assert cliente.get("/recortes/opciones").json()["estilo_equipo"]["color"] == "crema"


def test_detalle(logueado, tabla):
    r = logueado.get("/recortes/c1")
    assert r.status_code == 200
    c = r.json()
    assert len(c["lineas"]) == 2 and c["lineas"][0]["texto"] == "La gratitud es la llave" and c["lineas"][0]["inicio"] == "00:00:00,500"
    assert c["estilo_actual"] == rc.ESTILO_DEFECTO and c["estilo_propio"] is False and c["srt_corregido"] is False
    assert logueado.get("/recortes/nada").status_code == 404


# ---------------- Editar (regenerar) ----------------
def test_editar_validaciones(logueado, tabla):
    assert logueado.post("/recortes/c1/edicion", json={}).status_code == 400                       # nada cambió
    assert logueado.post("/recortes/c1/edicion", json={"fin_ms": 10000}).status_code == 400          # fin <= inicio
    assert logueado.post("/recortes/c1/edicion", json={"fin_ms": 11000}).status_code == 400          # 1 s
    assert logueado.post("/recortes/c1/edicion", json={"fin_ms": 200000}).status_code == 400         # > 3 min
    assert logueado.post("/recortes/c3/edicion", json={"fin_ms": 9000}).status_code == 409           # no está listo
    assert logueado.post("/recortes/c1/edicion", json={"segmentos": [[0, 1000]]}).status_code == 400  # fuera del tramo
    assert logueado.post("/recortes/c1/edicion", json={"lineas": [{"inicio": "00:00:00,500", "fin": "00:00:02,000", "texto": "  "}]}).status_code == 400
    assert tabla["cambios"] == []


def test_editar_tramo_y_pausas(logueado, tabla):
    r = logueado.post("/recortes/c1/edicion", json={"inicio_ms": 12000, "fin_ms": 40000, "quitar_pausas": True})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["edicion"] == {"inicio_ms": 12000, "fin_ms": 40000, "quitar_pausas": True}
    assert d["partes"] == ["tramo 00:12–00:40", "sin pausas largas"]
    cid, campos = tabla["cambios"][0]
    assert cid == "c1" and campos["estado"] == "pedido" and campos["error"] is None
    assert campos["nota"].startswith("Cambios de franco el ") and "tramo 00:12–00:40" in campos["nota"]
    assert "se arman de nuevo" in d["avisos"][0]


def test_editar_subtitulos_y_estilo(logueado, tabla):
    lineas = [{"inicio": "00:00:00,500", "fin": "00:00:02,000", "texto": "La gratitud es la LLAVE"},
              {"inicio": "00:00:02,100", "fin": "00:00:04,000", "texto": ""}]      # la segunda se saca
    r = logueado.post("/recortes/c1/edicion", json={"lineas": lineas, "estilo": {"color": "amarillo de la marca", "negrita": True}})
    assert r.status_code == 200, r.text
    e = r.json()["edicion"]
    assert e["srt"] == "1\n00:00:00,500 --> 00:00:02,000\nLa gratitud es la LLAVE\n"
    assert e["estilo"]["color"] == "amarillo de la marca" and e["estilo"]["negrita"] is True and e["estilo"]["tipografia"] == "Raleway"
    assert "inicio_ms" not in e and r.json()["partes"] == ["subtítulos corregidos", "estilo"]
    # mismo estilo que el actual → no se guarda como cambio
    assert logueado.post("/recortes/c2/edicion", json={"estilo": rc.ESTILO_DEFECTO}).status_code == 400


def test_editar_segmentos(logueado, tabla):
    r = logueado.post("/recortes/c1/edicion", json={"segmentos": [[10000, 20000], [25000, 40000], [8000, 9000]]})
    assert r.status_code == 200, r.text
    assert r.json()["edicion"] == {"segmentos": [[10000, 20000], [25000, 40000]]}     # el de 8-9 s cae fuera y se descarta
    assert r.json()["partes"] == ["2 pedazos conservados"]
    # segmentos que cubren todo = sin pedazos
    tabla["filas"][0].update(estado="listo", edicion={"segmentos": [[10000, 20000], [25000, 40000]]})
    r = logueado.post("/recortes/c1/edicion", json={"segmentos": [[10000, 40000]]})
    assert r.status_code == 200 and r.json()["edicion"] == {} and r.json()["partes"] == ["sin pedazos sacados"]


def test_editar_tramo_descarta_srt_corregido(logueado, tabla):
    tabla["filas"][0]["edicion"] = {"srt": SRT.replace("alegría", "ALEGRÍA")}
    r = logueado.post("/recortes/c1/edicion", json={"inicio_ms": 11000})
    assert r.status_code == 200 and "srt" not in r.json()["edicion"] and "subtítulos rearmados" in r.json()["partes"]
    tabla["filas"][0].update(estado="listo", edicion={"srt": SRT.replace("alegría", "ALEGRÍA")})
    r = logueado.post("/recortes/c1/edicion", json={"inicio_ms": 11000, "descartar_srt": False})
    assert r.status_code == 200 and "ALEGRÍA" in r.json()["edicion"]["srt"] and "tramo anterior" in r.json()["avisos"][0]


def test_apagar_pausas_descarta_srt(logueado, tabla):
    tabla["filas"][0]["edicion"] = {"quitar_pausas": True, "sin_pausas": {"antes": 30, "despues": 25, "pausas": 3}, "srt": SRT}
    r = logueado.post("/recortes/c1/edicion", json={"quitar_pausas": False})
    assert r.status_code == 200
    assert r.json()["edicion"]["quitar_pausas"] is False and "srt" not in r.json()["edicion"] and "sin pausas" in r.json()["avisos"][0]


def test_editar_horizontal_ignora_subtitulos(logueado, tabla):
    r = logueado.post("/recortes/c2/edicion", json={"srt": "1\n00:00:00,000 --> 00:00:01,000\nhola\n", "fin_ms": 35000})
    assert r.status_code == 200 and r.json()["edicion"] == {"inicio_ms": 10000, "fin_ms": 35000}


def test_editar_ajeno(cliente, tabla):
    _login(cliente, "lizzie", "clave-lizzie")
    assert cliente.post("/recortes/c1/edicion", json={"fin_ms": 30000}).status_code == 403
    _login(cliente, "franco", "clave-franco")                                                   # aprobador: sí
    assert cliente.post("/recortes/c2/edicion", json={"fin_ms": 30000}).status_code == 200


# ---------------- Borrar, usos, reintentar ----------------
def test_borrar(cliente, tabla):
    _login(cliente, "lizzie", "clave-lizzie")
    assert cliente.get("/recortes/c1/usos").json()[0]["canal"] == "wordpress"
    assert cliente.get("/recortes/c3/usos").json() == []
    assert cliente.delete("/recortes/c1").status_code == 403                 # ajeno
    r = cliente.delete("/recortes/c2")
    assert r.status_code == 200 and r.json()["aviso"] == "Archivo borrado de WordPress."
    assert tabla["borrados_wp"] == [URL.replace("-vertical", "")]
    assert [f["id"] for f in tabla["filas"]] == ["c1", "c3", "c4"]
    assert cliente.delete("/recortes/c3").status_code == 200                 # con error: sin archivo, se borra la fila
    assert tabla["borrados_wp"] == [URL.replace("-vertical", "")]
    assert cliente.delete("/recortes/c3").status_code == 404


def test_borrar_wp_falla(cliente, tabla, monkeypatch):
    monkeypatch.setattr(publicar, "borrar_media_por_url", lambda cfg, url, quien="": (False, "WordPress no lo borró"))
    _login(cliente, "franco", "clave-franco")
    r = cliente.delete("/recortes/c1")
    assert r.status_code == 502 and "no lo borró" in r.json()["detail"]
    assert [f["id"] for f in tabla["filas"]][0] == "c1"


def test_reintentar(cliente, tabla):
    _login(cliente, "lizzie", "clave-lizzie")
    assert cliente.post("/recortes/c3/reintentar").status_code == 403
    _login(cliente, "franco", "clave-franco")
    assert cliente.post("/recortes/c1/reintentar").status_code == 409
    assert cliente.post("/recortes/c3/reintentar").status_code == 200
    assert tabla["cambios"][-1] == ("c3", {"estado": "pedido", "error": None})


def test_sin_sesion(cliente):
    for ruta in ("/recortes", "/recortes/opciones", "/recortes/estilo-defecto", "/recortes/c1", "/recortes/c1/usos"):
        assert cliente.get(ruta).status_code == 401, ruta
    assert cliente.post("/recortes/c1/edicion", json={}).status_code == 401
    assert cliente.delete("/recortes/c1").status_code == 401
