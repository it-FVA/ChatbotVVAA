"""(12/11, Franco) Métricas v4, tarjetas que cuentan algo: la serie por canal (db.metricas.serie_canal, metricas.serie, GET /serie) y las piezas de
cada canal (ultimas_piezas y mejor_pieza dentro de GET /canales). Todo con la base simulada de test_metricas.py."""
import db
import metricas
from test_metricas import mundo, pub, hace, AHORA, iso      # noqa: F401  (mundo es una fixture: Supabase simulada)


def _por_canal(logueado):
    return {c["clave"]: c for c in logueado.get("/admin/metricas/canales").json()["canales"]}


def _met(ref, canal, datos, dias=0, fuente="api"):
    return {"id": f"met-{ref}-{fuente}", "ambito": "pieza", "ref": ref, "canal": canal, "fuente": fuente, "capturado": hace(dias), "datos": dict(datos, crudo={}, errores=[])}


# ---------------- la serie ----------------
def test_serie_canal_una_por_dia_en_hora_argentina(monkeypatch):
    import db.metricas as dbm
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "k")
    filas = [{"capturado": "2026-11-10T01:00:00Z", "datos": {"alcance": 1}},      # 09/11 22:00 en Argentina
             {"capturado": "2026-11-10T12:00:00Z", "datos": {"alcance": 2}},      # 10/11 09:00
             {"capturado": "2026-11-10T20:00:00Z", "datos": {"alcance": 3}},      # 10/11 17:00
             {"capturado": "2026-11-11T02:30:00Z", "datos": {"alcance": 4}},      # 10/11 23:30: todavía es el 10 en Argentina, la última del día
             {"capturado": "2026-11-12T15:00:00Z", "datos": {"alcance": 5}},
             {"capturado": "no es una fecha", "datos": {}}]
    visto = []

    def consulta(tabla, filtros=None, select="*", order=None, limite=None):
        visto.append((tabla, filtros))
        return filas
    monkeypatch.setattr(db, "consulta", consulta)
    r = dbm.serie_canal("instagram", 28)
    assert [f["datos"]["alcance"] for f in r] == [1, 4, 5]                          # 09/11, 10/11 (la de las 23:30), 12/11
    tabla, filtros = visto[0]
    assert tabla == "metricas" and ("ref", ("eq", "instagram")) in filtros and ("fuente", ("eq", "api")) in filtros and ("ambito", ("eq", "canal")) in filtros
    assert any(c == "capturado" and op == "gte" for c, (op, _) in filtros)           # solo los últimos días
    monkeypatch.delenv("SUPABASE_URL")
    assert dbm.serie_canal("instagram", 28) == []                                    # sin Supabase


def test_ruta_serie(logueado, mundo, monkeypatch):
    filas = [{"capturado": "2026-11-10T20:00:00Z", "datos": {"alcance": 3, "seguidores": 100, "crudo": {"x": 1}, "errores": []}},
             {"capturado": "2026-11-11T20:00:00Z", "datos": {"errores": ["falló"]}},                     # sin números: no es un punto
             {"capturado": "2026-11-12T20:00:00Z", "datos": {"alcance": 7}}]
    pedidos = []
    monkeypatch.setattr(db, "serie_canal", lambda ref, dias: pedidos.append((ref, dias)) or filas)
    r = logueado.get("/admin/metricas/serie?canal=instagram&dias=28")
    assert r.status_code == 200, r.text
    assert pedidos == [("instagram", 28)]
    assert r.json() == {"canal": "instagram", "dias": 28, "puntos": [{"dia": "2026-11-10", "datos": {"alcance": 3, "seguidores": 100}}, {"dia": "2026-11-12", "datos": {"alcance": 7}}]}
    assert logueado.get("/admin/metricas/serie?canal=tiktok").status_code == 400
    assert logueado.get("/admin/metricas/serie?canal=mail&dias=0").status_code == 422
    monkeypatch.setattr(db, "serie_canal", lambda ref, dias: [])
    assert logueado.get("/admin/metricas/serie?canal=youtube").json() == {"canal": "youtube", "dias": 28, "puntos": []}


def test_ruta_serie_pide_permiso(cliente):
    assert cliente.get("/admin/metricas/serie?canal=instagram").status_code in (401, 403)


# ---------------- las piezas de cada canal ----------------
def test_ultimas_piezas_y_mejor(logueado, mundo):
    mundo["pubs"] += [pub(10, "instagram", "publicada", 1, ultimo={"permalink": "https://instagram.com/p/10"}), pub(11, "instagram", "publicada", 2),
                      pub(12, "instagram", "publicada", 5), pub(13, "instagram", "publicada", 40), pub(14, "instagram", "simulada", 0, modo="simulado")]
    mundo["filas"] += [_met("pub-1", "instagram", {"alcance": 955, "vistas": 1173}), _met("pub-10", "instagram", {"alcance": 300}), _met("pub-11", "instagram", {"alcance": 80, "vistas": 9999}),
                       _met("pub-13", "instagram", {"alcance": 50000}),                                                   # hace 40 días: no entra en «la mejor» del período
                       _met("pub-12", "instagram", {"alcance": 700}, fuente="manual")]                                   # a mano también cuenta
    ig = _por_canal(logueado)["instagram"]
    # publicadas (las de estado simulada y las de otros canales no): pub-10 (1 día), pub-11 (2), pub-1 (3), pub-12 (5), pub-13 (40)
    assert [p["id"] for p in ig["ultimas_piezas"]] == ["pub-10", "pub-11", "pub-1"]
    primera = ig["ultimas_piezas"][0]
    assert primera["titulo"] == "Pieza 10" and primera["ver_url"] == "https://instagram.com/p/10" and primera["campana"] is None and primera["metricas"]["alcance"] == 300
    assert primera["metricas"]["fuente"] == "api"
    uno = ig["ultimas_piezas"][2]
    assert uno["campana"] == "Lo común nos convoca" and uno["formato"] == "historia" and uno["metricas"]["vistas"] == 1173         # pub-1 está en la campaña A
    assert ig["ultimas_piezas"][1]["metricas"]["alcance"] == 80
    assert ig["mejor_pieza"]["id"] == "pub-1" and ig["mejor_pieza"]["metricas"]["alcance"] == 955                               # por alcance, aunque pub-11 tenga más vistas
    fb = _por_canal(logueado)["facebook"]
    assert fb["ultimas_piezas"] == [] and fb["mejor_pieza"] is None                                                             # las de Facebook no se publicaron
    assert _por_canal(logueado)["whatsapp"]["ultimas_piezas"] == []


def test_mejor_pieza_por_vistas_si_ninguna_tiene_alcance(logueado, mundo):
    mundo["pubs"] += [pub(20, "youtube", "publicada", 2), pub(21, "youtube", "publicada", 4), pub(22, "youtube", "publicada", 6)]
    mundo["filas"] += [_met("pub-20", "youtube", {"vistas": 40}), _met("pub-21", "youtube", {"vistas": 900})]
    yt = _por_canal(logueado)["youtube"]
    assert yt["mejor_pieza"]["id"] == "pub-21"
    assert yt["ultimas_piezas"][2]["metricas"] is None                                                                         # pub-22 todavía sin números


def test_piezas_sin_numeros_no_tienen_mejor(logueado, mundo):
    mundo["pubs"] += [pub(30, "youtube", "publicada", 2)]
    yt = _por_canal(logueado)["youtube"]
    assert [p["id"] for p in yt["ultimas_piezas"]] == ["pub-30"] and yt["ultimas_piezas"][0]["metricas"] is None and yt["mejor_pieza"] is None


def test_piezas_excluyen_usuarios_excluidos(logueado, mundo):
    mundo["config"]["metricas_excluir_usuarios"] = ["lizzie"]
    mundo["pubs"] += [dict(pub(40, "instagram", "publicada", 0), usuario="lizzie"), pub(41, "instagram", "publicada", 1)]
    ids = [p["id"] for p in _por_canal(logueado)["instagram"]["ultimas_piezas"]]
    assert ids[0] == "pub-41" and "pub-40" not in ids


def test_mail_frase_del_dia_y_newsletter(logueado, mundo):
    mundo["pubs"] += [dict(pub(50, "mail", "publicada", 1), usuario="frase_del_dia", titulo="Frase de hoy"), dict(pub(51, "newsletter", "publicada", 3), titulo="Newsletter de noviembre"),
                      dict(pub(52, "mail", "publicada", 2), usuario="frase_del_dia")]
    mundo["filas"] += [_met("pub-50", "mail", {"enviados": 2100}), _met("pub-52", "mail", {"enviados": 1900})]
    mail = _por_canal(logueado)["mail"]
    assert [p["id"] for p in mail["ultimas_piezas"]] == ["pub-50", "pub-52", "pub-51"]
    assert mail["ultimas_piezas"][0]["campana"] == "Frase del día (automática)" and mail["ultimas_piezas"][0]["metricas"]["enviados"] == 2100
    assert mail["ultimas_piezas"][2]["formato"] == "newsletter" and mail["ultimas_piezas"][2]["metricas"] is None and mail["ultimas_piezas"][2]["campana"] is None
    assert mail["mejor_pieza"] is None                                                                                         # enviar mucho no es «andar bien»: sin aperturas no hay mejor


def test_si_las_piezas_fallan_la_tarjeta_sale_igual(logueado, mundo, monkeypatch):
    mundo["filas"].append({"id": "c1", "ambito": "canal", "ref": "instagram", "canal": "instagram", "fuente": "api", "capturado": hace(0), "datos": {"alcance": 10}})

    def cae(*a, **k):
        raise RuntimeError("caída")
    monkeypatch.setattr(db, "publicaciones_para_metricas", cae)
    ig = _por_canal(logueado)["instagram"]
    assert ig["ultima"]["datos"]["alcance"] == 10 and ig["ultimas_piezas"] == [] and ig["mejor_pieza"] is None
