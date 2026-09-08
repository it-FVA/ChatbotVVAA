"""
PROTOTIPO — Penalización por DISTINCIONES.
Usa la tabla de Distinciones de la taxonomía v0.2 (esperanza ≠ expectativa,
gratitud de Br. David ≠ pensamiento positivo, etc.) para que, cuando buscás un
concepto, se BAJEN los pasajes que en realidad hablan del concepto OPUESTO.

Es la mitad (a) del paso 3 — la que tiene datos hoy. La mitad (b), traducir la
consulta al vocabulario de Br. David, queda pendiente hasta que el panel cargue
la columna 'Conceptos relacionados'.

Versión offline con BM25 (no necesita API): sirve para ver el efecto y como
primera versión desplegable. La versión de producción haría lo mismo sobre el
espacio vectorial.

Uso:
    pip install rank_bm25 openpyxl
    python prototipo_distinciones.py
"""
import os, re, json, unicodedata, sys
import numpy as np
from rank_bm25 import BM25Okapi
import openpyxl

# En Windows, al redirigir a un archivo (>) la consola usa cp1252 y se rompe con
# caracteres como → o …. Forzamos UTF-8 para que el guardado a archivo funcione.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
FRAG = os.path.join(HERE, "fragmentos.jsonl")
# la taxonomía puede estar al lado, o en la carpeta de análisis del otro proyecto
TAX_CANDIDATOS = [
    os.path.join(HERE, "Taxonomia_v02_normalizada.xlsx"),
    os.path.join(HERE, "..", "fva-transcripcion", "analisis", "Taxonomia_v02_normalizada.xlsx"),
]

_STOP = set("de la que el en y a los las un una por con para su al lo como mas más o e sus "
            "le les se nos me mi tu si no ni es son ser fue este esta esto del entre sobre "
            "desde hasta muy ya cuando donde porque pero tambien también".split())
def norm(t):
    t = unicodedata.normalize("NFKD", t.lower()); t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9ñ ]+", " ", t)
def tok(t): return [w for w in norm(t).split() if w not in _STOP and len(w) > 2]

def cargar_distinciones():
    path = next((p for p in TAX_CANDIDATOS if os.path.exists(p)), None)
    if not path:
        print("(no encontré la taxonomía; uso un set mínimo de ejemplo)")
        return {"esperanza": "expectativa expectativas", "gratitud": "pensamiento positivo autoayuda"}
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["Distinciones"]
    dist = {}
    for row in list(ws.iter_rows(values_only=True))[1:]:
        c = (row[1] or "").strip() if len(row) > 1 else ""
        opp = (row[2] or "").strip() if len(row) > 2 else ""
        if c and opp and opp.lower() != "none":
            dist[c.lower()] = opp.lower()
    return dist

def linea(frs, i, marca=""):
    r = frs[i]; tag = {"libro": "LIBRO", "youtube": "CLIP", "web": "ARTIC"}.get(r.get("fuente"), "?")
    txt = re.sub(r"\s+", " ", (r.get("texto") or ""))[:88]
    return f"   {marca:3}[{tag}] {(r.get('autor') or '—')[:13]:13} | {txt}"

def main():
    frs = [json.loads(l) for l in open(FRAG, encoding="utf-8")]
    print("Indexando BM25…")
    bm = BM25Okapi([tok(r.get("texto", "")) for r in frs])
    dist = cargar_distinciones()
    print(f"Distinciones cargadas: {len(dist)}\n")

    # concepto -> término(s) opuesto(s) a penalizar
    pruebas = ["esperanza", "gratitud", "confianza", "amor", "ocio"]
    for concepto in pruebas:
        opp = dist.get(concepto)
        if not opp:
            continue
        sc = bm.get_scores(tok(concepto))
        opsc = bm.get_scores(tok(opp))
        cand = list(np.argsort(-sc)[:40])
        # score final: afinidad al concepto menos afinidad al opuesto (penalización)
        mx = max(sc.max(), 1e-9); mo = max(opsc.max(), 1e-9)
        final = {i: sc[i]/mx - 0.6*(opsc[i]/mo) for i in cand}
        antes = cand[:5]
        despues = sorted(cand, key=lambda i: -final[i])[:5]
        bajaron = [i for i in antes if i not in despues]
        print("=" * 92)
        print(f"CONCEPTO: '{concepto}'   (se distingue de → '{opp}')")
        print("  ANTES (solo por parecido a '%s'):" % concepto)
        for i in antes:
            m = "⚠" if opsc[i] > sc[i] else ""
            print(linea(frs, int(i), m))
        print("  DESPUÉS (penalizando lo que habla de '%s'):" % opp)
        for i in despues:
            print(linea(frs, int(i)))
        if bajaron:
            print("  → Se bajaron del top-5:", ", ".join(f"'{re.sub(chr(92)+'s+',' ',(frs[b].get('titulo') or ''))[:30]}'" for b in bajaron))
        print()

if __name__ == "__main__":
    main()
