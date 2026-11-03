"""(3/11, Franco) El mail de la Frase del día puede arrancar de madrugada el mismo día, y el conteo de envíos no se corta en 1.000."""
import datetime

import db
import db.frases as dbf
import programar_frases as pf

JUE = datetime.date(2026, 11, 5)


def test_inicio_mail_madrugada_y_tarde_anterior():
    # antes que las redes (07:00): ese mismo día, de madrugada
    assert pf.inicio_mail(JUE, "01:00", "07:00") == "2026-11-05T01:00:00-03:00"
    assert pf.inicio_mail(JUE, "06:45", "07:00") == "2026-11-05T06:45:00-03:00"
    # después que las redes: la tarde del día anterior, como hasta ahora (15:00 es el default)
    assert pf.inicio_mail(JUE, "15:00", "07:00") == "2026-11-04T15:00:00-03:00"
    assert pf.inicio_mail(JUE) == "2026-11-04T15:00:00-03:00"
    # misma hora que las redes: el día anterior (nunca después de que salió en redes)
    assert pf.inicio_mail(JUE, "07:00", "07:00") == "2026-11-04T07:00:00-03:00"


def test_encolar_con_mail_a_la_una(monkeypatch):
    config = {"frase_mail_inicio": "01:00", "frase_hora": "07:00", "frase_imagen": "https://wp/fondo.jpg"}
    encoladas = []
    monkeypatch.setattr(db, "obtener_config", lambda k, d=None: config.get(k, d))
    monkeypatch.setattr(db, "encolar_publicacion", lambda u, canal, modo, titulo, texto, img, cuando, extra=None: encoladas.append((canal, titulo, cuando)) or f"p{len(encoladas)}")
    monkeypatch.setattr(db, "actualizar_frase", lambda fid, campos: None)
    monkeypatch.setattr(pf, "componer", lambda f, foto, estilo=None, formato=None: b"jpg")

    class Pub:
        @staticmethod
        def subir_imagen_wordpress(cfg, jpg, nombre, **k):
            return {"url": "https://wp/" + nombre}

    class Cfg:
        @staticmethod
        def resumen():
            return {"instagram": "real", "mail": "real"}

    frase = {"id": "f5", "texto": "Gracias.", "autor": "Br. David", "imagen_url": None, "estilo": None, "piezas": None}
    piezas, aviso = pf.encolar_frase(frase, JUE, Cfg(), db, Pub(), hora="07:00", canales=["historia", "mail"])
    cuando = {titulo: c for _, titulo, c in encoladas}
    assert set(piezas) == {"historia", "mail"}
    assert cuando["Frase del día 05/11/2026 (mail)"] == "2026-11-05T01:00:00-03:00"
    assert cuando["Frase del día 05/11/2026 (historia)"] == "2026-11-05T07:00:00-03:00"


def test_resumen_envios_pagina_mas_de_mil(monkeypatch):
    """Supabase corta en 1.000 filas: con 2.241 (1.000 enviadas primero) el conteo tiene que ver las 1.241 pendientes."""
    filas = [{"estado": "enviado"}] * 1000 + [{"estado": "pendiente"}] * 1241
    pedidos = []

    def _req(method, params="", body=None, tabla=None, **k):
        pedidos.append(params)
        desde = int(params.split("offset=")[1])
        return filas[desde:desde + 1000]          # como el servidor: nunca más de 1.000
    monkeypatch.setattr(dbf._db, "disponible", lambda: True)
    monkeypatch.setattr(dbf._db, "_req", _req)
    r = dbf.resumen_envios("p1")
    assert r == {"pendiente": 1241, "enviado": 1000, "error": 0, "total": 2241}
    assert len(pedidos) == 3 and all("order=id" in p and "limit=1000" in p for p in pedidos)
