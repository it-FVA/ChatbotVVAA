"""(18/11, Franco: inventario de avisos) Los avisos que salen desde la cola, con Slack y mail simulados (nunca se manda nada real):
pieza que falló al publicar (primer error y definitivo), pieza publicada de verdad (no la Frase del día), los avisos de una vez por
día (frases que se acaban, token de Instagram por vencer) y el cierre del mail de la frase (con errores o incompleto)."""
import datetime
import sys
import types

import pytest

import avisos
import db
import frase_mail
import procesar_cola
import publicar
from test_frase_cola import base, PerfitFalso, _cfg, MAN  # noqa: F401  (la db en memoria de la cola y la frase)
import programar_frases as pf


@pytest.fixture
def slack(monkeypatch):
    """Slack «configurado» y capturado; sin SMTP."""
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.test/abc")
    for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASS"):
        monkeypatch.delenv(k, raising=False)
    mandados = []
    monkeypatch.setattr(avisos, "_slack", lambda texto: mandados.append(texto) or True)
    return mandados


@pytest.fixture
def cola_simulada(base, monkeypatch):
    """procesar_cola.main con la db en memoria de test_frase_cola y los módulos vecinos apagados."""
    monkeypatch.setattr(db, "listar_usuarios", lambda limite=500: [
        {"usuario": "lizzie", "email": "l@x.org", "rol": "creador", "activo": True},
        {"usuario": "julian", "email": "j@x.org", "rol": "aprobador", "activo": True}], raising=False)
    monkeypatch.setitem(sys.modules, "frase_mail", types.SimpleNamespace(avanzar=lambda d, pe: []))
    monkeypatch.setitem(sys.modules, "perfit", types.SimpleNamespace())
    monkeypatch.setitem(sys.modules, "programar_frases", types.SimpleNamespace(main=lambda a=None: 0, USUARIO="frase_del_dia"))
    monkeypatch.setitem(sys.modules, "meta_token", types.SimpleNamespace(renovar_token_ig=lambda: None, info_token=lambda: {"vence": None}))
    monkeypatch.setattr(procesar_cola, "_cargar_config_local", lambda: None)
    monkeypatch.setattr(procesar_cola, "_avisos_diarios", lambda d: [])
    monkeypatch.setattr(sys, "argv", ["procesar_cola.py"])
    monkeypatch.setenv("PUBLICAR_INSTAGRAM", "real")
    return base


# ---------------- (1) pieza que falló al publicar ----------------
def test_pieza_que_falla_avisa_en_el_primer_error_y_en_el_definitivo(cola_simulada, slack, monkeypatch):
    monkeypatch.setattr(publicar, "publicar_instagram", lambda *a, **k: {"ok": False, "modo": "real", "aviso": "Meta dijo no"})
    pid = db.encolar_publicacion("lizzie", "instagram", "real", "Tres momentos", "hola", "https://wp/i.jpg", "2026-11-03T07:00:00-03:00")
    procesar_cola.main()
    assert cola_simulada.pubs[pid]["estado"] == "pendiente"
    assert len(slack) == 1 and "Pieza con error al publicar: Instagram — lizzie" in slack[0]
    assert "intento 1 de 3" in slack[0] and "Meta dijo no" in slack[0] and "Se reintenta en la próxima corrida" in slack[0]
    assert "Iba a salir el 2026-11-03 07:00" in slack[0] and "«Tres momentos»" in slack[0]
    procesar_cola.main()                       # segundo intento: sin aviso (sería ruido)
    assert len(slack) == 1
    procesar_cola.main()                       # tercero: queda en error y avisa de nuevo
    assert cola_simulada.pubs[pid]["estado"] == "error"
    assert len(slack) == 2 and "Pieza NO salió: Instagram — lizzie" in slack[1] and "Falló 3 veces" in slack[1] and "/publicaciones" in slack[1]


def test_pieza_fallo_va_a_quien_la_hizo_y_a_los_aprobadores(monkeypatch):
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    monkeypatch.setenv("SMTP_HOST", "smtp.test"); monkeypatch.setenv("SMTP_USER", "u"); monkeypatch.setenv("SMTP_PASS", "p")
    mails = []
    monkeypatch.setattr(avisos, "_mail", lambda dest, asunto, texto: mails.append((dest, asunto, texto)) or True)
    from test_avisos import _DB
    r = avisos.pieza_fallo(_DB(), {"usuario": "lizzie", "canal": "facebook", "texto": "Hola"}, "excepción: timeout", 3, definitivo=True, sincrono=True)
    assert r["mail"] is True
    assert mails[0][0] == ["b@x.org", "j@x.org", "l@x.org"] and mails[0][1] == "Pieza NO salió: Facebook — lizzie" and "timeout" in mails[0][2]


# ---------------- (2) pieza publicada ----------------
def test_pieza_publicada_avisa_con_el_link_y_no_para_la_frase_del_dia(cola_simulada, slack, monkeypatch):
    monkeypatch.setattr(publicar, "publicar_instagram", lambda *a, **k: {"ok": True, "modo": "real", "id": "178", "permalink": "https://www.instagram.com/p/abc/"})
    p1 = db.encolar_publicacion("lizzie", "instagram", "real", "", "Tres momentos para agradecer", "https://wp/i.jpg", "2026-11-03T07:00:00-03:00")
    p2 = db.encolar_publicacion("frase_del_dia", "instagram", "real", "Frase", "hola", "https://wp/i.jpg", "2026-11-03T07:00:00-03:00", extra={"formato": "historia"})
    procesar_cola.main()
    assert cola_simulada.pubs[p1]["estado"] == "publicada" and cola_simulada.pubs[p2]["estado"] == "publicada"
    assert len(slack) == 1 and "Pieza publicada: Instagram — lizzie" in slack[0] and "https://www.instagram.com/p/abc/" in slack[0]


def test_pieza_simulada_no_avisa(cola_simulada, slack, monkeypatch):
    monkeypatch.setenv("PUBLICAR_INSTAGRAM", "simulado")
    monkeypatch.setattr(publicar, "publicar_instagram", lambda *a, **k: {"ok": True, "modo": "simulado"})
    pid = db.encolar_publicacion("lizzie", "instagram", "simulado", "T", "hola", "https://wp/i.jpg", "2026-11-03T07:00:00-03:00")
    procesar_cola.main()
    assert cola_simulada.pubs[pid]["estado"] == "simulada" and slack == []


def test_link_publicado_por_canal():
    assert avisos.link_publicado({"permalink": "https://ig/p/1"}) == "https://ig/p/1"
    assert avisos.link_publicado({"link": "https://blog/x", "id": 5}) == "https://blog/x"
    assert avisos.link_publicado({"id": "123_456"}) == "id 123_456"
    assert avisos.link_publicado({"ok": True}) is None and avisos.link_publicado("texto") is None


# ---------------- (3) y (4) una vez por día: frases que se acaban, token por vencer ----------------
class _Config:
    def __init__(self, frases, activa=True):
        self.config, self.frases = {"frase_activa": activa}, frases
    def obtener_config(self, k, d=None): return self.config.get(k, d)
    def guardar_config(self, k, v, usuario=None): self.config[k] = v
    def listar_frases(self, desde=None, hasta=None, limite=2000):
        return [f for f in self.frases if not desde or f["fecha"] >= str(desde)]


def _frases(hoy, dias):
    return [{"fecha": (hoy + datetime.timedelta(days=i)).isoformat(), "estado": "programada"} for i in range(1, dias + 1)]


def test_dias_con_frase_cuenta_desde_manana_hasta_el_primer_hueco():
    hoy = datetime.date(2026, 11, 18)
    assert procesar_cola.dias_con_frase(_Config(_frases(hoy, 3)), hoy) == (3, "2026-11-21")
    assert procesar_cola.dias_con_frase(_Config([]), hoy) == (0, None)
    con_hueco = _frases(hoy, 2) + [{"fecha": "2026-11-25", "estado": "programada"}, {"fecha": "2026-11-21", "estado": "publicada"}]
    assert procesar_cola.dias_con_frase(_Config(con_hueco), hoy) == (2, "2026-11-20")


def test_frases_pocas_avisa_una_vez_por_dia_desde_las_ocho(slack, monkeypatch):
    hoy = datetime.date(2026, 11, 18)
    base = _Config(_frases(hoy, 4))
    monkeypatch.setitem(sys.modules, "meta_token", types.SimpleNamespace(info_token=lambda: {"vence": None}))
    temprano = datetime.datetime(2026, 11, 18, 7, 30, tzinfo=datetime.timezone(datetime.timedelta(hours=-3)))
    assert procesar_cola._avisos_diarios(base, ahora=temprano) == [] and slack == []
    ocho = temprano.replace(hour=8, minute=5)
    lineas = procesar_cola._avisos_diarios(base, ahora=ocho)
    assert len(slack) == 1 and "Quedan 4 días con frase asignada (hasta el 2026-11-22)" in slack[0] and "/frases" in slack[0]
    assert any("quedan 4 días" in l and "avisado" in l for l in lineas) and any("no se sabe cuándo vence" in l for l in lineas)
    assert base.config["avisos_diarios"] == {"frases_pocas": "2026-11-18"}
    procesar_cola._avisos_diarios(base, ahora=ocho.replace(hour=12))     # misma jornada: no repite
    assert len(slack) == 1
    procesar_cola._avisos_diarios(base, ahora=ocho + datetime.timedelta(days=1))   # al día siguiente, de nuevo (quedan 3)
    assert len(slack) == 2 and "Quedan 3 días" in slack[1]


def test_frases_sin_manana_apagada_o_con_muchas_no_avisa(slack, monkeypatch):
    hoy = datetime.date(2026, 11, 18)
    ocho = datetime.datetime(2026, 11, 18, 8, 5, tzinfo=datetime.timezone(datetime.timedelta(hours=-3)))
    monkeypatch.setitem(sys.modules, "meta_token", types.SimpleNamespace(info_token=lambda: {"vence": None}))
    procesar_cola._avisos_diarios(_Config(_frases(hoy, 0)), ahora=ocho)
    assert "Mañana no tiene frase asignada" in slack[-1]
    procesar_cola._avisos_diarios(_Config(_frases(hoy, 0), activa=False), ahora=ocho)
    procesar_cola._avisos_diarios(_Config(_frases(hoy, 12)), ahora=ocho)
    assert len(slack) == 1


def test_token_ig_por_vencer_avisa_a_diez_dias_y_no_sin_fecha(slack, monkeypatch):
    base = _Config([], activa=False)
    ocho = datetime.datetime(2026, 11, 18, 9, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=-3)))
    vence = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=9, hours=12)
    monkeypatch.setitem(sys.modules, "meta_token", types.SimpleNamespace(info_token=lambda: {"vence": vence, "origen": "config"}))
    lineas = procesar_cola._avisos_diarios(base, ahora=ocho)
    assert len(slack) == 1 and "token de Instagram está por vencer" in slack[0] and "(9 días)" in slack[0]
    assert avisos.TRELLO_TOKEN_IG in slack[0] and "Renovar token" in slack[0] and "/admin" in slack[0]
    assert base.config["avisos_diarios"]["token_ig"] == "2026-11-18" and any("vence en 9 días" in l for l in lineas)
    procesar_cola._avisos_diarios(base, ahora=ocho.replace(hour=20))
    assert len(slack) == 1
    # con 25 días no avisa; sin fecha tampoco
    base2 = _Config([], activa=False)
    monkeypatch.setitem(sys.modules, "meta_token", types.SimpleNamespace(info_token=lambda: {"vence": vence + datetime.timedelta(days=16)}))
    assert any("sin aviso" in l for l in procesar_cola._avisos_diarios(base2, ahora=ocho)) and len(slack) == 1
    monkeypatch.setitem(sys.modules, "meta_token", types.SimpleNamespace(info_token=lambda: {"vence": None}))
    assert any("no se sabe" in l for l in procesar_cola._avisos_diarios(_Config([], activa=False), ahora=ocho)) and len(slack) == 1


def test_token_vencido_lo_dice(slack):
    avisos.token_ig_por_vencer(-2, datetime.datetime(2026, 11, 16, tzinfo=datetime.timezone.utc))
    assert "Venció el 16/11/2026" in slack[0] and "no salen hasta renovarlo" in slack[0]


def test_una_vez_por_dia_calla_si_no_puede_leer():
    class Rota:
        def obtener_config(self, k, d=None): raise RuntimeError("sin base")
    assert avisos.una_vez_por_dia(Rota(), "x", "2026-11-18") is False


# ---------------- (5) mail de la Frase del día con errores o incompleto ----------------
class _PerfitConErrores(PerfitFalso):
    def disparar(self, email, ctx):
        self.disparos.append((email, ctx["frase"]))
        if email == "c1@x.org":
            return {"ok": False, "estado": "error", "aviso": "Perfit: 400 contacto inválido"}
        return {"ok": True, "estado": "enviado", "aviso": "HTTP 200"}


def test_mail_que_cierra_con_errores_avisa(base, slack):
    piezas, _ = pf.encolar_frase(base.frases["f1"], MAN, _cfg(), db, publicar, canales=["mail"])
    p = base.pubs[piezas["mail"]]
    perfit = _PerfitConErrores("real")
    assert frase_mail.iniciar(p, db, perfit)["ok"]
    p["estado"] = "enviando"
    res = frase_mail.avanzar(db, perfit, max_por_corrida=50, hoy=MAN)
    assert res[0]["errores"] == 1 and res[0]["estado"] == "publicada"
    assert len(slack) == 1 and "terminó con errores" in slack[0] and f"Frase del {MAN.isoformat()}: 4 enviados, 1 con error, 0 pendientes" in slack[0]


def test_mail_sin_errores_no_avisa(base, slack):
    piezas, _ = pf.encolar_frase(base.frases["f1"], MAN, _cfg(), db, publicar, canales=["mail"])
    p = base.pubs[piezas["mail"]]
    perfit = PerfitFalso("real")
    frase_mail.iniciar(p, db, perfit)
    p["estado"] = "enviando"
    assert frase_mail.avanzar(db, perfit, max_por_corrida=50, hoy=MAN)[0]["estado"] == "publicada" and slack == []


def test_mail_incompleto_al_cierre_del_dia_avisa_una_sola_vez(base, slack):
    piezas, _ = pf.encolar_frase(base.frases["f1"], MAN, _cfg(), db, publicar, canales=["mail"])
    p = base.pubs[piezas["mail"]]
    perfit = PerfitFalso("real", fallar_en=2)         # el 2.º disparo da 429: quedan pendientes
    frase_mail.iniciar(p, db, perfit)
    p["estado"] = "enviando"
    r = frase_mail.avanzar(db, perfit, max_por_corrida=50, hoy=MAN)          # el día de la frase: sigue, sin aviso
    assert r[0]["quedan"] == 4 and slack == []
    pasado = MAN + datetime.timedelta(days=1)
    perfit.fallar_en = 3
    frase_mail.avanzar(db, perfit, max_por_corrida=50, hoy=pasado)            # ya pasó el día y hay pendientes: avisa
    assert len(slack) == 1 and "quedó incompleto" in slack[0] and "pendientes" in slack[0] and base.pubs[piezas["mail"]]["resultado"]["aviso_incompleto"] == pasado.isoformat()
    perfit.fallar_en = 4
    frase_mail.avanzar(db, perfit, max_por_corrida=50, hoy=pasado)            # otra tanda del mismo día: no repite
    assert len(slack) == 1
