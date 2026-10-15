"""
RECORTAR UN CLIP EXACTO (15/10, pedido de Beto): del video original guardado en Drive, cortar el tramo
citado por el bot y subirlo a la biblioteca de WordPress. Pensado para correr en GitHub Actions
(recortar_clip.yml), sin ninguna computadora nuestra: el original viene de la carpeta
"VIVIR AGRADECIDOS/chatbot/Videos originales" de Drive (un archivo por video, nombre = id de YouTube).

Drive se lee con el token OAuth de solo lectura (DRIVE_TOKEN_JSON, autorizado por Franco el 15/10 con el
cliente propio del Workspace, proyecto n8n1; autorizar_drive.py lo genera). Nada se comparte públicamente.

Uso:
    python recortar_clip.py --drive-id <id del archivo en Drive> --inicio 58.669 --fin 106.627 --nombre -064nr8Yy6M
    python recortar_clip.py --youtube -064nr8Yy6M --inicio 58.669 --fin 106.627      # busca el original por nombre
Variables de entorno: DRIVE_TOKEN_JSON, WP_SITE, WP_USER, WP_APP_PASSWORD, PUBLICAR_WORDPRESS (borrador o real).
Salida: imprime la URL del clip en WordPress y la deja en clip_url.txt.

El corte re-encodea (x264 veryfast) para que empiece y termine exactamente donde dice el fragmento,
sin depender de los keyframes del original. 720p máximo.
"""
import argparse, io, json, os, subprocess, shutil

CARPETA_ORIGINALES = "Videos originales"


def _drive():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    tok = json.loads(os.environ["DRIVE_TOKEN_JSON"])
    creds = Credentials.from_authorized_user_info(tok, ["https://www.googleapis.com/auth/drive.readonly"])
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def buscar_original(svc, youtube_id):
    """Busca <youtube_id>.mp4 (o .mkv/.mov) en Drive. Devuelve el id del archivo o None."""
    q = f"name contains '{youtube_id}' and trashed = false and mimeType contains 'video/'"
    r = svc.files().list(q=q, fields="files(id,name,size,parents)", pageSize=10).execute()
    for f in r.get("files", []):
        if f["name"].rsplit(".", 1)[0] == youtube_id:
            return f["id"]
    return None


def descargar_drive(svc, file_id, destino):
    from googleapiclient.http import MediaIoBaseDownload
    req = svc.files().get_media(fileId=file_id)
    with open(destino, "wb") as fh:
        dl = MediaIoBaseDownload(fh, req, chunksize=32 * 1024 * 1024)
        done = False
        while not done:
            status, done = dl.next_chunk()
            if status:
                print(f"  bajando original… {int(status.progress() * 100)}%", flush=True)
    return destino


def cortar(entrada, salida, inicio, fin, ffmpeg="ffmpeg"):
    cmd = [ffmpeg, "-y", "-loglevel", "error", "-ss", f"{inicio:.3f}", "-to", f"{fin:.3f}", "-i", entrada,
           "-vf", "scale='min(1280,iw)':-2", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
           "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", salida]
    subprocess.check_call(cmd)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--drive-id", default="")
    ap.add_argument("--youtube", default="", help="id de YouTube: busca el original en Drive por nombre")
    ap.add_argument("--inicio", type=float, required=True, help="segundos")
    ap.add_argument("--fin", type=float, required=True, help="segundos")
    ap.add_argument("--nombre", default="", help="nombre base del clip (por defecto el id de YouTube)")
    ap.add_argument("--titulo", default="")
    ap.add_argument("--ffmpeg", default=shutil.which("ffmpeg") or "ffmpeg")
    a = ap.parse_args()
    nombre = a.nombre or a.youtube or a.drive_id
    svc = _drive()
    file_id = a.drive_id or buscar_original(svc, a.youtube)
    if not file_id:
        raise SystemExit(f"No encontré el original de {a.youtube} en Drive (carpeta {CARPETA_ORIGINALES}).")

    original = f"original_{nombre}.mp4"
    descargar_drive(svc, file_id, original)
    clip = f"clip-{nombre}-{int(a.inicio)}-{int(a.fin)}.mp4"
    cortar(original, clip, a.inicio, a.fin, a.ffmpeg)
    print(f"clip: {clip} ({os.path.getsize(clip) // 1024} KB)")

    import publicar
    cfg = publicar.Config(os.environ)
    r = publicar.subir_imagen_wordpress(cfg, open(clip, "rb").read(), clip,
                                        titulo=a.titulo or f"Clip {nombre} {int(a.inicio)}-{int(a.fin)} s",
                                        etiquetas=["clip-exacto"], quien="actions", pieza=a.titulo)
    print(r)
    if not r.get("url"):
        raise SystemExit("No se subió a WordPress: " + str(r.get("aviso")))
    open("clip_url.txt", "w").write(r["url"])
    print("URL:", r["url"])


if __name__ == "__main__":
    main()
