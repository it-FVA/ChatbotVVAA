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

Subtítulos corregidos (19/10, pregunta de Julián en la reunión): cortar() acepta `srt_texto`, un SRT ya armado (el que
la persona corrigió en «Mis recortes», guardado en clips.edicion["srt"]) y lo quema tal cual; devuelve el SRT usado para
guardarlo en clips.srt. Prueba local sin Drive ni WordPress: --original <ruta.mp4> --srt <archivo.srt> --sin-subir.

Estilo de los subtítulos (19/10, tarde, pedido de Franco): tipografía (FUENTES_CLIPS), tamaño, color del texto, fondo/borde,
negrita y posición, elegidos en «Editar recorte → Estilo» o como estilo por defecto en el Panel admin (tabla config). Se
aplican vía force_style de libass (estilo_ass). Prueba local: --estilo '{"color":"amarillo de la marca","posicion":"centro"}'.

Quitar pausas largas (21/10, pedido de Julián en la reunión del 19/10, experimento aprobado por Franco): cortar(..., quitar_pausas=True)
saca los silencios de más de 0,7 s del tramo (ffmpeg silencedetect a -32 dB, dejando 0,25 s a cada lado) antes de armar el video, y
corre los tiempos de los subtítulos para que sigan sincronizados. CLI: --quitar-pausas. Ver quitar_pausas().

Segmentos (21/10, noche; fase 1 de la interfaz propia, editor visual de «Mis recortes»): cortar(..., segmentos=[(a, b), ...])
conserva solo esos tramos del clip (segundos relativos al tramo) y los pega uno tras otro: es «partir el recorte y sacar un
pedazo del medio». En clips.edicion viaja como "segmentos" = [[a_ms, b_ms], ...] absolutos del original (normalizar_segmentos
los pasa a relativos). Mismo mecanismo que quitar pausas (select/aselect) y los subtítulos se corren igual. Ver conservar_tramos().
"""
import argparse, io, json, os, re, subprocess, shutil

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

# ---------------- Estilo de los subtítulos (19/10, tarde; pedido de Franco) ----------------
# Lo que la persona elige en «✏️ Editar recorte → Estilo» (o el estilo por defecto del Panel admin, tabla config,
# clave 'clips_estilo') llega como dict con estas claves y se traduce al force_style de libass en estilo_ass().
# Tipografías: solo .ttf fijos (no variables) de fuentes/. nombre visible → (archivo, nombre de familia que ve libass).
FUENTES_CLIPS = {
    "Raleway": ("Raleway-Clips-SemiBold.ttf", "Raleway Clips"),   # la de la Fundación; semibold fijo
    "Lato": ("Lato-Regular.ttf", "Lato"),
}
TAMANOS = {"chico": 0.82, "normal": 1.0, "grande": 1.25}            # multiplican el tamaño base del formato
COLORES = {   # nombre visible → RGB (hex). libass los quiere en BGR: lo hace _ass_color.
    "blanco": "FFFFFF",
    "negro": "000000",
    "amarillo de la marca": "F4B43C",   # el de los botones del newsletter
    "crema": "FFF4D6",
    "verde de la marca": "3A6B35",
}
FONDOS = {   # qué va detrás o alrededor de las letras. nombre visible → (tipo, color hex o None, alpha 00=opaco..FF=transparente)
    "sombra oscura": ("caja", "000000", "90"),    # lo de siempre: caja negra translúcida
    "caja negra": ("caja", "000000", "20"),
    "caja blanca": ("caja", "FFFFFF", "20"),
    "caja amarilla": ("caja", "F4B43C", "20"),
    "borde negro": ("borde", "000000", "00"),
    "borde blanco": ("borde", "FFFFFF", "00"),
    "sin fondo": ("nada", None, "FF"),
}
POSICIONES_SUB = {"abajo": 2, "centro": 10, "arriba": 6}   # Alignment en numeración SSA (la que usa force_style sobre un SRT: +4 arriba, +8 medio); probado el 19/10: con 5/8 salía arriba a la izquierda
ESTILO_DEFECTO = {"tipografia": "Raleway", "tamano": "normal", "color": "blanco", "fondo": "sombra oscura",
                  "negrita": False, "posicion": "abajo"}


def normalizar_estilo(estilo):
    """Completa con ESTILO_DEFECTO y descarta valores que no están en las listas (una clave vieja o un typo no rompe la cola)."""
    e = dict(ESTILO_DEFECTO)
    for k, v in (estilo or {}).items():
        if k == "negrita":
            e[k] = bool(v)
        elif k in e and v in {"tipografia": FUENTES_CLIPS, "tamano": TAMANOS, "color": COLORES, "fondo": FONDOS,
                              "posicion": POSICIONES_SUB}[k]:
            e[k] = v
    return e


def _ass_color(hex_rgb, alpha="00"):
    """'F4B43C' → '&H00 3C B4 F4' (libass: &HAABBGGRR)."""
    r, g, b = hex_rgb[0:2], hex_rgb[2:4], hex_rgb[4:6]
    return f"&H{alpha}{b}{g}{r}"


def estilo_ass(estilo, formato="vertical"):
    """Dict de estilo → cadena force_style de libass. Tamaños sobre PlayResY=288 (libass escala solo al alto real)."""
    e = normalizar_estilo(estilo)
    base, margen = (17, 46) if formato == "vertical" else (13, 24)
    tam = max(8, int(round(base * TAMANOS[e["tamano"]])))
    familia = FUENTES_CLIPS[e["tipografia"]][1]
    tipo, color_fondo, alpha = FONDOS[e["fondo"]]
    primario = _ass_color(COLORES[e["color"]])
    if tipo == "caja":
        # (la «sombra oscura» es exactamente la de antes del 19/10: borde &H70, caja &H90)
        borde = (f"BorderStyle=4,Outline=1,Shadow=0,OutlineColour={_ass_color(color_fondo, '70' if alpha == '90' else alpha)},"
                 f"BackColour={_ass_color(color_fondo, alpha)}")
    elif tipo == "borde":
        borde = f"BorderStyle=1,Outline=2,Shadow=0,OutlineColour={_ass_color(color_fondo, alpha)},BackColour=&HFF000000"
    else:
        borde = "BorderStyle=1,Outline=0,Shadow=0,OutlineColour=&HFF000000,BackColour=&HFF000000"
    return (f"FontName={familia},FontSize={tam},PrimaryColour={primario},{borde},Bold={'1' if e['negrita'] else '0'},"
            f"Alignment={POSICIONES_SUB[e['posicion']]},MarginV={margen},MarginL=14,MarginR=14")


def _filtro_subtitulos(srt, formato, estilo=None):
    """Filtro ffmpeg para quemar el SRT. Las fuentes se copian a ./sub_fuentes (ruta relativa: una letra de unidad
    con ":" rompe el parser de filtros en Windows). Estilo: ver estilo_ass (None = ESTILO_DEFECTO)."""
    os.makedirs("sub_fuentes", exist_ok=True)
    carpeta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fuentes")
    for archivo, _ in FUENTES_CLIPS.values():
        if not os.path.exists(os.path.join("sub_fuentes", archivo)):
            shutil.copy(os.path.join(carpeta, archivo), os.path.join("sub_fuentes", archivo))
    return f"subtitles={srt}:fontsdir=sub_fuentes:force_style='{estilo_ass(estilo, formato)}'"


def quiere_subtitulos(formato, opcion="auto"):
    """'auto': sí en vertical (shorts/reels), no en horizontal. 'si'/'no' fuerzan."""
    return opcion == "si" or (opcion == "auto" and formato == "vertical")


# ---------------- Quitar pausas largas (21/10; experimento del 19/10 aprobado por Franco) ----------------
# Estilo Riverside: se detectan los silencios del clip (ffmpeg silencedetect, umbral -32 dB, mínimo 0,7 s) y se saca el
# medio de cada uno dejando un colchón de 0,25 s a cada lado para que no suene cortado. En una charla de 53 s sacó 8 s
# (12 pausas); en una meditación casi nada (las pausas son parte del contenido, pero el umbral de 0,7 s no las toca si hay
# música o respiración audible). Se aplica DESPUÉS de cortar el tramo y ANTES de quemar los subtítulos, y los tiempos de
# las palabras / del SRT se corren con _mapear_tiempo para que sigan sincronizados.

def _run_ffmpeg(ffmpeg, args):
    return subprocess.run([ffmpeg, "-hide_banner", "-y"] + args, capture_output=True, text=True, encoding="utf-8", errors="replace")


def duracion_video(path, ffmpeg="ffmpeg"):
    """Duración en segundos según `ffmpeg -i` (no hace falta ffprobe). None si no la encuentra."""
    r = _run_ffmpeg(ffmpeg, ["-i", path])
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", r.stderr)
    if not m:
        return None
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)


def detectar_silencios(path, ffmpeg="ffmpeg", umbral_db=-32, min_sil=0.7):
    """[(inicio, fin), ...] en segundos de los silencios de más de min_sil s por debajo de umbral_db."""
    r = _run_ffmpeg(ffmpeg, ["-i", path, "-af", f"silencedetect=noise={umbral_db}dB:d={min_sil}", "-f", "null", "-"])
    ini = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", r.stderr)]
    fin = [float(x) for x in re.findall(r"silence_end: (-?[\d.]+)", r.stderr)]
    if len(ini) > len(fin):   # silencio que llega hasta el final del archivo: no tiene silence_end
        total = duracion_video(path, ffmpeg)
        if total is not None:
            fin.append(total)
    return [(max(0.0, a), b) for a, b in zip(ini, fin) if b > a]


def tramos_con_voz(total, silencios, colchon=0.25):
    """Lo que se conserva: todo menos el medio de cada silencio (se deja `colchon` s a cada lado). [(a, b), ...]."""
    keep, t = [], 0.0
    for a, b in silencios:
        a2, b2 = a + colchon, b - colchon
        if b2 - a2 <= 0.05:        # pausa demasiado corta una vez descontado el colchón: se deja
            continue
        if a2 > t:
            keep.append((t, a2))
        t = max(t, b2)
    if total > t:
        keep.append((t, total))
    return [(a, b) for a, b in keep if b - a > 0.05]


def _mapear_tiempo(t, keep):
    """Segundo `t` del clip con pausas → segundo del clip sin pausas. Un momento que cayó dentro de una pausa sacada
    va al punto del corte (ahí no hay palabras, así que los subtítulos no se pierden)."""
    acumulado = 0.0
    for a, b in keep:
        if t < a:
            return acumulado
        if t <= b:
            return acumulado + (t - a)
        acumulado += b - a
    return acumulado


def conservar_tramos(entrada, salida, keep, ffmpeg="ffmpeg", que="conservar los tramos"):
    """(21/10, noche) Arma `salida` con solo los tramos `keep` = [(a, b), ...] (segundos de `entrada`), pegados uno tras otro
    en ese orden (select/aselect + setpts/asetpts; re-encode x264 veryfast crf 18, aac 160k). Es el mecanismo de quitar pausas
    y también el de «sacar un pedazo del medio» (segmentos). Devuelve la duración resultante en segundos."""
    expr = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in keep)
    r = _run_ffmpeg(ffmpeg, ["-loglevel", "error", "-i", entrada,
                             "-vf", f"select='{expr}',setpts=N/FRAME_RATE/TB", "-af", f"aselect='{expr}',asetpts=N/SR/TB",
                             "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "aac", "-b:a", "160k", salida])
    if r.returncode != 0 or not os.path.exists(salida):
        raise RuntimeError(f"ffmpeg no pudo {que}: " + (r.stderr or "").strip()[-300:])
    return duracion_video(salida, ffmpeg) or sum(b - a for a, b in keep)


def _quitar_pausas_tramos(entrada, salida, ffmpeg="ffmpeg", umbral_db=-32, min_sil=0.7, colchon=0.25):
    """Como quitar_pausas, pero devuelve también los tramos conservados (para correr los subtítulos)."""
    total = duracion_video(entrada, ffmpeg)
    if total is None:
        raise RuntimeError("no pude leer la duración del clip para quitar las pausas")
    sil = detectar_silencios(entrada, ffmpeg, umbral_db, min_sil)
    keep = tramos_con_voz(total, sil, colchon)
    pausas = sum(1 for a, b in sil if (b - a) - 2 * colchon > 0.05)
    if not pausas:
        shutil.copyfile(entrada, salida)
        return total, total, 0, [(0.0, total)]
    despues = conservar_tramos(entrada, salida, keep, ffmpeg, "quitar las pausas")
    return total, despues, pausas, keep


# ---------------- Segmentos: partir el recorte y sacar un pedazo del medio (21/10, noche; editor visual de la web) ----------------
def normalizar_segmentos(segmentos, inicio_ms, fin_ms):
    """clips.edicion["segmentos"] = [[a_ms, b_ms], ...]: los tramos que se CONSERVAN, en milisegundos ABSOLUTOS del video original
    (como inicio_ms/fin_ms). Devuelve [(a, b), ...] en segundos relativos al tramo [inicio_ms, fin_ms], recortados a él, ordenados
    y sin solaparse; o None si no hay nada que sacar (vacío, o cubren el tramo entero). ValueError si ninguno cae en el tramo."""
    if not segmentos:
        return None
    tramos = []
    for s in segmentos:
        a, b = max(int(s[0]), int(inicio_ms)), min(int(s[1]), int(fin_ms))
        if b - a >= 50:
            tramos.append((a, b))
    tramos.sort()
    unidos = []
    for a, b in tramos:
        if unidos and a <= unidos[-1][1]:
            unidos[-1] = (unidos[-1][0], max(unidos[-1][1], b))
        else:
            unidos.append((a, b))
    if not unidos:
        raise ValueError("ningún segmento cae dentro del tramo")
    if len(unidos) == 1 and unidos[0] == (int(inicio_ms), int(fin_ms)):
        return None
    return [((a - inicio_ms) / 1000, (b - inicio_ms) / 1000) for a, b in unidos]


def _componer_mapas(mapas):
    """Varias listas keep aplicadas una tras otra (p. ej. segmentos y después pausas) → una sola lista [(a, b), ...] de lo que
    queda del tramo plano en el video final, en segundos del tramo plano. Es lo que la web usa para llevar un segundo del
    reproductor al segundo del original (clips.edicion["timeline"])."""
    if not mapas:
        return None
    res = list(mapas[0])
    for m in mapas[1:]:
        nuevo = []
        for a, b in m:   # (a, b) está en la timeline de SALIDA de res: se lleva a la de entrada
            acum = 0.0
            for p, q in res:
                lo, hi = max(a, acum), min(b, acum + (q - p))
                if hi - lo > 0.001:
                    nuevo.append((p + (lo - acum), p + (hi - acum)))
                acum += q - p
        res = nuevo
    return [(round(a, 3), round(b, 3)) for a, b in res]


def quitar_pausas(entrada, salida, ffmpeg="ffmpeg", umbral_db=-32, min_sil=0.7, colchon=0.25):
    """Arma `salida` = `entrada` sin las pausas largas (re-encode h264/aac). Devuelve (duración antes, duración después,
    cantidad de pausas sacadas), en segundos."""
    antes, despues, n, _ = _quitar_pausas_tramos(entrada, salida, ffmpeg, umbral_db, min_sil, colchon)
    return antes, despues, n


def _srt_a_segundos(t):
    """'HH:MM:SS,mmm' → segundos."""
    h, m, s = t.strip().replace(".", ",").split(":")
    s, ms = (s.split(",") + ["0"])[:2]
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")[:3]) / 1000


def _correr_srt(srt_txt, keep):
    """Corre los tiempos de un SRT (timeline con pausas) a la timeline sin pausas. El texto no se toca."""
    lineas = []
    for l in leer_srt(srt_txt):
        t0 = _mapear_tiempo(_srt_a_segundos(l["inicio"]), keep)
        t1 = _mapear_tiempo(_srt_a_segundos(l["fin"]), keep)
        if t1 - t0 < 0.2:   # la línea quedó aplastada contra un corte: que al menos se alcance a leer
            t1 = t0 + 0.2
        lineas.append({"inicio": _srt_tiempo(t0), "fin": _srt_tiempo(t1), "texto": l["texto"]})
    return armar_srt_de_lineas(lineas)


def cortar(entrada, salida, inicio, fin, ffmpeg="ffmpeg", formato="horizontal", palabras=None, srt_texto=None, estilo=None,
           quitar_pausas=False, srt_ya_sin_pausas=False, info=None, segmentos=None):
    """formato 'horizontal': el tramo tal cual (hasta 1280 de ancho). 'vertical' (15/10, pedido de Franco: shorts,
    reels, historias): lienzo 1080x1920 con el video centrado y, de fondo, el mismo video desenfocado.
    palabras: lista [[palabra, inicio_ms, fin_ms], ...] del video entero → subtítulos quemados (None = sin).
    srt_texto (19/10): un SRT ya armado (tiempos relativos al clip) que se quema tal cual en vez de armarlo desde
    `palabras`; es lo que manda cuando la persona corrigió los subtítulos en «Mis recortes».
    estilo (19/10, tarde): dict con tipografia/tamano/color/fondo/negrita/posicion (ver ESTILO_DEFECTO); None = el de siempre.
    quitar_pausas (21/10): saca los silencios largos del tramo antes de armar el video (ver quitar_pausas()); los tiempos de
    `palabras` o de `srt_texto` se corren solos para que los subtítulos sigan sincronizados. srt_ya_sin_pausas=True avisa que
    `srt_texto` ya está en la timeline sin pausas (es el SRT de un video que ya se había hecho sin pausas, con el mismo
    tramo) y no hay que correrlo. Si se pasa un dict en `info`, queda info["sin_pausas"] = {"antes", "despues", "pausas"}.
    segmentos (21/10, noche): [(a, b), ...] en segundos relativos al tramo [inicio, fin], los pedazos que se conservan (ver
    normalizar_segmentos); se aplican ANTES de quitar las pausas. info["segmentos"] = {"antes", "despues", "tramos"} e
    info["timeline"] = lo que queda del tramo plano en el video final (_componer_mapas), para que la web ubique los tiempos.
    srt_ya_sin_pausas vale también para los segmentos: True = el SRT ya está en la timeline del video final.
    Devuelve el texto SRT que se quemó ('' si el clip salió sin subtítulos)."""
    sub, srt_txt = "", ""
    temporales = []
    mapas = []   # listas keep aplicadas en orden (segmentos, pausas): con ellas se corren las palabras y el SRT
    if segmentos or quitar_pausas:
        # 1) el tramo tal cual (sin subtítulos ni lienzo); 2) solo los segmentos; 3) sin pausas; el corte de siempre sigue sobre
        # ese archivo desde 0
        base = os.path.splitext(os.path.basename(salida))[0]
        tmp_tramo = f"{base}.tramo.mp4"
        temporales.append(tmp_tramo)
        subprocess.check_call([ffmpeg, "-y", "-loglevel", "error", "-ss", f"{inicio:.3f}", "-to", f"{fin:.3f}", "-i", entrada,
                               "-vf", "scale='min(1280,iw)':-2", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                               "-c:a", "aac", "-b:a", "160k", tmp_tramo])
        if palabras:   # palabras del video entero (ms absolutos) → relativas al tramo plano
            ini_ms, fin_ms = int(inicio * 1000), int(fin * 1000)
            palabras = [[w[0], max(0, w[1] - ini_ms), max(0, min(w[2], w[1] + 1500) - ini_ms)]
                        for w in palabras if w[1] < fin_ms and w[2] > ini_ms]
        entrada, inicio, fin = tmp_tramo, 0.0, fin - inicio
        if segmentos:
            tmp_seg = f"{base}.segmentos.mp4"
            temporales.append(tmp_seg)
            antes = fin
            fin = conservar_tramos(entrada, tmp_seg, segmentos, ffmpeg, "pegar los segmentos")
            mapas.append(list(segmentos))
            entrada = tmp_seg
            if isinstance(info, dict):
                info["segmentos"] = {"antes": round(antes, 1), "despues": round(fin, 1), "tramos": len(segmentos)}
        if quitar_pausas:
            tmp_sin = f"{base}.sinpausas.mp4"
            temporales.append(tmp_sin)
            antes, despues, n_pausas, keep = _quitar_pausas_tramos(entrada, tmp_sin, ffmpeg)
            mapas.append(keep)
            entrada, fin = tmp_sin, despues
            if isinstance(info, dict):
                info["sin_pausas"] = {"antes": round(antes, 1), "despues": round(despues, 1), "pausas": n_pausas}
        if isinstance(info, dict):
            info["timeline"] = _componer_mapas(mapas)
        if palabras:
            for keep in mapas:
                palabras = [[w[0], int(_mapear_tiempo(w[1] / 1000, keep) * 1000), int(_mapear_tiempo(w[2] / 1000, keep) * 1000)]
                            for w in palabras]
    if srt_texto and srt_texto.strip():
        srt_txt = srt_texto.strip().replace("\r", "") + "\n"
        if mapas and not srt_ya_sin_pausas:
            for keep in mapas:
                srt_txt = _correr_srt(srt_txt, keep)
    elif palabras:
        srt_txt = armar_srt(palabras, inicio, fin)
    if srt_txt:
        srt = os.path.splitext(os.path.basename(salida))[0] + ".srt"   # en el cwd, sin ":" ni barras que confundan al filtro
        open(srt, "w", encoding="utf-8").write(srt_txt)
        sub = "," + _filtro_subtitulos(srt, formato, estilo)
    if formato == "vertical":
        vf = ("[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:5,eq=brightness=-0.08[bg];"
              "[0:v]scale=1080:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p" + sub)
        filtro = ["-filter_complex", vf]
    else:
        filtro = ["-vf", "scale='min(1280,iw)':-2" + sub]
    cmd = [ffmpeg, "-y", "-loglevel", "error", "-ss", f"{inicio:.3f}", "-to", f"{fin:.3f}", "-i", entrada,
           *filtro, "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
           "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", salida]
    try:
        subprocess.check_call(cmd)
    finally:
        for t in temporales:
            try:
                os.remove(t)
            except OSError:
                pass
    return srt_txt if sub else ""


def leer_srt(texto):
    """(19/10) Parsea un SRT a [{"n", "inicio", "fin", "texto"}] (inicio/fin como 'HH:MM:SS,mmm').
    Lo usa «Mis recortes» para mostrar una caja de texto por línea."""
    lineas = []
    for bloque in re.split(r"\n\s*\n", (texto or "").replace("\r", "").strip()):
        filas = [f for f in bloque.split("\n") if f.strip()]
        if len(filas) < 2 or "-->" not in filas[1]:
            continue
        t0, t1 = [x.strip() for x in filas[1].split("-->", 1)]
        lineas.append({"n": filas[0].strip(), "inicio": t0, "fin": t1, "texto": " ".join(f.strip() for f in filas[2:])})
    return lineas


def armar_srt_de_lineas(lineas):
    """(19/10) Inverso de leer_srt: [{"inicio", "fin", "texto"}] → texto SRT. Saltea las líneas con texto vacío
    (la persona las borró) y renumera."""
    out, i = [], 0
    for l in lineas:
        texto = " ".join((l.get("texto") or "").split())
        if not texto:
            continue
        i += 1
        out.append(f"{i}\n{l['inicio']} --> {l['fin']}\n{texto}\n")
    return "\n".join(out)


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
    ap.add_argument("--original", default="", help="(19/10) ruta local del original: no baja nada de Drive (busca <nombre>.palabras.json al lado)")
    ap.add_argument("--srt", default="", help="(19/10) archivo .srt ya armado (tiempos relativos al clip): se quema tal cual")
    ap.add_argument("--sin-subir", action="store_true", help="(19/10) solo cortar, sin subir a WordPress")
    ap.add_argument("--estilo", default="", help='(19/10) estilo de los subtítulos, JSON: {"tipografia":"Lato","tamano":"grande","color":"amarillo de la marca","fondo":"borde negro","negrita":true,"posicion":"centro"}')
    ap.add_argument("--quitar-pausas", action="store_true", help="(21/10) sacar los silencios de más de 0,7 s (umbral -32 dB, colchón 0,25 s)")
    ap.add_argument("--segmentos", default="", help='(21/10, noche) tramos que se conservan, en segundos del ORIGINAL: "58.6-70,75-106.6" (lo demás del tramo se saca)')
    a = ap.parse_args()
    nombre = a.nombre or a.youtube or a.drive_id or os.path.splitext(os.path.basename(a.original))[0]
    srt_texto = open(a.srt, encoding="utf-8").read() if a.srt else None
    quiere = quiere_subtitulos(a.formato, a.subtitulos) and not srt_texto
    if a.original:
        original, palabras = a.original, None
        pj = os.path.join(os.path.dirname(a.original), f"{nombre}.palabras.json")
        if quiere and os.path.exists(pj):
            palabras = json.load(open(pj, encoding="utf-8"))
    else:
        svc = _drive()
        file_id = a.drive_id or buscar_original(svc, a.youtube)
        if not file_id:
            raise SystemExit(f"No encontré el original de {a.youtube} en Drive (carpeta {CARPETA_ORIGINALES}).")
        original = f"original_{nombre}.mp4"
        descargar_drive(svc, file_id, original)
        palabras = buscar_palabras(svc, a.youtube or nombre) if quiere else None
    clip = f"clip-{nombre}-{int(a.inicio)}-{int(a.fin)}{'-vertical' if a.formato == 'vertical' else ''}.mp4"
    estilo = json.loads(a.estilo) if a.estilo else None
    info = {}
    segmentos = None
    if a.segmentos:
        pares = [[int(float(x) * 1000) for x in t.split("-")] for t in a.segmentos.split(",") if t.strip()]
        segmentos = normalizar_segmentos(pares, int(a.inicio * 1000), int(a.fin * 1000))
    con_sub = cortar(original, clip, a.inicio, a.fin, a.ffmpeg, a.formato, palabras, srt_texto, estilo,
                     quitar_pausas=a.quitar_pausas, info=info, segmentos=segmentos)
    print(f"clip: {clip} ({os.path.getsize(clip) // 1024} KB){' · con subtítulos' if con_sub else ''}")
    if info.get("segmentos"):
        sg = info["segmentos"]
        print(f"segmentos: {sg['antes']:.1f} s → {sg['despues']:.1f} s, {sg['tramos']} tramos conservados")
    if info.get("sin_pausas"):
        sp = info["sin_pausas"]
        print(f"sin pausas: {sp['antes']:.1f} s → {sp['despues']:.1f} s, {sp['pausas']} pausas sacadas")
    if con_sub:
        open(os.path.splitext(clip)[0] + ".usado.srt", "w", encoding="utf-8").write(con_sub)
    if a.sin_subir:
        return

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
