"""Pruebas de api/newsletter_rutas.py sin Supabase ni OpenAI: db y newsletter.redactar mockeados."""
import db
import newsletter


def _con_db(monkeypatch, filas):
    monkeypatch.setattr(db, "disponible", lambda: True)
    monkeypatch.setattr(db, "listar_mias", lambda u, limite=50: [f for f in filas if f["usuario"] == u])

    def _req(method, params="", body=None, tabla="conversaciones"):
        assert tabla == "publicaciones"
        if method == "GET":
            pid = params.split("id=eq.")[1].split("&")[0]
            return [f for f in filas if f["id"] == pid and f"usuario=eq.{f['usuario']}" in params and f["estado"] == "borrador"]
        if method == "DELETE":
            pid = params.split("id=eq.")[1].split("&")[0]
            filas[:] = [f for f in filas if f["id"] != pid]
            return []
    monkeypatch.setattr(db, "_req", _req)


def test_plantillas_y_html(logueado):
    r = logueado.get("/newsletter/plantillas")
    assert r.status_code == 200 and set(r.json()["plantillas"]) == {"mensual", "revivi"} and "agenda" in r.json()["vacios"]["mensual"]
    r = logueado.post("/newsletter/html", json={"plantilla": "mensual", "datos": {"asunto": "Octubre", "reflexion": "Hola <b>mundo</b>",
                                                                                   "video": {"titulo": "Un video", "url": "https://x/v", "imagen_url": ""}}})
    assert r.status_code == 200
    j = r.json()
    assert j["titulo"] == "Octubre" and "&lt;b&gt;mundo" in j["html"] and "UN RECORTE PARA VER" in j["html"]
    assert logueado.post("/newsletter/html", json={"plantilla": "otra", "datos": {}}).status_code == 400
    assert logueado.post("/newsletter/html", json={"plantilla": "revivi", "datos": {"episodios": [{"titulo": "EP", "texto": "t", "url": "", "imagen_url": ""}]}}).json()["titulo"] == "Newsletter"


def test_redactar(logueado, monkeypatch):
    def _redactar(p, tema, d):
        d = dict(d, asunto=f"Reviví: {tema}")
        return d, [{"titulo": "Charla", "autor": "Br. David", "tag": "VIDEO", "ir": "https://y/1", "url": "https://y/0"}]
    monkeypatch.setattr(newsletter, "redactar", _redactar)
    r = logueado.post("/newsletter/redactar", json={"plantilla": "revivi", "tema": "la confianza", "datos": {}})
    assert r.status_code == 200 and r.json()["datos"]["asunto"] == "Reviví: la confianza" and r.json()["materiales"][0]["url"] == "https://y/1"
    assert logueado.post("/newsletter/redactar", json={"plantilla": "revivi", "tema": "  ", "datos": {}}).status_code == 400


def test_borradores_y_aprobacion(logueado, monkeypatch):
    filas = [{"id": "b1", "usuario": "franco", "canal": "newsletter", "estado": "borrador", "titulo": "Octubre", "creado": "2026-10-20T10:00:00",
              "texto": "<html>", "resultado": {"pieza": {"plantilla": "revivi", "datos": {"asunto": "Octubre"}}, "guardado_en": "2026-10-20T10:00:00"}},
             {"id": "b2", "usuario": "franco", "canal": "instagram", "estado": "borrador", "titulo": "IG", "creado": "", "resultado": {}},
             {"id": "b3", "usuario": "lizzie", "canal": "newsletter", "estado": "borrador", "titulo": "De otra", "creado": "", "resultado": {}}]
    _con_db(monkeypatch, filas)
    guardados = []
    monkeypatch.setattr(db, "guardar_borrador", lambda u, canal, titulo, texto, img, fecha, pieza, pid=None: guardados.append((canal, titulo, pieza, pid)) or (pid or "nuevo"))
    propuestas = []
    monkeypatch.setattr(db, "proponer_publicacion", lambda u, canal, modo, titulo, texto, img, fecha, extra=None: propuestas.append((canal, modo, titulo, extra)) or "p1")

    r = logueado.get("/newsletter/borradores")
    assert r.status_code == 200 and [b["id"] for b in r.json()] == ["b1"] and r.json()[0]["plantilla"] == "revivi"
    r = logueado.get("/newsletter/borradores/b1")
    assert r.status_code == 200 and r.json()["plantilla"] == "revivi" and r.json()["datos"]["asunto"] == "Octubre" and len(r.json()["datos"]["episodios"]) == 3
    assert logueado.get("/newsletter/borradores/b3").status_code == 404

    r = logueado.post("/newsletter/borrador", json={"plantilla": "mensual", "datos": {"mes": "Noviembre"}, "borrador_id": "b1"})
    assert r.status_code == 200 and r.json()["id"] == "b1" and guardados[-1][1] == "Newsletter Noviembre" and guardados[-1][3] == "b1"
    r = logueado.post("/newsletter/borrador", json={"plantilla": "mensual", "datos": {}, "borrador_id": "b3"})   # ajeno: se crea uno nuevo
    assert r.json()["id"] == "nuevo" and guardados[-1][3] is None

    assert logueado.post("/newsletter/a-aprobar", json={"plantilla": "mensual", "datos": {}}).status_code == 400   # sin asunto
    r = logueado.post("/newsletter/a-aprobar", json={"plantilla": "mensual", "datos": {"asunto": "Octubre"}, "borrador_id": "b1"})
    assert r.status_code == 200 and r.json()["estado"] == "a_aprobar" and "franco" in r.json()["mensaje"]
    assert propuestas[-1][:3] == ("newsletter", "borrador", "Octubre") and propuestas[-1][3]["plantilla"] == "mensual"
    assert all(f["id"] != "b1" for f in filas)     # el borrador retomado se eliminó


def test_sin_sesion(cliente):
    assert cliente.get("/newsletter/plantillas").status_code == 401
