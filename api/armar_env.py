"""(21/10) Arma `api.env` (en la raíz del repo, ignorado por git) con las variables que la API necesita en el hosting,
a partir de `.streamlit/secrets.toml` (o del archivo que indique FVA_SECRETS). Después se pega en Render:
Environment → «Add from .env». Uso:  python api/armar_env.py  [--web https://fva-web.vercel.app]
Agrega: USUARIOS_JSON / IDIOMAS_JSON (de las tablas [usuarios] / [idiomas]), SESION_SECRETO nuevo, COOKIE_SEGURA=1,
COOKIE_SAMESITE=none y CORS_ORIGENES con el dominio de la web. NUNCA subir api.env al repo (es público)."""
import os, sys, json, secrets, tomllib

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ruta = os.environ.get("FVA_SECRETS") or os.path.join(RAIZ, ".streamlit", "secrets.toml")
web = "https://fva-web.vercel.app"
if "--web" in sys.argv:
    web = sys.argv[sys.argv.index("--web") + 1]
d = tomllib.load(open(ruta, "rb"))
lineas = []
for k, v in d.items():
    if isinstance(v, (str, int, float, bool)):
        lineas.append(f"{k}={json.dumps(v) if isinstance(v, str) and any(c in v for c in ' #\"') else v}")
for tabla, clave in (("usuarios", "USUARIOS_JSON"), ("idiomas", "IDIOMAS_JSON")):
    if isinstance(d.get(tabla), dict):
        lineas.append(f"{clave}={json.dumps({str(a): str(b) for a, b in d[tabla].items()}, ensure_ascii=False)}")
lineas += [f"SESION_SECRETO={secrets.token_urlsafe(48)}", "COOKIE_SEGURA=1", "COOKIE_SAMESITE=none", f"CORS_ORIGENES={web}"]
salida = os.path.join(RAIZ, "api.env")
open(salida, "w", encoding="utf-8").write("\n".join(lineas) + "\n")
print(f"{salida}: {len(lineas)} variables. Pegalo en Render > Environment > Add from .env. No lo subas al repo.")
