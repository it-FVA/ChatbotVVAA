"""
MEDIR CON EL SET DORADO — la regla con la que se mide si un cambio del buscador mejora o empeora.

Lee el borrador del set dorado (fva-transcripcion/analisis/Set-dorado-BORRADOR.xlsx - Borrador.csv):
cada consulta tiene uno o más "Título del contenido" esperados (las filas siguientes sin N°
pertenecen a la misma consulta). Para cada modo del buscador corre todas las consultas y cuenta
en cuántas aparece al menos un título esperado entre los primeros N resultados (acierto@N),
y en qué posición apareció el primero.

El título se compara normalizado (sin tildes, minúsculas) y por contención en cualquier
dirección, porque el set dorado escribe "La fe y la esperanza" y el corpus "La fe y la esperanza
(continuación)". Es una medida gruesa pero repetible: sirve para comparar modos, no como nota
absoluta.

Uso (desde la carpeta del repo, con OPENAI_API_KEY y los secrets en .streamlit/secrets.toml):
    python medir_set_dorado.py                       # modos de expansión, sin reranker (determinista)
    python medir_set_dorado.py --con-reranker        # además con el reranker de producción (tiene ruido)
    python medir_set_dorado.py --n 10
    python medir_set_dorado.py --solo-dificiles

Salida: medicion-set-dorado.md en esta carpeta. Cada consulta cuesta una llamada de embedding
(+ traducción cacheada, + reranker si se pide) por modo.
"""
import os, sys, csv, argparse, unicodedata, re
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from comparar_busqueda import _cargar_secrets, MODOS_EXPANSION, poner_modo  # noqa: E402

_cargar_secrets()

SET = os.path.join(HERE, "..", "fva-transcripcion", "analisis", "Set-dorado-BORRADOR.xlsx - Borrador.csv")


def _norm(s):
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", s)).strip()


def leer_set(solo_dificiles=False):
    """[{n, consulta, dificultad, titulos:[...]}]"""
    out, actual = [], None
    with open(SET, encoding="utf-8-sig", newline="") as f:
        for fila in csv.DictReader(f):
            n = (fila.get("N°") or fila.get("Nº") or "").strip()
            titulo = (fila.get("Título del contenido") or "").strip()
            if n:
                actual = {"n": n, "consulta": (fila.get("Consulta") or "").strip(),
                          "dificultad": (fila.get("Dificultad") or "").strip(), "titulos": []}
                out.append(actual)
            if actual is not None and titulo:
                actual["titulos"].append(titulo)
    out = [c for c in out if c["consulta"] and c["titulos"]]
    if solo_dificiles:
        out = [c for c in out if _norm(c["dificultad"]).startswith("dif")]
    return out


def coincide(titulo_esperado, titulo_resultado):
    a, b = _norm(titulo_esperado), _norm(titulo_resultado)
    if not a or not b:
        return False
    return a in b or b in a


def posicion_acierto(esperados, resultados):
    for i, r in enumerate(resultados, 1):
        if any(coincide(t, r.get("titulo") or "") for t in esperados):
            return i
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--con-reranker", action="store_true")
    ap.add_argument("--solo-dificiles", action="store_true")
    ap.add_argument("--autor", default="", help='filtro de autor; vacío = sin filtro (el set dorado mezcla autores)')
    ap.add_argument("--modos", choices=["expansion", "plan"], default="expansion",
                    help="expansion: P/L/X (Conceptos relacionados) · plan: A/B/B2/C del plan del buscador (híbrida, limpieza, reranker ampliado)")
    args = ap.parse_args()
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("Falta OPENAI_API_KEY.")
    if not os.path.exists(SET):
        raise SystemExit(f"No encuentro el set dorado en {SET}")

    import nucleo
    consultas = leer_set(args.solo_dificiles)
    print(f"{len(consultas)} consultas del set dorado · acierto@{args.n}")

    if args.modos == "plan":
        from comparar_busqueda import MODOS
        modos = {k: dict(v, EXPANSION_CONSULTA="0") for k, v in MODOS.items()}
        variantes = [("con reranker", True)]            # estos modos se distinguen justamente por el reranker
    else:
        modos = dict(MODOS_EXPANSION)
        variantes = [("sin reranker", False)] + ([("con reranker", True)] if args.con_reranker else [])
    salida = "medicion-set-dorado.md" if args.modos == "expansion" else "medicion-set-dorado-plan.md"

    tabla = {}      # (modo, variante) -> {"aciertos": int, "pos": [..], "fallas": [n...]}
    detalle = {}    # n -> {(modo, variante): pos}
    for nombre, cfg in modos.items():
        for vnombre, rerank in variantes:
            clave = (nombre, vnombre)
            tabla[clave] = {"aciertos": 0, "pos": [], "fallas": []}
            poner_modo(cfg)
            for c in consultas:
                res = nucleo.buscar(c["consulta"], n=args.n, autor=args.autor or None, rerank=rerank)
                p = posicion_acierto(c["titulos"], res)
                detalle.setdefault(c["n"], {})[clave] = p
                if p:
                    tabla[clave]["aciertos"] += 1
                    tabla[clave]["pos"].append(p)
                else:
                    tabla[clave]["fallas"].append(c["n"])
            t = tabla[clave]
            print(f"  {nombre:36} {vnombre:13} aciertos {t['aciertos']}/{len(consultas)}")

    lineas = [f"# Medición con el set dorado — {datetime.now():%Y-%m-%d %H:%M}", "",
              f"{len(consultas)} consultas{' (solo difíciles)' if args.solo_dificiles else ''} · acierto@{args.n} = "
              "al menos un título esperado entre los primeros resultados · filtro de autor: "
              f"**{args.autor or 'ninguno'}**", "",
              "| Modo | Variante | Aciertos | Posición media del primer acierto |", "|---|---|---|---|"]
    for (m, v), t in tabla.items():
        media = sum(t["pos"]) / len(t["pos"]) if t["pos"] else 0
        lineas.append(f"| {m} | {v} | **{t['aciertos']}/{len(consultas)}** | {media:.2f} |")
    lineas += ["", "## Por consulta (posición del primer acierto; — = no apareció)", "",
               "| N° | Consulta | " + " | ".join(f"{m.split(' ·')[0]} {v.split()[0]}" for m, v in tabla) + " |",
               "|---|---|" + "---|" * len(tabla)]
    for c in consultas:
        celdas = [str(detalle[c["n"]].get(k) or "—") for k in tabla]
        lineas.append(f"| {c['n']} | {c['consulta'][:70]} | " + " | ".join(celdas) + " |")
    lineas += ["", "## Qué cambia entre modos", ""]
    base = next(iter(tabla))
    for k in list(tabla)[1:]:
        gana = [n for n in detalle if detalle[n].get(k) and not detalle[n].get(base)]
        pierde = [n for n in detalle if detalle[n].get(base) and not detalle[n].get(k)]
        lineas.append(f"- **{k[0]} ({k[1]})** vs {base[0]} ({base[1]}): gana {len(gana)} consultas {gana}, pierde {len(pierde)} {pierde}")
    out = os.path.join(HERE, salida)
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas) + "\n")
    poner_modo({"EXPANSION_CONSULTA": os.environ.get("EXPANSION_CONSULTA", "0")})
    print(f"\nInforme: {out}")


if __name__ == "__main__":
    main()
