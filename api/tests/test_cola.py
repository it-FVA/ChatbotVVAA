"""procesar_cola: la pieza se marca 'procesando' antes del conector y vuelve a 'pendiente' si falla (con db y publicar simulados)."""
import sys

import pytest

import db
import publicar
import procesar_cola


@pytest.fixture
def cola(monkeypatch):
    estado = {"filas": {}, "llamadas": [], "tomadas": set()}

    def reclamar(pid, resultado=None):
        if pid in estado["tomadas"]:
            return False
        estado["tomadas"].add(pid)
        estado["llamadas"].append(("reclamar", pid))
        return True

    monkeypatch.setattr(procesar_cola, "_cargar_config_local", lambda: None)
    monkeypatch.setattr(sys, "argv", ["procesar_cola.py", "--simular"])
    monkeypatch.setattr(db, "disponible", lambda: True)
    monkeypatch.setattr(db, "vaciar_papelera_vencida", lambda: 0)
    monkeypatch.setattr(db, "liberar_procesando_viejas", lambda minutos=30: [])
    monkeypatch.setattr(db, "reclamar_publicacion", reclamar)
    monkeypatch.setattr(db, "listar_pendientes", lambda vencidas=False, limite=50: [
        {"id": "p1", "canal": "instagram", "texto": "hola", "imagen_url": "http://i/x.png", "intentos": 0, "resultado": {}}])
    monkeypatch.setattr(db, "actualizar_publicacion", lambda pid, campos: estado["llamadas"].append(("actualizar", pid, campos["estado"])))
    monkeypatch.setitem(sys.modules, "programar_frases", type("M", (), {"main": staticmethod(lambda a: None)}))
    monkeypatch.setitem(sys.modules, "frase_mail", type("M", (), {"avanzar": staticmethod(lambda d, p: [])}))
    monkeypatch.setitem(sys.modules, "perfit", type("M", (), {}))
    return estado


def test_reclama_antes_de_publicar_y_queda_simulada(cola, monkeypatch):
    def conector(cfg, imagen, texto, quien="", historia=False):
        cola["llamadas"].append(("conector",))
        return {"ok": True, "modo": "simulado"}
    monkeypatch.setattr(publicar, "publicar_instagram", conector)
    assert procesar_cola.main() == 0
    assert cola["llamadas"] == [("reclamar", "p1"), ("conector",), ("actualizar", "p1", "simulada")]


def test_si_otra_corrida_la_tomo_no_se_publica(cola, monkeypatch):
    cola["tomadas"].add("p1")
    monkeypatch.setattr(publicar, "publicar_instagram", lambda *a, **k: pytest.fail("no debía publicarse dos veces"))
    assert procesar_cola.main() == 0
    assert cola["llamadas"] == []


def test_si_el_conector_falla_vuelve_a_pendiente(cola, monkeypatch):
    monkeypatch.setattr(publicar, "publicar_instagram", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("Meta caído")))
    procesar_cola.main()
    assert cola["llamadas"][-1] == ("actualizar", "p1", "pendiente")
