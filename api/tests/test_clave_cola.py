"""La clave acotada de la cola (revisión 3/11, 5.3 punto 21): el JWT que se genera, cuándo la usa db y qué permisos da el SQL."""
import base64, hashlib, hmac, json, os, re
import importlib.util

import db
import api.migrar as migrar

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _generador():
    spec = importlib.util.spec_from_file_location("generar_clave_cola", os.path.join(RAIZ, "api", "generar_clave_cola.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _decodificar(parte):
    return json.loads(base64.urlsafe_b64decode(parte + "=" * (-len(parte) % 4)))


def test_el_jwt_trae_el_rol_cola_y_la_firma_es_la_del_secreto():
    token = _generador().generar("secreto-de-prueba", ahora=1_000_000)
    cab, cuerpo, firma = token.split(".")
    assert _decodificar(cab) == {"alg": "HS256", "typ": "JWT"}
    datos = _decodificar(cuerpo)
    assert datos["role"] == "cola" and datos["iss"] == "supabase" and datos["iat"] == 1_000_000
    assert datos["exp"] == 1_000_000 + 5 * 365 * 24 * 3600
    esperada = hmac.new(b"secreto-de-prueba", f"{cab}.{cuerpo}".encode(), hashlib.sha256).digest()
    assert base64.urlsafe_b64decode(firma + "=" * (-len(firma) % 4)) == esperada


def test_db_usa_la_clave_de_la_cola_si_existe(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co/rest/v1")
    monkeypatch.setenv("SUPABASE_KEY", "service-role")
    monkeypatch.delenv("SUPABASE_KEY_COLA", raising=False)
    assert db._cfg() == ("https://x.supabase.co", "service-role")          # la API: sin cambios
    monkeypatch.setenv("SUPABASE_KEY_COLA", "clave-cola")
    assert db._cfg() == ("https://x.supabase.co", "clave-cola")
    monkeypatch.setenv("SUPABASE_KEY_COLA", "   ")                           # un secret vacío en GitHub no deja a la cola sin clave
    assert db._cfg()[1] == "service-role"
    assert db.disponible()


def test_la_cola_recibe_el_secret_y_la_api_no():
    cola = open(os.path.join(RAIZ, ".github", "workflows", "cola.yml"), encoding="utf-8").read()
    render = open(os.path.join(RAIZ, "render.yaml"), encoding="utf-8").read()
    assert "SUPABASE_KEY_COLA: ${{ secrets.SUPABASE_KEY_COLA }}" in cola
    assert "SUPABASE_KEY_COLA" not in render


def test_el_sql_manual_no_lo_aplica_migrar_y_da_permisos_solo_sobre_las_tablas_acordadas():
    assert "manual_cola_rol" not in migrar.archivos()
    sql = open(os.path.join(RAIZ, "api", "migraciones", "manual_cola_rol.sql"), encoding="utf-8").read()
    # solo las líneas que NO son comentario: el bloque OPCIONAL de conversaciones queda comentado
    activo = "\n".join(l for l in sql.splitlines() if not l.strip().startswith("--"))
    tablas = set(re.findall(r"grant [a-z, ]+ on public\.(\w+)\s+to cola", activo))
    assert tablas == {"publicaciones", "frases", "frase_envios", "config", "clips", "migraciones"}
    assert "usuarios" not in activo and "conversaciones" not in activo
    assert re.search(r"grant select\s+on public\.migraciones\s+to cola", activo)      # migraciones: solo lectura
