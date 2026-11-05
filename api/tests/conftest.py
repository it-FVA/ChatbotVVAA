"""Entorno de prueba: sin secrets.toml, sin Supabase, sin cargar el corpus, usuarios fijos (en una tabla simulada en memoria).
Todo se define ANTES de importar api.main (que carga la configuración al importarse)."""
import os, sys
import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

os.environ["FVA_SECRETS"] = "-"
os.environ["API_CARGAR_CORPUS"] = "0"
os.environ["API_PAPELERA"] = "0"       # (5/11) la papelera periódica no arranca en las pruebas
os.environ["SESION_SECRETO"] = "secreto-de-prueba"
os.environ["BCRYPT_RONDAS"] = "4"
os.environ["DOMINIO_FVA"] = "viviragradecidos.org"
for k in ("SUPABASE_URL", "SUPABASE_KEY", "GOOGLE_CLIENT_ID"):
    os.environ.pop(k, None)
os.environ.setdefault("OPENAI_API_KEY", "")

from fastapi.testclient import TestClient   # noqa: E402
import db                                   # noqa: E402
from api import cuentas                     # noqa: E402
from api.main import app                    # noqa: E402
from tabla_usuarios import instalar_base    # noqa: E402


def pytest_configure(config):
    config.addinivalue_line("markers", "real: llama a OpenAI de verdad (necesita OPENAI_API_KEY; se saltea si falta)")


@pytest.fixture(autouse=True)
def tabla_usuarios(request, monkeypatch):
    """Desde el 3/11 las cuentas viven solo en la tabla `usuarios`: cada prueba tiene una tabla en memoria con franco (admin),
    lizzie y gratefulness (creadoras). Sin tocar db.disponible(): lo demás sigue respondiendo como sin Supabase.
    Las pruebas de un módulo con TABLA_PROPIA = True (test_cuentas) arman su propia tabla."""
    if getattr(request.module, "TABLA_PROPIA", False):
        yield None
        return
    t = instalar_base(monkeypatch, db, cuentas)
    yield t
    cuentas.olvidar()


@pytest.fixture
def cliente():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def logueado(cliente):
    r = cliente.post("/login", json={"usuario": "franco", "clave": "clave-franco"})
    assert r.status_code == 200, r.text
    return cliente
