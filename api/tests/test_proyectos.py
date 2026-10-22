"""Pruebas de api/proyectos.py (22/10) sin Supabase: db._req reemplazado por un PostgREST de juguete en memoria que entiende
los filtros que usa el módulo (eq, in, is.null, select, order). Así se prueba la lógica real de permisos y de «un ítem
vive en un solo proyecto», no solo las rutas."""
import re, uuid
from urllib.parse import unquote

import pytest

import db
import api.proyectos as pr


class FakePostgrest:
    def __init__(self):
        self.t = {k: [] for k in ("proyectos", "proyecto_items", "compartidos", "conversaciones", "clips", "publicaciones", "usuarios")}
        self.llamadas = []

    def agregar(self, tabla, **fila):
        fila.setdefault("id", str(uuid.uuid4()))
        fila.setdefault("creado", "2026-10-22T10:00:00+00:00")
        if tabla in ("proyectos", "conversaciones"):
            fila.setdefault("actualizado", fila["creado"])
        if tabla == "proyecto_items":
            fila.setdefault("agregado", fila["creado"])
        if tabla == "usuarios":
            fila.setdefault("activo", True)
        self.t[tabla].append(fila)
        return fila

    def _filtros(self, params):
        qs = params[1:] if params.startswith("?") else params
        filtros, select, order = [], None, None
        for parte in qs.split("&") if qs else []:
            if not parte:
                continue
            k, _, v = parte.partition("=")
            v = unquote(v)
            if k == "select":
                select = [c.strip() for c in v.split(",")]
            elif k == "order":
                order = v
            elif k == "limit":
                pass
            else:
                filtros.append((k, v))
        return filtros, select, order

    def _cumple(self, fila, k, v):
        x = fila.get(k)
        if v.startswith("eq."):
            return str(x) == v[3:]
        if v.startswith("in.("):
            return str(x) in v[4:-1].split(",")
        if v == "is.null":
            return x is None
        raise AssertionError(f"filtro no soportado en el fake: {k}={v}")

    def __call__(self, method, params="", body=None, tabla="conversaciones"):
        self.llamadas.append((method, tabla, params))
        filtros, select, order = self._filtros(params)
        filas = [f for f in self.t[tabla] if all(self._cumple(f, k, v) for k, v in filtros)]
        if method == "GET":
            if order:
                col, _, sentido = order.partition(".")
                filas = sorted(filas, key=lambda f: str(f.get(col) or ""), reverse=(sentido == "desc"))
            return [({c: f.get(c) for c in select} if select else dict(f)) for f in filas]
        if method == "POST":
            return [self.agregar(tabla, **dict(body))]
        if method == "PATCH":
            for f in filas:
                f.update(body)
            return [dict(f) for f in filas]
        if method == "DELETE":
            self.t[tabla] = [f for f in self.t[tabla] if f not in filas]
            if tabla == "proyectos":      # on delete cascade
                ids = {f["id"] for f in filas}
                self.t["proyecto_items"] = [i for i in self.t["proyecto_items"] if i["proyecto_id"] not in ids]
                for p in list(self.t["proyectos"]):
                    if p.get("padre_id") in ids:
                        self("DELETE", f"?id=eq.{p['id']}", tabla="proyectos")
            return [dict(f) for f in filas]
        raise AssertionError(method)


@pytest.fixture
def base(monkeypatch):
    fake = FakePostgrest()
    monkeypatch.setattr(db, "disponible", lambda: True)
    monkeypatch.setattr(db, "_req", fake)
    from api import cuentas
    h = {u: cuentas.hashear(f"clave-{u}") for u in ("franco", "lizzie")}      # el login mira la tabla primero (hash bcrypt)
    fake.agregar("usuarios", usuario="franco", nombre="Franco", email="franco@viviragradecidos.org", rol="admin", clave_hash=h["franco"])
    fake.agregar("usuarios", usuario="lizzie", nombre="Lizzie", email="lizzie@viviragradecidos.org", rol="creador", clave_hash=h["lizzie"])
    fake.agregar("usuarios", usuario="julian", nombre="Julián", email="julian@viviragradecidos.org", rol="creador")
    fake.agregar("usuarios", usuario="dormido", nombre="Baja", email="x@x.org", rol="creador", activo=False)
    fake.agregar("conversaciones", id="c1", usuario="franco", titulo="Gratitud", mensajes=[{"role": "user", "content": "hola"}], borrada=None)
    fake.agregar("conversaciones", id="c2", usuario="lizzie", titulo="De Lizzie", mensajes=[], borrada=None)
    fake.agregar("clips", id="k1", video_id="abc123def", titulo="Clip", formato="vertical", estado="listo", url="https://x/clip.mp4", pedido_por="franco")
    fake.agregar("publicaciones", id="p1", usuario="franco", canal="instagram", estado="borrador", titulo="", texto="Un texto " * 20, imagen_url="https://x/foto.jpg")
    return fake


def _como(cliente, usuario):
    """`logueado` y `cliente` son el MISMO TestClient (misma cookie): acá se cambia de persona."""
    r = cliente.post("/login", json={"usuario": usuario, "clave": f"clave-{usuario}"})
    assert r.status_code == 200, r.text
    return cliente


def _lizzie(cliente):
    return _como(cliente, "lizzie")


# ---------------- CRUD de proyectos y subcarpetas ----------------
def test_crear_listar_editar_borrar(logueado, base):
    r = logueado.post("/proyectos", json={"nombre": "  Campaña   gratitud ", "emoji": "🙏"})
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["nombre"] == "Campaña gratitud" and p["permiso"] == "dueño" and p["padre_id"] is None and p["emoji"] == "🙏"
    sub = logueado.post("/proyectos", json={"nombre": "Octubre", "padre_id": p["id"]}).json()
    assert sub["padre_id"] == p["id"]
    lista = logueado.get("/proyectos").json()
    assert [x["nombre"] for x in lista["proyectos"]] == ["Campaña gratitud", "Octubre"]
    # renombrar y mover: la raíz no puede ir adentro de su hija
    assert logueado.patch(f"/proyectos/{sub['id']}", json={"nombre": "Noviembre"}).json()["nombre"] == "Noviembre"
    assert logueado.patch(f"/proyectos/{p['id']}", json={"padre_id": sub["id"]}).status_code == 400
    assert logueado.patch(f"/proyectos/{p['id']}", json={"padre_id": p["id"]}).status_code == 400
    assert logueado.patch(f"/proyectos/{sub['id']}", json={"padre_id": ""}).json()["padre_id"] is None
    assert logueado.post("/proyectos", json={"nombre": "   "}).status_code == 400
    # ver: migas y subcarpetas
    logueado.patch(f"/proyectos/{sub['id']}", json={"padre_id": p["id"]})
    v = logueado.get(f"/proyectos/{sub['id']}").json()
    assert [m["nombre"] for m in v["migas"]] == ["Campaña gratitud", "Noviembre"] and v["permiso"] == "dueño"
    v = logueado.get(f"/proyectos/{p['id']}").json()
    assert [s["nombre"] for s in v["subcarpetas"]] == ["Noviembre"]
    # borrar la raíz se lleva la subcarpeta
    assert logueado.delete(f"/proyectos/{p['id']}").json()["ok"]
    assert logueado.get(f"/proyectos/{sub['id']}").status_code == 404
    assert logueado.get("/proyectos").json()["proyectos"] == []


def test_profundidad_maxima(logueado, base):
    padre = None
    for i in range(pr.PROFUNDIDAD_MAX):
        r = logueado.post("/proyectos", json={"nombre": f"n{i}", "padre_id": padre})
        assert r.status_code == 200, r.text
        padre = r.json()["id"]
    assert logueado.post("/proyectos", json={"nombre": "demasiado", "padre_id": padre}).status_code == 400


# ---------------- Ítems ----------------
def test_items_resumen_y_un_solo_proyecto(logueado, base):
    a = logueado.post("/proyectos", json={"nombre": "A"}).json()
    b = logueado.post("/proyectos", json={"nombre": "B"}).json()
    r = logueado.post(f"/proyectos/{a['id']}/items", json={"tipo": "conversacion", "item_id": "c1"})
    assert r.status_code == 200, r.text
    it = r.json()["item"]
    assert it["titulo"] == "Gratitud" and it["tipo"] == "conversacion" and it["propio"] and not r.json()["ya"]
    assert logueado.post(f"/proyectos/{a['id']}/items", json={"tipo": "conversacion", "item_id": "c1"}).json()["ya"]
    logueado.post(f"/proyectos/{a['id']}/items", json={"tipo": "recorte", "item_id": "k1"})
    logueado.post(f"/proyectos/{a['id']}/items", json={"tipo": "pieza", "item_id": "p1"})
    logueado.post(f"/proyectos/{a['id']}/items", json={"tipo": "imagen", "item_id": "https://x/compuesta.jpg", "datos": {"titulo": "Frase con logo"}})
    v = logueado.get(f"/proyectos/{a['id']}").json()
    por = {i["tipo"]: i for i in v["items"]}
    assert por["recorte"]["miniatura"].endswith("abc123def/hqdefault.jpg") and por["recorte"]["estado"] == "listo"
    assert por["pieza"]["miniatura"] == "https://x/foto.jpg" and por["pieza"]["titulo"].endswith("…") and por["pieza"]["canal"] == "instagram"
    assert por["imagen"]["titulo"] == "Frase con logo" and por["imagen"]["url"] == "https://x/compuesta.jpg"
    assert len(v["items"]) == 4
    # ubicaciones en la lista
    lista = logueado.get("/proyectos").json()
    assert lista["ubicaciones"]["conversacion"]["c1"] == a["id"] and lista["proyectos"][0]["n_items"] == 4
    # la misma conversación a B: se va de A
    logueado.post(f"/proyectos/{b['id']}/items", json={"tipo": "conversacion", "item_id": "c1"})
    assert {i["tipo"] for i in logueado.get(f"/proyectos/{a['id']}").json()["items"]} == {"recorte", "pieza", "imagen"}
    assert logueado.get("/proyectos").json()["ubicaciones"]["conversacion"]["c1"] == b["id"]
    # mover el recorte a B y quitar la pieza
    rec = por["recorte"]
    r = logueado.post(f"/proyectos/{a['id']}/items/{rec['id']}/mover", json={"proyecto_id": b["id"]})
    assert r.status_code == 200 and r.json()["item"]["proyecto_id"] == b["id"]
    assert logueado.delete(f"/proyectos/{a['id']}/items/{por['pieza']['id']}").json()["ok"]
    assert {i["tipo"] for i in logueado.get(f"/proyectos/{a['id']}").json()["items"]} == {"imagen"}
    assert logueado.delete(f"/proyectos/{a['id']}/items/{por['pieza']['id']}").status_code == 404
    # validaciones
    assert logueado.post(f"/proyectos/{a['id']}/items", json={"tipo": "conversacion", "item_id": "c2"}).status_code == 404   # de Lizzie, no compartida
    assert logueado.post(f"/proyectos/{a['id']}/items", json={"tipo": "recorte", "item_id": "zzz"}).status_code == 404
    assert logueado.post(f"/proyectos/{a['id']}/items", json={"tipo": "otro", "item_id": "x"}).status_code == 400
    assert logueado.post(f"/proyectos/{a['id']}/items", json={"tipo": "imagen", "item_id": "no-es-url"}).status_code == 400
    # quitar del proyecto no borra el original
    assert base.t["clips"][0]["id"] == "k1" and len(base.t["publicaciones"]) == 1


def test_item_borrado_sigue_listado(logueado, base):
    a = logueado.post("/proyectos", json={"nombre": "A"}).json()
    logueado.post(f"/proyectos/{a['id']}/items", json={"tipo": "recorte", "item_id": "k1"})
    base.t["clips"] = []
    v = logueado.get(f"/proyectos/{a['id']}").json()
    assert v["items"][0]["estado"] == "no_existe" and not v["items"][0]["existe"]


# ---------------- Compartir ----------------
def test_compartir_proyecto_ver_y_editar(logueado, base, cliente):
    a = logueado.post("/proyectos", json={"nombre": "Compartida"}).json()
    sub = logueado.post("/proyectos", json={"nombre": "Sub", "padre_id": a["id"]}).json()
    logueado.post(f"/proyectos/{a['id']}/items", json={"tipo": "conversacion", "item_id": "c1"})
    assert logueado.put(f"/compartidos/proyecto/{a['id']}", json={"usuario": "nadie", "permiso": "ver"}).status_code == 404
    assert logueado.put(f"/compartidos/proyecto/{a['id']}", json={"usuario": "franco"}).status_code == 400
    r = logueado.put(f"/compartidos/proyecto/{a['id']}", json={"usuario": "Lizzie", "permiso": "ver"})
    assert r.status_code == 200 and r.json() == {"ok": True, "usuario": "lizzie", "permiso": "ver", "nuevo": True}
    con = logueado.get(f"/compartidos/proyecto/{a['id']}").json()
    assert con["dueno"] and con["con"][0]["usuario"] == "lizzie" and con["con"][0]["nombre"] == "Lizzie"
    assert logueado.get("/proyectos").json()["proyectos"][0]["compartido_con_n"] == 1

    # Lizzie lo ve (con la subcarpeta, permiso heredado) pero no lo cambia
    _lizzie(cliente)
    lista = cliente.get("/proyectos").json()["proyectos"]
    assert {(p["nombre"], p["permiso"], p.get("raiz_compartida")) for p in lista} == {("Compartida", "ver", True), ("Sub", "ver", False)}
    assert lista[0]["compartido_por"] == "franco"
    v = cliente.get(f"/proyectos/{a['id']}").json()
    assert v["permiso"] == "ver" and v["items"][0]["titulo"] == "Gratitud" and not v["items"][0]["propio"] and v["compartido_con"] == []
    assert cliente.patch(f"/proyectos/{a['id']}", json={"nombre": "x"}).status_code == 403
    assert cliente.post(f"/proyectos/{sub['id']}/items", json={"tipo": "conversacion", "item_id": "c2"}).status_code == 403
    assert cliente.delete(f"/proyectos/{a['id']}").status_code == 403
    assert cliente.put(f"/compartidos/proyecto/{a['id']}", json={"usuario": "julian"}).status_code == 403
    conmigo = cliente.get("/compartidos-conmigo").json()
    assert [p["nombre"] for p in conmigo["proyectos"]] == ["Compartida"] and conmigo["proyectos"][0]["n_items"] == 1
    # la conversación de adentro se abre en el chat en modo lectura
    c = cliente.get("/conversaciones/c1").json()
    assert c["compartida"] == {"por": "franco", "permiso": "ver"}
    assert cliente.post("/conversaciones/c1/mensajes", json={"texto": "hola"}).status_code == 404

    # Franco sube el permiso a editar: Lizzie agrega a la subcarpeta y renombra; sigue sin poder borrar ni compartir
    _como(logueado, "franco")
    logueado.put(f"/compartidos/proyecto/{a['id']}", json={"usuario": "lizzie", "permiso": "editar"})
    assert len(base.t["compartidos"]) == 1
    _lizzie(cliente)
    assert cliente.post(f"/proyectos/{sub['id']}/items", json={"tipo": "conversacion", "item_id": "c2"}).status_code == 200
    assert cliente.patch(f"/proyectos/{sub['id']}", json={"nombre": "Sub de Lizzie"}).json()["nombre"] == "Sub de Lizzie"
    assert cliente.patch(f"/proyectos/{sub['id']}", json={"padre_id": ""}).status_code == 403
    assert cliente.delete(f"/proyectos/{a['id']}").status_code == 403
    assert cliente.get("/conversaciones/c1").json()["compartida"]["permiso"] == "editar"
    # ahora Franco ve la conversación de Lizzie por el proyecto
    _como(logueado, "franco")
    assert logueado.get("/conversaciones/c2").json()["compartida"] == {"por": "lizzie", "permiso": "editar"}

    # descompartir: Lizzie se saca sola; después ya no ve nada
    _lizzie(cliente)
    assert cliente.delete(f"/compartidos/proyecto/{a['id']}/julian").status_code == 403
    assert cliente.delete(f"/compartidos/proyecto/{a['id']}/lizzie").json()["ok"]
    assert cliente.get(f"/proyectos/{a['id']}").status_code == 404
    assert cliente.get("/compartidos-conmigo").json()["proyectos"] == []


def test_compartir_conversacion_suelta(logueado, base, cliente):
    assert logueado.put("/compartidos/conversacion/c2", json={"usuario": "julian"}).status_code == 404   # no es de Franco
    r = logueado.put("/compartidos/conversacion/c1", json={"usuario": "julian", "permiso": "ver"})
    assert r.status_code == 200
    cliente.post("/login", json={"usuario": "lizzie", "clave": "clave-lizzie"})
    assert cliente.get("/conversaciones/c1").status_code == 404      # con Lizzie no
    base.agregar("usuarios", usuario="julian2")
    base.t["compartidos"][0]["con_usuario"] = "lizzie"               # (simulamos que era con Lizzie)
    c = cliente.get("/conversaciones/c1").json()
    assert c["compartida"] == {"por": "franco", "permiso": "ver"} and c["titulo"] == "Gratitud"
    conmigo = cliente.get("/compartidos-conmigo").json()
    assert conmigo["conversaciones"][0]["id"] == "c1" and conmigo["conversaciones"][0]["compartido_por"] == "franco"
    # la puede guardar en una carpeta suya (la ve), pero no renombrarla (chat_rutas sigue exigiendo que sea propia)
    a = cliente.post("/proyectos", json={"nombre": "Mías"}).json()
    assert cliente.post(f"/proyectos/{a['id']}/items", json={"tipo": "conversacion", "item_id": "c1"}).status_code == 200
    assert cliente.patch("/conversaciones/c1", json={"titulo": "x"}).status_code == 404


def test_buscar_usuarios(logueado, base):
    r = logueado.get("/usuarios/buscar?q=li")
    assert [u["usuario"] for u in r.json()] == ["julian", "lizzie"]     # «julian@…» y «Lizzie»; sin «dormido» (inactivo) ni franco
    assert [u["usuario"] for u in logueado.get("/usuarios/buscar?q=viviragradecidos").json()] == ["julian", "lizzie"]
    assert logueado.get("/usuarios/buscar?q=zzz").json() == []


def test_sin_supabase_y_sin_sesion(logueado, cliente):
    assert logueado.get("/proyectos").json() == {"proyectos": [], "ubicaciones": {}}
    assert logueado.post("/proyectos", json={"nombre": "x"}).status_code == 503
    assert logueado.get("/compartidos-conmigo").json() == {"proyectos": [], "conversaciones": []}
    cliente.cookies.clear()
    assert cliente.get("/proyectos").status_code == 401
    assert cliente.get("/compartidos-conmigo").status_code == 401
    assert cliente.get("/usuarios/buscar").status_code == 401
