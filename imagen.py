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
Tipografías en `fuentes/` (licencia OFL). `tipografia`: "Lora" (serif, la de siempre) o "Lato"
(sans); para sumar otra, poner el .ttf en `fuentes/` y agregarla a TIPOGRAFIAS. `posicion`: "centro"
(como siempre), "arriba" o "abajo"; el degradado oscuro acompaña a la posición. `alineacion`:
"centro" o "izquierda". (8/10, pedido de Julián tras la primera prueba real.)
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
# nombre visible → (archivo de la cita, archivo de la firma en cursiva)
# (15/10) Raleway es la tipografía de la Fundación (Julián la mandó; es la misma de Google Fonts, OFL).
# Es variable: el peso se elige con PESOS. Va primera = la que sale por defecto.
TIPOGRAFIAS = {
    "Raleway (Fundación)": ("Raleway-Variable.ttf", "Raleway-Italic-Variable.ttf"),
    "Lora": ("Lora-Variable.ttf", "Lato-Italic.ttf"),
    "Lato": ("Lato-Regular.ttf", "Lato-Italic.ttf"),
}
PESOS = {"normal": 400, "fina": 300, "negrita": 700}   # eje wght de las fuentes variables; Lato (fija) lo ignora
TIPOGRAFIA_DEFAULT = "Raleway (Fundación)"
POSICIONES = ("centro", "arriba", "abajo")
ALINEACIONES = ("centro", "izquierda")
# (13/10) Logos que Julián subió a la biblioteca de WordPress (reunión 13/10: "qué logo querés" +
# tamaño estándar por formato). nombre visible → URL. Tamaño: los apaisados ocupan el 22 % del ancho,
# los cuadrados (la flor) el 10 % del alto; margen 5 % (8 % arriba/abajo en historias, por la interfaz de IG).
LOGOS = {
    "Sin logo": None,
    "Amarillo": "https://viviragradecidos.org/wp-content/uploads/2026/10/Logo_VA_2026_amarillo_sombra.png",
    "Blanco": "https://viviragradecidos.org/wp-content/uploads/2026/10/Logo_VA_2026_boanco_sombra.png",
    "Flor amarilla": "https://viviragradecidos.org/wp-content/uploads/2026/10/Logo_VA_2026_flor_amarillo_sombra.png",
    "Flor blanca": "https://viviragradecidos.org/wp-content/uploads/2026/10/Logo_VA_2026_flor_blanco_sombra.png",
}
POSICIONES_LOGO = ("abajo derecha", "abajo izquierda", "abajo centro", "arriba derecha", "arriba izquierda", "arriba centro")
_LOGO_CACHE = {}


def _logo_png(logo):
    """logo: nombre de LOGOS, URL o bytes. Devuelve Image RGBA o None."""
    if not logo:
        return None
    src = LOGOS.get(logo, logo) if isinstance(logo, str) else logo
    if not src:
        return None
    k = src if isinstance(src, str) else hash(bytes(src))
    if k not in _LOGO_CACHE:
        _LOGO_CACHE[k] = _abrir(src).convert("RGBA")
    return _LOGO_CACHE[k]


def _pegar_logo(img, logo, posicion_logo, formato):
    """Pega el logo con tamaño estándar. Devuelve (img, alto_ocupado_arriba, alto_ocupado_abajo)."""
    lg = _logo_png(logo)
    if lg is None:
        return img, 0, 0
    ancho, alto = img.size
    if lg.width / max(lg.height, 1) > 1.5:
        w = int(ancho * 0.22); h = int(lg.height * w / lg.width)
    else:
        h = int(alto * 0.10); w = int(lg.width * h / lg.height)
    lg = lg.resize((max(w, 1), max(h, 1)), Image.LANCZOS)
    mx = int(ancho * 0.05)
    my = int(alto * (0.08 if formato == "historia" else 0.05))
    pos = posicion_logo if posicion_logo in POSICIONES_LOGO else "abajo derecha"
    vert, horiz = pos.split(" ", 1)
    x = {"derecha": ancho - mx - w, "izquierda": mx, "centro": (ancho - w) // 2}[horiz]
    y = alto - my - h if vert == "abajo" else my
    img.paste(lg, (x, y), lg)
    ocupado = my + h
    return img, (ocupado if vert == "arriba" else 0), (ocupado if vert == "abajo" else 0)


def _fuente(nombre, tam, peso=400):
    ruta = os.path.join(FUENTES, nombre)
    try:
        f = ImageFont.truetype(ruta, tam)
    except OSError:
        return ImageFont.load_default()
    # Fuentes variables: la instancia por defecto puede ser "Thin" (Raleway); fijamos el peso pedido.
    try:
        if f.get_variation_axes():
            f.set_variation_by_axes([peso])
    except Exception:
        pass
    return f


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


def _ajustar(texto, draw, ancho_max, alto_max, fuente_nombre, tam_max=64, tam_min=34, max_lineas=9, peso=400):
    """Busca el tamaño de letra más grande con el que el texto entra en la caja."""
    for tam in range(tam_max, tam_min - 1, -2):
        f = _fuente(fuente_nombre, tam, peso)
        lineas = _partir(texto, f, ancho_max, draw)
        interlineado = int(tam * 1.32)
        alto = interlineado * len(lineas)
        if len(lineas) <= max_lineas and alto <= alto_max:
            return f, lineas, interlineado
    f = _fuente(fuente_nombre, tam_min, peso)
    lineas = _partir(texto, f, ancho_max, draw)[:max_lineas]
    if len(lineas) == max_lineas and not lineas[-1].endswith("…"):
        lineas[-1] = lineas[-1].rstrip(".,;:") + "…"
    return f, lineas, int(tam_min * 1.32)


def componer_imagen(foto, texto, firma="— Br. David", formato="cuadrado", oscurecer=0.45, calidad=90,
                    tipografia=None, posicion="centro", alineacion="centro", logo=None, posicion_logo="abajo derecha",
                    peso="normal"):
    """Devuelve bytes JPEG: la foto recortada al formato, oscurecida, con el texto y la firma."""
    tipografia = tipografia or TIPOGRAFIA_DEFAULT
    wght = PESOS.get(peso, 400)
    ancho, alto = FORMATOS.get(formato, FORMATOS["cuadrado"])
    f_cita_nombre, f_firma_nombre = TIPOGRAFIAS.get(tipografia, TIPOGRAFIAS[TIPOGRAFIA_DEFAULT])
    posicion = posicion if posicion in POSICIONES else "centro"
    alineacion = alineacion if alineacion in ALINEACIONES else "centro"
    img = _abrir(foto)
    img = ImageOps.exif_transpose(img).convert("RGB")
    img = ImageOps.fit(img, (ancho, alto), method=Image.LANCZOS, centering=(0.5, 0.5))

    # Degradado: más oscuro en el centro-abajo donde va el texto, más suave arriba.
    velo = Image.new("L", (1, alto))
    for y in range(alto):
        t = y / max(alto - 1, 1)
        if posicion == "arriba":
            t = 1.0 - t   # el texto va arriba: ahí va lo más oscuro
        # 0.55·oscurecer en el extremo lejano → oscurecer pleno desde el 35% hacia el texto
        peso = oscurecer * (0.55 + 0.45 * min(t / 0.35, 1.0))
        velo.putpixel((0, y), int(255 * peso))
    velo = velo.resize((ancho, alto))
    negro = Image.new("RGB", (ancho, alto), (0, 0, 0))
    img = Image.composite(negro, img, velo)

    img, logo_arriba, logo_abajo = _pegar_logo(img, logo, posicion_logo, formato)

    draw = ImageDraw.Draw(img)
    margen = int(ancho * 0.09)
    ancho_caja = ancho - 2 * margen
    alto_caja = int(alto * 0.62)

    texto = (texto or "").strip()
    if not texto:
        # (13/10) foto + logo, sin frase
        salida = io.BytesIO()
        img.save(salida, format="JPEG", quality=calidad, optimize=True)
        return salida.getvalue()
    f_cita, lineas, inter = _ajustar(texto, draw, ancho_caja, alto_caja, f_cita_nombre, peso=wght)
    f_firma = _fuente(f_firma_nombre, max(int(f_cita.size * 0.55), 26), 400)

    alto_texto = inter * len(lineas)
    sep_firma = int(inter * 0.9) if firma else 0
    alto_firma = int(f_firma.size * 1.3) if firma else 0
    bloque = alto_texto + sep_firma + alto_firma
    if posicion == "arriba":
        y = max(int(alto * 0.10), logo_arriba + int(alto * 0.03))
    elif posicion == "abajo":
        y = alto - bloque - max(int(alto * 0.10), logo_abajo + int(alto * 0.03))
    else:
        y = (alto - bloque) // 2 + int(alto * 0.03)

    def _x(w):
        return margen if alineacion == "izquierda" else (ancho - w) / 2

    sombra = (0, 0, 0)
    for linea in lineas:
        w = draw.textlength(linea, font=f_cita)
        x = _x(w)
        draw.text((x + 2, y + 2), linea, font=f_cita, fill=sombra)
        draw.text((x, y), linea, font=f_cita, fill=(255, 255, 255))
        y += inter

    if firma:
        y += sep_firma
        w = draw.textlength(firma, font=f_firma)
        x = _x(w)
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


# ---------------- (23/10, prueba de Julián) Cabecera del newsletter ----------------
# "Que la imagen se ajuste sola al formato de la cabecera y que el título vaya encima; fondo oscuro → letra blanca,
# fondo claro → azul de la Fundación." Formato fijo 1600×500 (en el mail se ve a 600×188).
CABECERA_ANCHO, CABECERA_ALTO = 1600, 500
AZUL_FUNDACION = (0, 50, 63)       # #00323f


def _luminancia(img):
    """0 (negro) a 255 (blanco): promedio del gris de la imagen (ya recortada a la zona que importa)."""
    g = img.convert("L").resize((32, 32))
    px = list(g.getdata())
    return sum(px) / max(len(px), 1)


def componer_cabecera(foto, titulo, ancho=CABECERA_ANCHO, alto=CABECERA_ALTO, calidad=88, color=None):
    """Devuelve (bytes JPEG, "blanco"|"azul"): la foto recortada a 1600×500 con el título centrado encima.
    El color de la letra sale solo del fondo (luminancia de la franja central): oscuro → blanco, claro → azul #00323f;
    `color` lo fuerza. Sin título, devuelve la foto recortada sola."""
    img = _abrir(foto)
    img = ImageOps.exif_transpose(img).convert("RGB")
    img = ImageOps.fit(img, (ancho, alto), method=Image.LANCZOS, centering=(0.5, 0.5))
    titulo = " ".join((titulo or "").split())
    franja = img.crop((int(ancho * 0.15), int(alto * 0.2), int(ancho * 0.85), int(alto * 0.8)))
    oscuro = _luminancia(franja) < 128
    elegido = color if color in ("blanco", "azul") else ("blanco" if oscuro else "azul")
    if not titulo:
        salida = io.BytesIO()
        img.save(salida, format="JPEG", quality=calidad, optimize=True)
        return salida.getvalue(), elegido
    # un velo suave para que la letra se lea sobre fotos con mucho detalle (más oscuro o más claro según la letra)
    velo = Image.new("RGB", (ancho, alto), (0, 0, 0) if elegido == "blanco" else (255, 255, 255))
    img = Image.blend(img, velo, 0.18)
    draw = ImageDraw.Draw(img)
    f_nombre, _ = TIPOGRAFIAS[TIPOGRAFIA_DEFAULT]
    margen = int(ancho * 0.08)
    f, lineas, inter = _ajustar(titulo, draw, ancho - 2 * margen, int(alto * 0.7), f_nombre, tam_max=110, tam_min=48, max_lineas=3, peso=700)
    rgb = (255, 255, 255) if elegido == "blanco" else AZUL_FUNDACION
    y = (alto - inter * len(lineas)) // 2
    for linea in lineas:
        w = draw.textlength(linea, font=f)
        draw.text(((ancho - w) / 2, y), linea, font=f, fill=rgb)
        y += inter
    salida = io.BytesIO()
    img.save(salida, format="JPEG", quality=calidad, optimize=True)
    return salida.getvalue(), elegido
