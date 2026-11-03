"""(3/11) El ÚNICO cargador de secretos locales. Lo usan la API (api/config.py), la cola (procesar_cola.py), los recortes
(procesar_clips.py), programar_frases.py y los scripts de la raíz.

Fuera de Render y de GitHub Actions las claves están en `.streamlit/secrets.toml` (nombre histórico; es el archivo local de
secretos, no se sube al repo) o en el archivo que indique FVA_SECRETS. FVA_SECRETS="-" desactiva la carga (lo usan los tests).
Lo que ya está en el entorno NO se pisa. Si el archivo no existe y el entorno no trae SUPABASE_URL (o sea, no es un
servidor con las variables cargadas), avisa por stderr en vez de seguir en silencio sin claves.
"""
import os, sys, tomllib

RAIZ = os.path.dirname(os.path.abspath(__file__))
RUTA_DEFECTO = os.path.join(RAIZ, ".streamlit", "secrets.toml")
CLAVE_ENV = os.path.join(RAIZ, "..", "fva-transcripcion", "clave.env")      # resto del uso desde la terminal (opcional)


def ruta():
    return os.environ.get("FVA_SECRETS") or RUTA_DEFECTO


def cargar_al_entorno(avisar=True, clave_env=False):
    """Pone en os.environ los valores simples del archivo de secretos (sin pisar lo ya definido). Devuelve las tablas
    ([usuarios], [idiomas]…) como dict, y {} si no cargó nada. Con clave_env=True también lee ../fva-transcripcion/clave.env."""
    r = ruta()
    tablas = {}
    if r == "-":
        return tablas
    if os.path.exists(r):
        try:
            with open(r, "rb") as f:
                datos = tomllib.load(f)
        except (OSError, tomllib.TOMLDecodeError) as e:
            print(f"[secretos] No pude leer {r}: {e}", file=sys.stderr)
            datos = {}
        for k, v in datos.items():
            if isinstance(v, dict):
                tablas[k] = v
            elif isinstance(v, (str, int, float, bool)) and k not in os.environ:
                os.environ[k] = str(v)
    elif avisar and not os.environ.get("SUPABASE_URL"):
        print(f"[secretos] No encontré {r} y el entorno no trae SUPABASE_URL: sigo sin claves. "
              "(En GitHub Actions o Render llegan por variables de entorno; en local, copiar secrets.toml o fijar FVA_SECRETS.)", file=sys.stderr)
    if clave_env and os.path.exists(CLAVE_ENV):
        with open(CLAVE_ENV, encoding="utf-8") as f:
            for linea in f:
                if "=" in linea and not linea.strip().startswith("#"):
                    k, v = linea.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"'))
    return tablas
