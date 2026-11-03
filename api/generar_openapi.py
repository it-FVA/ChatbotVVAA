"""(3/11, revisión 5.2 punto 10) Escribe el OpenAPI de la API en web/openapi.json, de donde `npm run tipos` (openapi-typescript)
genera web/src/tiposApi.d.ts. Así la web usa los modelos Pydantic (Pieza y los demás) sin copiarlos a mano.

Uso, desde la raíz del repo:   python api/generar_openapi.py      (o `npm run tipos` en web/, que hace las dos cosas)
La prueba api/tests/test_openapi.py falla si el archivo quedó viejo: regenerarlo y commitearlo junto con el cambio del modelo.
"""
import json, os, sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SALIDA = os.path.join(RAIZ, "web", "openapi.json")


def texto():
    sys.path.insert(0, RAIZ)
    os.environ.setdefault("FVA_SECRETS", "-")
    os.environ.setdefault("API_CARGAR_CORPUS", "0")
    from api.main import app
    return json.dumps(app.openapi(), ensure_ascii=False, indent=1, sort_keys=True) + "\n"


if __name__ == "__main__":
    t = texto()
    with open(SALIDA, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(t)
    print(f"escrito {SALIDA} ({len(t)} caracteres)")
