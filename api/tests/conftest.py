"""Entorno de prueba: sin secrets.toml, sin Supabase, sin cargar el corpus, usuarios fijos.
Todo se define ANTES de importar api.main (que carga la configuración al importarse)."""
import os, sys, json
import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

os.environ["FVA_SECRETS"] = "-"
os.environ["API_CARGAR_CORPUS"] = "0"
os.environ["SESION_SECRETO"] = "secreto-de-prueba"
os.environ["BCRYPT_RONDAS"] = "4"
os.environ["USUARIOS_JSON"] = json.dumps({"franco": "clave-franco", "lizzie": "clave-lizzie", "gratefulness": "clave-g"})
os.environ["APROBADORES"] = "franco"
os.environ["DOMINIO_FVA"] = "viviragradecidos.org"
for k in ("SUPABASE_URL", "SUPABASE_KEY", "GOOGLE_CLIENT_ID"):
    os.environ.pop(k, None)
os.environ.setdefault("OPENAI_API_KEY", "")

from fastapi.testclient import TestClient   # noqa: E402
from api.main import app                    # noqa: E402


def pytest_configure(config):
    config.addinivalue_line("markers", "real: llama a OpenAI de verdad (necesita OPENAI_API_KEY; se saltea si falta)")


@pytest.fixture
def cliente():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def logueado(cliente):
    r = cliente.post("/login", json={"usuario": "franco", "clave": "clave-franco"})
    assert r.status_code == 200, r.text
    return cliente
