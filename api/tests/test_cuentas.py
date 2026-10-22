"""Pruebas de la gestión de usuarios (22/10) con una tabla `usuarios` y una lista blanca SIMULADAS en memoria
(monkeypatch sobre db): login por tabla y fallback a secrets, «primera vez», cambio y reset de clave,
roles, protección del último admin, lista blanca, renombrar, Google que crea la fila."""
import pytest

import db
import api.auth as auth
import api.cuentas as cuentas


class Tabla:
    """Imita las funciones de db que usa api/cuentas.py y api/auth.py."""

    def __init__(self):
        self.filas = {}
        self.lista = {}
        self.cambios = []
        self.renombres = []
        self.n = 0

    def _nuevo_id(self):
        self.n += 1
        return f"id-{self.n}"

    # usuarios
    def usuario_por_nombre(self, u):
        return next((dict(f) for f in self.filas.values() if f["usuario"] == u.strip().lower()), None)

    def usuario_por_email(self, e):
        return next((dict(f) for f in self.filas.values() if (f.get("email") or "").lower() == e.strip().lower()), None)

    def usuario_por_id(self, i):
        return dict(self.filas[i]) if i in self.filas else None

    def listar_usuarios(self, limite=500):
        return [dict(f) for f in sorted(self.filas.values(), key=lambda f: f["usuario"])]

    def crear_usuario(self, usuario, email=None, nombre=None, rol="creador", clave_hash=None, clave_temporal=False, creado_por=None):
        i = self._nuevo_id()
        self.filas[i] = {"id": i, "usuario": usuario.lower(), "email": (email or "").lower() or None, "nombre": nombre, "rol": rol,
                         "clave_hash": clave_hash, "clave_temporal": clave_temporal, "activo": True, "creado": "2026-10-22T00:00:00Z",
                         "actualizado": None, "ultimo_login": None, "creado_por": creado_por}
        return dict(self.filas[i])

    def actualizar_usuario(self, i, campos):
        self.filas[i].update(campos)
        return dict(self.filas[i])

    def borrar_usuario(self, i):
        self.filas.pop(i, None)
        return []

    def marcar_login(self, i):
        self.filas[i]["ultimo_login"] = "2026-10-22T11:30:00Z"

    def renombrar_usuario_en_tablas(self, viejo, nuevo):
        self.renombres.append((viejo, nuevo))
        return {"conversaciones": 2, "publicaciones": 1, "clips": 0, "uso_openai": 0}

    def registrar_cambio_usuario(self, quien, accion, usuario=None, detalle=None):
        self.cambios.append((quien, accion, usuario, detalle))

    def listar_cambios_usuarios(self, limite=100):
        return [{"id": i, "cuando": "2026-10-22T10:00:00Z", "quien": q, "accion": a, "usuario": u, "detalle": d}
                for i, (q, a, u, d) in reversed(list(enumerate(self.cambios)))]

    # lista blanca
    def autorizado(self, email):
        return self.lista.get(email.strip().lower())

    def listar_autorizados(self, limite=200):
        return list(self.lista.values())

    def agregar_autorizado(self, email, rol, agregado_por, nota=None):
        self.lista[email.lower()] = {"email": email.lower(), "rol": rol, "agregado_por": agregado_por, "nota": nota}
        return [self.lista[email.lower()]]

    def quitar_autorizado(self, email):
        self.lista.pop(email.lower(), None)
        return []


@pytest.fixture
def tabla(monkeypatch):
    t = Tabla()
    monkeypatch.setattr(db, "disponible", lambda: True)
    for nombre in ("usuario_por_nombre", "usuario_por_email", "usuario_por_id", "listar_usuarios", "crear_usuario", "actualizar_usuario",
                   "borrar_usuario", "marcar_login", "renombrar_usuario_en_tablas", "registrar_cambio_usuario", "listar_cambios_usuarios",
                   "autorizado", "listar_autorizados", "agregar_autorizado", "quitar_autorizado"):
        monkeypatch.setattr(db, nombre, getattr(t, nombre))
    cuentas.olvidar()
    # dos cuentas en la tabla: beto (admin, clave 'Clave-beto1') y pato (creador, clave temporal 'Temp-1234')
    t.crear_usuario("beto", email="beto@viviragradecidos.org", nombre="Beto", rol="admin", clave_hash=cuentas.hashear("Clave-beto1"), creado_por="test")
    t.crear_usuario("pato", email="pato@gmail.com", nombre="Pato", rol="creador", clave_hash=cuentas.hashear("Temp-1234"), clave_temporal=True, creado_por="test")
    yield t
    cuentas.olvidar()


def _entrar(cliente, usuario, clave):
    r = cliente.post("/login", json={"usuario": usuario, "clave": clave})
    assert r.status_code == 200, r.text
    return r.json()


# ---------------- Login ----------------
def test_login_por_tabla_y_rol_de_la_tabla(cliente, tabla):
    """beto NO está en USUARIOS_JSON ni en APROBADORES del test: entra por la tabla y es admin porque la tabla lo dice."""
    d = _entrar(cliente, "beto", "Clave-beto1")
    assert d["rol"]["nombre"] == "admin" and d["rol"]["aprueba"] and d["en_tabla"] and d["email"] == "beto@viviragradecidos.org"
    assert d["debe_cambiar_clave"] is False and d["tiene_clave"] is True
    assert tabla.filas["id-1"]["ultimo_login"]
    assert cliente.post("/login", json={"usuario": "beto", "clave": "otra"}).status_code == 401
    assert cliente.post("/login", json={"usuario": "BETO ", "clave": "Clave-beto1"}).status_code == 200   # sin distinguir mayúsculas


def test_fallback_a_secrets(cliente, tabla):
    """franco sigue solo en USUARIOS_JSON: entra como hasta ahora, con el rol de las listas (APROBADORES=franco, ADMINS default)."""
    d = _entrar(cliente, "franco", "clave-franco")
    assert d["rol"]["admin"] is True and d["en_tabla"] is False


def test_rol_de_la_tabla_manda_sobre_las_listas(cliente, tabla, monkeypatch):
    """Si 'lizzie' está en la tabla como creadora, aunque ADMINS la nombre, vale la tabla."""
    monkeypatch.setenv("ADMINS", "lizzie")
    tabla.crear_usuario("lizzie", rol="creador", clave_hash=cuentas.hashear("Clave-lizzie1"))
    d = _entrar(cliente, "lizzie", "Clave-lizzie1")
    assert d["rol"]["nombre"] == "creador de contenido" and d["rol"]["admin"] is False
    assert cliente.get("/admin/usuarios").status_code == 403


def test_clave_temporal_obliga_a_cambiarla(cliente, tabla):
    d = _entrar(cliente, "pato", "Temp-1234")
    assert d["debe_cambiar_clave"] is True
    r = cliente.post("/cuentas/clave", json={"actual": "mala", "nueva": "Nueva-clave1"})
    assert r.status_code == 401
    assert cliente.post("/cuentas/clave", json={"actual": "Temp-1234", "nueva": "corta"}).status_code == 400
    assert cliente.post("/cuentas/clave", json={"actual": "Temp-1234", "nueva": "12345678"}).status_code == 400
    r = cliente.post("/cuentas/clave", json={"actual": "Temp-1234", "nueva": "Nueva-clave1"})
    assert r.status_code == 200, r.text
    assert cliente.get("/yo").json()["debe_cambiar_clave"] is False
    assert cliente.post("/login", json={"usuario": "pato", "clave": "Temp-1234"}).status_code == 401
    assert _entrar(cliente, "pato", "Nueva-clave1")["debe_cambiar_clave"] is False
    assert ("pato", "clave_propia", "pato", {}) in tabla.cambios


def test_cambiar_clave_usuario_de_secrets(logueado, tabla):
    assert logueado.post("/cuentas/clave", json={"actual": "clave-franco", "nueva": "Nueva-clave1"}).status_code == 409


def test_cuenta_desactivada(cliente, tabla):
    tabla.filas["id-2"]["activo"] = False
    assert cliente.post("/login", json={"usuario": "pato", "clave": "Temp-1234"}).status_code == 403


def test_sin_clave_avisa(cliente, tabla):
    tabla.crear_usuario("nuevo", email="nuevo@viviragradecidos.org")
    r = cliente.post("/login", json={"usuario": "nuevo", "clave": "x"})
    assert r.status_code == 409 and "Primera vez" in r.json()["detail"]


# ---------------- Primera vez ----------------
def test_primera_vez_dominio(cliente, tabla):
    r = cliente.post("/cuentas/verificar", json={"email": "Ana@ViVirAgradecidos.org"})
    assert r.status_code == 200 and r.json()["motivo"] == "dominio" and r.json()["usuario"] is None
    assert cliente.post("/cuentas/primera-vez", json={"email": "ana@viviragradecidos.org", "usuario": "Ana", "clave": "Clave-ana1"}).status_code == 200
    f = tabla.usuario_por_nombre("ana")
    assert f["rol"] == "creador" and f["email"] == "ana@viviragradecidos.org" and f["clave_hash"] and f["creado_por"] == "primera_vez"
    assert cliente.get("/yo").json()["usuario"] == "ana"
    # el mismo email no puede crear otra cuenta; el mismo usuario tampoco
    assert cliente.post("/cuentas/primera-vez", json={"email": "ana@viviragradecidos.org", "usuario": "ana2", "clave": "Clave-ana1"}).status_code == 409
    assert cliente.post("/cuentas/primera-vez", json={"email": "otra@viviragradecidos.org", "usuario": "ana", "clave": "Clave-ana1"}).status_code == 409
    # tampoco un usuario que sigue en secrets
    assert cliente.post("/cuentas/primera-vez", json={"email": "otra@viviragradecidos.org", "usuario": "franco", "clave": "Clave-ana1"}).status_code == 409


def test_primera_vez_lista_blanca_con_rol(cliente, tabla):
    tabla.agregar_autorizado("julian@gmail.com", "aprobador", "franco", nota="editor")
    r = cliente.post("/cuentas/primera-vez", json={"email": "julian@gmail.com", "usuario": "julian", "clave": "Clave-julian1"})
    assert r.status_code == 200 and r.json()["rol"]["nombre"] == "aprobador"


def test_primera_vez_no_permitido(cliente, tabla):
    r = cliente.post("/cuentas/verificar", json={"email": "intruso@gmail.com"})
    assert r.status_code == 403 and "lista" not in r.json()["detail"].lower().replace("no está habilitado", "")
    assert cliente.post("/cuentas/primera-vez", json={"email": "intruso@gmail.com", "usuario": "intruso", "clave": "Clave-intruso1"}).status_code == 403
    assert cliente.post("/cuentas/verificar", json={"email": "no-es-email"}).status_code == 400


def test_primera_vez_reglas_de_usuario_y_clave(cliente, tabla):
    base = {"email": "x@viviragradecidos.org"}
    assert cliente.post("/cuentas/primera-vez", json=dict(base, usuario="ab", clave="Clave-xx11")).status_code == 400
    assert cliente.post("/cuentas/primera-vez", json=dict(base, usuario="con espacio", clave="Clave-xx11")).status_code == 400
    assert cliente.post("/cuentas/primera-vez", json=dict(base, usuario="bien", clave="soloLetras")).status_code == 400
    assert cliente.post("/cuentas/primera-vez", json=dict(base, usuario="bien", clave="Clave-xx11")).status_code == 200


def test_primera_vez_cuenta_sin_clave_dejada_por_admin(cliente, tabla):
    """Un admin crea 'maria' sin clave con su email; María la crea desde «Primera vez» (el usuario ya está fijado)."""
    tabla.crear_usuario("maria", email="maria@gmail.com", rol="aprobador", creado_por="beto")
    r = cliente.post("/cuentas/verificar", json={"email": "maria@gmail.com"})
    assert r.json() == {"permitido": True, "motivo": "cuenta", "usuario": "maria", "sin_clave": True, "mensaje": None}
    r = cliente.post("/cuentas/primera-vez", json={"email": "maria@gmail.com", "usuario": "ignorado", "clave": "Clave-maria1"})
    assert r.status_code == 200 and r.json()["usuario"] == "maria" and r.json()["rol"]["nombre"] == "aprobador"
    # ya con clave: verificar avisa que entre por el login
    assert "ya tiene cuenta" in cliente.post("/cuentas/verificar", json={"email": "maria@gmail.com"}).json()["mensaje"]


# ---------------- Google crea la fila ----------------
def test_google_crea_la_fila_con_rol_de_la_lista(cliente, tabla, monkeypatch):
    tabla.agregar_autorizado("lu@gmail.com", "admin", "beto")
    monkeypatch.setattr(auth, "verificar_google", lambda t: "lu@gmail.com")
    r = cliente.post("/login/google", json={"id_token": "x"})
    assert r.status_code == 200 and r.json()["usuario"] == "lu@gmail.com" and r.json()["rol"]["admin"] is True and r.json()["en_tabla"]
    f = tabla.usuario_por_email("lu@gmail.com")
    assert f["rol"] == "admin" and f["clave_hash"] is None and f["creado_por"] == "google"
    # segunda vez: no crea otra
    cliente.post("/login/google", json={"id_token": "x"})
    assert len([f for f in tabla.filas.values() if f["email"] == "lu@gmail.com"]) == 1


def test_google_vincula_usuario_viejo_del_dominio(cliente, tabla, monkeypatch):
    """beto está en la tabla con email; 'juli' está sin email: juli@dominio queda vinculado a 'juli'."""
    tabla.crear_usuario("juli", rol="aprobador", clave_hash=cuentas.hashear("Clave-juli1"))
    monkeypatch.setattr(auth, "verificar_google", lambda t: "juli@viviragradecidos.org")
    r = cliente.post("/login/google", json={"id_token": "x"})
    assert r.status_code == 200 and r.json()["usuario"] == "juli" and r.json()["rol"]["nombre"] == "aprobador"
    assert tabla.usuario_por_nombre("juli")["email"] == "juli@viviragradecidos.org"


def test_google_cuenta_existente_entra_aunque_no_este_en_la_lista(cliente, tabla, monkeypatch):
    monkeypatch.setattr(auth, "verificar_google", lambda t: "pato@gmail.com")
    r = cliente.post("/login/google", json={"id_token": "x"})
    assert r.status_code == 200 and r.json()["usuario"] == "pato" and r.json()["admitido_por"] == "cuenta"
    tabla.filas["id-2"]["activo"] = False
    assert cliente.post("/login/google", json={"id_token": "x"}).status_code == 403


def test_google_rechazado(cliente, tabla, monkeypatch):
    monkeypatch.setattr(auth, "verificar_google", lambda t: "nadie@gmail.com")
    assert cliente.post("/login/google", json={"id_token": "x"}).status_code == 403
    assert tabla.usuario_por_email("nadie@gmail.com") is None


# ---------------- Administración ----------------
@pytest.fixture
def admin(cliente, tabla):
    _entrar(cliente, "beto", "Clave-beto1")
    return cliente


def test_admin_solo_admins(cliente, tabla):
    _entrar(cliente, "pato", "Temp-1234")
    for ruta in ("/admin/usuarios", "/admin/lista-blanca", "/admin/cambios"):
        assert cliente.get(ruta).status_code == 403
    cliente.post("/logout")
    assert cliente.get("/admin/usuarios").status_code == 401


def test_admin_lista_usuarios(admin, tabla):
    d = admin.get("/admin/usuarios").json()
    assert [u["usuario"] for u in d["usuarios"]] == ["beto", "pato"]
    assert all("clave_hash" not in u for u in d["usuarios"]) and d["usuarios"][0]["tiene_clave"] is True
    assert d["en_secrets"] == ["franco", "gratefulness", "lizzie"]   # todavía no importados


def test_admin_crear_y_borrar(admin, tabla):
    r = admin.post("/admin/usuarios", json={"usuario": "nueva", "email": "nueva@gmail.com", "nombre": "Nueva", "rol": "aprobador", "clave": "temporal"})
    assert r.status_code == 201, r.text
    temporal = r.json()["clave_temporal"]
    assert temporal and len(temporal) == 12 and r.json()["usuario"]["clave_temporal"] is True
    d = admin.post("/login", json={"usuario": "nueva", "clave": temporal}).json()     # la temporal sirve para entrar...
    assert d["debe_cambiar_clave"] is True                                            # ...pero obliga a cambiarla
    _entrar(admin, "beto", "Clave-beto1")
    assert admin.post("/admin/usuarios", json={"usuario": "nueva", "rol": "creador"}).status_code == 409
    assert admin.post("/admin/usuarios", json={"usuario": "franco", "rol": "creador"}).status_code == 409   # existe en secrets
    assert admin.post("/admin/usuarios", json={"usuario": "otra", "email": "nueva@gmail.com"}).status_code == 409
    r = admin.post("/admin/usuarios", json={"usuario": "sinclave", "email": "s@viviragradecidos.org", "rol": "creador"})
    assert r.status_code == 201 and r.json()["clave_temporal"] is None and r.json()["usuario"]["tiene_clave"] is False
    uid = r.json()["usuario"]["id"]
    assert admin.delete(f"/admin/usuarios/{uid}").status_code == 200
    assert tabla.usuario_por_nombre("sinclave") is None
    assert admin.delete(f"/admin/usuarios/{uid}").status_code == 404
    assert [c[1] for c in tabla.cambios if c[0] == "beto"] == ["crear", "crear", "borrar"]


def test_admin_cambiar_rol_activar_y_editar(admin, tabla):
    r = admin.patch("/admin/usuarios/id-2", json={"rol": "aprobador", "nombre": "Patricio", "email": "patricio@gmail.com"})
    assert r.status_code == 200 and r.json()["usuario"]["rol"] == "aprobador" and r.json()["usuario"]["nombre"] == "Patricio"
    assert admin.patch("/admin/usuarios/id-2", json={"rol": "jefe"}).status_code == 400
    assert admin.patch("/admin/usuarios/id-2", json={"email": "beto@viviragradecidos.org"}).status_code == 409
    # desactivar: pato ya no entra ni con sesión abierta
    assert admin.patch("/admin/usuarios/id-2", json={"activo": False}).json()["usuario"]["activo"] is False
    assert admin.post("/login", json={"usuario": "pato", "clave": "Temp-1234"}).status_code == 403
    assert admin.patch("/admin/usuarios/id-2", json={"activo": True}).json()["usuario"]["activo"] is True
    acciones = [c[1] for c in tabla.cambios if c[0] == "beto"]
    assert acciones == ["rol", "desactivar", "activar"]


def test_admin_no_se_toca_a_si_mismo_ni_al_ultimo_admin(admin, tabla):
    assert admin.patch("/admin/usuarios/id-1", json={"rol": "creador"}).status_code == 400
    assert admin.patch("/admin/usuarios/id-1", json={"activo": False}).status_code == 400
    assert admin.delete("/admin/usuarios/id-1").status_code == 400
    assert admin.patch("/admin/usuarios/id-1", json={"nombre": "Beto R."}).status_code == 200     # esto sí
    # otro admin: no se lo puede bajar si es el único... beto sigue activo, así que sí se puede bajar a 'pato' admin
    admin.patch("/admin/usuarios/id-2", json={"rol": "admin"})
    assert admin.patch("/admin/usuarios/id-2", json={"rol": "creador"}).status_code == 200
    # pato admin y beto desactivado por pato → beto sería el último... probamos desde pato: beto es el único admin activo además de pato
    admin.patch("/admin/usuarios/id-2", json={"rol": "admin"})
    _entrar(admin, "pato", "Temp-1234")
    assert admin.patch("/admin/usuarios/id-1", json={"activo": False}).status_code == 200    # quedan pato
    assert admin.patch("/admin/usuarios/id-1", json={"rol": "creador"}).status_code == 200   # beto inactivo: no cuenta
    _entrar(admin, "pato", "Temp-1234")
    assert admin.patch("/admin/usuarios/id-2", json={"rol": "creador"}).status_code == 400   # pato: uno mismo


def test_admin_reset_clave(admin, tabla):
    r = admin.post("/admin/usuarios/id-2/clave", json={"modo": "temporal"})
    temporal = r.json()["clave_temporal"]
    assert r.status_code == 200 and temporal and tabla.filas["id-2"]["clave_temporal"] is True
    assert admin.post("/login", json={"usuario": "pato", "clave": "Temp-1234"}).status_code == 401
    assert admin.post("/login", json={"usuario": "pato", "clave": temporal}).json()["debe_cambiar_clave"] is True
    _entrar(admin, "beto", "Clave-beto1")
    r = admin.post("/admin/usuarios/id-2/clave", json={"modo": "sin_clave"})
    assert r.status_code == 200 and r.json()["clave_temporal"] is None and tabla.filas["id-2"]["clave_hash"] is None
    assert admin.post("/login", json={"usuario": "pato", "clave": temporal}).status_code == 409
    assert admin.post("/admin/usuarios/id-2/clave", json={"modo": "otro"}).status_code == 400
    # sin email no se puede dejar «sin clave»
    tabla.crear_usuario("sinmail", clave_hash=cuentas.hashear("Clave-sin1"))
    assert admin.post("/admin/usuarios/id-3/clave", json={"modo": "sin_clave"}).status_code == 400
    assert all(temporal not in str(c) for c in tabla.cambios)    # la clave nunca va al registro


def test_admin_renombrar(admin, tabla):
    r = admin.post("/admin/usuarios/id-2/renombrar", json={"usuario": "Patricio"})
    assert r.status_code == 200 and r.json()["usuario"]["usuario"] == "patricio" and r.json()["tablas"]["conversaciones"] == 2
    assert tabla.renombres == [("pato", "patricio")]
    assert admin.post("/admin/usuarios/id-2/renombrar", json={"usuario": "beto"}).status_code == 409
    assert admin.post("/admin/usuarios/id-2/renombrar", json={"usuario": "franco"}).status_code == 409
    assert admin.post("/admin/usuarios/id-2/renombrar", json={"usuario": "a b"}).status_code == 400
    _entrar(admin, "patricio", "Temp-1234")


def test_admin_lista_blanca(admin, tabla):
    assert admin.get("/admin/lista-blanca").json() == {"emails": [], "dominio": "viviragradecidos.org"}
    r = admin.put("/admin/lista-blanca", json={"email": "Nuevo@Gmail.com", "rol": "aprobador", "nota": "diseñador"})
    assert r.status_code == 200 and tabla.lista["nuevo@gmail.com"]["rol"] == "aprobador" and tabla.lista["nuevo@gmail.com"]["nota"] == "diseñador"
    assert admin.put("/admin/lista-blanca", json={"email": "nuevo@gmail.com", "rol": "admin"}).status_code == 200
    assert admin.put("/admin/lista-blanca", json={"email": "nuevo@gmail.com", "rol": "x"}).status_code == 400
    assert admin.put("/admin/lista-blanca", json={"email": "no-es-email", "rol": "creador"}).status_code == 400
    assert admin.delete("/admin/lista-blanca/nuevo@gmail.com").status_code == 200 and tabla.lista == {}
    assert [c[1] for c in tabla.cambios if c[0] == "beto"] == ["lista_alta", "lista_editar", "lista_baja"]
    assert len(admin.get("/admin/cambios").json()) == 3


def test_sin_migracion_da_503(admin, monkeypatch):
    def rompe(*a, **k):
        raise RuntimeError('Supabase 404: {"code":"PGRST205","message":"Could not find the table public.usuarios"}')
    monkeypatch.setattr(db, "listar_usuarios", rompe)
    r = admin.get("/admin/usuarios")
    assert r.status_code == 503 and "migración" in r.json()["detail"]


def test_hash_nunca_en_claro(tabla):
    h = cuentas.hashear("Clave-beto1")
    assert h.startswith("$2") and "Clave-beto1" not in h
    assert cuentas.verificar_hash("Clave-beto1", h) and not cuentas.verificar_hash("otra", h) and not cuentas.verificar_hash("x", None)
