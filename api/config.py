"""Configuración de la API.

Regla: la API es independiente del hosting. Todo se lee de VARIABLES DE ENTORNO con los mismos nombres
que hoy usan los secrets de Streamlit (OPENAI_API_KEY, SUPABASE_URL, APROBADORES, …).

En local, si existe `.streamlit/secrets.toml` (o el archivo que indique FVA_SECRETS), se carga al entorno
sin pisar lo que ya esté definido, igual que hace procesar_cola._cargar_config_local. FVA_SECRETS="-"
desactiva esa carga (lo usan los tests).

Las tablas [usuarios] e [idiomas] de secrets no caben en una variable simple: en el servidor se pasan como
JSON en USUARIOS_JSON e IDIOMAS_JSON ({"franco": "clave", …} / {"gratefulness": "en"}).
"""
import os, json, tomllib

from . import RAIZ

# Mismos valores por defecto que app.py (interruptores del buscador; ver ARQUITECTURA-BUSCADOR.md)
DEFECTOS = {
    "ASISTENTE_MODELO": "gpt-4o-mini",
    "BUSQUEDA_HIBRIDA": "0", "LIMPIEZA_EXTRA": "0",
    "RERANK_CANDIDATOS": "15", "RERANK_CHARS": "150", "CONTEXTO_CHARS": "1200",
    "DATOS_FIJOS_URL": "", "DISTINCIONES_URL": "", "CONCEPTOS_URL": "", "EXPANSION_CONSULTA": "1",
}

# (7/10) Idioma por usuario: comunidades inglesa y alemana de Br. David (app.py, _IDIOMAS_DEFAULT)
_IDIOMAS_DEFAULT = {"gratefulness": "en", "dankbarleben": "de"}

_CFG = {"usuarios": {}, "idiomas": {}, "cargado": False, "secrets": None}


def cargar():
    """Carga una sola vez. Devuelve el dict de configuración (usuarios, idiomas)."""
    if _CFG["cargado"]:
        return _CFG
    ruta = os.environ.get("FVA_SECRETS") or os.path.join(RAIZ, ".streamlit", "secrets.toml")
    tablas = {}
    if ruta != "-" and os.path.exists(ruta):
        with open(ruta, "rb") as f:
            datos = tomllib.load(f)
        for k, v in datos.items():
            if isinstance(v, dict):
                tablas[k] = v
            elif isinstance(v, (str, int, float, bool)) and k not in os.environ:
                os.environ[k] = str(v)
        _CFG["secrets"] = ruta
    for k, d in DEFECTOS.items():
        os.environ.setdefault(k, d)
    usuarios = {str(k): str(v) for k, v in (tablas.get("usuarios") or {}).items()}
    usuarios.update({str(k): str(v) for k, v in json.loads(os.environ.get("USUARIOS_JSON") or "{}").items()})
    idiomas = {str(k): str(v).lower() for k, v in (tablas.get("idiomas") or {}).items()}
    idiomas.update({str(k): str(v).lower() for k, v in json.loads(os.environ.get("IDIOMAS_JSON") or "{}").items()})
    _CFG.update(usuarios=usuarios, idiomas=idiomas, cargado=True)
    return _CFG


def usuarios():
    return cargar()["usuarios"]


def idioma(usuario):
    """'es' | 'en' | 'de', como app.py: [idiomas] en secrets, si no el default por cuenta, si no español."""
    i = cargar()["idiomas"].get(usuario, _IDIOMAS_DEFAULT.get(usuario, "es"))
    return i if i in ("es", "en", "de") else "es"


def dominio_fva():
    """Dominio de la Fundación para el login con Google (DOMINIO_FVA, ej. viviragradecidos.org). Vacío = solo la lista."""
    return os.environ.get("DOMINIO_FVA", "").strip().lower().lstrip("@")
