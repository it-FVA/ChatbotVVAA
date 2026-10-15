"""
RECORTAR UN CLIP EXACTO (15/10, pedido de Beto): del video original guardado en Drive, cortar el tramo
citado por el bot y subirlo a la biblioteca de WordPress. Pensado para correr en GitHub Actions
(recortar_clip.yml), sin ninguna computadora nuestra: el original viene de la carpeta
"VIVIR AGRADECIDOS/chatbot/Videos originales" de Drive (un archivo por video, nombre = id de YouTube).

Uso:
    python recortar_clip.py --drive-id <id del archivo en Drive> --inicio 58.669 --fin 106.627 --nombre -064nr8Yy6M
Secrets/variables de entorno: WP_SITE, WP_USER, WP_APP_PASSWORD, PUBLICAR_WORDPRESS (borrador o real).
Salida: imprime la URL del clip en WordPress y la deja en clip_url.txt.

El corte re-encodea (x264 veryfast) para que empiece y termine exactamente donde dice el fragmento,
sin depender de los keyframes del original. 720p máximo.
"""
import argparse, os, subprocess, sys, shutil


def descargar_drive(file_id, destino):
    """Baja un archivo de Drive compartido 'con el enlace' (maneja el aviso de virus de archivos grandes)."""
    try:
        import gdown
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "gdown"])
        import gdown
    out = gdown.download(id=file_id, output=destino, quiet=False, fuzzy=True)
    if not out or not os.path.exists(destino):
        raise SystemExit("No pude bajar el original de Drive (¿está compartido con el enlace?).")
    return destino


def cortar(entrada, salida, inicio, fin, ffmpeg="ffmpeg"):
    cmd = [ffmpeg, "-y", "-ss", f"{inicio:.3f}", "-to", f"{fin:.3f}", "-i", entrada,
           "-vf", "scale='min(1280,iw)':-2", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
           "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", salida]
    subprocess.check_call(cmd)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--drive-id", required=True)
    ap.add_argument("--inicio", type=float, required=True, help="segundos")
    ap.add_argument("--fin", type=float, required=True, help="segundos")
    ap.add_argument("--nombre", required=True, help="id de YouTube o nombre base")
    ap.add_argument("--titulo", default="")
    ap.add_argument("--ffmpeg", default=shutil.which("ffmpeg") or "ffmpeg")
    a = ap.parse_args()

    original = f"original_{a.nombre}.mp4"
    descargar_drive(a.drive_id, original)
    clip = f"clip-{a.nombre}-{int(a.inicio)}-{int(a.fin)}.mp4"
    cortar(original, clip, a.inicio, a.fin, a.ffmpeg)
    print(f"clip: {clip} ({os.path.getsize(clip) // 1024} KB)")

    import publicar
    cfg = publicar.Config(os.environ)
    r = publicar.subir_imagen_wordpress(cfg, open(clip, "rb").read(), clip,
                                        titulo=a.titulo or f"Clip {a.nombre} {int(a.inicio)}-{int(a.fin)} s",
                                        etiquetas=["clip-exacto"], quien="actions", pieza=a.titulo)
    print(r)
    if not r.get("url"):
        raise SystemExit("No se subió a WordPress: " + str(r.get("aviso")))
    open("clip_url.txt", "w").write(r["url"])
    print("URL:", r["url"])


if __name__ == "__main__":
    main()
