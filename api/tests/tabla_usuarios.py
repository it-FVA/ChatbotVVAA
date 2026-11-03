"""La tabla `usuarios` y la lista blanca simuladas en memoria: las usan test_cuentas, el conftest y servidor_simulado."""


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

    def poner_rol(self, usuario, rol):
        """Atajo de las pruebas: cambia el rol de una cuenta (y la caché de api.cuentas la relee en el próximo login)."""
        fila = next(f for f in self.filas.values() if f["usuario"] == usuario)
        fila["rol"] = rol

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

NOMBRES_DB = ("usuario_por_nombre", "usuario_por_email", "usuario_por_id", "listar_usuarios", "crear_usuario", "actualizar_usuario",
              "borrar_usuario", "marcar_login", "renombrar_usuario_en_tablas", "registrar_cambio_usuario", "listar_cambios_usuarios",
              "autorizado", "listar_autorizados", "agregar_autorizado", "quitar_autorizado")

# Las cuentas de las pruebas que no son de cuentas: franco (admin), lizzie y gratefulness (creadoras). Desde el 3/11 viven en la
# tabla (ya no hay contraseñas en secrets ni listas APROBADORES/ADMINS).
CUENTAS_BASE = (("franco", "admin", "clave-franco"), ("lizzie", "creador", "clave-lizzie"), ("gratefulness", "creador", "clave-g"))


def sembrar_base(t, hashear):
    for usuario, rol, clave in CUENTAS_BASE:
        t.crear_usuario(usuario, rol=rol, clave_hash=hashear(clave), creado_por="test")


def instalar_base(monkeypatch, db, cuentas):
    """Una Tabla con las cuentas base, enchufada a db y a api.cuentas SIN tocar db.disponible() (lo demás sigue como sin Supabase)."""
    t = Tabla()
    sembrar_base(t, cuentas.hashear)
    monkeypatch.setattr(cuentas, "tabla_disponible", lambda: True)
    for nombre in NOMBRES_DB:
        monkeypatch.setattr(db, nombre, getattr(t, nombre))
    cuentas.olvidar()
    return t
