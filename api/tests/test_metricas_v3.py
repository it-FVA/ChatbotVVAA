"""(12/11, Franco) Métricas v3, los datos: el mail coherente (Frase del día + lista), los estados `saliendo` y `cancelada`, `descripcion` de las
campañas, el período anterior (`anterior`) y las tasas de cada canal, y db.metricas.captura_cerca_de. Todo con la base y Perfit simulados."""
import datetime as dt

import pytest

import db
import metricas
from test_metricas import Cfg, mundo, pub, hace, AHORA, iso      # noqa: F401  (mundo es una fixture: Supabase simulada)
from test_metricas_perfit import ENV, CLAVE, sim                  # noqa: F401


@pytest.fixture(autouse=True)
def entorno_perfit(monkeypatch):
    monkeypatch.setenv("PERFIT_API_KEY", CLAVE)
    monkeypatch.setenv("PERFIT_CUENTA", "viviragradecido")
    monkeypatch.setenv("PERFIT_LISTA_FRASE", "55")


def _por_canal(logueado):
    return {c["clave"]: c for c in logueado.get("/admin/metricas/canales").json()["canales"]}


def _cuentas_mail(mundo):
    return [f["datos"] for f in mundo["filas"] if f["ambito"] == "canal" and f["ref"] == "mail"]


# ---------------- 1. mail ----------------
def _mundo_mail(mundo, monkeypatch, lista):
    """Dos mails de la Frase del día en el período (uno se lee ahora, el otro ya tenía captura), uno viejo y uno simulado; ninguna campaña de Perfit."""
    mundo["pubs"] += [pub(40, "mail", "publicada", 3), pub(41, "mail", "publicada", 4), pub(42, "mail", "publicada", 40), pub(43, "mail", "simulada", 3, modo="simulado")]
    mundo["filas"].append({"id": "m41", "ambito": "pieza", "ref": "pub-41", "canal": "mail", "fuente": "api", "capturado": hace(0, 5), "datos": {"enviados": 2000, "crudo": {}, "errores": []}})
    monkeypatch.setattr(db, "resumen_envios", lambda pid, fecha=None, prueba=None: {"pendiente": 0, "enviado": 900, "error": 5, "total": 905})
    return sim(monkeypatch, [("/campaigns", {"paging": {"total": 0, "next": None}, "data": []}), ("/lists/55", lista)])


def test_mail_suma_la_frase_y_la_lista(mundo, monkeypatch):
    _mundo_mail(mundo, monkeypatch, {"success": True, "data": {"id": 55, "name": "Frase", "activeContacts": 2300, "totalContacts": 2500}})
    desde_pub = [p for p in mundo["pubs"] if p["id"] == "pub-40"]            # la pasada de la cola solo trae la que no se leyó hace poco
    assert metricas._captura_mail("t", AHORA, desde_pub) == {"ok": True, "piezas": 1, "error": None}
    cuenta = _cuentas_mail(mundo)[0]
    assert cuenta["enviados_frase"] == 900 + 2000                            # la fresca (pub-40) + la última captura de pub-41; ni la de hace 40 días ni la simulada
    assert cuenta["lista_contactos"] == 2300
    assert cuenta["enviados"] == 0 and cuenta["crudo"]["campanas_en_periodo"] == 0 and cuenta["errores"] == []
    assert set(metricas._numeros({"datos": cuenta})) >= {"enviados_frase", "lista_contactos", "enviados"}


def test_mail_si_la_lista_falla_no_esta_y_lo_dice(mundo, monkeypatch):
    _mundo_mail(mundo, monkeypatch, RuntimeError("Perfit 500 en GET /lists/55: boom"))
    assert metricas._captura_mail("t", AHORA, [])["ok"] is True
    cuenta = _cuentas_mail(mundo)[0]
    assert "lista_contactos" not in cuenta and cuenta["enviados_frase"] == 2000
    assert any(e.startswith("No pude leer la lista de la Frase del día") for e in cuenta["errores"]) and CLAVE not in str(cuenta)


def test_mail_sin_lista_configurada_ni_pieza(mundo, monkeypatch):
    monkeypatch.delenv("PERFIT_LISTA_FRASE")
    sim(monkeypatch, [("/campaigns", {"paging": {"total": 0, "next": None}, "data": []})])
    assert metricas._captura_mail("t", AHORA, [])["ok"] is True
    cuenta = _cuentas_mail(mundo)[0]
    assert "lista_contactos" not in cuenta and cuenta["errores"] == []          # sin lista configurada no hay número ni error
    assert cuenta["enviados_frase"] == 0                                         # sin piezas de mail en el período, cero verdadero
    # una pieza sin ningún número (nunca se leyó): no se inventa un cero
    mundo["pubs"].append(pub(50, "mail", "publicada", 2))
    metricas._captura_mail("t", AHORA, [])
    assert "enviados_frase" not in _cuentas_mail(mundo)[-1]


def test_la_tarjeta_mail_trae_los_numeros_nuevos(logueado, mundo, monkeypatch):
    _mundo_mail(mundo, monkeypatch, {"data": {"activeContacts": 2300}})
    metricas._captura_mail("t", AHORA, [p for p in mundo["pubs"] if p["id"] == "pub-40"])
    m = _por_canal(logueado)["mail"]
    assert m["api"] == "disponible" and m["ultima"]["datos"]["enviados_frase"] == 2900 and m["ultima"]["datos"]["lista_contactos"] == 2300
    assert m["tasas"] == {"aperturas_sobre_enviados": None, "clics_sobre_enviados": None}      # sin enviados de campañas (0): no hay tasa


# ---------------- 3. estados y descripción ----------------
def test_saliendo_y_cancelada(logueado, mundo):
    nuevas = [pub(60, "mail", "enviando", 0), pub(61, "mail", "cancelada", 1), pub(62, "mail", "cancelada", 2), pub(63, "mail", "rechazada", 3)]
    for p in nuevas:
        p["usuario"] = "frase_del_dia"
    mundo["pubs"] += nuevas
    d = logueado.get("/admin/metricas/campanas").json()
    t = d["totales"]
    assert t["saliendo"] == 1 and t["cancelada"] == 2 and t["no_salio"] == 2          # no_salio: error de pub-6 + rechazada
    assert t["piezas"] == t["publicada"] + t["saliendo"] + t["programada"] + t["en_aprobacion"] == 4        # saliendo cuenta como hecha; cancelada no
    assert t["por_canal"].get("mail") == 1
    f = next(c for c in d["campanas"] if c["id"] == "frase_del_dia")
    assert f["por_estado"]["saliendo"] == 1 and f["por_estado"]["cancelada"] == 2 and f["por_estado"]["no_salio"] == 1
    assert {p["id"]: p["estado_grupo"] for p in f["piezas"]}["pub-60"] == "saliendo"


def test_descripcion_de_las_campanas(logueado, mundo, monkeypatch):
    p = pub(70, "instagram", "publicada", 1)
    p["usuario"] = "frase_del_dia"
    mundo["pubs"].append(p)
    original = db.proyectos.proyectos_por_ids
    monkeypatch.setattr(db.proyectos, "proyectos_por_ids", lambda ids: [dict(x, descripcion="Cuidar lo común" if x["id"] == "A" else "  ") for x in original(ids)])
    d = logueado.get("/admin/metricas/campanas").json()
    por = {c["id"]: c for c in d["campanas"]}
    assert por["A"]["descripcion"] == "Cuidar lo común" and por["B"]["descripcion"] is None and d["sueltas"]["descripcion"] is None
    assert por["frase_del_dia"]["descripcion"] == "La plataforma la arma y la manda sola cada día: historia de Instagram y mail"


# ---------------- 4. período anterior y tasas ----------------
def _canal(ref, hace_dias, datos):
    return {"id": f"{ref}{hace_dias}", "ambito": "canal", "ref": ref, "canal": ref, "fuente": "api", "capturado": hace(hace_dias),
            "periodo_desde": "2026-10-01", "periodo_hasta": "2026-10-29", "datos": dict(datos, crudo={"x": 1}, errores=[])}


def test_anterior_y_tasas(logueado, mundo):
    mundo["filas"] += [
        _canal("instagram", 0, {"alcance": 3100, "seguidores": 10000, "interacciones": 310}),
        _canal("instagram", 27, {"alcance": 2000, "seguidores": 9900}),                 # la más cercana a 28 días antes
        _canal("instagram", 21, {"alcance": 1, "seguidores": 1}),                        # dentro de la ventana, pero más lejos de 28
        _canal("instagram", 10, {"alcance": 999}),                                       # fuera de la ventana (menos de 20 días)
        _canal("facebook", 0, {"alcance": 50}),                                          # sin captura anterior
        _canal("sitio", 0, {"visitas": 12352, "visitantes": 3000}),
        _canal("mail", 0, {"enviados": 1000, "aperturas": 400, "clics": 25}),
        _canal("youtube", 0, {"vistas": 5, "alcance": 5, "seguidores": 0}),             # seguidores 0: no se divide
    ]
    por = _por_canal(logueado)
    ig = por["instagram"]
    assert ig["anterior"]["datos"] == {"alcance": 2000, "seguidores": 9900} and ig["anterior"]["periodo_hasta"] == "2026-10-29"
    assert "crudo" not in ig["anterior"]["datos"] and ig["anterior"]["capturado"] == hace(27)
    assert ig["tasas"] == {"alcance_sobre_seguidores": 0.31, "interacciones_sobre_alcance": 0.1}
    assert por["facebook"]["anterior"] is None and por["facebook"]["tasas"] == {"alcance_sobre_seguidores": None, "interacciones_sobre_alcance": None}
    assert por["sitio"]["tasas"] == {"visitas_por_dia": 441.143}                         # 12.352 / 28
    assert por["mail"]["tasas"] == {"aperturas_sobre_enviados": 0.4, "clics_sobre_enviados": 0.025}
    assert por["youtube"]["tasas"]["alcance_sobre_seguidores"] is None
    assert por["whatsapp"]["anterior"] is None and por["whatsapp"]["tasas"] == {} and por["instagram"]["manual"] is None


def test_anterior_si_la_base_falla_no_tumba_la_tarjeta(logueado, mundo, monkeypatch):
    mundo["filas"].append(_canal("instagram", 0, {"alcance": 10, "seguidores": 100}))

    def cae(*a, **k):
        raise RuntimeError("caída")
    monkeypatch.setattr(db, "captura_cerca_de", cae)
    ig = _por_canal(logueado)["instagram"]
    assert ig["anterior"] is None and ig["ultima"]["datos"]["alcance"] == 10 and ig["tasas"]["alcance_sobre_seguidores"] == 0.1


# ---------------- db.metricas.captura_cerca_de ----------------
def test_captura_cerca_de(monkeypatch):
    import db.metricas as dbm
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "k")
    filas = [{"capturado": hace(d), "ref": "instagram"} for d in (22, 27, 31, 35)] + [{"capturado": None}]
    visto = []

    def consulta(tabla, filtros=None, select="*", order=None, limite=None):
        visto.append((tabla, filtros, order))
        return filas
    monkeypatch.setattr(db, "consulta", consulta)
    objetivo = AHORA - dt.timedelta(days=28)
    f = dbm.captura_cerca_de("canal", "instagram", objetivo, desde=AHORA - dt.timedelta(days=40), hasta=AHORA - dt.timedelta(days=20))
    assert f["capturado"] == hace(27)
    tabla, filtros, orden = visto[0]
    claves = [(c, op) for c, (op, _) in filtros]
    assert tabla == "metricas" and ("capturado", "gte") in claves and ("capturado", "lte") in claves
    assert ("fuente", ("eq", "api")) in filtros and ("ref", ("eq", "instagram")) in filtros          # solo capturas por API
    filas.clear()
    assert dbm.captura_cerca_de("canal", "instagram", objetivo) is None
    monkeypatch.delenv("SUPABASE_URL")
    assert dbm.captura_cerca_de("canal", "instagram", objetivo) is None                                  # sin Supabase
