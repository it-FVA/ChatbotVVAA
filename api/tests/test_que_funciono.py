"""(8/11, Beto) Paso 3 del chat con criterio de marketing: la herramienta que_funciono. metricas.que_funciono / texto_para_el_modelo con
un `db` simulado (dos campañas, números de la plataforma y anotados a mano, una pieza de un usuario excluido) y la herramienta en el
chat con el modelo simulado. Sin red, sin claves."""
import datetime as dt, json
from types import SimpleNamespace

import pytest

import db
import metricas
import nucleo
import api.chat as chat

AHORA = dt.datetime.now(dt.timezone.utc)


def hace(dias):
    return (AHORA - dt.timedelta(days=dias)).strftime("%Y-%m-%dT%H:%M:%SZ")


def pub(i, canal, dias, usuario="pato", estado="publicada", **res):
    return {"id": f"p{i}", "creado": hace(dias + 1), "usuario": usuario, "canal": canal, "modo": "real", "titulo": f"Pieza {i}", "estado": estado,
            "fecha_programada": None, "procesado_en": hace(dias) if estado == "publicada" else None, "resultado": res, "imagen_url": None}


def fila(ref, fuente, datos, ambito="pieza", canal="instagram", dias=1, **extra):
    return dict({"ambito": ambito, "ref": ref, "canal": canal, "fuente": fuente, "capturado": hace(dias), "datos": datos}, **extra)


class Cfg:
    configurado = {"instagram": True, "facebook": True, "youtube": True, "mail": True, "wordpress": True, "whatsapp": True}

    def modo(self, c):
        return "real"


@pytest.fixture
def mundo(monkeypatch):
    pubs = [
        pub(1, "instagram", 3, formato="reel"),
        pub(2, "instagram", 5, formato="historia"),
        pub(3, "facebook", 4),
        pub(4, "instagram", 6, formato="carrusel"),                      # publicada sin números
        pub(5, "instagram", 2, usuario="interno", formato="reel"),         # de un usuario excluido
        pub(6, "instagram", 1, estado="simulada", formato="reel"),          # prueba: no cuenta
        pub(7, "youtube", 8, video_url="https://x/v.mp4"),
    ]
    items = [{"proyecto_id": "A", "item_id": "p1"}, {"proyecto_id": "A", "item_id": "p2"}, {"proyecto_id": "A", "item_id": "p4"},
             {"proyecto_id": "B", "item_id": "p3"}, {"proyecto_id": "B", "item_id": "p7"}, {"proyecto_id": "B", "item_id": "p5"}]
    proyectos = {"A": {"id": "A", "nombre": "Lo común nos convoca", "dueno": "pato", "creado": hace(50)},
                 "B": {"id": "B", "nombre": "Polarizaciones", "dueno": "pato", "creado": hace(60)}}
    filas = [
        fila("p1", "api", {"alcance": 2100, "me_gusta": 90}),
        fila("p1", "manual", {"alcance": 5}),                              # la de la plataforma gana
        fila("p2", "manual", {"alcance": 300}),
        fila("p3", "manual", {"vistas": 700, "interacciones": 20}, canal="facebook"),
        fila("p5", "api", {"alcance": 99999}),                             # excluida
        fila("p7", "api", {"vistas": 1500}, canal="youtube"),
        fila("instagram", "api", {"alcance": 8000, "seguidores": 4100}, ambito="canal", periodo_desde=None),
        fila("facebook", "manual", {"alcance": 900}, ambito="canal", canal="facebook", periodo_desde=hace(30), periodo_hasta=hace(2)),
    ]

    def ultimas(ambito, refs=None, fuente=None):
        out = {}
        for f in sorted(filas, key=lambda x: x["capturado"], reverse=True):
            if f["ambito"] != ambito or (refs is not None and f["ref"] not in [str(r) for r in refs]) or (fuente and f["fuente"] != fuente):
                continue
            out.setdefault((f["ref"], f["fuente"]), f)
        return out

    st = {"config": {"metricas_excluir_usuarios": ["interno"]}}
    monkeypatch.setattr(db, "ultimas_metricas", ultimas)
    monkeypatch.setattr(db, "publicaciones_para_metricas", lambda desde: list(pubs))
    monkeypatch.setattr(db, "piezas_de_proyectos", lambda: [dict(i) for i in items])
    monkeypatch.setattr(db.proyectos, "proyectos_por_ids", lambda ids: [proyectos[i] for i in sorted(ids) if i in proyectos])
    monkeypatch.setattr(db, "obtener_config", lambda clave, defecto=None: st["config"].get(clave, defecto))
    return st


def test_mejores_ordenadas_con_fuente_y_sin_excluidos(mundo):
    d = metricas.que_funciono(Cfg())
    assert d["periodo"] == "últimos 90 días"
    # alcance primero (2100, 300), después las que solo tienen vistas (1500 YouTube, 700 Facebook)
    assert [m["titulo"] for m in d["mejores"]] == ["Pieza 1", "Pieza 2", "Pieza 7", "Pieza 3"]
    p1 = d["mejores"][0]
    assert p1["metricas"]["alcance"] == 2100 and p1["fuente"] == "desde la plataforma" and p1["campana"] == "Lo común nos convoca"
    assert d["mejores"][1]["fuente"] == "anotado a mano" and p1["formato"] == "reel"
    assert "Pieza 5" not in json.dumps(d) and "Pieza 6" not in [m["titulo"] for m in d["mejores"]]
    json.dumps(d)                                                       # serializable
    assert [c["nombre"] for c in d["campanas"]] == ["Lo común nos convoca", "Polarizaciones"]
    assert d["campanas"][0]["piezas_hechas"] == 3 and d["campanas"][1]["piezas_hechas"] == 2        # la excluida no cuenta
    assert len(metricas.que_funciono(Cfg(), tope=2)["mejores"]) == 2


def test_filtros(mundo):
    assert [m["titulo"] for m in metricas.que_funciono(Cfg(), canal="facebook")["mejores"]] == ["Pieza 3"]
    assert [m["titulo"] for m in metricas.que_funciono(Cfg(), formato="historia")["mejores"]] == ["Pieza 2"]
    d = metricas.que_funciono(Cfg(), campana="polariz")
    assert [m["titulo"] for m in d["mejores"]] == ["Pieza 7", "Pieza 3"] and [c["nombre"] for c in d["campanas"]] == ["Polarizaciones"]
    vacio = metricas.que_funciono(Cfg(), formato="carrusel")             # hay una publicada pero sin números
    assert vacio["mejores"] == [] and any("Instagram: ninguna pieza publicada tiene números" in s for s in vacio["sin_datos"])
    nada = metricas.que_funciono(Cfg(), canal="instagram", dias=1)
    assert nada["mejores"] == [] and any("No hay piezas publicadas" in s for s in nada["sin_datos"])


def test_sin_datos_dice_que_falta(mundo):
    d = metricas.que_funciono(Cfg())
    assert "1 pieza publicada sin números" in d["sin_datos"]           # el carrusel de Instagram
    assert any(s.startswith("YouTube: sin números de la cuenta") for s in d["sin_datos"])
    assert not any("WhatsApp" in m["canal"] for m in d["mejores"])


def test_canales_con_fuente_y_periodo(mundo):
    d = metricas.que_funciono(Cfg())
    ig = next(c for c in d["canales"] if c["canal"].startswith("Instagram"))
    assert ig["alcance"] == 8000 and ig["seguidores"] == 4100 and ig["fuente"] == "desde la plataforma" and ig["periodo"] == "últimos 28 días"
    fb = next(c for c in d["canales"] if c["canal"].startswith("Facebook"))
    assert fb["fuente"] == "anotado a mano" and " al " in fb["periodo"]


def test_texto_para_el_modelo(mundo):
    d = metricas.que_funciono(Cfg())
    t = metricas.texto_para_el_modelo(d)
    assert len(t) <= 1500 and "últimos 90 días" in t and "desde la plataforma" in t and "anotado a mano" in t
    assert "alcance 2100" in t and "Pieza 1" in t and "Falta:" in t
    corto = metricas.texto_para_el_modelo(d, tope=400)
    assert len(corto) <= 400 and "(recortado)" in corto
    # muchas piezas largas: igual respeta el tope
    d["mejores"] = d["mejores"] * 20
    assert len(metricas.texto_para_el_modelo(d)) <= 1500


def test_texto_sin_numeros_recomienda_la_guia(mundo):
    t = metricas.texto_para_el_modelo(metricas.que_funciono(Cfg(), canal="whatsapp"))
    assert "No hay números" in t and "guía de canales" in t and "alcance" not in t


# ---------------- la herramienta en el chat ----------------
def test_herramienta_registrada_y_consigna():
    tool = next(t for t in nucleo.TOOLS if t["function"]["name"] == "que_funciono")
    props = tool["function"]["parameters"]["properties"]
    assert set(props) == {"canal", "formato", "campana", "dias"} and "required" not in tool["function"]["parameters"]
    msg = nucleo.system_msg()
    assert "═══ QUÉ FUNCIONÓ (Métricas) ═══" in msg and "que_funciono" in msg and "nunca inventes un número" in msg.lower()
    bloque = msg.split("═══ QUÉ FUNCIONÓ (Métricas) ═══")[1].split("\n\n")[0].strip().splitlines()
    assert len(bloque) <= 8
    assert "porque" in msg.split("═══ QUÉ FUNCIONÓ (Métricas) ═══")[1]


def test_ejecutar_tool_devuelve_el_texto(mundo, monkeypatch):
    import publicar
    monkeypatch.setattr(db, "disponible", lambda: True)
    monkeypatch.setattr(publicar, "Config", lambda *a, **k: Cfg())
    texto, res = nucleo._ejecutar_tool("que_funciono", {"canal": "", "formato": "reel", "dias": 60})
    assert res == [] and "MÉTRICAS REALES" in texto and "últimos 60 días" in texto and "Pieza 1" in texto and "Pieza 2" not in texto


def test_sin_supabase_avisa_y_no_rompe(monkeypatch):
    monkeypatch.setattr(db, "disponible", lambda: False)
    texto, res = nucleo._ejecutar_tool("que_funciono", {})
    assert res == [] and "Métricas no está disponible ahora" in texto
    monkeypatch.setattr(db, "disponible", lambda: True)               # la base falla
    monkeypatch.setattr(db, "publicaciones_para_metricas", lambda desde: (_ for _ in ()).throw(RuntimeError("caída")))
    texto, _ = nucleo._ejecutar_tool("que_funciono", {"dias": "no es número"})
    assert "Métricas no está disponible ahora" in texto


def test_en_el_chat_el_modelo_recibe_el_texto(mundo, monkeypatch):
    import publicar
    monkeypatch.setattr(db, "disponible", lambda: True)
    monkeypatch.setattr(publicar, "Config", lambda *a, **k: Cfg())
    visto = {}

    def _chat_falso(cl, messages, **kw):
        tc = SimpleNamespace(id="c1", function=SimpleNamespace(name="que_funciono", arguments=json.dumps({"canal": "instagram"})))
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="", tool_calls=[tc]))])

    def _stream_falso(cl, messages, **kw):
        visto["tool"] = messages[-1]
        yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="El reel del 5/11."))])

    monkeypatch.setattr(nucleo, "_get_client", lambda: None)
    monkeypatch.setattr(nucleo, "system_msg", lambda: "system de prueba")
    monkeypatch.setattr(nucleo, "_chat", _chat_falso)
    monkeypatch.setattr(chat, "_chat_stream", _stream_falso)
    fin = chat.responder([{"role": "user", "content": "¿qué funcionó en Instagram?"}], usuario="franco")
    assert visto["tool"]["role"] == "tool" and "MÉTRICAS REALES" in visto["tool"]["content"] and "alcance 2100" in visto["tool"]["content"]
    assert fin["texto"] == "El reel del 5/11." and fin["pieza"] is None and fin["campana"] is None
