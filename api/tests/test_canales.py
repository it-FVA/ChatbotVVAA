"""(3/11) El registro único de canales (canales.py) y el despacho único publicar.enviar_pieza: cada canal con su conector simulado,
sin red. Si se agrega un canal al registro, estas pruebas lo recorren solas."""
import sys

import pytest

import canales
import publicar
import procesar_cola
import programar_frases


def _cfg(**modos):
    fuente = {c.variable: modos.get(c.clave, "simulado") for c in canales.CANALES.values()}
    fuente.update({"WP_SITE": "x.org", "WP_USER": "u", "WP_APP_PASSWORD": "p"})
    return publicar.Config(fuente)


# ---------------- el registro ----------------
def test_registro_consistente():
    for c in canales.CANALES.values():
        assert c.variable.startswith("PUBLICAR_") and "apagado" in c.modos
        assert c.clave == c.clave.lower() and c.texto and c.nombre
        if c.en_disenar:
            assert c.foto is not None, f"{c.clave}: un canal de Diseñar tiene que tener conector"
    # las salidas de la Frase del día apuntan a canales reales
    for k, s in canales.SALIDAS_FRASE.items():
        assert s["canal"] in canales.CANALES and canales.CANALES[s["canal"]].frase
    assert canales.canal_de_salida("historia") == ("instagram", "historia")
    assert canales.canal_de_salida("home") == ("home", None)
    assert canales.canal_de_salida("otro") == (None, None)
    # lo que antes eran listas sueltas en cuatro archivos
    assert list(canales.nombres()) == ["wordpress", "instagram", "facebook", "youtube"]
    assert canales.textos()["wordpress"] == "Blogpost" and canales.textos()["mail"] == "Mail (frase del día)"
    assert canales.formato_por_canal() == {"instagram": "vertical", "facebook": "cuadrado"}
    assert programar_frases.CANALES_POSIBLES == {k: s["nombre"] for k, s in canales.SALIDAS_FRASE.items()}
    assert set(canales.variables()) >= {"PUBLICAR_WORDPRESS", "PUBLICAR_INSTAGRAM", "PUBLICAR_FACEBOOK", "PUBLICAR_YOUTUBE",
                                        "PUBLICAR_MAIL", "PUBLICAR_HOME", "PUBLICAR_WHATSAPP"}
    assert all(set(x) >= {"clave", "nombre", "texto", "icono", "en_disenar"} for x in canales.para_web())


def test_reglas_por_canal():
    ig, fb, wp, yt = (canales.CANALES[k] for k in ("instagram", "facebook", "wordpress", "youtube"))
    assert ig.va_a_la_cola("real") and ig.va_a_la_cola("simulado") and not ig.va_a_la_cola("apagado")
    assert fb.va_a_la_cola("simulado") and not fb.va_a_la_cola("real")
    assert not wp.va_a_la_cola("real") and yt.va_a_la_cola("privado") and yt.va_a_la_cola("real")
    assert wp.puede_proponer("borrador") and ig.puede_proponer("real") and not fb.puede_proponer("simulado") and yt.puede_proponer("real") and yt.puede_proponer("privado") and not yt.puede_proponer("simulado")   # (5/11) YouTube pasa por aprobación
    assert wp.requiere_titulo and yt.requiere_titulo and not ig.requiere_titulo


def test_config_desde_el_registro():
    cfg = publicar.Config({"PUBLICAR_WORDPRESS": "real", "PUBLICAR_INSTAGRAM": "cualquiercosa", "PUBLICAR_WHATSAPP": "real", "PUBLICAR_MAIL": "simulado"})
    assert cfg.modo("wordpress") == "real" and cfg.modo_wp == "real"
    assert cfg.modo("instagram") == "apagado"            # valor desconocido = no publicar
    assert cfg.modo("whatsapp") == "apagado"             # WhatsApp no tiene modo real todavía
    assert cfg.modo("home") == "real"                    # sin PUBLICAR_HOME hereda el de WordPress
    assert cfg.modo("mail") == "simulado" and cfg.resumen()["mail"] == "simulado"
    s = cfg.simulada()
    assert s.modos["wordpress"] == "simulado" and s.modos["instagram"] == "apagado" and cfg.modos["wordpress"] == "real"
    cfg.modo_ig = "real"                                  # los alias siguen escribiendo en modos
    assert cfg.modos["instagram"] == "real"


def test_aviso():
    assert "apagado" in canales.aviso("instagram", "apagado", False)
    assert "{cuando}" in canales.aviso("instagram", "real", True) and "cola" in canales.aviso("instagram", "real", True)
    assert "{cuando}" not in canales.aviso("instagram", "real", False)
    assert "Facebook" in canales.aviso("facebook", "real", True) and "10 minutos" in canales.aviso("facebook", "real", True)
    assert "YouTube Studio" in canales.aviso("youtube", "privado", False)


# ---------------- enviar_pieza: un camino para todos los canales ----------------
@pytest.mark.parametrize("canal", [c.clave for c in canales.CANALES.values() if c.foto])
def test_enviar_pieza_foto_en_simulado(canal, monkeypatch):
    """Cada canal con conector, en simulado, sin red (mail: frase_mail simulado)."""
    monkeypatch.setitem(sys.modules, "frase_mail", type("M", (), {"iniciar": staticmethod(lambda p, db, perfit: {"ok": True, "modo": "simulado", "estado_cola": "enviando"})}))
    monkeypatch.setitem(sys.modules, "perfit", type("M", (), {}))
    monkeypatch.setattr(publicar, "_registrar", lambda e: e)
    pieza = {"id": "p1", "canal": canal, "titulo": "Título", "texto": "Hola", "imagen_url": "https://wp/x.jpg",
             "fecha_programada": "2026-01-01T07:00:00+00:00", "resultado": {"formato": "cuadrado", "texto_imagen": "Hola", "autor": "David"}}
    res = publicar.enviar_pieza(_cfg(), pieza, quien="prueba")
    assert res["ok"] is True and res.get("modo") == "simulado", (canal, res)


def test_enviar_pieza_video_y_desconocido(monkeypatch):
    llamadas = []
    monkeypatch.setattr(publicar, "publicar_instagram_video", lambda cfg, url, texto, quien="", historia=False: llamadas.append(("ig", url, historia)) or {"ok": True, "modo": "simulado"})
    monkeypatch.setattr(publicar, "publicar_facebook_video", lambda cfg, url, texto, quien="", fecha=None, titulo="": llamadas.append(("fb", url, fecha, titulo)) or {"ok": True, "modo": "simulado"})
    monkeypatch.setattr(publicar, "bajar_bytes", lambda url, timeout=300: pytest.fail("en simulado no se baja el video"))
    monkeypatch.setattr(publicar, "publicar_youtube", lambda cfg, datos, titulo, desc, **k: llamadas.append(("yt", len(datos), k.get("nombre_archivo"))) or {"ok": True, "modo": "simulado"})
    cfg = _cfg()
    base = {"titulo": "T", "texto": "x", "imagen_url": None, "fecha_programada": None, "resultado": {"video_url": "https://wp/clip.mp4", "formato": "historia"}}
    assert publicar.enviar_pieza(cfg, dict(base, canal="instagram"), "u")["ok"]
    assert publicar.enviar_pieza(cfg, dict(base, canal="facebook"), "u")["ok"]
    assert publicar.enviar_pieza(cfg, dict(base, canal="youtube"), "u")["ok"]
    assert llamadas == [("ig", "https://wp/clip.mp4", True), ("fb", "https://wp/clip.mp4", None, "T"), ("yt", 0, "clip.mp4")]
    r = publicar.enviar_pieza(cfg, dict(base, canal="telegram"), "u")
    assert r["ok"] is False and "desconocido" in r["aviso"]
    r = publicar.enviar_pieza(cfg, dict(base, canal="newsletter"), "u")
    assert r["ok"] is False and "no se publica" in r["aviso"]


def test_enviar_pieza_solo_pasa_fechas_futuras(monkeypatch):
    """Una pieza vencida (la cola) se publica ahora; una con fecha futura (envío directo) la programa el proveedor."""
    visto = []
    monkeypatch.setattr(publicar, "publicar_facebook", lambda cfg, img, texto, quien="", fecha=None: visto.append(fecha) or {"ok": True, "modo": "simulado"})
    cfg = _cfg()
    publicar.enviar_pieza(cfg, {"canal": "facebook", "texto": "x", "fecha_programada": "2020-01-01T10:00:00+00:00"}, "u")
    publicar.enviar_pieza(cfg, {"canal": "facebook", "texto": "x", "fecha_programada": "2099-01-01T13:00:00+00:00"}, "u")
    publicar.enviar_pieza(cfg, {"canal": "facebook", "texto": "x", "fecha_programada": "2099-06-01T09:30:00"}, "u")
    publicar.enviar_pieza(cfg, {"canal": "facebook", "texto": "x", "fecha_programada": None}, "u")
    assert visto == [None, "2099-01-01T10:00:00", "2099-06-01T09:30:00", None]


def test_simular_cubre_todos_los_canales(monkeypatch):
    """`--simular` fuerza TODOS los canales del registro (antes: solo WordPress, Instagram y Facebook)."""
    for c in canales.CANALES.values():
        monkeypatch.setenv(c.variable, "real")
    monkeypatch.setattr(procesar_cola, "_cargar_config_local", lambda: None)
    monkeypatch.setattr(sys, "argv", ["procesar_cola.py", "--simular"])
    import db
    monkeypatch.setattr(db, "disponible", lambda: False)
    procesar_cola.main()
    import os
    assert all(os.environ[v] == "simulado" for v in canales.variables())
