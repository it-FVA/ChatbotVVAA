"""(5/11, Franco) Carruseles: varias fotos por pieza en Instagram y Facebook. Validación, conectores (simulado y real con la red
simulada), despacho de enviar_pieza y el viaje de `imagenes` por enviar / proponer / borrador / detalle. Sin Supabase ni Meta."""
import json
import urllib.parse

import pytest

import canales
import db
import publicar
import api.chat_rutas as cr

FOTOS = [f"https://wp/f{i}.jpg" for i in range(1, 4)]


def _cfg(**modos):
    fuente = {c.variable: modos.get(c.clave, "simulado") for c in canales.CANALES.values()}
    fuente.update({"WP_SITE": "x.org", "WP_USER": "u", "WP_APP_PASSWORD": "p", "META_IG_TOKEN": "tok-ig", "META_IG_USER_ID": "IG1",
                   "META_FB_PAGE_ID": "PG1", "META_FB_PAGE_TOKEN": "tok-fb"})
    return publicar.Config(fuente)


@pytest.fixture
def red(monkeypatch):
    """Cambia publicar._http: guarda cada llamada (url, método, parámetros) y responde con ids correlativos."""
    llamadas = []
    estado = {"n": 0, "falla_en": None}

    def _http(url, method="GET", headers=None, data=None):
        params = dict(urllib.parse.parse_qsl(data.decode())) if data else dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
        llamadas.append((url.split("?")[0].split("/", 4)[-1], method, params))
        if "fields" in params:
            return {"status_code": "FINISHED", "permalink": "https://instagram.com/p/x"}, None
        estado["n"] += 1
        if estado["falla_en"] == estado["n"]:
            return None, {"message": "rechazado"}
        return {"id": f"id{estado['n']}"}, None
    monkeypatch.setattr(publicar, "_http", _http)
    monkeypatch.setattr(publicar.time, "sleep", lambda s: None)
    monkeypatch.setattr(publicar, "_registrar", lambda e: e)
    return {"llamadas": llamadas, "estado": estado}


# ---------------- conectores en simulado / apagado ----------------
def test_conectores_simulado_y_apagado():
    r = publicar.publicar_instagram_carrusel(_cfg(), FOTOS, "Hola", quien="u")
    assert r["ok"] and r["modo"] == "simulado" and r["pieza"]["imagenes"] == FOTOS and r["pieza"]["caption"] == "Hola"
    r = publicar.publicar_facebook_fotos(_cfg(), FOTOS, "Hola", quien="u")
    assert r["ok"] and r["modo"] == "simulado" and r["pieza"]["imagenes"] == FOTOS and r["pieza"]["message"] == "Hola"
    assert publicar.publicar_instagram_carrusel(_cfg(instagram="apagado"), FOTOS, "x")["ok"] is False
    assert publicar.publicar_facebook_fotos(_cfg(facebook="apagado"), FOTOS, "x")["ok"] is False


# ---------------- Instagram real ----------------
def test_instagram_real_orden_hijos_contenedor_publish(red):
    r = publicar.publicar_instagram_carrusel(_cfg(instagram="real"), FOTOS, "Pie del posteo", quien="u")
    assert r["ok"] and r["id"] == "id5" and r["permalink"] == "https://instagram.com/p/x"
    posts = [(p, par) for p, m, par in red["llamadas"] if m == "POST"]
    assert [p for p, _ in posts] == ["IG1/media"] * 4 + ["IG1/media_publish"]
    for (_, par), foto in zip(posts[:3], FOTOS):             # hijos: la foto, is_carousel_item, sin caption
        assert par["image_url"] == foto and par["is_carousel_item"] == "true" and "caption" not in par
    cont = posts[3][1]
    assert cont["media_type"] == "CAROUSEL" and cont["children"] == "id1,id2,id3" and cont["caption"] == "Pie del posteo"
    assert posts[4][1]["creation_id"] == "id4"


def test_instagram_real_si_un_hijo_falla_no_publica(red):
    red["estado"]["falla_en"] = 2
    r = publicar.publicar_instagram_carrusel(_cfg(instagram="real"), FOTOS, "x")
    assert r["ok"] is False and "foto 2 de 3" in r["aviso"] and "no se publicó nada" in r["aviso"]
    assert not any(p.endswith("media_publish") or par.get("media_type") == "CAROUSEL" for p, m, par in red["llamadas"])


def test_carrusel_real_valida_cantidad_y_https(red):
    assert "entre 2 y 10" in publicar.publicar_instagram_carrusel(_cfg(instagram="real"), FOTOS[:1], "x")["aviso"]
    assert "entre 2 y 10" in publicar.publicar_facebook_fotos(_cfg(facebook="real"), FOTOS * 4, "x")["aviso"]
    assert "https" in publicar.publicar_instagram_carrusel(_cfg(instagram="real"), ["http://a/1.jpg", "https://a/2.jpg"], "x")["aviso"]
    assert red["llamadas"] == []


# ---------------- Facebook real ----------------
def test_facebook_real_fotos_sin_publicar_y_feed_con_attached_media(red):
    r = publicar.publicar_facebook_fotos(_cfg(facebook="real"), FOTOS, "Mensaje")
    assert r["ok"] and r["id"] == "id4"
    paths = [p for p, m, par in red["llamadas"]]
    assert paths == ["PG1/photos"] * 3 + ["PG1/feed"]
    for (_, _, par), foto in zip(red["llamadas"][:3], FOTOS):
        assert par["url"] == foto and par["published"] == "false"
    feed = red["llamadas"][3][2]
    assert feed["message"] == "Mensaje" and "published" not in feed
    assert [json.loads(feed[f"attached_media[{i}]"]) for i in range(3)] == [{"media_fbid": "id1"}, {"media_fbid": "id2"}, {"media_fbid": "id3"}]


def test_facebook_real_programado_y_foto_que_falla(red):
    fecha = "2099-01-01T10:00:00"
    r = publicar.publicar_facebook_fotos(_cfg(facebook="real"), FOTOS, "M", fecha=fecha)
    feed = red["llamadas"][-1][2]
    assert r["ok"] and feed["published"] == "false" and int(feed["scheduled_publish_time"]) > 0 and "PROGRAMADO" in r["aviso"]
    red["llamadas"].clear()
    red["estado"].update(n=0, falla_en=3)
    r = publicar.publicar_facebook_fotos(_cfg(facebook="real"), FOTOS, "M")
    assert r["ok"] is False and "foto 3 de 3" in r["aviso"] and not any(p.endswith("/feed") for p, m, par in red["llamadas"])


# ---------------- despacho ----------------
def test_enviar_pieza_despacha_carrusel(monkeypatch):
    vistos = []
    monkeypatch.setattr(publicar, "publicar_instagram_carrusel", lambda cfg, imgs, texto, quien="": vistos.append(("ig", imgs, texto)) or {"ok": True, "modo": "simulado"})
    monkeypatch.setattr(publicar, "publicar_facebook_fotos", lambda cfg, imgs, texto, quien="", fecha=None: vistos.append(("fb", imgs, fecha)) or {"ok": True, "modo": "simulado"})
    monkeypatch.setattr(publicar, "publicar_instagram", lambda *a, **k: vistos.append("foto-ig") or {"ok": True})
    monkeypatch.setattr(publicar, "publicar_facebook", lambda *a, **k: vistos.append("foto-fb") or {"ok": True})
    pieza = {"texto": "T", "imagen_url": FOTOS[0], "fecha_programada": None, "resultado": {"imagenes": FOTOS}}
    publicar.enviar_pieza(_cfg(), dict(pieza, canal="instagram"), "u")
    publicar.enviar_pieza(_cfg(), dict(pieza, canal="facebook"), "u")
    assert vistos == [("ig", FOTOS, "T"), ("fb", FOTOS, None)]
    vistos.clear()                    # con una sola foto (o ninguna lista) sigue la foto de siempre
    publicar.enviar_pieza(_cfg(), dict(pieza, canal="instagram", resultado={"imagenes": FOTOS[:1]}), "u")
    publicar.enviar_pieza(_cfg(), dict(pieza, canal="facebook", resultado={}), "u")
    assert vistos == ["foto-ig", "foto-fb"]
    assert canales.CANALES["instagram"].carrusel and canales.CANALES["facebook"].carrusel and canales.CANALES["wordpress"].carrusel is None


# ---------------- rutas ----------------
@pytest.fixture
def rutas(monkeypatch):
    monkeypatch.setattr(db, "disponible", lambda: True)
    monkeypatch.setattr(cr, "modos", lambda: {"wordpress": "borrador", "instagram": "real", "facebook": "real", "youtube": "privado"})
    for k, v in (("INSTAGRAM", "real"), ("FACEBOOK", "real"), ("WORDPRESS", "borrador"), ("YOUTUBE", "privado")):
        monkeypatch.setenv("PUBLICAR_" + k, v)
    guardado = {}
    monkeypatch.setattr(db, "proponer_publicacion", lambda usuario, canal, modo, titulo, texto, imagen_url, fecha, extra=None, por=None:
                        guardado.update(imagen_url=imagen_url, extra=extra) or "p1")
    monkeypatch.setattr(db, "guardar_borrador", lambda usuario, canal, titulo, texto, imagen_url, fecha, pieza, pid=None, por=None, conservar=None:
                        guardado.update(imagen_url=imagen_url, pieza=pieza) or "b1")
    monkeypatch.setattr(db, "encolar_publicacion", lambda usuario, canal, modo, titulo, texto, imagen_url, fecha, extra=None, por=None:
                        guardado.update(imagen_url=imagen_url, extra=extra) or "q1")
    monkeypatch.setattr("avisos.pieza_a_aprobar", lambda *a, **k: None)
    return guardado


@pytest.mark.parametrize("ruta", ["/publicar/a-aprobar", "/publicar/enviar", "/publicaciones/a-aprobar"])
def test_validacion(logueado, rutas, ruta):
    base = {"modo": "simulado", "canal": "instagram", "texto": "x", "imagenes": FOTOS}
    def pedir(**c):
        return logueado.post(ruta, json=dict(base, **c))
    r = pedir(imagenes=FOTOS[:1])
    assert r.status_code == 400 and r.json()["detail"] == "Un carrusel lleva entre 2 y 10 fotos."
    assert pedir(imagenes=[f"https://wp/{i}.jpg" for i in range(11)]).json()["detail"] == "Un carrusel lleva entre 2 y 10 fotos."
    for canal, extra in (("youtube", {"titulo": "T"}), ("wordpress", {"titulo": "T"})):
        r = pedir(canal=canal, **extra)
        assert r.status_code == 400 and r.json()["detail"] == "El carrusel solo sale en posteo de Instagram o Facebook."
    assert pedir(formato="historia").json()["detail"] == "El carrusel solo sale en posteo de Instagram o Facebook."
    assert pedir(video_url="https://wp/c.mp4").status_code == 400
    assert pedir(imagenes=["http://a/1.jpg", "https://a/2.jpg"]).status_code == 400


def test_enviar_simulado_compone_cada_foto_y_no_sube(logueado, rutas, monkeypatch):
    """(18/11, Franco) El carrusel se compone foto por foto (frase, firma y logo), como la foto única. En «Ver simulado» WordPress
    está simulado: las compuestas no se suben, viajan las originales y un solo aviso lo dice."""
    import imagen
    import api.publicar_rutas as pr
    pr._CACHE_COMPUESTAS.clear()
    visto = []
    monkeypatch.setattr(imagen, "componer_imagen", lambda foto, texto, **k: visto.append((foto, texto, k["firma"], k["logo"], k["formato"])) or b"JPG" + texto.encode())
    for canal in ("instagram", "facebook"):
        visto.clear()
        pr._CACHE_COMPUESTAS.clear()
        r = logueado.post("/publicar/enviar", json={"modo": "simulado", "canal": canal, "texto": "Hola", "imagenes": FOTOS,
                                                    "texto_imagen": "La gratitud", "usar_compuesta": True, "logo": "Amarillo", "formato": "vertical"})
        j = r.json()
        assert r.status_code == 200, r.text
        assert j["ok"] and j["simulado"] is True and j["imagenes"] == FOTOS and j["imagen_url"] == FOTOS[0] and j["formato"] == "vertical"
        assert [v[0] for v in visto] == FOTOS and all(v[1:] == ("La gratitud", "— Br. David", "Amarillo", "vertical") for v in visto)
        assert len([a for a in j["avisos"] if "no se sube" in a]) == 1


def test_aplicar_carrusel_conserva_diseno_y_alinea_por_url():
    from api.pieza import Pieza
    p = Pieza(canal="facebook", texto="x", imagenes=FOTOS, texto_imagen="Común", logo="Amarillo", formato="historia", usar_compuesta=True,
              imagenes_diseno=[{"url": FOTOS[2], "texto": "Propia", "compuesta": True}, {"url": FOTOS[1], "compuesta": False}])
    p.aplicar_carrusel("facebook")
    assert p.texto_imagen == "Común" and p.logo == "Amarillo" and p.usar_compuesta is True and p.formato is None   # historia no es carrusel
    assert [d.url for d in p.imagenes_diseno] == FOTOS
    assert p.diseno_foto(0) == ("Común", True) and p.diseno_foto(1) == ("Común", False) and p.diseno_foto(2) == ("Propia", True)
    # texto "" = esta foto sin frase (solo logo); sin lista = todas con la frase común
    p = Pieza(canal="facebook", texto="x", imagenes=FOTOS[:2], texto_imagen="Común", imagenes_diseno=[{"url": FOTOS[0], "texto": "  "}])
    p.aplicar_carrusel("facebook")
    assert p.diseno_foto(0) == ("", True) and p.diseno_foto(1) == ("Común", True)
    assert Pieza(canal="facebook", texto="x", imagenes=FOTOS[:2], texto_imagen="C").diseno_foto(1) == ("C", True)
    # el dict guardado y la vuelta (retomar) conservan el diseño por foto
    g = p.a_borrador("facebook")
    assert g["imagenes_diseno"][0] == {"url": FOTOS[0], "texto": "", "compuesta": True, "firma": None}
    # (26/11) firma por foto: None = la de la pieza, "" = sin firma, otra = propia; se normaliza como el texto
    p = Pieza(canal="facebook", texto="x", imagenes=FOTOS, texto_imagen="Común", firma="— Pieza",
              imagenes_diseno=[{"url": FOTOS[0], "texto": "Una", "firma": "  — León XIV "}, {"url": FOTOS[1], "firma": "  "}, {"url": FOTOS[2]}])
    p.aplicar_carrusel("facebook")
    assert [d.firma for d in p.imagenes_diseno] == ["— León XIV", "", None]
    assert p.firma_foto(0) == "— León XIV" and p.firma_foto(1) == "" and p.firma_foto(2) == "— Pieza"
    assert Pieza(canal="facebook", texto="x", imagenes=FOTOS[:2]).firma_foto(1, "— Br. David") == "— Br. David"
    v = Pieza.desde_fila({"canal": "facebook", "estado": "borrador", "resultado": {"pieza": g}})
    assert v.imagenes == FOTOS[:2] and v.imagenes_diseno[0].texto == "" and v.imagenes_diseno[1].texto is None


def test_a_aprobar_carrusel_compone_sube_y_guarda_originales(logueado, rutas, monkeypatch):
    """(18/11, Franco) Al mandar a aprobación cada foto compuesta va a WordPress; `imagenes` (lo que sube la cola) son las compuestas,
    `pieza.imagenes` las originales. La foto «tal cual» no se compone ni se sube; la de texto "" lleva solo el logo."""
    import imagen
    import api.publicar_rutas as pr
    pr._CACHE_COMPUESTAS.clear()
    visto, subidas = [], []
    monkeypatch.setattr(imagen, "componer_imagen", lambda foto, texto, **k: visto.append((foto, texto, k["firma"], k["logo"])) or b"JPG" + foto.encode())

    def _subir(cfg, datos, nombre, titulo="", etiquetas=None, quien="", pieza=""):
        subidas.append((cfg.modo_wp, nombre, titulo, datos))
        return {"ok": True, "modo": cfg.modo_wp, "url": f"https://wp/compuesta-{len(subidas)}.jpg", "id": len(subidas)}
    monkeypatch.setattr(publicar, "subir_imagen_wordpress", _subir)
    r = logueado.post("/publicar/a-aprobar", json={"canal": "instagram", "titulo": "Tres", "texto": "Hola", "imagenes": FOTOS, "texto_imagen": "La gratitud",
                                                   "logo": "Amarillo", "formato": "cuadrado",
                                                   "imagenes_diseno": [{"url": FOTOS[0]}, {"url": FOTOS[1], "compuesta": False}, {"url": FOTOS[2], "texto": ""}]})
    assert r.status_code == 200, r.text
    assert visto == [(FOTOS[0], "La gratitud", "— Br. David", "Amarillo"), (FOTOS[2], "", "", "Amarillo")]
    assert [x[0] for x in subidas] == ["borrador", "borrador"] and subidas[0][2] == "Tres 1" and subidas[1][2] == "Tres 3"
    assert rutas["extra"]["imagenes"] == ["https://wp/compuesta-1.jpg", FOTOS[1], "https://wp/compuesta-2.jpg"]
    assert rutas["imagen_url"] == "https://wp/compuesta-1.jpg" and r.json()["imagen_url"] == "https://wp/compuesta-1.jpg"
    assert rutas["extra"]["pieza"]["imagenes"] == FOTOS and rutas["extra"]["pieza"]["imagenes_diseno"][1]["compuesta"] is False
    assert rutas["extra"]["formato"] == "cuadrado" and rutas["extra"]["texto_imagen"] == "La gratitud"
    # (26/11, Julián) tres citas de tres autores: cada foto con su firma; la que no trae firma usa la de la pieza
    visto.clear(); subidas.clear()
    r = logueado.post("/publicar/a-aprobar", json={"canal": "instagram", "titulo": "Tres", "texto": "Hola", "imagenes": FOTOS, "texto_imagen": "La gratitud",
                                                   "firma": "— Br. David", "formato": "cuadrado",
                                                   "imagenes_diseno": [{"url": FOTOS[0], "texto": "Uno", "firma": "— León XIV"}, {"url": FOTOS[1], "texto": "Dos", "firma": ""}, {"url": FOTOS[2]}]})
    assert r.status_code == 200, r.text
    assert [(v[1], v[2]) for v in visto] == [("Uno", "— León XIV"), ("Dos", ""), ("La gratitud", "— Br. David")]
    assert rutas["extra"]["pieza"]["imagenes_diseno"][0]["firma"] == "— León XIV"
    # «Publicar así» destildado: nada se compone ni se sube, van las originales
    visto.clear(); subidas.clear()
    logueado.post("/publicar/a-aprobar", json={"canal": "facebook", "texto": "x", "imagenes": FOTOS, "texto_imagen": "f", "usar_compuesta": False})
    assert visto == [] and subidas == [] and rutas["extra"]["imagenes"] == FOTOS
    # una foto que no se puede componer sigue sola y avisa; las demás salen
    visto.clear(); subidas.clear()
    monkeypatch.setattr(imagen, "componer_imagen", lambda foto, texto, **k: (_ for _ in ()).throw(OSError("sin red")) if foto == FOTOS[1] else b"JPG" + foto.encode())
    r = logueado.post("/publicar/a-aprobar", json={"canal": "facebook", "texto": "x", "imagenes": FOTOS, "texto_imagen": "f"})
    assert any("foto 2" in a for a in r.json()["avisos"]) and rutas["extra"]["imagenes"][1] == FOTOS[1] and len(subidas) == 2


def test_enviar_con_fecha_encola_con_imagenes(logueado, rutas):
    r = logueado.post("/publicar/enviar", json={"modo": "simulado", "canal": "instagram", "texto": "x", "imagenes": FOTOS, "fecha": "2026-12-24", "hora": "18:00"})
    assert r.json()["encolada"] is True and r.json()["imagenes"] == FOTOS
    assert rutas["extra"]["imagenes"] == FOTOS and rutas["imagen_url"] == FOTOS[0] and rutas["extra"]["texto_imagen"] is None


def test_proponer_y_borrador_guardan_imagenes(logueado, rutas):
    r = logueado.post("/publicar/a-aprobar", json={"canal": "facebook", "texto": "x", "imagenes": FOTOS, "imagen_url": "https://otra/x.jpg"})
    assert r.status_code == 200, r.text
    assert rutas["imagen_url"] == FOTOS[0] and rutas["extra"]["imagenes"] == FOTOS and rutas["extra"]["pieza"]["imagenes"] == FOTOS
    r = logueado.post("/publicar/borrador", json={"canal": "instagram", "texto": "x", "imagenes": FOTOS[:2]})
    assert r.status_code == 200 and rutas["imagen_url"] == FOTOS[0] and rutas["pieza"]["imagenes"] == FOTOS[:2]
    r = logueado.post("/publicaciones/a-aprobar", json={"canal": "instagram", "texto": "x", "imagenes": FOTOS})
    assert r.status_code == 200 and rutas["extra"]["imagenes"] == FOTOS
    # sin imagenes: la clave queda en null
    logueado.post("/publicar/a-aprobar", json={"canal": "facebook", "texto": "x", "imagen_url": "https://wp/a.jpg"})
    assert rutas["extra"]["imagenes"] is None


def test_detalle_y_decorar_devuelven_imagenes(logueado, rutas, monkeypatch):
    import api.publicar_rutas as pr
    fila = {"id": "b1", "usuario": "franco", "canal": "instagram", "estado": "borrador", "texto": "x", "imagen_url": FOTOS[0],
            "resultado": {"imagenes": FOTOS, "pieza": {"canal": "instagram", "imagenes": FOTOS}}}
    monkeypatch.setattr(db, "obtener_publicacion", lambda pid: dict(fila))
    j = logueado.get("/publicaciones/b1").json()
    assert j["imagenes"] == FOTOS and j["pieza"]["imagenes"] == FOTOS
    assert pr.decorar({"canal": "instagram", "estado": "a_aprobar", "resultado": {}})["imagenes"] is None
