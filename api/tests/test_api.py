"""Pruebas sin OpenAI ni Supabase: salud, login, sesión, roles y una conversación con el chat mockeado."""
import json
from types import SimpleNamespace

import nucleo
import db
import api.chat as chat
import api.auth as auth


def test_salud(cliente):
    r = cliente.get("/salud")
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True and d["supabase"] is False and d["corpus_cargado"] is False
    assert d["login_google"] is False and d["google_client_id"] is None


def test_login_bueno(cliente):
    r = cliente.post("/login", json={"usuario": "franco", "clave": "clave-franco"})
    assert r.status_code == 200
    d = r.json()
    assert d["usuario"] == "franco" and d["idioma"] == "es"
    assert d["rol"]["aprueba"] is True and d["rol"]["nombre"] == "aprobador / admin"
    assert auth.COOKIE in r.cookies
    yo = cliente.get("/yo")
    assert yo.status_code == 200 and yo.json()["usuario"] == "franco"


def test_login_malo(cliente):
    assert cliente.post("/login", json={"usuario": "franco", "clave": "otra"}).status_code == 401
    assert cliente.post("/login", json={"usuario": "nadie", "clave": "x"}).status_code == 401
    assert cliente.get("/yo").status_code == 401


def test_yo_sin_sesion(cliente):
    assert cliente.get("/yo").status_code == 401
    assert cliente.get("/conversaciones").status_code == 401
    assert cliente.get("/recortes").status_code == 401
    assert cliente.get("/publicaciones").status_code == 401


def test_cookie_trucha(cliente):
    cliente.cookies.set(auth.COOKIE, "no-es-una-firma")
    assert cliente.get("/yo").status_code == 401


def test_roles_e_idioma(cliente):
    r = cliente.post("/login", json={"usuario": "gratefulness", "clave": "clave-g"})
    d = r.json()
    assert d["idioma"] == "en" and d["rol"]["aprueba"] is False and d["rol"]["nombre"] == "creador de contenido"
    assert cliente.get("/recortes?todos=1").status_code == 403
    assert cliente.get("/publicaciones?todos=1").status_code == 403
    assert cliente.get("/autorizados").status_code == 403


def test_aprobador_ve_todo(logueado):
    assert logueado.get("/recortes?todos=1").status_code == 200
    assert logueado.get("/publicaciones?todos=1").status_code == 200
    assert logueado.get("/autorizados").status_code == 200


def test_logout(logueado):
    assert logueado.post("/logout").status_code == 200
    assert logueado.get("/yo").status_code == 401


def test_listas_sin_supabase(logueado):
    assert logueado.get("/conversaciones").json() == []
    assert logueado.get("/recortes").json() == []
    assert logueado.get("/publicaciones").json()["piezas"] == []
    assert logueado.get("/conversaciones/123").status_code == 503


# ---------------- Login con Google ----------------
def test_google_sin_configurar(cliente):
    assert cliente.post("/login/google", json={"id_token": "x"}).status_code == 503


def test_google_dominio(cliente, monkeypatch):
    monkeypatch.setattr(auth, "verificar_google", lambda t: "alguien@viviragradecidos.org")
    r = cliente.post("/login/google", json={"id_token": "x"})
    assert r.status_code == 200, r.text
    assert r.json()["usuario"] == "alguien@viviragradecidos.org" and r.json()["admitido_por"] == "dominio"
    assert r.json()["rol"]["aprueba"] is False
    assert cliente.get("/yo").json()["origen"] == "google"


def test_google_lista_y_rechazo(cliente, monkeypatch):
    monkeypatch.setattr(auth, "verificar_google", lambda t: "patricio@gmail.com")
    monkeypatch.setattr(db, "autorizado", lambda e: None)
    assert cliente.post("/login/google", json={"id_token": "x"}).status_code == 403
    monkeypatch.setattr(db, "autorizado", lambda e: {"email": e, "rol": "aprobador"})
    r = cliente.post("/login/google", json={"id_token": "x"})
    assert r.status_code == 200 and r.json()["admitido_por"] == "lista" and r.json()["rol"]["aprueba"] is True


def test_google_email_de_la_lista_de_aprobadores(cliente, monkeypatch):
    """franco@dominio hereda el rol de 'franco' en APROBADORES (parte antes de la arroba)."""
    monkeypatch.setattr(auth, "verificar_google", lambda t: "franco@viviragradecidos.org")
    r = cliente.post("/login/google", json={"id_token": "x"})
    assert r.status_code == 200 and r.json()["rol"]["aprueba"] is True


# ---------------- Chat mockeado ----------------
MATS = [{"tag": "CLIP · 13:26–14:10", "titulo": "La gratitud como respuesta a la vida", "texto": "La gratitud es la llave de la alegría.",
         "autor": "Br. David", "fuente": "youtube", "url": "https://www.youtube.com/watch?v=abc123def", "doc": "abc123def",
         "score": 0.5, "inicio_ms": 806000, "fin_ms": 850000, "pagina": None, "ir": "https://www.youtube.com/watch?v=abc123def&t=806s"},
        {"tag": "LIBRO · Gratitud", "titulo": "Gratitud, el corazón de la plegaria", "texto": "Texto del libro.", "autor": "Br. David",
         "fuente": "libro", "url": None, "doc": "libro-1", "score": 0.4, "inicio_ms": None, "fin_ms": None, "pagina": 12, "ir": ""}]
RESPUESTA = "Br. David dice que la gratitud es la llave de la alegría (La gratitud como respuesta a la vida)."


def _mock_cerebro(monkeypatch, llamadas):
    """Primera llamada: el modelo pide buscar_material; herramienta mockeada; segunda llamada en streaming."""
    def _chat_falso(cl, messages, **kw):
        llamadas.append(("chat", kw))
        tc = SimpleNamespace(id="call_1", function=SimpleNamespace(name="buscar_material", arguments=json.dumps({"consulta": "gratitud"})))
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="", tool_calls=[tc]))])

    def _tool_falsa(nombre, args):
        llamadas.append(("tool", nombre, args))
        return nucleo.contexto(MATS), MATS

    def _stream_falso(cl, messages, **kw):
        llamadas.append(("stream", kw))
        for palabra in RESPUESTA.split(" "):
            yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=palabra + " "))])

    monkeypatch.setattr(nucleo, "_get_client", lambda: None)
    monkeypatch.setattr(nucleo, "system_msg", lambda: "system de prueba")
    monkeypatch.setattr(nucleo, "_chat", _chat_falso)
    monkeypatch.setattr(nucleo, "_ejecutar_tool", _tool_falsa)
    monkeypatch.setattr(nucleo, "titular", lambda msgs: "Título de prueba")
    monkeypatch.setattr(chat, "_chat_stream", _stream_falso)


def test_chat_sin_streaming(logueado, monkeypatch):
    llamadas = []
    _mock_cerebro(monkeypatch, llamadas)
    r = logueado.post("/conversaciones/nueva/mensajes", json={"texto": "¿qué dice Br. David sobre la gratitud?"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["texto"].strip() == RESPUESTA
    assert d["conversacion_id"] is None           # sin Supabase no se guarda
    assert len(d["tarjetas"]) == 2
    assert d["tarjetas"][0]["citada"] is True and d["tarjetas"][1]["citada"] is False
    assert d["tarjetas"][0]["recortes"] == {"horizontal": None, "vertical": None}
    assert "recortes" not in d["tarjetas"][1]
    assert d["mensaje"]["role"] == "assistant" and d["mensaje"]["mats"] == MATS and d["pieza"] is None
    assert llamadas[0][0] == "chat" and llamadas[0][1]["tools"] is nucleo.TOOLS
    assert llamadas[1][:2] == ("tool", "buscar_material") and llamadas[2][0] == "stream"
    assert nucleo.USUARIO_ACTUAL == ""             # se limpia después de la herramienta


def test_usuario_actual_durante_la_herramienta(logueado, monkeypatch):
    visto = []
    llamadas = []
    _mock_cerebro(monkeypatch, llamadas)

    def _tool(nombre, args):
        visto.append(nucleo.USUARIO_ACTUAL)
        return "nada", []
    monkeypatch.setattr(nucleo, "_ejecutar_tool", _tool)
    logueado.post("/conversaciones/nueva/mensajes", json={"texto": "pedime el recorte"})
    assert visto == ["franco"]


def _leer_sse(resp):
    eventos, nombre = [], None
    for linea in resp.iter_lines():
        if linea.startswith("event: "):
            nombre = linea[7:]
        elif linea.startswith("data: "):
            eventos.append((nombre, json.loads(linea[6:])))
    return eventos


def test_chat_streaming(logueado, monkeypatch):
    _mock_cerebro(monkeypatch, [])
    with logueado.stream("POST", "/conversaciones/nueva/mensajes",
                         json={"texto": "¿qué dice Br. David sobre la gratitud?", "stream": True}) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        ev = _leer_sse(r)
    nombres = [n for n, _ in ev]
    assert nombres[0] == "inicio" and nombres[-1] == "fin"
    assert "fuentes" in nombres and nombres.count("texto") == len(RESPUESTA.split(" "))
    assert nombres.index("fuentes") < nombres.index("texto")
    texto = "".join(d["delta"] for n, d in ev if n == "texto")
    fin = ev[-1][1]
    assert texto.strip() == RESPUESTA == fin["texto"].strip()
    assert len([d for n, d in ev if n == "fuentes"][0]["tarjetas"]) == 2


def test_chat_con_pieza(logueado, monkeypatch):
    """El bot llama a proponer_publicacion: el evento pieza llega antes del texto y queda en el mensaje."""
    _mock_cerebro(monkeypatch, [])
    pieza = {"canal": "instagram", "titulo": "Gratitud", "texto": "La gratitud es la llave.", "fecha": "", "hora": "",
             "texto_imagen": "", "firma": "", "imagen_busqueda": "amanecer"}
    monkeypatch.setattr(nucleo, "_ejecutar_tool", lambda n, a: ("Recuadro preparado", {"__pieza__": pieza}))
    r = logueado.post("/conversaciones/nueva/mensajes", json={"texto": "dale, publicalo"})
    assert r.status_code == 200 and r.json()["pieza"] == pieza and r.json()["tarjetas"] == []


def test_chat_texto_vacio(logueado):
    assert logueado.post("/conversaciones/nueva/mensajes", json={"texto": "   "}).status_code == 400


def test_chat_conversacion_ajena(logueado, monkeypatch):
    monkeypatch.setattr(db, "disponible", lambda: True)
    monkeypatch.setattr(db, "cargar_conversacion_de", lambda cid, u: None)
    assert logueado.post("/conversaciones/otra-id/mensajes", json={"texto": "hola"}).status_code == 404
    assert logueado.get("/conversaciones/otra-id").status_code == 404
