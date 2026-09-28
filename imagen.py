"""
imagen.py — Texto sobre imagen (28/9). Pieza de redes = foto del banco + frase encima + firma.

Decidido en la reunión del 28/9: lo hace el bot con una herramienta propia (Pillow), Canva no entra.
Julián arma el banco de fotos limpias; esto toma una de esas fotos y la frase de la pieza y devuelve
el JPG listo para publicar. No genera imágenes ni busca en internet.

Uso:
    from imagen import componer_imagen
    jpg_bytes = componer_imagen(foto, texto, firma="— Br. David", formato="cuadrado")

`foto` puede ser bytes, una ruta o una URL http(s). `formato`: "cuadrado" (1080×1080, IG/FB),
"vertical" (1080×1350, feed IG) o "historia" (1080×1920). Devuelve bytes JPEG.

Cómo compone: recorta la foto para cubrir el lienzo (sin deformar), oscurece con un degradado suave
para que el texto blanco se lea sobre cualquier fondo, elige el tamaño de letra más grande con el
que la frase entra en la caja (máx. 7 líneas), la centra, y abajo pone la firma en cursiva.
Tipografías en `fuentes/` (Lora para la cita, Lato para la firma; licencia OFL).
"""
import io
import os
import textwrap

from PIL import Image, ImageDraw, ImageFont, ImageOps

AQUI = os.path.dirname(os.path.abspath(__file__))
FUENTES = os.path.join(AQUI, "fuentes")

FORMATOS = {
    "cuadrado": (1080, 1080),
    "vertical": (1080, 1350),
    "historia": (1080, 1920),
}


def _fuente(nombre, tam):
    ruta = os.path.join(FUENTES, nombre)
    try:
        return ImageFont.truetype(ruta, tam)
    except OSError:
        return ImageFont.load_default()


def _abrir(foto):
    if isinstance(foto, (bytes, bytearray)):
        return Image.open(io.BytesIO(foto))
    if isinstance(foto, str) and foto.startswith(("http://", "https://")):
        import urllib.request
        req = urllib.request.Request(foto, headers={"User-Agent": "Mozilla/5.0 (FVA imagen.py)"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return Image.open(io.BytesIO(r.read()))
    return Image.open(foto)


def _partir(texto, fuente, ancho_max, draw):
    """Parte el texto en líneas que entren en ancho_max con esa fuente. Respeta saltos de línea."""
    lineas = []
    for parrafo in texto.split("\n"):
        if not parrafo.strip():
            lineas.append("")
            continue
        # textwrap por cantidad de caracteres es una aproximación; después se verifica en píxeles.
        ancho_char = max(draw.textlength("n", font=fuente), 1)
        cols = max(int(ancho_max / ancho_char), 8)
        for linea in textwrap.wrap(parrafo, width=cols, break_long_words=False, break_on_hyphens=False):
            while draw.textlength(linea, font=fuente) > ancho_max and " " in linea:
                # se pasó: mover la última palabra a la línea siguiente
                cabeza, cola = linea.rsplit(" ", 1)
                lineas.append(cabeza)
                linea = cola
            lineas.append(linea)
    return lineas


def _ajustar(texto, draw, ancho_max, alto_max, fuente_nombre, tam_max=64, tam_min=34, max_lineas=9):
    """Busca el tamaño de letra más grande con el que el texto entra en la caja."""
    for tam in range(tam_max, tam_min - 1, -2):
        f = _fuente(fuente_nombre, tam)
        lineas = _partir(texto, f, ancho_max, draw)
        interlineado = int(tam * 1.32)
        alto = interlineado * len(lineas)
        if len(lineas) <= max_lineas and alto <= alto_max:
            return f, lineas, interlineado
    f = _fuente(fuente_nombre, tam_min)
    lineas = _partir(texto, f, ancho_max, draw)[:max_lineas]
    if len(lineas) == max_lineas and not lineas[-1].endswith("…"):
        lineas[-1] = lineas[-1].rstrip(".,;:") + "…"
    return f, lineas, int(tam_min * 1.32)


def componer_imagen(foto, texto, firma="— Br. David", formato="cuadrado", oscurecer=0.45, calidad=90):
    """Devuelve bytes JPEG: la foto recortada al formato, oscurecida, con el texto centrado y la firma."""
    ancho, alto = FORMATOS.get(formato, FORMATOS["cuadrado"])
    img = _abrir(foto)
    img = ImageOps.exif_transpose(img).convert("RGB")
    img = ImageOps.fit(img, (ancho, alto), method=Image.LANCZOS, centering=(0.5, 0.5))

    # Degradado: más oscuro en el centro-abajo donde va el texto, más suave arriba.
    velo = Image.new("L", (1, alto))
    for y in range(alto):
        t = y / max(alto - 1, 1)
        # 0.55·oscurecer arriba → oscurecer pleno desde el 35% hacia abajo
        peso = oscurecer * (0.55 + 0.45 * min(t / 0.35, 1.0))
        velo.putpixel((0, y), int(255 * peso))
    velo = velo.resize((ancho, alto))
    negro = Image.new("RGB", (ancho, alto), (0, 0, 0))
    img = Image.composite(negro, img, velo)

    draw = ImageDraw.Draw(img)
    margen = int(ancho * 0.09)
    ancho_caja = ancho - 2 * margen
    alto_caja = int(alto * 0.62)

    texto = (texto or "").strip()
    f_cita, lineas, inter = _ajustar(texto, draw, ancho_caja, alto_caja, "Lora-Variable.ttf")
    f_firma = _fuente("Lato-Italic.ttf", max(int(f_cita.size * 0.55), 26))

    alto_texto = inter * len(lineas)
    sep_firma = int(inter * 0.9) if firma else 0
    alto_firma = int(f_firma.size * 1.3) if firma else 0
    bloque = alto_texto + sep_firma + alto_firma
    y = (alto - bloque) // 2 + int(alto * 0.03)

    sombra = (0, 0, 0)
    for linea in lineas:
        w = draw.textlength(linea, font=f_cita)
        x = (ancho - w) / 2
        draw.text((x + 2, y + 2), linea, font=f_cita, fill=sombra)
        draw.text((x, y), linea, font=f_cita, fill=(255, 255, 255))
        y += inter

    if firma:
        y += sep_firma
        w = draw.textlength(firma, font=f_firma)
        x = (ancho - w) / 2
        draw.text((x + 1, y + 1), firma, font=f_firma, fill=sombra)
        draw.text((x, y), firma, font=f_firma, fill=(235, 235, 235))

    salida = io.BytesIO()
    img.save(salida, format="JPEG", quality=calidad, optimize=True)
    return salida.getvalue()


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("uso: python imagen.py <foto> <salida.jpg> [texto]")
        sys.exit(1)
    txt = sys.argv[3] if len(sys.argv) > 3 else "“Una vez que logres ser simultáneamente consciente de la luz y de la oscuridad, podrás mirar con nuevos ojos a todo lo que se presenta oscuro a tu alrededor.”"
    with open(sys.argv[2], "wb") as f:
        f.write(componer_imagen(sys.argv[1], txt))
    print("ok", sys.argv[2])
