"""(22/10) nucleo.buscar con VECTORES=supabase / LEXICO=supabase, sin OpenAI ni Supabase: corpus de juguete y db.* mockeado.
Lo que se prueba: que el modo supabase use match_fragmentos / match_lexico y no el .npy ni BM25, que el ranking y el
score salgan de lo que devuelve Postgres, que la fusión RRF con el léxico siga funcionando y que el default sea local."""
import numpy as np
import pytest

import db
import nucleo

CORPUS = [
    {"fragmento_id": "a:0", "documento_id": "d0", "fuente": "web", "titulo": "Gratitud y alegría", "autor": "Br. David", "texto": "La gratitud es la llave de la alegría y abre el corazón."},
    {"fragmento_id": "b:0", "documento_id": "d1", "fuente": "youtube", "titulo": "Charla sobre el miedo", "autor": "Virginia Gawel", "texto": "El miedo y la confianza: cómo vincularnos con el miedo.", "inicio_ms": 1000, "fin_ms": 9000, "url": "https://www.youtube.com/watch?v=b"},
    {"fragmento_id": "c:0", "documento_id": "d2", "fuente": "libro", "titulo": "Gratefulness, the heart of prayer", "autor": "Br. David", "texto": "Gratefulness is the key to joy.", "idioma": "en", "pagina": 12},
    {"fragmento_id": "d:0", "documento_id": "d3", "fuente": "web", "titulo": "Esperanza y expectativa", "autor": "Br. David", "texto": "La esperanza es apertura a la sorpresa; la expectativa, a lo imaginable."},
]


@pytest.fixture
def juguete(monkeypatch):
    monkeypatch.setattr(nucleo, "_FRS", list(CORPUS))
    emb = np.eye(4, 512, dtype="float32")             # fragmento i = vector base i: la similitud con una consulta es su componente i
    monkeypatch.setattr(nucleo, "_EMB", emb)
    monkeypatch.setattr(nucleo, "_BM25", None)
    monkeypatch.setattr(nucleo, "_traducir_en", lambda t: t)       # sin traducción (misma consulta)
    monkeypatch.setattr(nucleo, "expandir_consulta", lambda c, max_terminos=8: "")
    monkeypatch.setenv("BUSQUEDA_HIBRIDA", "0")
    monkeypatch.setenv("LIMPIEZA_EXTRA", "0")
    monkeypatch.delenv("VECTORES", raising=False)
    monkeypatch.delenv("LEXICO", raising=False)
    vectores = {"gratitud": [0.9, 0.1, 0.8, 0.0], "miedo": [0.0, 0.95, 0.0, 0.1]}

    def _embed(q):
        v = np.zeros(512, dtype="float32")
        v[:4] = vectores.get(q, [0.2, 0.2, 0.2, 0.2])
        return v
    monkeypatch.setattr(nucleo, "embed_query", _embed)
    llamadas = {"vectores": [], "lexico": []}

    def _match(vs, k=300):
        llamadas["vectores"].append((len(vs), k))
        # Postgres devolvería los k mejores por coseno: simulamos con la misma matriz
        sims = np.max([emb @ np.array(v, dtype="float32") for v in vs], axis=0)
        return {int(i): float(sims[i]) for i in np.argsort(-sims)[:k] if sims[i] > 0}

    def _lexico(consulta, k=300):
        llamadas["lexico"].append(consulta)
        return [3, 0] if "esperanza" in consulta else []
    monkeypatch.setattr(db, "match_fragmentos", _match)
    monkeypatch.setattr(db, "match_lexico", _lexico)
    return llamadas


def test_default_local_no_toca_supabase(juguete):
    res = nucleo.buscar("gratitud", n=2, rerank=False)
    assert [r["doc"] for r in res] == ["d0", "d2"] and res[0]["score"] == 0.9
    assert juguete["vectores"] == [] and juguete["lexico"] == []


def test_modo_supabase_mismo_ranking(juguete, monkeypatch):
    monkeypatch.setenv("VECTORES", "supabase")
    monkeypatch.setenv("VECTORES_K", "50")
    res = nucleo.buscar("gratitud", n=2, rerank=False)
    assert [r["doc"] for r in res] == ["d0", "d2"] and res[0]["score"] == 0.9 and res[1]["tag"].startswith("LIBRO")
    assert juguete["vectores"] == [(1, 50)]                 # una sola llamada a Postgres con la consulta (sin traducción distinta)
    res = nucleo.buscar("miedo", n=1, rerank=False)
    assert res[0]["doc"] == "d1" and res[0]["tag"].startswith("CLIP")


def test_modo_supabase_varias_consultas_fusion_maximo(juguete, monkeypatch):
    """Traducción distinta de la consulta: las dos van juntas en UNA llamada (match_fragmentos_varios fusiona por máximo)."""
    monkeypatch.setenv("VECTORES", "supabase")
    monkeypatch.setattr(nucleo, "_traducir_en", lambda t: "miedo" if t == "gratitud" else t)
    res = nucleo.buscar("gratitud", n=3, rerank=False)
    assert juguete["vectores"] == [(2, 300)]
    assert [r["doc"] for r in res] == ["d1", "d0", "d2"]      # 0.95 (miedo) > 0.9 > 0.8


def test_lexico_supabase_con_rrf(juguete, monkeypatch):
    monkeypatch.setenv("VECTORES", "supabase")
    monkeypatch.setenv("LEXICO", "supabase")
    monkeypatch.setenv("BUSQUEDA_HIBRIDA", "1")
    res = nucleo.buscar("esperanza", n=4, rerank=False)
    # vectorial: todos 0.2 (empate, orden d0..d3); el léxico pone d3 y d0 primero → RRF los deja arriba de d1 y d2
    assert juguete["lexico"] == ["esperanza"]
    assert set(r["doc"] for r in res[:2]) == {"d0", "d3"} and [r["doc"] for r in res[2:]] == ["d1", "d2"]
    # sin BUSQUEDA_HIBRIDA el léxico no se consulta
    monkeypatch.setenv("BUSQUEDA_HIBRIDA", "0")
    nucleo.buscar("esperanza", n=2, rerank=False)
    assert juguete["lexico"] == ["esperanza"]


def test_lexico_supabase_falla_sigue_vectorial(juguete, monkeypatch):
    monkeypatch.setenv("VECTORES", "supabase")
    monkeypatch.setenv("LEXICO", "supabase")
    monkeypatch.setenv("BUSQUEDA_HIBRIDA", "1")

    def _rompe(consulta, k=300):
        raise RuntimeError("Supabase rpc/match_lexico 500")
    monkeypatch.setattr(db, "match_lexico", _rompe)
    res = nucleo.buscar("gratitud", n=2, rerank=False)
    assert [r["doc"] for r in res] == ["d0", "d2"]


def test_cargar_no_lee_npy_en_modo_supabase(monkeypatch):
    monkeypatch.setattr(nucleo, "_FRS", None)
    monkeypatch.setattr(nucleo, "_EMB", None)
    monkeypatch.setenv("VECTORES", "supabase")
    leidos = []
    monkeypatch.setattr(nucleo.np, "load", lambda p: leidos.append(p) or np.zeros((1, 512)))
    import builtins, io
    abierto = builtins.open
    monkeypatch.setattr(builtins, "open", lambda p, *a, **k: io.StringIO('{"fragmento_id": "x:0", "documento_id": "x", "texto": "hola"}\n') if str(p).endswith("fragmentos.jsonl") else abierto(p, *a, **k))
    frs, emb = nucleo.cargar()
    assert len(frs) == 1 and emb is None and leidos == []
    monkeypatch.setenv("VECTORES", "local")
    frs, emb = nucleo.cargar()
    assert len(leidos) == 1 and emb is not None


def test_analizar_modo_supabase(juguete, monkeypatch):
    monkeypatch.setenv("VECTORES", "supabase")
    resumen, res = nucleo.analizar("gratitud")
    assert "Br. David: 2" in resumen and juguete["vectores"][0] == (1, 500)
