"""(23/11) Práctica del día: la planilla maestra trae Práctica y Texto original, el importador los lee y la API los expone en la frase."""
import importar_frases
import api.frases._comun as fr


def test_leer_csv_lee_practica_y_texto_original():
    csv = ("Frase,Autor,Fuente,Tema / subtema,Validada,Observación,Práctica,Texto original\n"
           "Una frase,Alguien,Grateful Living 2026,,Pendiente,Verificar fuente,Hoy agradecé algo chico.,A sentence\n"
           "Otra frase,Otro,Frase del día recuperada,Vínculos,Validada,,,\n")
    filas = importar_frases.leer_csv(csv)
    assert [f["texto"] for f in filas] == ["Una frase", "Otra frase"]      # «Texto original» no se confunde con la columna Frase
    assert filas[0]["practica"] == "Hoy agradecé algo chico." and filas[0]["texto_original"] == "A sentence"
    assert filas[0]["validada"] is False                                     # Pendiente no entra al calendario
    assert filas[1]["practica"] is None and filas[1]["texto_original"] is None and filas[1]["validada"] is True


def test_leer_csv_sin_las_columnas_nuevas():
    filas = importar_frases.leer_csv("Frase,Autor,Fuente,Tema / subtema,Validada,Observación\nUna frase,Alguien,x,,Validada,\n")
    assert filas[0]["practica"] is None and filas[0]["texto_original"] is None


def test_publica_expone_practica():
    f = {"id": "f1", "texto": "Una frase", "autor": "Alguien", "fecha": None, "estado": "programada", "validada": False,
         "practica": "Hoy agradecé algo chico.", "texto_original": "A sentence"}
    p = fr._publica(f)
    assert p["practica"] == "Hoy agradecé algo chico." and p["texto_original"] == "A sentence"
    assert fr._publica(dict(f, practica=None))["practica"] is None


def test_get_paginado_junta_las_paginas(monkeypatch):
    """(23/11) Supabase devuelve 1000 filas como mucho por llamada: con frases > 1000 el GET sigue con offset hasta completar."""
    import db._cliente as cli
    llamadas = []

    def _llamar(url, method, body, key, prefer, timeout):
        llamadas.append(url)
        lim = int(url.split("limit=")[1].split("&")[0]); off = int(url.split("offset=")[1].split("&")[0])
        return [{"n": i} for i in range(off, min(off + lim, 1557))]
    monkeypatch.setattr(cli, "_llamar", _llamar)
    filas = cli._get_paginado("https://x/rest/v1/frases?select=id&order=orden.asc&limit=2000", "k", None, 30)
    assert len(filas) == 1557 and filas[-1]["n"] == 1556 and len(llamadas) == 2
    assert "limit=1000&offset=0" in llamadas[0] and "limit=1000&offset=1000" in llamadas[1]
    # un limit chico es una sola llamada; un offset pedido es el punto de partida
    llamadas.clear()
    assert len(cli._get_paginado("https://x/rest/v1/frases?limit=50&offset=20", "k", None, 30)) == 50
    assert llamadas == ["https://x/rest/v1/frases?limit=50&offset=20"]
