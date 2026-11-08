"""Modo campaña del chat (8/11, Beto): el modelo simulado llama a proponer_campana y la API crea el Proyecto, los borradores de
cada pieza, los ítems del Proyecto, el evento SSE `campana` y guarda la campaña en el mensaje de la conversación.
Usa el PostgREST de juguete de test_proyectos (las tablas proyectos, proyecto_items, publicaciones y conversaciones)."""
import json
from types import SimpleNamespace

import nucleo
import api.chat as chat
from test_proyectos import FakePostgrest, base, logueado   # noqa: F401  (fixtures)

TABLA_PROPIA = True

FUENTE = "«Gratitud, el corazón de la plegaria» — Br. David"
PIEZAS = [
    {"canal": "instagram", "formato": "historia", "titulo": "Confiar es soltar",
     "texto": "¿Te diste cuenta de cuánto sostenés?\n\n«La confianza es soltar.» — Br. David, «Gratitud»",
     "texto_imagen": "La confianza es soltar.", "firma": "— Br. David", "fuente": FUENTE, "porque": "La historia conversa con los que ya nos siguen."},
    {"canal": "newsletter", "formato": "", "titulo": "Una semana de confianza", "texto": "Esta semana, una pregunta: ¿en qué confiás sin darte cuenta?",
     "texto_imagen": "", "firma": "", "fuente": FUENTE, "porque": "El mail es gente propia: ahí se profundiza."},
    {"canal": "facebook", "formato": "cuadrado", "titulo": "La misma tarjeta", "texto": "«La confianza es soltar.» — Br. David",
     "texto_imagen": "La confianza es soltar.", "firma": "— Br. David", "fuente": FUENTE, "porque": "Se produce una vez y se publica en cinco lugares."},
]
ARGS = {"nombre": "Confianza plena en la vida", "descripcion": "Invitar a confiar en la vida. Para quienes ya nos siguen.", "piezas": PIEZAS}


def _mock_modelo(monkeypatch, args=ARGS):
    def _chat_falso(cl, messages, **kw):
        tc = SimpleNamespace(id="c1", function=SimpleNamespace(name="proponer_campana", arguments=json.dumps(args)))
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="", tool_calls=[tc]))])

    def _stream_falso(cl, messages, **kw):
        _stream_falso.mensajes = messages
        for palabra in ["Armé", " la", " campaña."]:
            yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=palabra))])

    monkeypatch.setattr(nucleo, "_get_client", lambda: None)
    monkeypatch.setattr(nucleo, "system_msg", lambda: "system de prueba")
    monkeypatch.setattr(nucleo, "_chat", _chat_falso)
    monkeypatch.setattr(nucleo, "titular", lambda msgs: "Campaña de confianza")
    monkeypatch.setattr(chat, "_chat_stream", _stream_falso)
    return _stream_falso


def _eventos(r):
    out = []
    for bloque in r.text.split("\n\n"):
        nombre, datos = None, []
        for linea in bloque.splitlines():
            if linea.startswith("event: "):
                nombre = linea[7:]
            elif linea.startswith("data: "):
                datos.append(linea[6:])
        if nombre:
            out.append((nombre, json.loads("\n".join(datos))))
    return out


def _mandar(logueado, texto="armá la campaña"):
    return logueado.post("/conversaciones/c1/mensajes", json={"texto": texto, "stream": True}, headers={"Accept": "text/event-stream"})


def test_crea_proyecto_borradores_items_y_evento(logueado, base, monkeypatch):
    stream = _mock_modelo(monkeypatch)
    r = _mandar(logueado)
    assert r.status_code == 200, r.text
    eventos = _eventos(r)
    camp = dict(eventos)["campana"]
    # el Proyecto es de la persona que chatea
    assert camp["nombre"] == "Confianza plena en la vida"
    proys = base.t["proyectos"]
    assert len(proys) == 1 and proys[0]["id"] == camp["proyecto_id"] and proys[0]["dueno"] == "franco"
    assert proys[0]["descripcion"].startswith("Invitar a confiar")
    # tres borradores nuevos (el p1 de la base ya existía), con su formato y su fuente en resultado
    nuevos = [p for p in base.t["publicaciones"] if p["id"] != "p1"]
    assert len(nuevos) == 3 and all(p["estado"] == "borrador" and p["usuario"] == "franco" for p in nuevos)
    por_canal = {p["canal"]: p for p in nuevos}
    assert set(por_canal) == {"instagram", "newsletter", "facebook"}
    ig = por_canal["instagram"]
    assert ig["resultado"]["formato"] == "historia" and ig["resultado"]["pieza"]["fmt"] == "historia"
    assert ig["resultado"]["fuente"] == FUENTE
    assert ig["resultado"]["porque"].startswith("La historia") and ig["resultado"]["origen"] == "campana_chat"
    assert ig["texto"].startswith("¿Te diste cuenta") and ig["resultado"]["pieza"]["texto_imagen"] == "La confianza es soltar."
    assert por_canal["facebook"]["resultado"]["pieza"]["fmt"] == "cuadrado"
    nl = por_canal["newsletter"]
    assert nl["resultado"]["pieza"]["plantilla"] == "mensual" and nl["resultado"]["pieza"]["datos"]["asunto"] == "Una semana de confianza"
    assert "en qué confiás" in nl["resultado"]["pieza"]["datos"]["reflexion"]
    # los ítems del Proyecto: las tres piezas y la conversación
    items = base.t["proyecto_items"]
    assert sorted(i["item_id"] for i in items if i["tipo"] == "pieza") == sorted(p["id"] for p in nuevos)
    assert [i["item_id"] for i in items if i["tipo"] == "conversacion"] == ["c1"]
    assert all(i["proyecto_id"] == camp["proyecto_id"] and i["agregado_por"] == "franco" for i in items)
    # el evento: una fila por pieza con la url de Diseñar (o del editor de newsletter)
    assert [p["canal"] for p in camp["piezas"]] == ["instagram", "newsletter", "facebook"]
    for p in camp["piezas"]:
        base_url = "/newsletter" if p["canal"] == "newsletter" else "/publicar"
        assert p["url_editar"] == f"{base_url}?borrador={p['id']}" and p["canal_texto"]
    assert camp["piezas"][0]["canal_texto"] == "Instagram" and camp["piezas"][0]["formato"] == "historia"
    # va antes del texto y el modelo recibió el aviso de que quedó guardada
    nombres = [n for n, _ in eventos]
    assert nombres.index("campana") < nombres.index("texto") < nombres.index("fin")
    assert "guardada" in stream.mensajes[-1]["content"]
    # queda en el mensaje del asistente de la conversación: al reabrirla se ve
    msg = base.t["conversaciones"][0]["mensajes"][-1]
    assert msg["role"] == "assistant" and msg["campana"]["proyecto_id"] == camp["proyecto_id"]
    reabierta = logueado.get("/conversaciones/c1").json()
    assert reabierta["mensajes"][-1]["campana"]["piezas"][0]["url_editar"] == camp["piezas"][0]["url_editar"]
    # los borradores aparecen en el Proyecto con su título
    v = logueado.get(f"/proyectos/{camp['proyecto_id']}").json()
    assert sorted(i["titulo"] for i in v["items"] if i["tipo"] == "pieza") == ["Confiar es soltar", "La misma tarjeta", "Una semana de confianza"]


def test_conversacion_nueva_se_suma_al_proyecto(logueado, base, monkeypatch):
    _mock_modelo(monkeypatch)
    r = logueado.post("/conversaciones/nueva/mensajes", json={"texto": "armá la campaña"})     # sin streaming
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["campana"]["nombre"] == "Confianza plena en la vida" and d["mensaje"]["campana"] == d["campana"]
    nueva = d["conversacion_id"]
    assert nueva and [i["item_id"] for i in base.t["proyecto_items"] if i["tipo"] == "conversacion"] == [nueva]


def test_si_ya_hay_un_proyecto_con_ese_nombre_se_usa(logueado, base, monkeypatch):
    base.agregar("proyectos", nombre="  confianza   PLENA en la vida", dueno="franco", padre_id=None)
    base.agregar("proyectos", nombre="Confianza plena en la vida", dueno="lizzie", padre_id=None)     # el de otra persona no cuenta
    _mock_modelo(monkeypatch)
    camp = dict(_eventos(_mandar(logueado)))["campana"]
    propio = next(p for p in base.t["proyectos"] if p["dueno"] == "franco")
    assert camp["proyecto_id"] == propio["id"] and len(base.t["proyectos"]) == 2
    assert len([i for i in base.t["proyecto_items"] if i["proyecto_id"] == propio["id"] and i["tipo"] == "pieza"]) == 3


def test_la_conversacion_que_ya_esta_en_otro_proyecto_no_se_mueve(logueado, base, monkeypatch):
    otro = base.agregar("proyectos", nombre="Otro", dueno="franco", padre_id=None)
    base.agregar("proyecto_items", proyecto_id=otro["id"], tipo="conversacion", item_id="c1", agregado_por="franco")
    _mock_modelo(monkeypatch)
    camp = dict(_eventos(_mandar(logueado)))["campana"]
    conv = [i for i in base.t["proyecto_items"] if i["tipo"] == "conversacion"]
    assert len(conv) == 1 and conv[0]["proyecto_id"] == otro["id"] and camp["proyecto_id"] != otro["id"]


def test_con_menos_de_dos_piezas_no_se_crea_nada(logueado, base, monkeypatch):
    _mock_modelo(monkeypatch, dict(ARGS, piezas=PIEZAS[:1]))
    ev = dict(_eventos(_mandar(logueado)))
    assert "campana" not in ev and base.t["proyectos"] == [] and len(base.t["publicaciones"]) == 1
    assert ev["fin"]["campana"] is None


def test_herramienta_limpia_los_argumentos():
    extra = [dict(PIEZAS[0], canal="tiktok"), dict(PIEZAS[0], texto="")] + [PIEZAS[0]] * 5
    texto, res = nucleo._ejecutar_tool("proponer_campana", dict(ARGS, piezas=PIEZAS + extra))
    c = res["__campana__"]
    assert c["nombre"] == "Confianza plena en la vida" and len(c["piezas"]) == 6      # tope de 6; la de tiktok y la sin texto no entran
    assert all(p["canal"] in nucleo.CANALES_CHAT and p["texto"] for p in c["piezas"])
    assert "proponer_campana" in [t["function"]["name"] for t in nucleo.TOOLS]
    assert "proponer_campana" in nucleo.system_msg() and "SOLO cuando la persona pide armar o guardar la campaña" in nucleo.system_msg()
