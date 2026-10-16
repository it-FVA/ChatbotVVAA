"""
AUTORIZAR YOUTUBE (16/10). Genera el permiso para subir videos al canal (YOUTUBE_TOKEN_JSON) con el
cliente OAuth propio del Workspace (DRIVE_CLIENT_ID / DRIVE_CLIENT_SECRET, proyecto n8n1, app publicada
en producción el 16/10: el permiso no vence a los 7 días como pasaba con la app en modo prueba).

Hay que autorizar con la cuenta dueña del canal (webviviragradecidos@gmail.com), no con la del Workspace.
Mientras Google no audite el proyecto (YouTube API compliance audit), los videos subidos por API quedan
PRIVADOS aunque se pida público: modo "privado" en PUBLICAR_YOUTUBE y se publican desde YouTube Studio.

Uso (desde ChatbotVVAA):  python autorizar_youtube.py
Imprime el link; abrirlo en el navegador con la cuenta del canal y aceptar. Escribe YOUTUBE_TOKEN_JSON
en .streamlit/secrets.toml (reemplaza el viejo). Después: pegarlo en Streamlit Cloud y en los secrets de GitHub.
"""
import json, re, tomllib
from google_auth_oauthlib.flow import InstalledAppFlow

SECRETS = ".streamlit/secrets.toml"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly"]

s = tomllib.load(open(SECRETS, "rb"))
cfg = {"installed": {"client_id": s["DRIVE_CLIENT_ID"], "client_secret": s["DRIVE_CLIENT_SECRET"],
                     "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                     "token_uri": "https://oauth2.googleapis.com/token"}}
flow = InstalledAppFlow.from_client_config(cfg, SCOPES)
creds = flow.run_local_server(port=8767, open_browser=False, prompt="consent", access_type="offline")
tok = {"token": creds.token, "refresh_token": creds.refresh_token, "token_uri": creds.token_uri,
       "client_id": creds.client_id, "client_secret": creds.client_secret, "scopes": list(creds.scopes or SCOPES)}
assert tok["refresh_token"], "Google no devolvió refresh_token: revocar el acceso en la cuenta y volver a correr."
linea = "YOUTUBE_TOKEN_JSON = '''" + json.dumps(tok, ensure_ascii=False) + "'''\n"
t = open(SECRETS, encoding="utf-8").read()
if re.search(r"^YOUTUBE_TOKEN_JSON = ", t, re.M):
    t = re.sub(r"^YOUTUBE_TOKEN_JSON = '''.*?'''\n", linea, t, count=1, flags=re.M | re.S)
else:
    t += "\n" + linea
open(SECRETS, "w", encoding="utf-8").write(t)
print("OK: YOUTUBE_TOKEN_JSON guardado en", SECRETS)
print("Para Streamlit Cloud y GitHub (secret YOUTUBE_TOKEN_JSON):")
print(json.dumps(tok, ensure_ascii=False))
