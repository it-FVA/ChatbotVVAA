"""Pruebas de api/publicar_rutas.py (fase 3, 22/10) sin Supabase, WordPress ni redes: db, publicar e imagen con monkeypatch.
franco es admin (publica directo); lizzie, creadora de contenido (todo simulado, manda a aprobación)."""
import io

import pytest

import db
import publicar
import imagen
import api.chat_rutas as cr
import api.publicar_rutas as pr

JPG = b"\xff\xd8\xff\xe0" + b"0" * 64 + b"\xff\xd9"


@pytest.fixture
def lizzie():
    """Un cliente aparte (otra cookie) para la creadora de contenido."""
    from fastapi.testclient import TestClient
    from api.main import app
    with TestClient(app) as c:
        r = c.post("/login", json={"usuario": "lizzie", "clave": "clave-lizzie"})
        assert r.status_code == 200, r.text
        yield c


@pytest.fixture
def base(monkeypatch):
    """Supabase «disponible», modos reales fijos y una tabla publicaciones en memoria mínima para _fila / DELETE."""
    monkeypatch.setattr(db, "disponible", lambda: True)
    monkeypatch.setattr(cr, "modos", lambda: {"wordpress": "borrador", "instagram": "real", "facebook": "simulado", "youtube": "privado",
                                              "wp_configurado": True, "ig_configurado": True, "fb_configurado": False, "yt_configurado": True})
    monkeypatch.setenv("PUBLICAR_WORDPRESS", "borrador")
    monkeypatch.setenv("PUBLICAR_INSTAGRAM", "real")
    monkeypatch.setenv("PUBLICAR_FACEBOOK", "simulado")
    monkeypatch.setenv("PUBLICAR_YOUTUBE", "privado")
    filas = {}
    llamadas = []

    def _req(method, params="", body=None, tabla="conversaciones"):
        llamadas.append((method, params, body, tabla))
        if tabla == "publicaciones" and method == "GET" and params.startswith("?id=eq."):
            pid = params[len("?id=eq."):].split("&")[0]
            return [dict(filas[pid])] if pid in filas else []
        if tabla == "publicaciones" and method == "DELETE":
            pid = params[len("?id=eq."):].split("&")[0]
            filas.pop(pid, None)
        return []
    monkeypatch.setattr(db, "_req", _req)
    monkeypatch.setattr(db, "registrar_publicacion", lambda **k: llamadas.append(("registro", k)) or "reg")
    monkeypatch.setattr(imagen, "componer_imagen", lambda foto, texto, **k: JPG + texto.encode("utf-8"))
    pr._CACHE_COMPUESTAS.clear()
    return {"filas": filas, "llamadas": llamadas}


# ---------------- Opciones, banco, componer ----------------
def test_opciones_por_rol(logueado, lizzie, base, monkeypatch):
    d = logueado.get("/publicar/opciones").json()
    assert d["publica"] is True and d["canales"]["instagram"]["modo"] == "real" and d["canales"]["instagram"]["modo_real"] == "real"
    assert d["canales"]["wordpress"]["a_aprobar"] is True and d["canales"]["facebook"]["a_aprobar"] is False
    assert "Sin logo" in d["logos"] and d["tipografia_defecto"] in d["tipografias"] and d["formatos"]["historia"] == [1080, 1920]
    assert d["firma_defecto"] == "— Br. David" and d["formato_por_canal"]["instagram"] == "vertical"
    # la creadora ve todo simulado (publicar_ui._cfg), salvo lo apagado
    monkeypatch.setattr(cr, "modos", lambda: {"wordpress": "borrador", "instagram": "real", "facebook": "apagado", "youtube": "privado"})
    d = lizzie.get("/publicar/opciones").json()
    assert d["publica"] is False and d["canales"]["instagram"]["modo"] == "simulado" and d["canales"]["instagram"]["modo_real"] == "real"
    assert d["canales"]["facebook"]["modo"] == "apagado"


def test_subir_al_banco(logueado, base, monkeypatch):
    subidas = []

    def _subir(cfg, datos, nombre, titulo="", etiquetas=None, quien="", pieza=""):
        subidas.append((nombre, titulo, quien, len(datos)))
        return {"ok": True, "modo": cfg.modo_wp, "url": "https://wp/x.jpg", "id": 5}
    monkeypatch.setattr(publicar, "subir_imagen_wordpress", _subir)
    r = logueado.post("/banco/subir", files={"archivo": ("mi foto ñ.jpg", io.BytesIO(JPG), "image/jpeg")}, data={"titulo": "Amanecer"})
    assert r.status_code == 200 and r.json()["url"] == "https://wp/x.jpg" and r.json()["ok"] is True
    assert subidas == [("mi-foto-.jpg", "Amanecer", "franco", len(JPG))]
    assert logueado.post("/banco/subir", files={"archivo": ("a.txt", io.BytesIO(b"x"), "text/plain")}).status_code == 400
    assert logueado.post("/banco/subir", files={"archivo": ("a.jpg", io.BytesIO(b""), "image/jpeg")}).status_code == 400
    # WordPress en simulado: no sube, pero lo dice (no es error HTTP)
    monkeypatch.setattr(publicar, "subir_imagen_wordpress", lambda *a, **k: {"ok": True, "modo": "simulado", "url": None, "id": None, "aviso": "Simulado: la imagen no se subió."})
    r = logueado.post("/banco/subir", files={"archivo": ("a.jpg", io.BytesIO(JPG), "image/jpeg")})
    assert r.status_code == 200 and r.json()["ok"] is False and "Simulado" in r.json()["aviso"]


def test_componer(logueado, base, monkeypatch):
    visto = []
    monkeypatch.setattr(imagen, "componer_imagen", lambda foto, texto, **k: visto.append((foto, texto, k)) or JPG)
    r = logueado.post("/publicar/componer", json={"imagen_url": "https://wp/f.jpg", "texto_imagen": "La gratitud — Br. David", "firma": "— Br. David",
                                                  "formato": "historia", "tipografia": "Lora", "peso": "negrita", "posicion": "abajo",
                                                  "alineacion": "izquierda", "logo": "Flor amarilla", "posicion_logo": "arriba centro"})
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg" and r.content == JPG
    foto, texto, k = visto[0]
    assert foto == "https://wp/f.jpg" and texto == "La gratitud"            # la firma repetida al final del texto no se duplica
    assert k == {"firma": "— Br. David", "formato": "historia", "tipografia": "Lora", "posicion": "abajo", "alineacion": "izquierda",
                 "peso": "negrita", "logo": "Flor amarilla", "posicion_logo": "arriba centro"}
    # misma composición: sale de la caché (no se vuelve a componer); valores desconocidos caen a los defaults
    logueado.post("/publicar/componer", json={"imagen_url": "https://wp/f.jpg", "texto_imagen": "La gratitud — Br. David", "firma": "— Br. David",
                                              "formato": "historia", "tipografia": "Lora", "peso": "negrita", "posicion": "abajo",
                                              "alineacion": "izquierda", "logo": "Flor amarilla", "posicion_logo": "arriba centro"})
    assert len(visto) == 1
    logueado.post("/publicar/componer", json={"imagen_url": "https://wp/g.jpg", "texto_imagen": "x", "formato": "raro", "tipografia": "Comic", "logo": "Sin logo"})
    assert visto[1][2]["formato"] == "cuadrado" and visto[1][2]["tipografia"] == imagen.TIPOGRAFIA_DEFAULT and visto[1][2]["logo"] is None
    assert logueado.post("/publicar/componer", json={"imagen_url": "foto.jpg", "texto_imagen": "x"}).status_code == 400
    monkeypatch.setattr(imagen, "componer_imagen", lambda *a, **k: (_ for _ in ()).throw(OSError("sin red")))
    assert logueado.post("/publicar/componer", json={"imagen_url": "https://wp/h.jpg", "texto_imagen": "y"}).status_code == 502


# ---------------- Borrador ----------------
def test_borrador_completo(logueado, base, monkeypatch):
    guardado = {}

    def _guardar(usuario, canal, titulo, texto, imagen_url, fecha, pieza, pid=None):
        guardado.update(usuario=usuario, canal=canal, titulo=titulo, imagen_url=imagen_url, fecha=fecha, pieza=pieza, pid=pid)
        return pid or "b1"
    monkeypatch.setattr(db, "guardar_borrador", _guardar)
    r = logueado.post("/publicar/borrador", json={"canal": "instagram", "titulo": "T", "texto": "x", "imagen_url": "https://wp/f.jpg", "fecha": "2026-11-02", "hora": "10:00",
                                                  "texto_imagen": "Frase", "firma": "— D", "formato": "historia", "tipografia": "Lora", "peso": "fina", "posicion": "arriba",
                                                  "alineacion": "izquierda", "logo": "Blanco", "posicion_logo": "abajo centro", "usar_compuesta": False, "imagen_busqueda": "mar"})
    assert r.status_code == 200 and r.json()["id"] == "b1" and r.json()["estado"] == "borrador"
    pz = guardado["pieza"]
    assert guardado["fecha"] == "2026-11-02T10:00:00-03:00" and pz["fmt"] == "historia" and pz["logo"] == "Blanco" and pz["plogo"] == "abajo centro"
    assert pz["tipo"] == "Lora" and pz["peso"] == "fina" and pz["pos"] == "arriba" and pz["ali"] == "izquierda" and pz["usar_comp"] is False
    assert pz["busq"] == "mar" and pz["url"] == "https://wp/f.jpg" and pz["origen"] == "web" and pz["fecha"] == "2026-11-02" and pz["hora"] == "10:00"
    # retomando: actualiza el mismo si es propio y sigue siendo borrador
    base["filas"]["b1"] = {"id": "b1", "usuario": "franco", "estado": "borrador", "canal": "instagram", "resultado": {}}
    r = logueado.post("/publicar/borrador", json={"canal": "instagram", "texto": "y", "borrador_id": "b1"})
    assert r.status_code == 200 and guardado["pid"] == "b1"
    base["filas"]["b1"]["usuario"] = "lizzie"
    assert logueado.post("/publicar/borrador", json={"canal": "instagram", "texto": "y", "borrador_id": "b1"}).status_code == 409
    assert logueado.post("/publicar/borrador", json={"canal": "instagram", "texto": "y", "borrador_id": "nope"}).status_code == 404
    assert logueado.post("/publicar/borrador", json={"canal": "", "texto": "y"}).status_code == 400


# ---------------- A aprobación ----------------
def test_a_aprobar_con_compuesta(lizzie, base, monkeypatch):
    propuesto, subidas = {}, []

    def _proponer(usuario, canal, modo, titulo, texto, imagen_url, fecha, extra=None):
        propuesto.update(usuario=usuario, canal=canal, modo=modo, titulo=titulo, texto=texto, imagen_url=imagen_url, fecha=fecha, extra=extra)
        return "p1"
    monkeypatch.setattr(db, "proponer_publicacion", _proponer)

    def _subir(cfg, datos, nombre, titulo="", etiquetas=None, quien="", pieza=""):
        subidas.append((cfg.modo_wp, nombre, etiquetas, datos))
        return {"ok": True, "modo": cfg.modo_wp, "url": "https://wp/compuesta.jpg", "id": 9}
    monkeypatch.setattr(publicar, "subir_imagen_wordpress", _subir)
    base["filas"]["b7"] = {"id": "b7", "usuario": "lizzie", "estado": "borrador"}
    r = lizzie.post("/publicar/a-aprobar", json={"canal": "instagram", "titulo": "Gratitud", "texto": "**Hola** [link](https://x.y)", "imagen_url": "https://wp/f.jpg",
                                                 "texto_imagen": "La gratitud es la llave", "formato": "vertical", "logo": "Amarillo", "fecha": "2026-11-03", "hora": "9:15",
                                                 "borrador_id": "b7"})
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "a_aprobar" and r.json()["imagen_url"] == "https://wp/compuesta.jpg" and "franco" in r.json()["mensaje"]
    # la compuesta se subió con la config REAL de WordPress (borrador), etiquetada, y es lo que viaja en la pieza
    assert subidas[0][0] == "borrador" and subidas[0][1].startswith("pieza-") and subidas[0][2] == ["pieza-compuesta"] and subidas[0][3].startswith(JPG)
    assert propuesto["imagen_url"] == "https://wp/compuesta.jpg" and propuesto["modo"] == "real" and propuesto["texto"] == "Hola link"
    assert propuesto["fecha"] == "2026-11-03T09:15:00-03:00"
    assert propuesto["extra"] == {"texto_imagen": "La gratitud es la llave", "formato": "vertical", "video_url": None, "origen": "web"}
    assert "b7" not in base["filas"]                       # el borrador retomado se eliminó
    # sin frase ni logo: no se compone ni se sube nada; «Publicar así» destildado tampoco
    subidas.clear()
    lizzie.post("/publicar/a-aprobar", json={"canal": "instagram", "texto": "x", "imagen_url": "https://wp/f.jpg", "logo": "Sin logo"})
    lizzie.post("/publicar/a-aprobar", json={"canal": "instagram", "texto": "x", "imagen_url": "https://wp/f.jpg", "texto_imagen": "f", "usar_compuesta": False})
    assert subidas == [] and propuesto["imagen_url"] == "https://wp/f.jpg" and propuesto["extra"]["formato"] == "vertical"
    # pieza de video: formato = reel/historia, sin composición
    lizzie.post("/publicar/a-aprobar", json={"canal": "instagram", "texto": "x", "video_url": "https://wp/clip.mp4", "vfmt": "historia", "video_formato": "vertical"})
    assert propuesto["extra"]["video_url"] == "https://wp/clip.mp4" and propuesto["extra"]["formato"] == "historia"
    # reglas: Facebook en simulado no se puede proponer; YouTube tampoco; título obligatorio en WordPress
    assert lizzie.post("/publicar/a-aprobar", json={"canal": "facebook", "texto": "x"}).status_code == 400
    assert lizzie.post("/publicar/a-aprobar", json={"canal": "youtube", "titulo": "t", "texto": "x", "video_url": "https://wp/c.mp4"}).status_code == 400
    assert lizzie.post("/publicar/a-aprobar", json={"canal": "wordpress", "texto": "x"}).status_code == 400


def test_a_aprobar_wp_no_sube(lizzie, base, monkeypatch):
    """Si WordPress no acepta la compuesta, la pieza sigue con la foto sola y un aviso (como Streamlit)."""
    monkeypatch.setattr(db, "proponer_publicacion", lambda *a, **k: "p2")
    monkeypatch.setattr(publicar, "subir_imagen_wordpress", lambda *a, **k: {"ok": False, "modo": "borrador", "aviso": "WordPress no aceptó la imagen: 500"})
    r = lizzie.post("/publicar/a-aprobar", json={"canal": "facebook" if False else "instagram", "texto": "x", "imagen_url": "https://wp/f.jpg", "texto_imagen": "frase"})
    assert r.status_code == 200 and r.json()["imagen_url"] == "https://wp/f.jpg" and "sin la frase" in r.json()["avisos"][0]


# ---------------- Enviar: simulado y real ----------------
def test_ver_simulado_creadora(lizzie, base, monkeypatch):
    """«Ver simulado»: todos los canales en simulado; no sube la compuesta ni llama a ninguna API; queda 'prueba' en el registro."""
    llamadas = base["llamadas"]
    r = lizzie.post("/publicar/enviar", json={"modo": "simulado", "canal": "instagram", "texto": "Hola **mundo**", "imagen_url": "https://wp/f.jpg",
                                              "texto_imagen": "frase", "formato": "cuadrado"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["ok"] is True and d["modo"] == "simulado" and d["simulado"] is True and d["encolada"] is False
    assert d["pieza"]["caption"] == "Hola mundo" and d["texto_final"] == "Hola mundo" and d["imagen_url"] == "https://wp/f.jpg"
    assert any("sin la frase" in a for a in d["avisos"])            # la compuesta no se pudo subir (WP simulado)
    registros = [l for l in llamadas if l[0] == "registro"]
    assert any(k["estado"] == "prueba" and k["usuario"] == "lizzie" and k["canal"] == "instagram" for _, k in registros)
    assert any(k["resultado"].get("texto_imagen") == "frase" and k["resultado"].get("origen") == "web" for _, k in registros)
    # modo real: la creadora no puede
    assert lizzie.post("/publicar/enviar", json={"modo": "real", "canal": "instagram", "texto": "x"}).status_code == 403
    # Facebook simulado con fecha: Instagram siempre y Facebook fuera de real van a la cola, incluso en simulado
    monkeypatch.setattr(db, "encolar_publicacion", lambda *a, **k: "q1")
    r = lizzie.post("/publicar/enviar", json={"modo": "simulado", "canal": "instagram", "texto": "x", "fecha": "2026-12-01", "hora": "08:00"})
    assert r.json()["encolada"] is True and r.json()["id"] == "q1" and "2026-12-01 08:00" in r.json()["aviso"]


def test_enviar_real_instagram(logueado, base, monkeypatch):
    publicado, subidas = {}, []
    monkeypatch.setattr(publicar, "subir_imagen_wordpress", lambda cfg, datos, nombre, **k: subidas.append(cfg.modo_wp) or {"ok": True, "url": "https://wp/comp.jpg", "id": 3, "modo": cfg.modo_wp})

    def _ig(cfg, imagen_url, texto, quien="", historia=False):
        publicado.update(modo=cfg.modo_ig, imagen_url=imagen_url, texto=texto, quien=quien, historia=historia)
        return {"ok": True, "modo": cfg.modo_ig, "id": "17", "permalink": "https://instagram.com/p/x", "pieza": {"image_url": imagen_url, "caption": texto}, "aviso": "PUBLICADO en Instagram."}
    monkeypatch.setattr(publicar, "publicar_instagram", _ig)
    base["filas"]["b3"] = {"id": "b3", "usuario": "franco", "estado": "borrador"}
    r = logueado.post("/publicar/enviar", json={"modo": "real", "canal": "instagram", "texto": "Hola", "imagen_url": "https://wp/f.jpg", "texto_imagen": "frase",
                                                "formato": "historia", "borrador_id": "b3"})
    assert r.status_code == 200, r.text
    assert publicado == {"modo": "real", "imagen_url": "https://wp/comp.jpg", "texto": "Hola", "quien": "franco", "historia": True}
    assert subidas == ["borrador"] and r.json()["permalink"] == "https://instagram.com/p/x" and r.json()["simulado"] is False
    assert "b3" not in base["filas"]
    # con fecha, Instagram va a la cola (la API de Instagram no programa)
    monkeypatch.setattr(db, "encolar_publicacion", lambda usuario, canal, modo, titulo, texto, imagen_url, fecha, extra=None: publicado.update(cola=(canal, modo, fecha, extra)) or "q2")
    r = logueado.post("/publicar/enviar", json={"modo": "real", "canal": "instagram", "texto": "Hola", "fecha": "2026-12-24", "hora": "18:00", "video_url": "https://wp/c.mp4", "vfmt": "reel"})
    assert r.json()["encolada"] is True and publicado["cola"] == ("instagram", "real", "2026-12-24T18:00:00-03:00", {"texto_imagen": None, "formato": "reel", "video_url": "https://wp/c.mp4", "origen": "web"})


def test_enviar_wordpress_y_youtube(logueado, base, monkeypatch):
    hecho = {}
    monkeypatch.setattr(publicar, "media_id_por_url", lambda cfg, url: 44 if url else None)

    def _wp(cfg, titulo, contenido, imagen_id=None, categorias=None, quien="", fecha=None):
        hecho.update(titulo=titulo, contenido=contenido, imagen_id=imagen_id, fecha=fecha, modo=cfg.modo_wp)
        return {"ok": True, "modo": cfg.modo_wp, "estado": "draft", "id": 1, "link_editar": "https://wp/edit", "link": "https://wp/p", "pieza": {}, "aviso": "Borrador creado."}
    monkeypatch.setattr(publicar, "publicar_wordpress", _wp)
    r = logueado.post("/publicar/enviar", json={"modo": "real", "canal": "wordpress", "titulo": "Entrada", "texto": "<p>**md** se conserva</p>", "imagen_url": "https://wp/f.jpg",
                                                "fecha": "2026-11-10", "hora": "07:30", "video_url": "https://wp/clip.mp4"})
    assert r.status_code == 200 and r.json()["link_editar"] == "https://wp/edit"
    assert hecho["titulo"] == "Entrada" and hecho["imagen_id"] == 44 and hecho["fecha"] == "2026-11-10T07:30:00" and hecho["modo"] == "borrador"
    assert hecho["contenido"].startswith("<!-- wp:video -->") and "**md** se conserva" in hecho["contenido"]
    # YouTube sin recorte: 400 (el archivo se sube desde Streamlit); con recorte en privado baja el mp4 y lo sube
    assert logueado.post("/publicar/enviar", json={"modo": "real", "canal": "youtube", "titulo": "T", "texto": "d"}).status_code == 400
    monkeypatch.setattr(publicar, "bajar_bytes", lambda url, timeout=300: (b"mp4", None))
    monkeypatch.setattr(publicar, "publicar_youtube", lambda cfg, datos, titulo, desc, **k: hecho.update(yt=(len(datos), titulo, k.get("nombre_archivo"), cfg.modo_yt)) or {"ok": True, "modo": cfg.modo_yt, "link": "https://youtu.be/1", "pieza": {}})
    r = logueado.post("/publicar/enviar", json={"modo": "real", "canal": "youtube", "titulo": "T", "texto": "d", "video_url": "https://wp/clip.mp4"})
    assert r.status_code == 200 and hecho["yt"] == (3, "T", "clip.mp4", "privado") and r.json()["link"] == "https://youtu.be/1"
    # canal apagado
    monkeypatch.setenv("PUBLICAR_FACEBOOK", "apagado")
    assert logueado.post("/publicar/enviar", json={"modo": "real", "canal": "facebook", "texto": "x"}).status_code == 400
    # el conector falla con excepción: ok False, sin 500
    monkeypatch.setattr(publicar, "publicar_wordpress", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    r = logueado.post("/publicar/enviar", json={"modo": "real", "canal": "wordpress", "titulo": "E", "texto": "t"})
    assert r.status_code == 200 and r.json()["ok"] is False and "boom" in r.json()["aviso"]


# ---------------- Mis publicaciones: decorar, una, eliminar ----------------
FILAS = [
    {"id": "a", "creado": "2026-10-20T10:00:00", "usuario": "franco", "canal": "instagram", "modo": "real", "titulo": "A", "texto": "t", "imagen_url": "https://wp/a.jpg",
     "estado": "publicada", "fecha_programada": "2026-10-21T09:00:00-03:00", "resultado": {"aprobada_por": "beto", "aprobada_en": "2026-10-20T11:00:00", "ultimo": {"permalink": "https://ig/p/1"}}},
    {"id": "b", "creado": "2026-10-20T10:00:00", "usuario": "franco", "canal": "wordpress", "modo": "borrador", "titulo": "B", "texto": "x", "imagen_url": None,
     "estado": "borrador", "fecha_programada": None, "resultado": {"pieza": {"canal": "wordpress", "titulo": "B", "texto": "x", "fmt": "cuadrado", "logo": "Blanco", "busq": "mar", "fecha": "2026-11-01", "hora": "09:00"}}},
    {"id": "c", "creado": "2026-10-20T10:00:00", "usuario": "franco", "canal": "newsletter", "modo": "", "titulo": "C", "texto": "<html>x</html>", "imagen_url": None,
     "estado": "lista", "fecha_programada": None, "resultado": {"pieza": {"plantilla": "mensual"}}},
    {"id": "d", "creado": "2026-10-20T10:00:00", "usuario": "franco", "canal": "facebook", "modo": "real", "titulo": "", "texto": "x", "imagen_url": None,
     "estado": "error", "fecha_programada": None, "resultado": {"video_url": "https://wp/c.mp4", "ultimo": {"ok": False, "aviso": "Facebook no aceptó el video"}}},
    {"id": "e", "creado": "2026-10-20T10:00:00", "usuario": "franco", "canal": "instagram", "modo": "real", "titulo": "", "texto": "x", "imagen_url": None,
     "estado": "subida", "fecha_programada": None, "resultado": {}},
]


def test_mis_publicaciones_decoradas(logueado, base, monkeypatch):
    monkeypatch.setattr(db, "listar_mias", lambda u: [dict(f) for f in FILAS])
    d = logueado.get("/publicaciones").json()
    por = {p["id"]: p for p in d["piezas"]}
    assert "e" not in por and por["a"]["estado_texto"] == "publicada" and por["a"]["ver_url"] == "https://ig/p/1" and por["a"]["aprobada_por"] == "beto"
    assert por["a"]["eliminable"] is False and por["b"]["retomable"] is True and por["b"]["eliminable"] is True and por["b"]["canal_texto"] == "Blogpost"
    assert por["c"]["plantilla"] == "mensual" and por["c"]["estado_texto"].startswith("lista") and por["d"]["error_texto"].startswith("Facebook no") and por["d"]["video_url"] == "https://wp/c.mp4"
    assert d["solapas"]["Borradores"] == ["b"] and d["solapas"]["Publicadas"] == ["a", "c"] and "borrador" in d["eliminables"]


def test_una_publicacion_y_retomar(logueado, lizzie, base):
    for f in FILAS:
        base["filas"][f["id"]] = dict(f)
    r = logueado.get("/publicaciones/b")
    assert r.status_code == 200
    pz = r.json()["pieza"]
    assert pz["_pid"] == "b" and pz["canal"] == "wordpress" and pz["fmt"] == "cuadrado" and pz["logo"] == "Blanco" and pz["imagen_busqueda"] == "mar" and pz["fecha"] == "2026-11-01"
    # una pieza sin dict pieza (p. ej. rechazada): se arma con los campos de la fila y la fecha programada
    base["filas"]["a"]["estado"] = "rechazada"
    pz = logueado.get("/publicaciones/a").json()["pieza"]
    assert pz["titulo"] == "A" and pz["url"] == "https://wp/a.jpg" and pz["fecha"] == "2026-10-21" and pz["hora"] == "09:00"
    assert logueado.get("/publicaciones/zzz").status_code == 404
    # lizzie no es aprobadora: no ve las piezas de franco (franco sí vería las de ella)
    assert lizzie.get("/publicaciones/a").status_code == 403


def test_eliminar(logueado, base, monkeypatch):
    monkeypatch.setattr(db, "eliminar_publicacion", lambda pid, u: pid == "b" and u == "franco")
    assert logueado.delete("/publicaciones/b").json() == {"ok": True}
    assert logueado.delete("/publicaciones/a").status_code == 409


# ---------------- Aprobación ----------------
def test_aprobacion_flujo(logueado, lizzie, base, monkeypatch):
    pend = {"id": "p9", "creado": "2026-10-22T10:00:00", "usuario": "lizzie", "canal": "instagram", "modo": "real", "titulo": "P", "texto": "t", "imagen_url": "https://wp/p.jpg",
            "fecha_programada": "2026-11-05T10:30:00-03:00", "estado": "a_aprobar", "resultado": {"propuesta_por": "lizzie", "texto_imagen": "frase", "formato": "vertical"}}
    base["filas"]["p9"] = dict(pend)
    monkeypatch.setattr(db, "listar_a_aprobar", lambda limite=50: [dict(pend)])
    d = logueado.get("/aprobacion/para-aprobar").json()
    assert d["modos"]["instagram"] == "real" and d["piezas"][0]["fecha_sugerida"] == "2026-11-05" and d["piezas"][0]["hora_sugerida"] == "10:30"
    # Supabase devuelve la fecha en UTC: la sugerencia va en hora Argentina
    monkeypatch.setattr(db, "listar_a_aprobar", lambda limite=50: [dict(pend, fecha_programada="2027-03-20T12:00:00+00:00")])
    assert logueado.get("/aprobacion/para-aprobar").json()["piezas"][0]["hora_sugerida"] == "09:00"
    monkeypatch.setattr(db, "listar_a_aprobar", lambda limite=50: [dict(pend)])
    assert d["piezas"][0]["texto_imagen"] == "frase" and d["piezas"][0]["propuesta_por"] == "lizzie"
    assert lizzie.get("/aprobacion/para-aprobar").status_code == 403
    hecho = {}
    monkeypatch.setattr(db, "aprobar_publicacion", lambda pid, u, fecha, modo, res=None: hecho.update(pid=pid, u=u, fecha=fecha, modo=modo, res=res))
    r = logueado.post("/aprobacion/p9/aprobar", json={"fecha": "2026-11-06", "hora": "8:05"})
    assert r.status_code == 200 and hecho == {"pid": "p9", "u": "franco", "fecha": "2026-11-06T08:05:00-03:00", "modo": "real", "res": pend["resultado"]}
    assert "2026-11-06 08:05" in r.json()["mensaje"]
    # rechazar con nota
    monkeypatch.setattr(db, "rechazar_publicacion", lambda pid, u, nota, res=None: hecho.update(rech=(pid, u, nota)))
    assert logueado.post("/aprobacion/p9/rechazar", json={"nota": " muy largo "}).json()["estado"] == "rechazada" and hecho["rech"] == ("p9", "franco", "muy largo")
    # ya no está pendiente
    base["filas"]["p9"]["estado"] = "rechazada"
    assert logueado.post("/aprobacion/p9/aprobar", json={}).status_code == 409
    assert logueado.post("/aprobacion/p9/rechazar", json={"nota": ""}).status_code == 409
    # newsletter: aprobar = lista
    base["filas"]["n1"] = {"id": "n1", "usuario": "lizzie", "canal": "newsletter", "estado": "a_aprobar", "resultado": {"propuesta_por": "lizzie"}}
    monkeypatch.setattr(db, "actualizar_publicacion", lambda pid, campos: hecho.update(nl=(pid, campos)))
    r = logueado.post("/aprobacion/n1/aprobar", json={})
    assert r.json()["estado"] == "lista" and hecho["nl"][1]["estado"] == "lista" and hecho["nl"][1]["resultado"]["aprobada_por"] == "franco"


def test_cola_registro_papelera(logueado, lizzie, base, monkeypatch):
    base["filas"]["q1"] = {"id": "q1", "usuario": "lizzie", "canal": "facebook", "estado": "pendiente", "resultado": {}}
    monkeypatch.setattr(db, "listar_pendientes", lambda vencidas=False, limite=50: [dict(base["filas"]["q1"], fecha_programada="2026-11-01T09:00:00-03:00")])
    assert logueado.get("/aprobacion/cola").json()[0]["canal_texto"] == "Facebook"
    cancel = []
    monkeypatch.setattr(db, "cancelar_publicacion", lambda pid, u: cancel.append((pid, u)))
    assert logueado.post("/aprobacion/q1/cancelar").json()["estado"] == "cancelada" and cancel == [("q1", "franco")]
    base["filas"]["q1"]["estado"] = "cancelada"
    assert logueado.post("/aprobacion/q1/cancelar").status_code == 409
    monkeypatch.setattr(db, "listar_registro", lambda limite=60: [dict(f) for f in FILAS])
    ids = [p["id"] for p in logueado.get("/aprobacion/registro").json()]
    assert ids == ["a", "c", "d"]                      # sin borradores ni subidas (NO_SON_PIEZAS)
    monkeypatch.setattr(db, "listar_papelera", lambda limite=200: [{"id": "c1", "usuario": "lizzie", "titulo": "T", "actualizado": "x", "borrada": "y"}])
    d = logueado.get("/aprobacion/papelera").json()
    assert d["dias"] == db.PAPELERA_DIAS and d["conversaciones"][0]["id"] == "c1"
    rest = []
    monkeypatch.setattr(db, "restaurar_conversacion", lambda cid: rest.append(cid))
    assert logueado.post("/aprobacion/papelera/c1/restaurar").json() == {"ok": True} and rest == ["c1"]
    for ruta in ("/aprobacion/cola", "/aprobacion/registro", "/aprobacion/papelera"):
        assert lizzie.get(ruta).status_code == 403


def test_sin_sesion(cliente):
    assert cliente.get("/publicar/opciones").status_code == 401
    assert cliente.post("/publicar/enviar", json={"canal": "instagram", "texto": "x"}).status_code == 401
    assert cliente.get("/aprobacion/para-aprobar").status_code == 401
    assert cliente.delete("/publicaciones/a").status_code == 401
