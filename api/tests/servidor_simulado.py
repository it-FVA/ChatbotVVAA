"""API de prueba para la web SIN Supabase ni OpenAI: la tabla `usuarios` y la lista blanca viven en memoria (la misma
`Tabla` de test_cuentas.py). Sirve para probar «Primera vez», Mi cuenta y Administración en el navegador sin tocar
la base real. Se pierde todo al cerrar.

    python api/tests/servidor_simulado.py        # http://127.0.0.1:8000 (la web en :5173 le pega por el proxy de Vite)

Cuentas: beto / Clave-beto1 (admin), pato / Temp-1234 (creador, clave temporal), julian (aprobador, sin clave:
la crea desde «Primera vez» con julian@gmail.com); en secrets: franco / clave-franco (admin por ADMINS).
Lista blanca: amiga@gmail.com (creador). Dominio: viviragradecidos.org.
"""
import os, sys, json

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ["FVA_SECRETS"] = "-"
os.environ["API_CARGAR_CORPUS"] = "0"
os.environ["SESION_SECRETO"] = "secreto-de-prueba-local"
os.environ["BCRYPT_RONDAS"] = "6"
os.environ["USUARIOS_JSON"] = json.dumps({"franco": "clave-franco", "gratefulness": "clave-g"})
os.environ["APROBADORES"] = "julian,franco,beto"
os.environ["DOMINIO_FVA"] = "viviragradecidos.org"
for k in ("SUPABASE_URL", "SUPABASE_KEY", "GOOGLE_CLIENT_ID", "OPENAI_API_KEY"):
    os.environ.pop(k, None)
os.environ["OPENAI_API_KEY"] = ""

import db                                   # noqa: E402
from test_cuentas import Tabla              # noqa: E402
from api import cuentas                     # noqa: E402

t = Tabla()
db.disponible = lambda: True
for nombre in ("usuario_por_nombre", "usuario_por_email", "usuario_por_id", "listar_usuarios", "crear_usuario", "actualizar_usuario",
               "borrar_usuario", "marcar_login", "renombrar_usuario_en_tablas", "registrar_cambio_usuario", "listar_cambios_usuarios",
               "autorizado", "listar_autorizados", "agregar_autorizado", "quitar_autorizado"):
    setattr(db, nombre, getattr(t, nombre))
# lo demás (conversaciones, recortes, publicaciones) responde vacío
for nombre in ("listar_conversaciones", "listar_clips", "listar_mias", "listar_registro"):
    setattr(db, nombre, lambda *a, **k: [])

t.crear_usuario("beto", email="beto@viviragradecidos.org", nombre="Beto", rol="admin", clave_hash=cuentas.hashear("Clave-beto1"), creado_por="simulado")
t.crear_usuario("pato", email="pato@gmail.com", nombre="Pato", rol="creador", clave_hash=cuentas.hashear("Temp-1234"), clave_temporal=True, creado_por="beto")
t.crear_usuario("julian", email="julian@gmail.com", nombre="Julián", rol="aprobador", creado_por="beto")
t.filas["id-1"]["ultimo_login"] = "2026-10-21T22:15:00Z"
t.agregar_autorizado("amiga@gmail.com", "creador", "beto", nota="diseñadora freelance")
t.registrar_cambio_usuario("beto", "crear", "pato", {"rol": "creador", "clave": "temporal"})
t.registrar_cambio_usuario("beto", "lista_alta", "amiga@gmail.com", {"rol": "creador"})

from api.main import app                    # noqa: E402
import uvicorn                              # noqa: E402

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8000")), log_level="warning")
