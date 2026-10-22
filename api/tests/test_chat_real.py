"""Una conversación REAL contra OpenAI con el corpus cargado. Se saltea si no hay OPENAI_API_KEY.
Correr:  OPENAI_API_KEY=... pytest api/tests -m real -s
No guarda nada en Supabase (se desactiva db.disponible)."""
import os
import pytest

import nucleo
import db

pytestmark = pytest.mark.real


@pytest.mark.skipif(not os.environ.get("OPENAI_API_KEY"), reason="sin OPENAI_API_KEY en el entorno")
def test_conversacion_real(logueado, monkeypatch):
    monkeypatch.setattr(db, "disponible", lambda: False)
    nucleo.cargar()
    r = logueado.post("/conversaciones/nueva/mensajes", json={"texto": "¿qué dice Br. David sobre la gratitud?"})
    assert r.status_code == 200, r.text
    d = r.json()
    print("\nRESPUESTA:", d["texto"][:400])
    print("FUENTES:", [(t["tag"], t["titulo"]) for t in d["tarjetas"]])
    assert len(d["texto"]) > 50 and not d["texto"].startswith("Error llamando al modelo")
    assert d["tarjetas"], "el bot tendría que haber buscado material"
    assert all(t.get("autor") for t in d["tarjetas"])
