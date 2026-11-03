"""(3/11) web/openapi.json (de donde salen los tipos TS) tiene que estar al día con los modelos de la API."""
import os

from api import generar_openapi


def test_openapi_al_dia():
    with open(generar_openapi.SALIDA, encoding="utf-8") as fh:
        guardado = fh.read()
    assert guardado == generar_openapi.texto(), (
        "web/openapi.json quedó viejo: correr `python api/generar_openapi.py` y `npm run tipos` en web/, y commitear los dos archivos.")
