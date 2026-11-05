"""
banco.py — Banco de imágenes: sincroniza una carpeta de Drive con la biblioteca de medios de WordPress (5/11, Franco y Julián).

Julián arma en Drive, dentro de «FBA Automatización de Contenidos», la carpeta «Banco de Imágenes» con subcarpetas (por formato y/o por
tema) y archivos con el nombre `etiqueta_etiqueta_1080x1920.jpg`. La cola (procesar_cola.py, cada 15 minutos) llama a
`sincronizar_banco`, que sube a WordPress lo que todavía no está subido, con título = etiquetas y la marca fija `banco-fva` en la
descripción (publicar.subir_imagen_wordpress(..., banco=True)). Esa marca es lo que después deja buscar SOLO en el banco
(publicar.buscar_imagenes_banco(..., solo_banco=True) y la clave de configuración `banco_solo`).

Convención de nombres (la del script viejo subir_banco.py):
  - medidas AAAAxBBBB en el nombre o en una carpeta → formato: iguales = cuadrado, más alto que ancho = vertical, más ancho = horizontal;
  - si no hay medidas, el nombre de una subcarpeta que sea un formato (cuadrado / vertical / horizontal; también historia, stories, apaisado);
  - el resto de las palabras (del nombre y de las subcarpetas, separadas por _ - espacio) son etiquetas; las medidas y las palabras sueltas
    («de», «foto», «final»…) no.
Registro: tabla banco_imagenes (db/banco.py): id de Drive, modified_time, wp_id, url, formato, etiquetas. Lo ya registrado no se vuelve a subir,
salvo que Drive diga que el archivo cambió (modifiedTime distinto).
"""
import os, re, tempfile

MARCA = "banco-fva"
TOPE_CORRIDA = 30                      # imágenes por corrida: el resto va en la siguiente, para no colgar la cola
MIMES = ("image/jpeg", "image/png", "image/webp")
CARPETA_MIME = "application/vnd.google-apps.folder"
FORMATOS = ("cuadrado", "vertical", "horizontal")
_ALIAS_FORMATO = {"cuadrado": "cuadrado", "vertical": "vertical", "horizontal": "horizontal",
                  "historia": "vertical", "historias": "vertical", "story": "vertical", "stories": "vertical", "apaisado": "horizontal"}
IGNORAR = {"y", "de", "la", "el", "con", "en", "para", "img", "image", "foto", "photo", "final", "copia", "copy", "los", "las", "del"}
_MEDIDAS = re.compile(r"(\d{3,4})\s*[x×]\s*(\d{3,4})")
_PROFUNDIDAD_MAX = 8


def extraer_carpeta_id(valor):
    """Acepta la URL pegada de Drive (…/folders/<id>?…, …?id=<id>) o el id solo. Devuelve el id o None si no se reconoce."""
    s = (valor or "").strip() if isinstance(valor, str) else ""
    if not s:
        return None
    m = re.search(r"/folders/([A-Za-z0-9_-]{10,})", s) or re.search(r"[?&]id=([A-Za-z0-9_-]{10,})", s)
    if m:
        return m.group(1)
    return s if re.fullmatch(r"[A-Za-z0-9_-]{10,}", s) else None


def formato_de_medidas(w, h):
    return "cuadrado" if w == h else ("vertical" if h > w else "horizontal")


def deducir(nombre, carpetas):
    """(etiquetas, formato) de un archivo: `nombre` con extensión y `carpetas` = nombres de las subcarpetas desde la raíz del banco.
    formato es None si ni las medidas ni las carpetas lo dicen."""
    base = os.path.splitext(nombre)[0]
    crudo = " ".join(list(carpetas) + [base]).lower()
    formato = None
    m = _MEDIDAS.search(base.lower()) or _MEDIDAS.search(" ".join(carpetas).lower())
    if m:
        formato = formato_de_medidas(int(m.group(1)), int(m.group(2)))
    etiquetas = []
    for t in re.split(r"[\s_\-\.\(\)\[\],]+", _MEDIDAS.sub(" ", crudo)):
        if not t:
            continue
        if t in _ALIAS_FORMATO:
            formato = formato or _ALIAS_FORMATO[t]          # una carpeta «Cuadrado» da el formato, no una etiqueta
            continue
        if t in IGNORAR or t.isdigit() or len(t) < 3:
            continue
        if t not in etiquetas:
            etiquetas.append(t)
    return etiquetas, formato


def listar_imagenes(svc, carpeta_id):
    """Todas las imágenes de la carpeta y sus subcarpetas: [{id, name, modifiedTime, carpetas: [nombres…]}]. Pagina files.list."""
    out, vistas = [], set()

    def recorrer(cid, ruta, nivel):
        if cid in vistas or nivel > _PROFUNDIDAD_MAX:
            return
        vistas.add(cid)
        q = f"'{cid}' in parents and trashed = false and (mimeType = '{CARPETA_MIME}' or " + " or ".join(f"mimeType = '{t}'" for t in MIMES) + ")"
        token, subcarpetas = None, []
        while True:
            r = svc.files().list(q=q, fields="nextPageToken, files(id, name, mimeType, modifiedTime)", pageSize=1000, pageToken=token,
                                 supportsAllDrives=True, includeItemsFromAllDrives=True, orderBy="name").execute()
            for f in r.get("files", []):
                if f.get("mimeType") == CARPETA_MIME:
                    subcarpetas.append(f)
                else:
                    out.append({"id": f["id"], "name": f["name"], "modifiedTime": f.get("modifiedTime"), "carpetas": list(ruta)})
            token = r.get("nextPageToken")
            if not token:
                break
        for sc in subcarpetas:
            recorrer(sc["id"], ruta + [sc["name"]], nivel + 1)

    recorrer(carpeta_id, [], 0)
    return out


def _bajar(svc, file_id, destino):
    datos = svc.files().get_media(fileId=file_id, supportsAllDrives=True).execute()
    with open(destino, "wb") as fh:
        fh.write(datos)


def sincronizar_banco(cfg, svc_drive, carpeta_id, registro, tope=TOPE_CORRIDA, descargar=None, guardar=None, quien="banco"):
    """Sube a WordPress lo de la carpeta de Drive que no esté en `registro` ({drive_id: {"modified_time": …}}) o que haya cambiado.
    `descargar(svc, file_id, destino)` y `guardar(drive_id, nombre, modified_time, wp_id, url, formato, etiquetas)` se pueden reemplazar
    (pruebas); por defecto bajan con Drive v3 y guardan en la tabla banco_imagenes (db.banco_guardar). Sin `id` de WordPress en la
    respuesta (modo simulado) no se registra nada: así no se bloquea la subida real.
    Máximo `tope` imágenes por corrida (las que fallan también cuentan); lo que sobra queda para la siguiente.
    Devuelve {"subidas", "salteadas", "errores", "pendientes", "simuladas", "detalle": [mensajes de error]}."""
    import publicar
    if guardar is None:
        import db
        guardar = db.banco_guardar
    descargar = descargar or _bajar
    resumen = {"subidas": 0, "salteadas": 0, "errores": 0, "pendientes": 0, "simuladas": 0, "detalle": []}
    if getattr(cfg, "modo_wp", None) == "apagado":
        resumen["detalle"].append("WordPress está apagado (PUBLICAR_WORDPRESS): no se sube nada.")
        return resumen
    pendientes = []
    for f in listar_imagenes(svc_drive, carpeta_id):
        previo = registro.get(f["id"])
        if previo is not None and (previo.get("modified_time") or None) == (f.get("modifiedTime") or None):
            resumen["salteadas"] += 1
        else:
            pendientes.append(f)
    resumen["pendientes"] = max(0, len(pendientes) - tope)
    with tempfile.TemporaryDirectory(prefix="banco_") as tmp:
        for f in pendientes[:tope]:
            try:
                etiquetas, formato = deducir(f["name"], f["carpetas"])
                ruta = os.path.join(tmp, f["id"] + os.path.splitext(f["name"])[1].lower())
                descargar(svc_drive, f["id"], ruta)
                res = publicar.subir_imagen_wordpress(cfg, ruta, f["name"], titulo=" ".join(etiquetas) or os.path.splitext(f["name"])[0],
                                                      etiquetas=etiquetas + ([formato] if formato else []), quien=quien, banco=True)
                if not res.get("ok"):
                    raise RuntimeError(res.get("aviso") or "WordPress no aceptó la imagen")
                if res.get("id") is None:               # simulado: no se subió nada, no se anota
                    resumen["simuladas"] += 1
                    continue
                guardar(f["id"], f["name"], f.get("modifiedTime"), res["id"], res.get("url"), formato, etiquetas)
                registro[f["id"]] = {"modified_time": f.get("modifiedTime"), "wp_id": res["id"]}
                resumen["subidas"] += 1
            except Exception as e:
                resumen["errores"] += 1
                resumen["detalle"].append(f"{f['name']}: {str(e)[:150]}")
    return resumen


def sincronizar_desde_config(cfg, svc=None):
    """Lo que hacen la cola y el botón «Sincronizar ahora»: lee banco_drive_carpeta de la config, arma el cliente de Drive (si no viene),
    carga el registro y sincroniza. None si no hay carpeta configurada."""
    import db
    carpeta = extraer_carpeta_id(db.obtener_config("banco_drive_carpeta"))
    if not carpeta:
        return None
    if svc is None:
        import recortar_clip
        svc = recortar_clip._drive()
    return sincronizar_banco(cfg, svc, carpeta, db.banco_registro())
