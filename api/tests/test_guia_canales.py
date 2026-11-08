"""Criterio de marketing del chat (8/11, Beto, tarjeta Trello 99): la consigna lleva el resumen de fuentes/guia_canales.md."""
import os
import pytest

import nucleo


def test_consigna_lleva_el_bloque_de_la_guia():
    msg = nucleo.system_msg()
    assert nucleo.GUIA_CANALES_RESUMEN.strip() in msg
    assert "QUÉ FORMATO PARA QUÉ (guía de canales, Beto 10/2026)" in msg


def test_el_bloque_tiene_las_ideas_clave():
    g = nucleo.GUIA_CANALES_RESUMEN.lower()
    for palabra in ("reel", "historia", "newsletter", "whatsapp", "gente propia", "propio", "prestado", "carrusel",
                    "youtube", "facebook", "se produce una vez y se publica en cinco lugares"):
        assert palabra in g, palabra
    assert "nunca propongas producir algo distinto para cada canal" in g


def test_el_bloque_no_se_agranda_sin_medida():
    # tope de 25 líneas pedido por Beto/Franco; el título cuenta
    assert len(nucleo.GUIA_CANALES_RESUMEN.strip().splitlines()) <= 25
    assert len(nucleo.GUIA_CANALES_RESUMEN) < 5500


@pytest.mark.real
@pytest.mark.skipif(not os.environ.get("OPENAI_API_KEY"), reason="sin OPENAI_API_KEY en el entorno")
def test_real_recomienda_formatos(monkeypatch):
    import db
    monkeypatch.setattr(db, "disponible", lambda: False)
    texto, _m, _q, _p = nucleo.responder_con_pieza(
        [{"role": "user", "content": "quiero hacer una campaña sobre la confianza plena en la vida, ¿qué formatos conviene?"}])
    print("\nRESPUESTA REAL:\n", texto)
    t = texto.lower()
    assert not t.startswith("error llamando")
    assert any(p in t for p in ("reel", "historia", "newsletter", "whatsapp"))
