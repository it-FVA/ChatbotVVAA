"""
RECORTAR UN CLIP EXACTO (15/10, pedido de Beto): del video original guardado en Drive, cortar el tramo
citado por el bot y subirlo a la biblioteca de WordPress. Pensado para correr en GitHub Actions
(recortar_clip.yml), sin ninguna computadora nuestra: el original viene de la carpeta
"VIVIR AGRADECIDOS/chatbot/Videos originales" de Drive (un archivo por video, nombre = id de YouTube).

Drive se lee con el token OAuth de solo lectura (DRIVE_TOKEN_JSON, autorizado por Franco el 15/10 con el
cliente propio del Workspace, proyecto n8n1; autorizar_drive.py lo genera). Nada se comparte públicamente.

Uso:
    python recortar_clip.py --drive-id <id del archivo en Drive> --inicio 58.669 --fin 106.627 --nombre -064nr8Yy6M
    python recortar_clip.py --youtube=-064nr8Yy6M --inicio 58.669 --fin 106.627     # busca el original por nombre
    (los ids de YouTube pueden empezar con "-": por eso va con "=")
Variables de entorno: DRIVE_TOKEN_JSON, WP_SITE, WP_USER, WP_APP_PASSWORD, PUBLICAR_WORDPRESS (borrador o real).
Salida: imprime la URL del clip en WordPress y la deja en clip_url.txt.

El corte re-encodea (x264 veryfast) para que empiece y termine exactamente donde dice el fragmento,
sin depender de los keyframes del original. 720p máximo.

Subtítulos quemados (15/10): si en la misma carpeta de Drive está <id>.palabras.json (lo exporta
fva-transcripcion/conectores/exportar_palabras.py desde las transcripciones de AssemblyAI, con tiempos por
palabra), el clip sale con subtítulos quemados en Raleway (fuentes/). Por defecto van en el vertical
(shorts, reels, historias) y no en el horizontal; --subtitulos si/no lo fuerza.
"""
import argparse, io, json, os, subprocess, shutil

CARPETA_ORIGINALES = "Videos originales"


def _drive():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    import socket
    socket.setdefaulttimeout(600)   # archivos de cientos de MB: sin esto, httplib2 corta a los 60 s
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
            status, done = dl.next_chunk(num_retries=5)
            if status:
                print(f"  bajando original… {int(status.progress() * 100)}%", flush=True)
    return destino


def buscar_palabras(svc, youtube_id):
    """Busca <youtube_id>.palabras.json en Drive y devuelve la lista [[palabra, inicio_ms, fin_ms], ...] o None."""
    nombre = f"{youtube_id}.palabras.json"
    r = svc.files().list(q=f"name = '{nombre}' and trashed = false", fields="files(id,name)", pageSize=5).execute()
    for f in r.get("files", []):
        if f["name"] == nombre:
            return json.loads(svc.files().get_media(fileId=f["id"]).execute().decode("utf-8"))
    return None


def _srt_tiempo(seg):
    ms = int(round(seg * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def armar_srt(palabras, inicio, fin, max_car=34, max_seg=2.8, pausa=0.7):
    """Agrupa las palabras del tramo [inicio, fin] (segundos) en líneas cortas de subtítulo, con tiempos
    relativos al clip. Corta la línea al pasar max_car caracteres, max_seg segundos, un silencio de más de
    `pausa` segundos, o al final de una oración (. ? !). Devuelve el texto SRT ('' si no hay palabras)."""
    ini_ms, fin_ms = int(inicio * 1000), int(fin * 1000)
    # AssemblyAI a veces estira una palabra sobre un silencio largo (p. ej. "Muy" de 20 s): tope de 1,5 s por palabra
    ws = [[w[0], w[1], min(w[2], w[1] + 1500)] for w in palabras if w[1] < fin_ms and w[2] > ini_ms]
    bloques, actual = [], []
    for w in ws:
        if actual:
            texto = " ".join(x[0] for x in actual)
            corta = (len(texto) + 1 + len(w[0]) > max_car or (w[2] - actual[0][1]) / 1000 > max_seg
                     or (w[1] - actual[-1][2]) / 1000 > pausa or actual[-1][0][-1:] in ".?!")
            if corta:
                bloques.append(actual)
                actual = []
        actual.append(w)
    if actual:
        bloques.append(actual)
    out = []
    for i, b in enumerate(bloques, 1):
        t0 = max(0.0, (b[0][1] - ini_ms) / 1000)
        t1 = min(fin - inicio, (b[-1][2] - ini_ms) / 1000 + 0.15)
        if i < len(bloques):   # que no pise al siguiente
            t1 = min(t1, (bloques[i][0][1] - ini_ms) / 1000)
        if t1 <= t0:
            continue
        out.append(f"{i}\n{_srt_tiempo(t0)} --> {_srt_tiempo(t1)}\n{' '.join(x[0] for x in b)}\n")
    return "\n".join(out)


FUENTE_SUB = "Raleway-Clips-SemiBold.ttf"   # instancia fija (wght 600) de Raleway-Variable, familia "Raleway Clips": libass no maneja fuentes variables


def _filtro_subtitulos(srt, formato):
    """Filtro ffmpeg para quemar el SRT. La fuente se copia a ./sub_fuentes (ruta relativa: una letra de unidad
    con ":" rompe el parser de filtros en Windows). Tamaño según el formato."""
    os.makedirs("sub_fuentes", exist_ok=True)
    origen = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fuentes", FUENTE_SUB)
    if not os.path.exists(os.path.join("sub_fuentes", FUENTE_SUB)):
        shutil.copy(origen, os.path.join("sub_fuentes", FUENTE_SUB))
    tam, margen = (17, 46) if formato == "vertical" else (13, 24)     # sobre PlayResY=288 (libass escala solo)
    estilo = (f"FontName=Raleway Clips,FontSize={tam},PrimaryColour=&H00FFFFFF,OutlineColour=&H70000000,"
              f"BackColour=&H90000000,BorderStyle=4,Outline=1,Shadow=0,Alignment=2,MarginV={margen},MarginL=14,MarginR=14")
    return f"subtitles={srt}:fontsdir=sub_fuentes:force_style='{estilo}'"


def quiere_subtitulos(formato, opcion="auto"):
    """'auto': sí en vertical (shorts/reels), no en horizontal. 'si'/'no' fuerzan."""
    return opcion == "si" or (opcion == "auto" and formato == "vertical")


def cortar(entrada, salida, inicio, fin, ffmpeg="ffmpeg", formato="horizontal", palabras=None):
    """formato 'horizontal': el tramo tal cual (hasta 1280 de ancho). 'vertical' (15/10, pedido de Franco: shorts,
    reels, historias): lienzo 1080x1920 con el video centrado y, de fondo, el mismo video desenfocado.
    palabras: lista [[palabra, inicio_ms, fin_ms], ...] del video entero → subtítulos quemados (None = sin).
    Devuelve True si el clip salió con subtítulos."""
    sub = ""
    if palabras:
        srt_txt = armar_srt(palabras, inicio, fin)
        if srt_txt:
            srt = os.path.splitext(os.path.basename(salida))[0] + ".srt"   # en el cwd, sin ":" ni barras que confundan al filtro
            open(srt, "w", encoding="utf-8").write(srt_txt)
            sub = "," + _filtro_subtitulos(srt, formato)
    if formato == "vertical":
        vf = ("[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:5,eq=brightness=-0.08[bg];"
              "[0:v]scale=1080:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p" + sub)
        filtro = ["-filter_complex", vf]
    else:
        filtro = ["-vf", "scale='min(1280,iw)':-2" + sub]
    cmd = [ffmpeg, "-y", "-loglevel", "error", "-ss", f"{inicio:.3f}", "-to", f"{fin:.3f}", "-i", entrada,
           *filtro, "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
           "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", salida]
    subprocess.check_call(cmd)
    return bool(sub)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--drive-id", default="")
    ap.add_argument("--youtube", default="", help="id de YouTube: busca el original en Drive por nombre")
    ap.add_argument("--inicio", type=float, required=True, help="segundos")
    ap.add_argument("--fin", type=float, required=True, help="segundos")
    ap.add_argument("--nombre", default="", help="nombre base del clip (por defecto el id de YouTube)")
    ap.add_argument("--titulo", default="")
    ap.add_argument("--formato", choices=["horizontal", "vertical"], default="horizontal")
    ap.add_argument("--subtitulos", choices=["auto", "si", "no"], default="auto", help="quemar subtítulos (auto: solo en vertical)")
    ap.add_argument("--ffmpeg", default=shutil.which("ffmpeg") or "ffmpeg")
    a = ap.parse_args()
    nombre = a.nombre or a.youtube or a.drive_id
    svc = _drive()
    file_id = a.drive_id or buscar_original(svc, a.youtube)
    if not file_id:
        raise SystemExit(f"No encontré el original de {a.youtube} en Drive (carpeta {CARPETA_ORIGINALES}).")

    original = f"original_{nombre}.mp4"
    descargar_drive(svc, file_id, original)
    clip = f"clip-{nombre}-{int(a.inicio)}-{int(a.fin)}{'-vertical' if a.formato == 'vertical' else ''}.mp4"
    palabras = buscar_palabras(svc, a.youtube or nombre) if quiere_subtitulos(a.formato, a.subtitulos) else None
    con_sub = cortar(original, clip, a.inicio, a.fin, a.ffmpeg, a.formato, palabras)
    print(f"clip: {clip} ({os.path.getsize(clip) // 1024} KB){' · con subtítulos' if con_sub else ''}")

    import publicar
    cfg = publicar.Config(os.environ)
    r = publicar.subir_imagen_wordpress(cfg, open(clip, "rb").read(), clip,
                                        titulo=a.titulo or f"Clip {nombre} {int(a.inicio)}-{int(a.fin)} s" + (" (vertical)" if a.formato == "vertical" else ""),
                                        etiquetas=["clip-exacto"], quien="actions", pieza=a.titulo)
    print(r)
    if not r.get("url"):
        raise SystemExit("No se subió a WordPress: " + str(r.get("aviso")))
    open("clip_url.txt", "w").write(r["url"])
    print("URL:", r["url"])


if __name__ == "__main__":
    main()
