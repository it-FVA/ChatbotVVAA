"""
COMPARAR BÚSQUEDA — para verificar por CONTENIDO, no por número.

Corre las mismas consultas por el buscador de la app tal como está hoy (A) y con
la híbrida prendida (B), y escribe un informe lado a lado con los textos reales
que devuelve cada uno. Lo lee cualquiera: no hace falta ser técnico para ver si
B trae mejores pasajes que A para "esperanza" o "voluntariado".

También sirve de prueba de humo: si termina y escribe el informe, el código
nuevo de nucleo.py no rompe nada. Primero corre una consulta en cada modo y
avisa si algo falla.

Uso (desde la carpeta del repo, con la OPENAI_API_KEY en .streamlit/secrets.toml):
    python comparar_busqueda.py                    # consultas por defecto
    python comparar_busqueda.py --con-reranker     # agrega la columna C: híbrida + reranker ampliado
    python comparar_busqueda.py --consulta "gratitud en el duelo"
    python comparar_busqueda.py --dificiles        # las consultas 'difícil' del set dorado

Salida: comparacion-busqueda.md en esta misma carpeta.

No toca el corpus ni la app: solo llama a nucleo.buscar() con distintas variables
de entorno y anota lo que vuelve. Cada consulta cuesta unas llamadas a OpenAI
(embedding + traducción + reranker) por modo.
"""
import os, sys, csv, argparse, unicodedata, re
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))

# --- secrets.toml -> entorno (igual que servidor.py) ---
def _cargar_secrets():
    p = os.path.join(HERE, ".streamlit", "secrets.toml")
    if not os.path.exists(p):
        return
    try:
        import tomllib
        with open(p, "rb") as f:
            data = tomllib.load(f)
        for k, v in data.items():
            if not isinstance(v, dict):
                os.environ.setdefault(k, str(v))
    except Exception as e:
        print("No pude leer secrets.toml:", e)

_cargar_secrets()

CONSULTAS_DEFAULT = [
    "¿Qué diferencia hace Br. David entre esperanza y expectativa?",
    "Material para una pieza sobre el Día del Voluntariado (servir, gratitud en acción)",
    "¿Qué es la gratuidad y por qué todo es un regalo, según Br. David?",
    "¿En qué se distingue la gratitud del pensamiento positivo o la autoayuda?",
    "¿Qué es la obediencia entendida como escucha?",
    "Material para un posteo sobre el silencio interior",
]

MODOS = {
    "A · como está hoy":               {"BUSQUEDA_HIBRIDA": "0", "LIMPIEZA_EXTRA": "0", "RERANK_CANDIDATOS": "15", "RERANK_CHARS": "150"},
    "B · híbrida":                     {"BUSQUEDA_HIBRIDA": "1", "LIMPIEZA_EXTRA": "0", "RERANK_CANDIDATOS": "15", "RERANK_CHARS": "150"},
    "B2 · híbrida + limpieza":         {"BUSQUEDA_HIBRIDA": "1", "LIMPIEZA_EXTRA": "1", "RERANK_CANDIDATOS": "15", "RERANK_CHARS": "150"},
    "C · híbrida + reranker ampliado": {"BUSQUEDA_HIBRIDA": "1", "LIMPIEZA_EXTRA": "1", "RERANK_CANDIDATOS": "50", "RERANK_CHARS": "400"},
}


def _norm(s):
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower()


def consultas_dificiles():
    """Las consultas marcadas 'difícil' en el set dorado del repo fva-transcripcion."""
    p = os.path.join(HERE, "..", "fva-transcripcion", "analisis", "Set-dorado-BORRADOR.xlsx - Borrador.csv")
    if not os.path.exists(p):
        p = os.path.join(os.path.expanduser("~"), "Downloads", "fva-transcripcion", "analisis",
                         "Set-dorado-BORRADOR.xlsx - Borrador.csv")
    if not os.path.exists(p):
        print("No encuentro el set dorado; uso las consultas por defecto.")
        return CONSULTAS_DEFAULT
    out = []
    with open(p, encoding="utf-8-sig", newline="") as f:
        for fila in csv.DictReader(f):
            n = (fila.get("N°") or fila.get("Nº") or "").strip()
            if n and _norm(fila.get("Dificultad", "")).startswith("dif"):
                out.append(fila["Consulta"].strip())
    return out or CONSULTAS_DEFAULT


def poner_modo(cfg):
    for k, v in cfg.items():
        os.environ[k] = v


def buscar_en_modo(nucleo, consulta, cfg, n, autor):
    poner_modo(cfg)
    return nucleo.buscar(consulta, n=n, autor=autor or None)


def fmt_resultado(i, r, marca):
    texto = re.sub(r"\s+", " ", r.get("texto") or "")[:320]
    return (f"**[{i}]** {marca} `{r['tag']}` · *{r['autor']}* · \"{r['titulo'][:70]}\"  \n"
            f"> {texto}…\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--consulta", action="append", help="una consulta (se puede repetir)")
    ap.add_argument("--dificiles", action="store_true", help="usar las consultas 'difícil' del set dorado")
    ap.add_argument("--con-reranker", action="store_true", help="agregar el modo C")
    ap.add_argument("--n", type=int, default=6, help="resultados por modo (la app usa 6)")
    ap.add_argument("--autor", default="Br. David", help='filtro de autor; "" para no filtrar')
    args = ap.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("Falta OPENAI_API_KEY (en .streamlit/secrets.toml o en el entorno).")

    import nucleo

    modos = dict(MODOS)
    if not args.con_reranker:
        modos.pop("C · híbrida + reranker ampliado")

    consultas = args.consulta or (consultas_dificiles() if args.dificiles else CONSULTAS_DEFAULT)

    # --- prueba de humo: una consulta por modo; si algo revienta, se ve acá ---
    print("Prueba de humo…")
    for nombre, cfg in modos.items():
        try:
            r = buscar_en_modo(nucleo, consultas[0], cfg, args.n, args.autor)
            print(f"  {nombre:34} OK ({len(r)} resultados)")
        except Exception as e:
            print(f"  {nombre:34} FALLÓ: {type(e).__name__}: {e}")
            raise SystemExit("No sigo: el modo de arriba rompe. Pegale este error a Claude.")

    # --- comparación ---
    lineas = [f"# Comparación de búsqueda — {datetime.now():%Y-%m-%d %H:%M}",
              "",
              f"Filtro de autor: **{args.autor or '(ninguno)'}** · {args.n} resultados por modo.",
              "",
              "Cómo leerlo: cada modo lista sus resultados en orden, del más al menos relevante según ese modo. ",
              "**≡** = ese pasaje aparece en todos los modos · **✚** = solo en ese modo · sin marca = en algunos.",
              "La pregunta a responder es una sola: *¿qué columna trae los pasajes que uno usaría ",
              "para armar la pieza?* No hace falta mirar puntajes.",
              ""]

    for q in consultas:
        print(f"\n· {q}")
        res = {}
        for nombre, cfg in modos.items():
            res[nombre] = buscar_en_modo(nucleo, q, cfg, args.n, args.autor)
            print(f"    {nombre:34} {len(res[nombre])} resultados")

        docs_por_modo = {m: {r["doc"] for r in rs} for m, rs in res.items()}
        en_todos = set.intersection(*docs_por_modo.values()) if docs_por_modo else set()

        lineas.append(f"---\n\n## {q}\n")
        for nombre, rs in res.items():
            lineas.append(f"### {nombre}\n")
            if not rs:
                lineas.append("_(sin resultados)_\n")
            for i, r in enumerate(rs, 1):
                otros = [m for m, d in docs_por_modo.items() if m != nombre and r["doc"] in d]
                marca = "≡" if r["doc"] in en_todos else ("✚" if not otros else "")
                lineas.append(fmt_resultado(i, r, marca))
        solo = {m: [r for r in rs if not any(r["doc"] in docs_por_modo[o] for o in docs_por_modo if o != m)]
                for m, rs in res.items()}
        resumen = " · ".join(f"{m.split(' ·')[0]}: {len(v)} propios" for m, v in solo.items())
        lineas.append(f"**Resumen:** {len(en_todos)} pasajes en común · {resumen}\n")

    out = os.path.join(HERE, "comparacion-busqueda.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas))
    poner_modo(MODOS["A · como está hoy"])   # dejar el entorno como estaba
    print(f"\nInforme: {out}")
    print("Abrilo y leé las columnas. La que trae pasajes que sirven, gana.")


if __name__ == "__main__":
    main()
