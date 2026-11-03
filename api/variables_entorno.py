"""(3/11) Lista ÚNICA de las variables de entorno del proyecto. De acá salen:
  - el bloque `envVars` de render.yaml (la API),
  - el bloque `env` de .github/workflows/cola.yml (la cola),
  - el chequeo «variables» de /salud/servicios (cuáles faltan en el entorno de la API).
Para agregar una variable: una entrada en VARIABLES y `python api/generar_config.py` (regenera los dos YAML).
El Blueprint de Render NO sincroniza las variables: las que no tienen `valor` (y las que cambian) hay que cargarlas a mano
en el panel; el chequeo de Salud avisa cuáles faltan.

Campos:
  nombre    el nombre de la variable
  valor     valor NO secreto que va escrito en render.yaml (None = se carga a mano en el panel)
  secreto   True = el valor no se escribe en ningún archivo del repo
  api       True = la usa la API (render.yaml)
  cola      None = la cola no la usa | "secret" = viene de los secrets del repo en GitHub | "valor" = el mismo `valor` fijo
  requerida True = si falta en la API, /salud/servicios avisa
  generar   True = Render genera el valor (generateValue)
  nota      comentario que va arriba de la variable en los YAML
"""

SECRET = "secret"
VALOR = "valor"


def _v(nombre, valor=None, *, secreto=False, api=True, cola=None, requerida=None, generar=False, nota=""):
    if requerida is None:
        requerida = api and (secreto or valor is not None or generar)
    return {"nombre": nombre, "valor": valor, "secreto": secreto, "api": api, "cola": cola, "requerida": requerida,
            "generar": generar, "nota": nota}


VARIABLES = [
    # --- Base: IA y datos ---
    _v("OPENAI_API_KEY", secreto=True),
    _v("SUPABASE_URL", secreto=True, cola=SECRET),
    _v("SUPABASE_KEY", secreto=True, cola=SECRET),
    _v("ASISTENTE_MODELO", "gpt-5.6-sol", nota="(21/10) Configuración NO secreta, administrada desde acá."),
    _v("BUSQUEDA_HIBRIDA", "1"),
    _v("LIMPIEZA_EXTRA", "1"),
    _v("RERANK_CANDIDATOS", "50"),
    _v("RERANK_CHARS", "400"),
    _v("RERANK_MODO", "fusion"),
    _v("EXPANSION_CONSULTA", "0"),
    _v("CONCEPTOS_URL", "https://docs.google.com/spreadsheets/d/e/2PACX-1vSxLDWgltMTAH6-Nu8rVB0e0QM6PgwvemkKEN78rOq7Bk0qyL-895nQ9zjzrPhvF9JNHy082O4DtN8X/pub?gid=528104219&single=true&output=csv"),
    _v("DISTINCIONES_URL", "https://docs.google.com/spreadsheets/d/e/2PACX-1vSxLDWgltMTAH6-Nu8rVB0e0QM6PgwvemkKEN78rOq7Bk0qyL-895nQ9zjzrPhvF9JNHy082O4DtN8X/pub?gid=222457179&single=true&output=csv"),
    # --- Sesión, web y accesos ---
    _v("COOKIE_SEGURA", "1"),
    _v("COOKIE_SAMESITE", "none"),
    _v("CORS_ORIGENES", "https://chatbot-vvaa.vercel.app"),
    _v("WEB_URL", "https://chatbot-vvaa.vercel.app"),
    _v("SESION_SECRETO", generar=True),
    _v("USUARIOS_JSON", secreto=True, requerida=False, nota="Transición: login con contraseñas de entorno, mientras haya cuentas que no estén en la tabla usuarios."),
    _v("GOOGLE_CLIENT_ID", "975482475680-o1clpt1idim34dormtuecg58knnga3ol.apps.googleusercontent.com"),
    _v("DOMINIO_FVA", "viviragradecidos.org"),
    _v("APROBADORES", "julian,franco,beto"),
    _v("PUBLICACION_DIRECTA", "julian,franco,beto"),
    _v("ADMINS", "franco,beto"),
    # --- Salud ---
    _v("SALUD_TOKEN", secreto=True, requerida=False, nota="Token para consultar /salud/servicios desde un monitor externo sin sesión (?token= o X-Salud-Token)."),
    _v("MEMORIA_LIMITE_MB", "512", nota="Límite de memoria del plan (MB), para la fila «memoria» de /salud/servicios (aviso al 80 %, error al 95 %)."),
    _v("META_IG_TOKEN_VENCE", "2026-11-22", nota="(22/10, salud) Vencimiento del token de Instagram Login (dura 60 días); corregirlo al renovar el token."),
    # --- Canales: modo de cada uno (apagado | simulado | borrador | real; YouTube: privado) ---
    _v("PUBLICAR_WORDPRESS", "real", cola=SECRET, nota="(2/11, Franco) real: el aprobador publica la entrada de verdad desde la plataforma (o la programa)."),
    _v("PUBLICAR_WHATSAPP", "simulado", cola=VALOR, nota="(2/11) prototipo: apagado | simulado (no hay modo real todavía)."),
    _v("PUBLICAR_HOME", "real", cola=VALOR, nota="(2/11) la frase del día en la home del sitio (canal «home»): borrador | real."),
    _v("PUBLICAR_INSTAGRAM", "real", cola=SECRET),
    _v("PUBLICAR_FACEBOOK", "real", cola=SECRET),
    _v("PUBLICAR_YOUTUBE", "privado", cola=SECRET),
    _v("PUBLICAR_MAIL", "simulado", cola=SECRET, nota="(26/10) Frase del día por mail con Perfit (perfit.py): apagado | simulado | real."),
    # --- WordPress ---
    _v("WP_SITE", "viviragradecidos.org", cola=SECRET),
    _v("WP_USER", "adminviviragradecidos", cola=SECRET),
    _v("WP_APP_PASSWORD", secreto=True, cola=SECRET),
    # --- Meta, YouTube, Drive ---
    _v("META_IG_USER_ID", "17841406237571284", cola=SECRET),
    _v("META_FB_PAGE_ID", "267335090073960", cola=SECRET),
    _v("META_IG_TOKEN", secreto=True, cola=SECRET),
    _v("META_FB_PAGE_TOKEN", secreto=True, cola=SECRET),
    _v("YOUTUBE_TOKEN_JSON", secreto=True, cola=SECRET),
    _v("DRIVE_TOKEN_JSON", secreto=True),
    # --- Perfit (mail de la frase) ---
    _v("PERFIT_API_KEY", secreto=True, cola=SECRET),
    _v("PERFIT_CUENTA", "viviragradecido", cola=VALOR, nota="Nombre de la cuenta en Perfit (no es secreto; verificado el 26/10)."),
    _v("PERFIT_TRIGGER_URL", secreto=True, cola=SECRET),
    _v("PERFIT_LISTA_FRASE", secreto=True, cola=SECRET),
    # --- Avisos al equipo (avisos.py): opcionales, alcanza con Slack o con SMTP ---
    _v("SLACK_WEBHOOK_URL", secreto=True, requerida=False, nota="(2/11) Avisos al equipo: Incoming Webhook del canal, y/o las SMTP_* (Google Workspace: smtp.gmail.com + contraseña de aplicación)."),
    _v("SMTP_HOST", requerida=False),
    _v("SMTP_PORT", requerida=False),
    _v("SMTP_USER", requerida=False),
    _v("SMTP_PASS", secreto=True, requerida=False),
    _v("AVISOS_DESDE", requerida=False),
]


def de_api():
    return [v for v in VARIABLES if v["api"]]


def de_cola():
    return [v for v in VARIABLES if v["cola"]]


def requeridas():
    return [v["nombre"] for v in VARIABLES if v["api"] and v["requerida"]]


def faltantes(entorno):
    """Nombres de las variables requeridas de la API que no están (o están vacías) en `entorno` (dict, p. ej. os.environ)."""
    return [n for n in requeridas() if not str(entorno.get(n, "") or "").strip()]
