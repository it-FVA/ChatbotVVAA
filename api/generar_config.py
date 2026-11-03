"""(3/11) Regenera, desde api/variables_entorno.py, el bloque `envVars` de render.yaml y el bloque `env` de
.github/workflows/cola.yml (lo que está entre las marcas «# >>> generado» y «# <<< generado»).
Uso:  python api/generar_config.py            reescribe los dos archivos
      python api/generar_config.py --revisar  no escribe; sale con 1 si alguno está desactualizado (lo usa un test)"""
import os, sys, json

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)
from api.variables_entorno import de_api, de_cola, SECRET

INI, FIN = "# >>> generado", "# <<< generado"
ARCHIVOS = (("render.yaml", 6), (".github/workflows/cola.yml", 10))


def _q(valor):
    return json.dumps(str(valor), ensure_ascii=False)


def bloque_render():
    out = []
    for v in de_api():
        if v["nota"]:
            out.append(f"      # {v['nota']}")
        out.append(f"      - key: {v['nombre']}")
        if v["generar"]:
            out.append("        generateValue: true")
        elif v["valor"] is None:
            out.append("        sync: false")
        else:
            out.append(f"        value: {_q(v['valor'])}")
    return out


def bloque_cola():
    out = []
    for v in de_cola():
        if v["nota"]:
            out.append(f"          # {v['nota']}")
        valor = "${{ secrets." + v["nombre"] + " }}" if v["cola"] == SECRET else _q(v["valor"])
        out.append(f"          {v['nombre']}: {valor}")
    return out


def _aplicar(texto, lineas, sangria):
    a, b = texto.index(INI), texto.index(FIN)
    ini_linea = texto.rfind("\n", 0, a) + 1
    fin_linea = texto.find("\n", b) + 1 or len(texto)
    pad = " " * sangria
    nuevo = [pad + INI + " (api/variables_entorno.py: no editar a mano; correr python api/generar_config.py)"] + lineas + [pad + FIN]
    return texto[:ini_linea] + "\n".join(nuevo) + "\n" + texto[fin_linea:]


def generar():
    """Devuelve {ruta relativa: (texto actual, texto generado)}, ambos con saltos de línea \\n."""
    res = {}
    for (ruta, sangria), lineas in zip(ARCHIVOS, (bloque_render(), bloque_cola())):
        with open(os.path.join(RAIZ, ruta), encoding="utf-8", newline="") as f:
            actual = f.read().replace("\r\n", "\n")
        res[ruta] = (actual, _aplicar(actual, lineas, sangria))
    return res


if __name__ == "__main__":
    cambios = generar()
    desactualizados = [r for r, (a, n) in cambios.items() if a != n]
    if "--revisar" in sys.argv:
        print("Desactualizados:", desactualizados or "ninguno")
        sys.exit(1 if desactualizados else 0)
    for r in desactualizados:
        with open(os.path.join(RAIZ, r), "w", encoding="utf-8", newline="") as f:
            f.write(cambios[r][1])
        print("Actualizado", r)
