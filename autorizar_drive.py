"""
AUTORIZAR LECTURA DE DRIVE (15/10): una sola vez, en la computadora de Franco. Usa el cliente OAuth propio
del Workspace (DRIVE_CLIENT_ID / DRIVE_CLIENT_SECRET, proyecto n8n1) y pide solo lectura de Drive.
Imprime la URL de consentimiento (abrirla con la cuenta de la Fundación), espera la aprobación en
http://localhost:8766/ y guarda el token (con refresh_token) en .streamlit/secrets.toml como
DRIVE_TOKEN_JSON. Ese mismo JSON va al secret DRIVE_TOKEN_JSON de GitHub Actions para que
recortar_clip.yml baje los originales de Drive sin compartir nada públicamente.
"""
import json, re, tomllib
from google_auth_oauthlib.flow import InstalledAppFlow

SECRETS = ".streamlit/secrets.toml"
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

s = tomllib.load(open(SECRETS, "rb"))
cfg = {"installed": {"client_id": s["DRIVE_CLIENT_ID"], "client_secret": s["DRIVE_CLIENT_SECRET"],
                     "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                     "token_uri": "https://oauth2.googleapis.com/token", "redirect_uris": ["http://localhost"]}}
flow = InstalledAppFlow.from_client_config(cfg, SCOPES)
creds = flow.run_local_server(port=8766, open_browser=False, prompt="consent", access_type="offline")
tok = json.loads(creds.to_json())

txt = open(SECRETS, encoding="utf-8").read()
linea = "DRIVE_TOKEN_JSON = '''" + json.dumps(tok) + "'''"
if "DRIVE_TOKEN_JSON" in txt:
    txt = re.sub(r"DRIVE_TOKEN_JSON = '''.*?'''", linea, txt, flags=re.S)
else:
    comentario = "# (15/10) Drive solo lectura, para bajar los originales de video en GitHub Actions.\n"
    txt = txt.replace('APROBADORES = "', comentario + linea + '\nAPROBADORES = "', 1)
open(SECRETS, "w", encoding="utf-8").write(txt)
print("OK: DRIVE_TOKEN_JSON guardado en secrets.toml; refresh_token:", bool(tok.get("refresh_token")))
