"""(8/11, Franco) Métricas de campañas y canales (api/metricas_rutas.py, metricas.py, metricas_meta.py, metricas_asesor.py)
con una Supabase simulada (monkeypatch sobre db), Meta simulado (monkeypatch sobre metricas_meta._http / las funciones de insights)
y el cliente de OpenAI simulado. Sin red, sin claves."""
import datetime as dt, json, types

import pytest

import db
import metricas
import metricas_meta
import metricas_youtube
import metricas_asesor
import nucleo

AHORA = dt.datetime.now(dt.timezone.utc)
TOKEN_IG = "IGQVJ-TOKEN-SECRETO-IG"
TOKEN_FB = "EAAB-TOKEN-SECRETO-FB"
TOKEN_YT = json.dumps({"client_id": "cid", "client_secret": "SECRETO-CLIENTE-YT", "refresh_token": "REFRESH-SECRETO-YT", "scopes": []})


def iso(d):
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def hace(dias=0, horas=0):
    return iso(AHORA - dt.timedelta(days=dias, hours=horas))


class Cfg:
    """Lo que usa metricas.py de publicar.Config."""
    ig_token, ig_id, fb_token, fb_page_id, wp_site = TOKEN_IG, "17841", TOKEN_FB, "999", "viviragradecidos.org"
    yt_token_json = TOKEN_YT
    configurado = {"instagram": True, "facebook": True, "youtube": True, "mail": True, "wordpress": True, "whatsapp": True}
    modos = {"instagram": "real", "facebook": "real", "wordpress": "real", "youtube": "privado", "mail": "apagado", "whatsapp": "simulado"}

    def modo(self, c):
        return self.modos.get(c, "apagado")


def pub(i, canal, estado, dias, proyecto=None, modo="real", **res):
    return {"id": f"pub-{i}", "creado": hace(dias + 1), "usuario": "pato", "canal": canal, "modo": modo, "titulo": f"Pieza {i}",
            "estado": estado, "fecha_programada": None, "procesado_en": hace(dias) if estado == "publicada" else None,
            "resultado": res, "imagen_url": None}


@pytest.fixture
def mundo(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "k")
    pubs = [
        pub(1, "instagram", "publicada", 3, ultimo={"id": "ig-1", "permalink": "https://instagram.com/p/1"}, formato="historia"),
        pub(2, "instagram", "pendiente", 1),
        pub(3, "facebook", "a_aprobar", 1),
        pub(4, "facebook", "borrador", 2),
        pub(5, "whatsapp", "simulada", 5, modo="simulado"),
        pub(6, "instagram", "error", 4),                       # suelta
        pub(7, "instagram", "publicada", 200),                 # fuera del período de 90 días
        pub(8, "instagram", "algo_raro", 6),                   # estado desconocido → prueba (suelta)
    ]
    items = [{"proyecto_id": "A", "item_id": "pub-1"}, {"proyecto_id": "A", "item_id": "pub-2"}, {"proyecto_id": "A", "item_id": "pub-3"},
             {"proyecto_id": "B", "item_id": "pub-4"}, {"proyecto_id": "B", "item_id": "pub-5"},
             {"proyecto_id": "C", "item_id": "pub-7"}]            # C: tiene piezas pero ninguna en el período
    proyectos = {"A": {"id": "A", "nombre": "Lo común nos convoca", "emoji": "🤝", "color": "#112233", "dueno": "pato", "creado": hace(50)},
                 "B": {"id": "B", "nombre": "Polarizaciones", "emoji": None, "color": None, "dueno": "pato", "creado": hace(120)},
                 "C": {"id": "C", "nombre": "Vieja", "emoji": None, "color": None, "dueno": "lizzie", "creado": hace(300)}}
    st = {"pubs": pubs, "filas": [], "config": {}, "cambios": [], "usos": [], "n": 0}

    def guardar(fila):
        st["n"] += 1
        f = dict(fila, id=f"m{st['n']}", creado=hace(0), capturado=fila.get("capturado") or iso(AHORA + dt.timedelta(seconds=st["n"])))
        f.setdefault("periodo_desde", None), f.setdefault("periodo_hasta", None), f.setdefault("nota", None), f.setdefault("canal", None)
        st["filas"].append(f)
        return f

    def ultimas(ambito, refs=None, fuente=None):
        out = {}
        for f in sorted(st["filas"], key=lambda x: x["capturado"], reverse=True):
            if f["ambito"] != ambito or (refs is not None and f["ref"] not in [str(r) for r in refs]) or (fuente and f["fuente"] != fuente):
                continue
            out.setdefault((f["ref"], f["fuente"]), f)
        return out

    monkeypatch.setattr(db, "guardar_metrica", guardar)
    monkeypatch.setattr(db, "ultimas_metricas", ultimas)
    monkeypatch.setattr(db, "publicaciones_para_metricas", lambda desde: [p for p in st["pubs"]])
    monkeypatch.setattr(db, "piezas_de_proyectos", lambda: [dict(i) for i in items])
    monkeypatch.setattr(db, "publicacion_por_id", lambda pid: next((p for p in st["pubs"] if p["id"] == pid), None))
    monkeypatch.setattr(db.proyectos, "proyectos_por_ids", lambda ids: [proyectos[i] for i in sorted(ids) if i in proyectos])
    monkeypatch.setattr(db, "obtener_config", lambda clave, defecto=None: st["config"].get(clave, defecto))
    monkeypatch.setattr(db, "guardar_config", lambda clave, valor, usuario=None: st["config"].__setitem__(clave, valor))
    monkeypatch.setattr(db, "registrar_cambio_usuario", lambda quien, accion, usuario=None, detalle=None: st["cambios"].append((quien, accion, usuario, detalle)))
    import api.metricas_rutas as mr
    monkeypatch.setattr(mr, "_config", lambda: Cfg())
    return st


# ---------------- estados ----------------
def test_grupo_de():
    assert metricas.grupo_de("publicada") == "publicada"
    for e in ("pendiente", "lista", "procesando", "enviando"):
        assert metricas.grupo_de(e) == "programada"
    assert metricas.grupo_de("a_aprobar") == "en_aprobacion" and metricas.grupo_de("borrador") == "borrador"
    for e in ("simulada", "prueba", "registrada", "lo-que-sea", None):
        assert metricas.grupo_de(e) == "prueba"
    for e in ("rechazada", "cancelada", "error"):
        assert metricas.grupo_de(e) == "no_salio"


# ---------------- campañas ----------------
def test_campanas(logueado, mundo):
    mundo["filas"] += [
        {"id": "x1", "ambito": "pieza", "ref": "pub-1", "canal": "instagram", "fuente": "api", "capturado": hace(1), "datos": {"alcance": 120, "me_gusta": 14, "crudo": {}, "errores": []}},
        {"id": "x2", "ambito": "pieza", "ref": "pub-1", "canal": "instagram", "fuente": "manual", "capturado": hace(0), "datos": {"alcance": 999}},
        {"id": "x3", "ambito": "pieza", "ref": "pub-4", "canal": "facebook", "fuente": "manual", "capturado": hace(0), "datos": {"alcance": 50}},
    ]
    r = logueado.get("/admin/metricas/campanas")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["periodo"]["tipo"] == "dias" and d["periodo"]["dias"] == 90 and d["periodo"]["hasta"] is None
    # totales (8/11): 7 piezas en el período (la de 200 días queda afuera), pero «piezas» suma solo publicada + programada + en aprobación
    t = d["totales"]
    assert t["piezas"] == 3 and t["publicada"] == 1 and t["programada"] == 1 and t["en_aprobacion"] == 1 and t["borrador"] == 1
    assert t["prueba"] == 2 and t["no_salio"] == 1                    # whatsapp simulada + algo_raro / error
    assert t["por_canal"] == {"instagram": 2, "facebook": 1}                    # solo las piezas que cuentan como hechas
    nombres = [c["nombre"] for c in d["campanas"]]
    assert nombres == ["Lo común nos convoca", "Polarizaciones", "Vieja"]        # por `ultima` descendente; la sin piezas del período al final
    a, b, c = d["campanas"]
    assert a["piezas_total"] == 3 and a["emoji"] == "🤝" and a["dueno"] == "pato"
    assert a["por_estado"] == {"publicada": 1, "programada": 1, "en_aprobacion": 1, "borrador": 0, "prueba": 0, "no_salio": 0}
    assert a["por_canal"]["instagram"]["publicada"] == 1 and a["por_canal"]["instagram"]["programada"] == 1 and a["por_canal"]["facebook"]["en_aprobacion"] == 1
    assert [p["id"] for p in a["piezas"]] == sorted([p["id"] for p in a["piezas"]], key=lambda i: {p["id"]: p["fecha"] for p in a["piezas"]}[i], reverse=True)
    p1 = next(p for p in a["piezas"] if p["id"] == "pub-1")
    assert p1["ver_url"] == "https://instagram.com/p/1" and p1["formato"] == "historia" and p1["canal_texto"] == "Instagram"
    assert p1["metricas"]["alcance"] == 120 and p1["metricas"]["fuente"] == "api"          # hay api y manual: gana la api
    assert "crudo" not in p1["metricas"] and "errores" not in p1["metricas"]
    assert next(p for p in b["piezas"] if p["id"] == "pub-4")["metricas"]["fuente"] == "manual"
    assert next(p for p in a["piezas"] if p["id"] == "pub-2")["metricas"] is None
    assert c["piezas"] == [] and c["piezas_total"] == 0 and c["primera"] is None
    s = d["sueltas"]
    assert s["id"] == "sueltas" and s["nombre"] == "Sin campaña" and s["piezas_total"] == 2
    assert {p["estado_grupo"] for p in s["piezas"]} == {"no_salio", "prueba"}


def test_campanas_periodo(logueado, mundo):
    mundo["pubs"][1]["creado"], mundo["pubs"][2]["creado"] = hace(1), hace(0, 5)
    d = logueado.get("/admin/metricas/campanas?dias=2").json()
    assert d["periodo"]["dias"] == 2
    assert {p["id"] for c in d["campanas"] + [d["sueltas"]] for p in c["piezas"]} == {"pub-2", "pub-3"}      # solo lo de hace menos de 2 días
    assert logueado.get("/admin/metricas/campanas?mes=2026-13").status_code == 400
    assert logueado.get("/admin/metricas/campanas?dias=0").status_code == 400
    mes = metricas.dt.datetime.now(metricas.ZONA_AR).strftime("%Y-%m")
    assert logueado.get(f"/admin/metricas/campanas?mes={mes}").json()["periodo"]["tipo"] == "mes"


# ---------------- canales ----------------
def test_canales_sin_captura(logueado, mundo):
    d = logueado.get("/admin/metricas/canales").json()
    assert d["actualizado"] is None
    assert [c["clave"] for c in d["canales"]] == ["instagram", "facebook", "youtube", "mail", "sitio", "whatsapp"]
    por = {c["clave"]: c for c in d["canales"]}
    assert por["instagram"]["api"] == "pendiente" and por["facebook"]["api"] == "pendiente"
    assert por["youtube"]["api"] == "pendiente" and "Actualizar" in por["youtube"]["nota_api"]
    assert por["mail"]["api"] == "no_hay" and por["sitio"]["api"] == "no_hay" and por["whatsapp"]["api"] == "no_hay"
    assert por["instagram"]["enlace"] == "https://business.facebook.com/latest/insights/overview"
    assert por["youtube"]["enlace"] == "https://studio.youtube.com/" and por["mail"]["enlace"] == "https://app.myperfit.com/"
    assert por["sitio"]["enlace"] == "https://wordpress.com/stats/day/viviragradecidos.org" and por["sitio"]["texto"] == "Sitio web"
    assert por["whatsapp"]["enlace"] is None
    assert por["instagram"]["ultima"] is None and por["instagram"]["manual"] is None


def test_canales_con_captura(logueado, mundo):
    mundo["filas"] += [
        {"id": "c1", "ambito": "canal", "ref": "instagram", "canal": "instagram", "fuente": "api", "capturado": hace(0, 2), "periodo_desde": "2026-10-10", "periodo_hasta": "2026-11-08",
         "datos": {"seguidores": 3400, "crudo": {}, "errores": ["Falta el permiso instagram_manage_insights en la conexión con Instagram"]}},
        {"id": "c2", "ambito": "canal", "ref": "facebook", "canal": "facebook", "fuente": "api", "capturado": hace(0, 1),
         "datos": {"seguidores": 800, "alcance": 5, "crudo": {}, "errores": []}},
        {"id": "c3", "ambito": "canal", "ref": "youtube", "canal": "youtube", "fuente": "manual", "capturado": hace(0), "periodo_desde": "2026-10-01",
         "periodo_hasta": "2026-10-31", "nota": "de Studio", "por": "franco", "datos": {"vistas": 1000}},
    ]
    d = logueado.get("/admin/metricas/canales").json()
    por = {c["clave"]: c for c in d["canales"]}
    assert por["instagram"]["api"] == "sin_permiso" and "instagram_manage_insights" in por["instagram"]["nota_api"]
    assert por["instagram"]["ultima"]["datos"]["seguidores"] == 3400 and por["instagram"]["ultima"]["periodo_hasta"] == "2026-11-08"
    assert por["facebook"]["api"] == "disponible"
    assert por["youtube"]["manual"]["datos"] == {"vistas": 1000} and por["youtube"]["manual"]["por"] == "franco" and por["youtube"]["manual"]["nota"] == "de Studio"
    assert d["actualizado"] == hace(0, 1)
    # error general (sin ningún número) → «error»
    mundo["filas"].append({"id": "c4", "ambito": "canal", "ref": "facebook", "canal": "facebook", "fuente": "api", "capturado": hace(0),
                           "datos": {"crudo": {}, "errores": ["Meta rechazó page_impressions: (#100) bla"]}})
    por = {c["clave"]: c for c in logueado.get("/admin/metricas/canales").json()["canales"]}
    assert por["facebook"]["api"] == "error" and "page_impressions" in por["facebook"]["nota_api"]


# ---------------- carga a mano ----------------
def test_manual_valida(logueado, mundo):
    def put(**kw):
        cuerpo = {"ambito": "canal", "ref": "instagram", "canal": "instagram", "datos": {"alcance": 10}}
        cuerpo.update(kw)
        return logueado.put("/admin/metricas/manual", json=cuerpo)
    assert put(ambito="resumen").status_code == 400
    assert put(ref="tiktok").status_code == 400
    assert put(datos={}).status_code == 400
    assert put(datos={"inventado": 3}).status_code == 400
    assert put(datos={"alcance": -1}).status_code == 400
    assert put(datos={"alcance": 1.5}).status_code == 400
    assert put(datos={"alcance": "10"}).status_code == 400
    assert put(datos={"alcance": True}).status_code == 400
    assert put(periodo_desde="10/10/2026").status_code == 400
    assert put(periodo_desde="2026-11-02", periodo_hasta="2026-11-01").status_code == 400
    assert put(ambito="pieza", ref="no-existe").status_code == 400
    assert mundo["filas"] == [] and mundo["cambios"] == []


def test_manual_guarda(logueado, mundo):
    r = logueado.put("/admin/metricas/manual", json={"ambito": "canal", "ref": "youtube", "canal": "youtube", "periodo_desde": "2026-10-01",
                                                      "periodo_hasta": "2026-10-31", "datos": {"vistas": 1200, "alcance": 0}, "nota": " de Studio "})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["ambito"] == "canal" and d["ref"] == "youtube" and d["datos"] == {"vistas": 1200, "alcance": 0} and d["por"] == "franco"
    assert d["nota"] == "de Studio" and d["periodo_desde"] == "2026-10-01" and d["id"]
    f = mundo["filas"][0]
    assert f["fuente"] == "manual" and f["por"] == "franco"
    assert mundo["cambios"][0][0] == "franco" and mundo["cambios"][0][2] == "metricas_manual:youtube" and mundo["cambios"][0][3]["a"] == {"vistas": 1200, "alcance": 0}
    # una pieza: el canal sale de la pieza
    r = logueado.put("/admin/metricas/manual", json={"ambito": "pieza", "ref": "pub-3", "datos": {"me_gusta": 4}})
    assert r.status_code == 200 and r.json()["canal"] == "facebook"
    # y se ve en campañas
    p = next(p for c in logueado.get("/admin/metricas/campanas").json()["campanas"] for p in c["piezas"] if p["id"] == "pub-3")
    assert p["metricas"]["me_gusta"] == 4 and p["metricas"]["fuente"] == "manual"


# ---------------- actualizar (Meta simulado) ----------------
def _con_video_youtube(mundo):
    mundo["pubs"].append(pub(20, "youtube", "publicada", 2, modo="privado", id="yt-1"))     # video subido en privado, con id de YouTube


def _meta_simulado(monkeypatch, facebook_sin_permiso=True, youtube_sin_scope=False):
    llamadas = []

    def canal_yt(cfg, dias=28):
        llamadas.append(("canal_yt", dias))
        if youtube_sin_scope:
            return {"seguidores": 90, "vistas": 5000, "crudo": {}, "errores": [metricas_youtube.TEXTO_SIN_SCOPE]}
        return {"seguidores": 90, "vistas": 700, "crudo": {}, "errores": []}

    def video_yt(cfg, video_id, analytics=True):
        llamadas.append(("video_yt", video_id, analytics))
        return {"vistas": 40, "me_gusta": 3, "crudo": {}, "errores": []}

    monkeypatch.setattr(metricas_youtube, "insights_canal_youtube", canal_yt)
    monkeypatch.setattr(metricas_youtube, "insights_video_youtube", video_yt)

    def cuenta_ig(cfg, dias=28):
        llamadas.append(("cuenta_ig", dias))
        return {"alcance": 1200, "seguidores": 3400, "crudo": {"x": 1}, "errores": []}

    def pieza_ig(cfg, media_id, historia=False):
        llamadas.append(("pieza_ig", media_id, historia))
        return {"alcance": 80, "me_gusta": 9, "crudo": {}, "errores": []}

    def pagina_fb(cfg, dias=28):
        llamadas.append(("pagina_fb", dias))
        if facebook_sin_permiso:
            return {"seguidores": 800, "crudo": {}, "errores": [metricas_meta.TEXTO_SIN_PERMISO_FB]}
        return {"seguidores": 800, "crudo": {}, "errores": []}

    def posteo_fb(cfg, post_id):
        llamadas.append(("posteo_fb", post_id))
        return {"vistas": 5, "crudo": {}, "errores": []}

    monkeypatch.setattr(metricas_meta, "insights_cuenta_instagram", cuenta_ig)
    monkeypatch.setattr(metricas_meta, "insights_pieza_instagram", pieza_ig)
    monkeypatch.setattr(metricas_meta, "insights_pagina_facebook", pagina_fb)
    monkeypatch.setattr(metricas_meta, "insights_posteo_facebook", posteo_fb)
    return llamadas


def test_actualizar(logueado, mundo, monkeypatch):
    llamadas = _meta_simulado(monkeypatch)
    _con_video_youtube(mundo)
    mundo["pubs"][0]["resultado"]["formato"] = "cuadrado"                              # pub-1 ya no es una historia vencida
    h = pub(9, "instagram", "publicada", 0, ultimo={"id": "ig-9"}, formato="historia")
    h["procesado_en"] = hace(0, 2)                                                     # una historia de hace 2 h: todavía tiene métricas
    mundo["pubs"].append(h)
    r = logueado.post("/admin/metricas/actualizar")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["instagram"] == {"ok": True, "piezas": 2, "error": None}                 # pub-1 y la historia: publicadas, reales, con id
    assert d["facebook"]["ok"] is False and d["facebook"]["error"].startswith(metricas_meta.TEXTO_SIN_PERMISO_FB) and d["facebook"]["piezas"] == 0
    assert ("pieza_ig", "ig-1", False) in llamadas and ("pieza_ig", "ig-9", True) in llamadas and ("cuenta_ig", 28) in llamadas
    assert not any(x[0] == "posteo_fb" for x in llamadas)                              # sin permiso no se pide pieza por pieza
    filas = mundo["filas"]
    assert {(f["ambito"], f["ref"], f["fuente"]) for f in filas} == {("canal", "instagram", "api"), ("pieza", "pub-1", "api"), ("pieza", "pub-9", "api"), ("canal", "facebook", "api"),
                                                                                  ("canal", "youtube", "api"), ("pieza", "pub-20", "api")}
    assert next(f for f in filas if f["ref"] == "instagram")["periodo_hasta"] and next(f for f in filas if f["ref"] == "instagram")["por"] == "franco"
    # la próxima carga de canales ya sabe que a Facebook le falta un permiso
    por = {c["clave"]: c for c in logueado.get("/admin/metricas/canales").json()["canales"]}
    assert por["facebook"]["api"] == "sin_permiso" and por["instagram"]["api"] == "disponible"
    assert d["youtube"] == {"ok": True, "piezas": 1, "error": None}                    # el video de YouTube (modo privado, publicado, con id)
    assert por["youtube"]["api"] == "disponible" and por["youtube"]["ultima"]["datos"]["seguidores"] == 90
    assert ("video_yt", "yt-1", True) in llamadas and ("canal_yt", 28) in llamadas


def test_actualizar_youtube_sin_scope(logueado, mundo, monkeypatch):
    llamadas = _meta_simulado(monkeypatch, youtube_sin_scope=True)
    _con_video_youtube(mundo)
    r = logueado.post("/admin/metricas/actualizar")
    assert r.status_code == 200, r.text
    y = r.json()["youtube"]
    assert y["ok"] is False and y["error"] == metricas_youtube.TEXTO_SIN_SCOPE and y["piezas"] == 1     # los videos igual se guardan
    assert ("video_yt", "yt-1", False) in llamadas                                    # sin permiso no se piden las estadísticas por video
    por = {c["clave"]: c for c in logueado.get("/admin/metricas/canales").json()["canales"]}
    assert por["youtube"]["api"] == "sin_permiso" and "autorizar_youtube.py" in por["youtube"]["nota_api"]
    assert por["youtube"]["ultima"]["datos"]["vistas"] == 5000


def test_actualizar_youtube_sin_token(logueado, mundo, monkeypatch):
    _meta_simulado(monkeypatch)
    monkeypatch.setattr(Cfg, "yt_token_json", "")
    r = logueado.post("/admin/metricas/actualizar")
    assert r.json()["youtube"] == {"ok": False, "piezas": 0, "error": "Falta la conexión con YouTube en el servidor."}


def test_actualizar_nunca_500(logueado, mundo, monkeypatch):
    def rota(cfg, dias=28):
        raise ValueError("reventó " + TOKEN_IG)
    monkeypatch.setattr(metricas_meta, "insights_cuenta_instagram", rota)
    monkeypatch.setattr(metricas_meta, "insights_pagina_facebook", lambda cfg, dias=28: {"seguidores": 1, "crudo": {}, "errores": []})
    monkeypatch.setattr(metricas_meta, "insights_posteo_facebook", lambda cfg, pid: {"vistas": 1, "crudo": {}, "errores": []})
    r = logueado.post("/admin/metricas/actualizar")
    assert r.status_code == 200
    assert r.json()["instagram"]["ok"] is False and TOKEN_IG not in r.json()["instagram"]["error"]
    assert r.json()["facebook"]["ok"] is True


def test_capturar_si_toca(mundo, monkeypatch):
    llamadas = _meta_simulado(monkeypatch, facebook_sin_permiso=False)
    assert metricas.capturar_si_toca(Cfg())["instagram"]["ok"] is True
    assert mundo["config"]["metricas_ultima_captura"]
    n = len(llamadas)
    assert metricas.capturar_si_toca(Cfg()) is None and len(llamadas) == n           # pasó menos de 1 hora
    mundo["config"]["metricas_ultima_captura"] = hace(0, 2)
    assert metricas.capturar_si_toca(Cfg()) is not None
    # nunca lanza
    monkeypatch.setattr(metricas, "capturar", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    mundo["config"]["metricas_ultima_captura"] = hace(0, 5)
    assert metricas.capturar_si_toca(Cfg()) is None


def test_la_cola_no_repite_piezas_recientes(mundo, monkeypatch):
    llamadas = _meta_simulado(monkeypatch, facebook_sin_permiso=False)
    mundo["pubs"][0]["resultado"]["formato"] = "cuadrado"                               # ya no es historia
    mundo["filas"].append({"id": "p", "ambito": "pieza", "ref": "pub-1", "canal": "instagram", "fuente": "api", "capturado": hace(0, 3), "datos": {"alcance": 1}})
    metricas.capturar(Cfg(), por="cola", todas=False)
    assert not any(x[0] == "pieza_ig" for x in llamadas)                                # capturada hace 3 h: se saltea
    metricas.capturar(Cfg(), por="api", todas=True)
    assert any(x[0] == "pieza_ig" for x in llamadas)


# ---------------- metricas_meta (HTTP simulado) ----------------
def _sim_http(monkeypatch, respuestas):
    visto = []

    def http(url, method="GET", headers=None, data=None):
        visto.append(url)
        for clave, resp in respuestas:
            if clave in url:
                return resp(url) if callable(resp) else resp
        return None, {"error": {"code": 100, "message": "no simulado"}}
    monkeypatch.setattr(metricas_meta, "_http", http)
    return visto


def test_meta_cuenta_instagram(monkeypatch):
    visto = _sim_http(monkeypatch, [
        ("/insights", ({"data": [{"name": "reach", "total_value": {"value": 1200}}, {"name": "views", "total_value": {"value": 5000}},
                                 {"name": "total_interactions", "total_value": {"value": 77}}, {"name": "accounts_engaged", "total_value": {"value": 40}}]}, None)),
        ("fields=followers_count", ({"followers_count": 3400, "media_count": 90}, None)),
    ])
    r = metricas_meta.insights_cuenta_instagram(Cfg(), 28)
    assert (r["alcance"], r["vistas"], r["interacciones"], r["seguidores"]) == (1200, 5000, 77, 3400)
    assert r["errores"] == [] and r["crudo"]["insights"]["accounts_engaged"] == {"value": 40}
    assert "me_gusta" not in r                                                         # lo que no dio la plataforma no está
    ins = next(u for u in visto if "/insights" in u)
    assert "metric=reach%2Cviews%2Caccounts_engaged%2Ctotal_interactions%2Cfollows_and_unfollows" in ins and "metric_type=total_value" in ins and "period=day" in ins
    assert ins.startswith("https://graph.instagram.com/v21.0/17841/insights")


def test_meta_rechazo_de_la_lista_reintenta_con_reach(monkeypatch):
    def insights(url):
        if "metric=reach&" in url or url.endswith("metric=reach") or "metric=reach" in url.split("&")[0].split("?")[-1] and "%2C" not in url:
            return {"data": [{"name": "reach", "total_value": {"value": 7}}]}, None
        return None, {"error": {"code": 100, "message": "(#100) metric views not supported"}}
    _sim_http(monkeypatch, [("/insights", insights), ("fields=followers_count", ({"followers_count": 1}, None))])
    r = metricas_meta.insights_cuenta_instagram(Cfg())
    assert r["alcance"] == 7 and "vistas" not in r
    assert any("Meta rechazó" in e and "views" in e for e in r["errores"])


@pytest.mark.parametrize("error", [{"code": 10, "message": "x"}, {"code": 200, "message": "x"}, {"code": 190, "message": "x"},
                                   {"code": 1, "message": "Requires instagram_manage_insights permission"}])
def test_meta_permiso_ig(monkeypatch, error):
    _sim_http(monkeypatch, [("/insights", (None, {"error": error})), ("fields=followers_count", ({"followers_count": 5}, None))])
    r = metricas_meta.insights_cuenta_instagram(Cfg())
    assert any(e.startswith(metricas_meta.TEXTO_SIN_PERMISO_IG) for e in r["errores"]) and r["seguidores"] == 5
    assert "Falta el permiso instagram_manage_insights en la conexión con Instagram" == metricas_meta.TEXTO_SIN_PERMISO_IG


def test_meta_el_token_no_se_filtra(monkeypatch):
    _sim_http(monkeypatch, [("/insights", (None, {"error": {"code": 100, "message": f"bad token {TOKEN_IG} y {TOKEN_FB}"}})),
                            ("fields=", (None, {"error": {"code": 100, "message": f"otra vez {TOKEN_IG}"}}))])
    for r in (metricas_meta.insights_cuenta_instagram(Cfg()), metricas_meta.insights_pieza_instagram(Cfg(), "m1"),
              metricas_meta.insights_pagina_facebook(Cfg()), metricas_meta.insights_posteo_facebook(Cfg(), "p1")):
        assert TOKEN_IG not in json.dumps(r) and TOKEN_FB not in json.dumps(r)
        assert r["errores"]


def test_meta_pieza_instagram_y_historia_vencida(monkeypatch):
    visto = _sim_http(monkeypatch, [
        ("/insights", ({"data": [{"name": "reach", "values": [{"value": 60}]}, {"name": "saved", "values": [{"value": 3}]},
                                 {"name": "shares", "values": [{"value": 2}]}, {"name": "total_interactions", "values": [{"value": 20}]}]}, None)),
        ("fields=like_count", ({"like_count": 14, "comments_count": 2, "media_type": "IMAGE", "permalink": "https://i/p"}, None)),
    ])
    r = metricas_meta.insights_pieza_instagram(Cfg(), "m1")
    assert (r["alcance"], r["guardados"], r["compartidos"], r["interacciones"], r["me_gusta"], r["comentarios"]) == (60, 3, 2, 20, 14, 2)
    assert "views" not in r["crudo"]["insights"] and "metric=reach%2Cviews%2Csaved%2Cshares%2Ctotal_interactions" in next(u for u in visto if "/insights" in u)
    # historia vencida
    _sim_http(monkeypatch, [("/insights", (None, {"error": {"code": 100, "message": "Media is no longer available"}})),
                            ("fields=media_type", ({"media_type": "IMAGE"}, None))])
    r = metricas_meta.insights_pieza_instagram(Cfg(), "h1", historia=True)
    assert any("24 horas" in e for e in r["errores"]) and "alcance" not in r


def test_meta_facebook(monkeypatch):
    def pagina(url):
        n = {"page_media_view": 100, "page_post_engagements": 10, "page_views_total": 7, "page_daily_follows": 2}
        return {"data": [{"name": k, "values": [{"value": v}, {"value": v}]} for k, v in n.items()]}, None
    _sim_http(monkeypatch, [("/999/insights", pagina), ("999?fields=followers_count", ({"followers_count": 800, "fan_count": 790}, None))])
    r = metricas_meta.insights_pagina_facebook(Cfg(), 28)
    assert (r["seguidores"], r["vistas"], r["interacciones"], r["seguidores_nuevos"]) == (800, 200, 20, 4)          # suma de los valores diarios
    assert r["crudo"]["insights"]["page_views_total"] == 14 and "alcance" not in r
    _sim_http(monkeypatch, [("/insights", ({"data": [{"name": "post_media_view", "values": [{"value": 90}]}, {"name": "post_total_media_view_unique", "values": [{"value": 70}]},
                                                      {"name": "post_clicks", "values": [{"value": 6}]},
                                                      {"name": "post_reactions_by_type_total", "values": [{"value": {"like": 3}}]}]}, None)),
                            ("fields=shares", ({"shares": {"count": 2}, "reactions": {"summary": {"total_count": 11}}, "comments": {"summary": {"total_count": 4}}}, None))])
    r = metricas_meta.insights_posteo_facebook(Cfg(), "999_1")
    assert (r["vistas"], r["alcance"], r["clics"], r["me_gusta"], r["comentarios"], r["compartidos"]) == (90, 70, 6, 11, 4, 2)
    assert r["crudo"]["insights"]["post_reactions_by_type_total"] == {"like": 3}
    _sim_http(monkeypatch, [("/insights", (None, {"error": {"code": 10, "message": "(#10) permission denied"}})), ("fields=shares", (None, {"error": {"code": 10, "message": "x"}}))])
    assert any(e.startswith(metricas_meta.TEXTO_SIN_PERMISO_FB) for e in metricas_meta.insights_posteo_facebook(Cfg(), "p")["errores"])


# ---------------- resumen con IA ----------------
class _ClienteFalso:
    def __init__(self, contenido):
        self.pedidos = []
        self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=self._create))
        self.contenido = contenido

    def _create(self, **kw):
        self.pedidos.append(kw)
        msg = types.SimpleNamespace(content=self.contenido)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)],
                                     usage=types.SimpleNamespace(prompt_tokens=900, completion_tokens=200, prompt_tokens_details=None))


def test_resumen(logueado, mundo, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-prueba")
    cl = _ClienteFalso(json.dumps({"texto": "A la campaña le fue bien.\n\n- Probá más reels.", "fuentes": ["inventada"], "falto": ["YouTube: sin datos"], "comparado_con": "Inventada"}))
    monkeypatch.setattr(nucleo, "_get_client", lambda: cl)
    usos = []
    monkeypatch.setattr(nucleo, "_registrar_uso", lambda modelo, usage, que: usos.append((modelo, que, nucleo.USUARIO.get(), usage.prompt_tokens)))
    mundo["filas"].append({"id": "x1", "ambito": "pieza", "ref": "pub-1", "canal": "instagram", "fuente": "api", "capturado": hace(1), "datos": {"alcance": 120, "me_gusta": 14}})
    # B (Polarizaciones, del mismo dueño) tiene una `ultima` anterior a la de A: es la «campaña anterior»
    assert logueado.get("/admin/metricas/resumen/A").json() is None
    r = logueado.post("/admin/metricas/resumen", json={"ref": "A", "dias": 90})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["ref"] == "A" and d["nombre"] == "Lo común nos convoca" and d["texto"].startswith("A la campaña le fue bien")
    assert d["comparado_con"] == "Polarizaciones"                                    # calculado de los datos, no lo que dijo el modelo
    assert d["fuentes"] == [f"Instagram (desde la plataforma, {metricas_asesor._dia(hace(1))})"]
    assert "YouTube: sin datos" in d["falto"] and any("Facebook: sin datos" in f for f in d["falto"])
    assert d["modelo"] == nucleo._modelo() and d["capturado"]
    # el pedido lleva las piezas, sus métricas con la fuente y la guía recortada
    sistema = cl.pedidos[0]["messages"][0]["content"]
    assert cl.pedidos[0]["messages"][-1] == {"role": "user", "content": "¿Cómo le fue a la campaña Lo común nos convoca?"}
    pedido = sistema
    assert "Pieza 1" in pedido and "alcance 120" in pedido and "desde la plataforma" in pedido and "sin métricas" in pedido
    assert "Los tres errores" in pedido and "## Instagram" in pedido and "## Facebook" in pedido and "## YouTube" not in pedido
    assert "Campaña anterior del mismo dueño: ### Polarizaciones" in pedido and "CANALES" in pedido
    # uso registrado como auxiliar, a nombre de quien lo pidió
    assert usos == [(nucleo._modelo(), "auxiliar", "franco", 900)]
    # la fila quedó guardada y el GET la devuelve
    f = [x for x in mundo["filas"] if x["ambito"] == "resumen"]
    assert len(f) == 1 and f[0]["ref"] == "A" and f[0]["fuente"] == "ia" and f[0]["canal"] is None and f[0]["datos"]["texto"].startswith("A la campaña")
    assert logueado.get("/admin/metricas/resumen/A").json()["texto"] == d["texto"]
    # sin ninguna métrica igual responde
    r = logueado.post("/admin/metricas/resumen", json={"ref": "sueltas"})
    assert r.status_code == 200 and r.json()["fuentes"] == [] and r.json()["comparado_con"] is None
    assert "ninguna" in cl.pedidos[1]["messages"][0]["content"]


def test_resumen_errores(logueado, mundo, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    r = logueado.post("/admin/metricas/resumen", json={"ref": "A"})
    assert r.status_code == 503 and r.json()["detail"] == "El resumen con IA no está disponible ahora"
    monkeypatch.setenv("OPENAI_API_KEY", "sk-prueba")
    monkeypatch.setattr(nucleo, "_get_client", lambda: _ClienteFalso("texto sin json"))
    monkeypatch.setattr(nucleo, "_registrar_uso", lambda *a: None)
    assert logueado.post("/admin/metricas/resumen", json={"ref": "no-existe"}).status_code == 404
    assert logueado.post("/admin/metricas/resumen", json={"ref": "A", "dias": 0}).status_code == 422
    assert logueado.post("/admin/metricas/resumen", json={"ref": "A"}).json()["texto"] == "texto sin json"     # sin JSON: se usa el texto tal cual


def test_tramos_de_la_guia():
    g = metricas_asesor.tramos_guia(["instagram"])
    assert "## Instagram" in g and "## Facebook" not in g and "Los tres errores" in g and "## Resumen" in g
    assert "Reel." in g


# ---------------- asesor de campañas ----------------
def _asesor_listo(monkeypatch, contenido=None):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-prueba")
    cl = _ClienteFalso(contenido or json.dumps({"texto": "Esta semana se movió *Lo común nos convoca*.", "fuentes": ["inventada"], "falto": ["Cargar YouTube"]}))
    monkeypatch.setattr(nucleo, "_get_client", lambda: cl)
    usos = []
    monkeypatch.setattr(nucleo, "_registrar_uso", lambda modelo, usage, que: usos.append((que, nucleo.USUARIO.get())))
    return cl, usos


def test_asesor_conversa(logueado, mundo, monkeypatch):
    cl, usos = _asesor_listo(monkeypatch)
    mundo["filas"].append({"id": "x1", "ambito": "pieza", "ref": "pub-1", "canal": "instagram", "fuente": "api", "capturado": hace(1), "datos": {"alcance": 120}})
    mundo["filas"].append({"id": "c1", "ambito": "canal", "ref": "instagram", "canal": "instagram", "fuente": "api", "capturado": hace(0, 2),
                           "periodo_desde": "2026-10-10", "periodo_hasta": "2026-11-08", "datos": {"seguidores": 3400, "crudo": {}, "errores": []}})
    msgs = [{"rol": "usuario", "texto": "¿Cómo nos fue?"}, {"rol": "asesor", "texto": "Bien."}, {"rol": "usuario", "texto": "¿Qué canal conviene?"}]
    r = logueado.post("/admin/metricas/asesor", json={"mensajes": msgs, "dias": 90})
    assert r.status_code == 200, r.text
    d = r.json()
    assert set(d) == {"texto", "fuentes", "falto"} and d["texto"].startswith("Esta semana")
    assert d["fuentes"] == [f"Instagram (desde la plataforma, {metricas_asesor._dia(hace(1))})"] and "Cargar YouTube" in d["falto"]
    enviados = cl.pedidos[0]["messages"]
    assert [m["role"] for m in enviados] == ["system", "user", "assistant", "user"] and enviados[-1]["content"] == "¿Qué canal conviene?"
    ctx = enviados[0]["content"]
    assert "Lo común nos convoca" in ctx and "alcance 120" in ctx and "seguidores 3400" in ctx and "PIEZAS SIN CAMPAÑA" in ctx and "## Instagram" in ctx
    assert "Hoy es" in ctx and "Los tres errores" in ctx
    assert usos == [("auxiliar", "franco")]
    assert [f for f in mundo["filas"] if f["ambito"] == "resumen"] == []                  # la conversación no se guarda
    # tope de 12 mensajes
    muchos = [{"rol": "usuario" if i % 2 == 0 else "asesor", "texto": f"m{i}"} for i in range(30)] + [{"rol": "usuario", "texto": "última"}]
    assert logueado.post("/admin/metricas/asesor", json={"mensajes": muchos}).status_code == 200
    assert len(cl.pedidos[1]["messages"]) == 1 + 12


def test_asesor_errores(logueado, mundo, monkeypatch):
    assert logueado.post("/admin/metricas/asesor", json={"mensajes": []}).status_code == 422
    assert logueado.post("/admin/metricas/asesor", json={"mensajes": [{"rol": "otro", "texto": "x"}]}).status_code == 422
    monkeypatch.setenv("OPENAI_API_KEY", "")
    r = logueado.post("/admin/metricas/asesor", json={"mensajes": [{"rol": "usuario", "texto": "hola"}]})
    assert r.status_code == 503 and r.json()["detail"] == "El resumen con IA no está disponible ahora"
    _asesor_listo(monkeypatch)
    assert logueado.post("/admin/metricas/asesor", json={"mensajes": [{"rol": "usuario", "texto": "hola"}, {"rol": "asesor", "texto": "chau"}]}).status_code == 400
    assert logueado.get("/admin/metricas/asesor/apertura?dias=0").status_code == 422


def test_apertura_una_vez_por_dia(logueado, mundo, monkeypatch):
    cl, usos = _asesor_listo(monkeypatch)
    r = logueado.get("/admin/metricas/asesor/apertura")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["nuevo"] is True and d["texto"].startswith("Esta semana") and d["capturado"]
    assert len(cl.pedidos) == 1 and "últimos 7 días" in cl.pedidos[0]["messages"][-1]["content"]
    f = [x for x in mundo["filas"] if x["ambito"] == "resumen"]
    assert len(f) == 1 and f[0]["ref"] == "apertura" and f[0]["fuente"] == "ia"
    # segunda vez, mismo día: sin modelo
    d2 = logueado.get("/admin/metricas/asesor/apertura").json()
    assert d2["nuevo"] is False and d2["texto"] == d["texto"] and len(cl.pedidos) == 1 and len(usos) == 1
    # si la guardada es de ayer, genera una nueva
    f[0]["capturado"] = hace(1, 1)
    d3 = logueado.get("/admin/metricas/asesor/apertura").json()
    assert d3["nuevo"] is True and len(cl.pedidos) == 2


# ---------------- permisos ----------------
def test_solo_admins(cliente, mundo):
    rutas = [("get", "/admin/metricas/campanas"), ("get", "/admin/metricas/canales"), ("post", "/admin/metricas/actualizar"),
             ("put", "/admin/metricas/manual"), ("get", "/admin/metricas/resumen/A"), ("post", "/admin/metricas/resumen"),
             ("get", "/admin/metricas/asesor/apertura"), ("post", "/admin/metricas/asesor")]
    for m, ruta in rutas:
        assert getattr(cliente, m)(ruta).status_code == 401
    cliente.post("/login", json={"usuario": "lizzie", "clave": "clave-lizzie"})
    for m, ruta in rutas:
        kw = {"json": {"ambito": "canal", "ref": "instagram", "datos": {"alcance": 1}}} if m == "put" else ({"json": {"mensajes": [{"rol": "usuario", "texto": "hola"}]}} if ruta.endswith("/asesor") else ({"json": {"ref": "A"}} if m == "post" else {}))
        assert getattr(cliente, m)(ruta, **kw).status_code == 403, ruta
    assert mundo["filas"] == []


# ---------------- Métricas v2 (8/11, Franco) ----------------
def test_frase_del_dia_es_una_campana_virtual(logueado, mundo, monkeypatch):
    for i, usuario in enumerate(("frase_del_dia", "frase_del_dia", "cola")):
        p = pub(30 + i, "instagram", "publicada", 1 + i, formato="historia")
        p["usuario"] = usuario
        mundo["pubs"].append(p)
    en_proyecto = pub(33, "instagram", "publicada", 2)               # de la Frase del día, pero ya está en una campaña: se queda ahí
    en_proyecto["usuario"] = "frase_del_dia"
    mundo["pubs"].append(en_proyecto)
    antes = db.piezas_de_proyectos()
    monkeypatch.setattr(db, "piezas_de_proyectos", lambda: [dict(i) for i in antes] + [{"proyecto_id": "A", "item_id": "pub-33"}])
    d = logueado.get("/admin/metricas/campanas").json()
    assert [c["id"] for c in d["campanas"]] == ["A", "B", "C", "frase_del_dia"]      # después de las reales; «Sin campaña» va aparte
    f = d["campanas"][-1]
    assert f["nombre"] == "Frase del día (automática)" and f["emoji"] == "📅" and f["dueno"] is None
    assert f["piezas_total"] == 3 and f["por_estado"]["publicada"] == 3 and f["por_canal"]["instagram"]["publicada"] == 3
    assert {p["id"] for p in f["piezas"]} == {"pub-30", "pub-31", "pub-32"}
    assert "pub-33" in {p["id"] for p in d["campanas"][0]["piezas"]}
    assert "pub-30" not in {p["id"] for p in d["sueltas"]["piezas"]}
    assert d["totales"]["publicada"] == 5                              # pub-1 + 3 de la Frase + pub-33


def test_frase_del_dia_sin_piezas_no_aparece(logueado, mundo):
    assert "frase_del_dia" not in [c["id"] for c in logueado.get("/admin/metricas/campanas").json()["campanas"]]


def test_excluir_usuarios(logueado, mundo):
    p = pub(40, "instagram", "publicada", 1)
    p["usuario"] = "desarrollo"
    q = pub(41, "instagram", "pendiente", 1)
    q["usuario"] = "frase_del_dia"
    mundo["pubs"] += [p, q]
    mundo["config"]["metricas_excluir_usuarios"] = ["desarrollo", "frase_del_dia"]
    d = logueado.get("/admin/metricas/campanas").json()
    todas = {x["id"] for c in d["campanas"] + [d["sueltas"]] for x in c["piezas"]}
    assert "pub-40" not in todas and "pub-41" not in todas
    assert "frase_del_dia" not in [c["id"] for c in d["campanas"]]
    assert d["totales"]["piezas"] == 3                                  # igual que sin esas piezas
    mundo["config"]["metricas_excluir_usuarios"] = []
    d = logueado.get("/admin/metricas/campanas").json()
    assert {x["id"] for c in d["campanas"] + [d["sueltas"]] for x in c["piezas"]} >= {"pub-40", "pub-41"}
    # los canales no se ven afectados
    mundo["config"]["metricas_excluir_usuarios"] = ["pato"]
    assert [c["clave"] for c in logueado.get("/admin/metricas/canales").json()["canales"]][0] == "instagram"


def test_totales_sin_borradores_ni_pruebas(logueado, mundo):
    d = logueado.get("/admin/metricas/campanas").json()
    t = d["totales"]
    assert t["piezas"] == t["publicada"] + t["programada"] + t["en_aprobacion"] == 3
    assert t["borrador"] == 1 and t["prueba"] == 2                      # se informan aparte
    b = d["campanas"][1]
    assert b["nombre"] == "Polarizaciones" and b["por_estado"]["borrador"] == 1 and b["piezas_total"] == 2


def test_cuando():
    ahora = dt.datetime(2026, 11, 8, 15, 0, tzinfo=metricas.ZONA_AR)
    assert metricas_asesor._cuando("2026-11-09T13:00:00Z", ahora) == "mañana 10:00 (9/11)"
    assert metricas_asesor._cuando("2026-11-08T21:30:00Z", ahora) == "hoy 18:30 (8/11)"
    assert metricas_asesor._cuando("2026-11-07T12:00:00Z", ahora) == "ayer 09:00 (7/11)"
    assert metricas_asesor._cuando("2026-11-12T13:00:00Z", ahora) == "12/11 10:00"
    assert metricas_asesor._cuando(None, ahora) == "sin fecha"


def test_asesor_nombra_las_piezas(logueado, mundo, monkeypatch):
    cl, usos = _asesor_listo(monkeypatch)
    manana = dt.datetime.now(metricas.ZONA_AR).replace(hour=10, minute=0, second=0, microsecond=0) + dt.timedelta(days=1)
    mundo["pubs"][1]["fecha_programada"] = iso(manana.astimezone(dt.timezone.utc))     # pub-2: programada, de pato
    mundo["pubs"][1]["titulo"] = "Mañana sale"
    mundo["pubs"][2]["titulo"] = "Espera aprobación"
    f = pub(50, "instagram", "publicada", 0, formato="historia")
    f["usuario"], f["titulo"] = "frase_del_dia", "Frase de hoy"
    mundo["pubs"].append(f)
    r = logueado.get("/admin/metricas/asesor/apertura")
    assert r.status_code == 200, r.text
    ped = cl.pedidos[0]
    ctx = ped["messages"][0]["content"]
    assert "Programadas:" in ctx and "«Mañana sale» (Instagram, mañana 10:00 (" in ctx and ", de pato)" in ctx
    assert "En aprobación:" in ctx and "«Espera aprobación» (Facebook" in ctx
    assert "Publicadas en los últimos 7 días:" in ctx and "«Pieza 1» (Instagram" in ctx
    assert "### Frase del día (automática)" in ctx and "«Frase de hoy»" in ctx
    assert "aparte: 1 borrador" in ctx and "Pieza 4" not in ctx                         # el borrador no se nombra, solo se cuenta
    assert "Máximo 350 palabras" in ctx and "hasta 350 palabras" in ctx
    assert "NOMBRÁ LAS PIEZAS" in ctx and "Frase del día (automática)" in metricas_asesor.SISTEMA
    pregunta = ped["messages"][-1]["content"]
    assert "NOMBRANDO las piezas" in pregunta and "últimos 7 días" in pregunta and "quedan programadas" in pregunta and "350" in pregunta
    # las preguntas libres también ven las piezas pero con el límite normal
    logueado.post("/admin/metricas/asesor", json={"mensajes": [{"rol": "usuario", "texto": "¿Qué sale mañana?"}]})
    libre = cl.pedidos[1]["messages"][0]["content"]
    assert "«Mañana sale»" in libre and "Máximo 250 palabras" in libre and "hasta 250 palabras" in libre


def test_resumen_de_la_frase_del_dia(logueado, mundo, monkeypatch):
    cl, usos = _asesor_listo(monkeypatch)
    f = pub(51, "instagram", "publicada", 1, formato="historia")
    f["usuario"], f["titulo"] = "frase_del_dia", "Frase de ayer"
    mundo["pubs"].append(f)
    assert logueado.get("/admin/metricas/resumen/frase_del_dia").json() is None
    r = logueado.post("/admin/metricas/resumen", json={"ref": "frase_del_dia"})
    assert r.status_code == 200, r.text
    assert r.json()["ref"] == "frase_del_dia" and r.json()["nombre"] == "Frase del día (automática)" and r.json()["comparado_con"] is None
    assert "CAMPAÑA DE LA PREGUNTA: Frase del día (automática)" in cl.pedidos[0]["messages"][0]["content"]
    assert logueado.get("/admin/metricas/resumen/frase_del_dia").json()["texto"]
