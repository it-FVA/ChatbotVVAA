"""Arma procedencia.json: las excepciones a mano de procedencia por fragmento (13/11/2026).

La procedencia normal la calcula nucleo.py a partir del campo `autor` (ver nucleo._procedencia_de). Este archivo
guarda lo que no se deduce del autor:
  - «Confiar plenamente en la vida» está firmado entero como Br. David, pero cada capítulo abre con un comentario
    de Alberto Rizzo («N / Título / por Alberto Rizzo» ... «por el Hermano David»), y el libro tiene prólogo, créditos
    y biografías de Rizzo. Se recorre el libro en orden y se marca cada fragmento según dónde cae.
  - Los fragmentos que Pato señaló en la validación de facetas (13/11): una cita de Br. David leída por Andy Saporiti,
    la paráfrasis de Maite Moreno, dos adaptaciones del programa Presencia y una nota del traductor.

Uso: python herramientas/armar_procedencia.py   (escribe procedencia.json en la raíz; se corre de nuevo si cambia el corpus)
"""
import json, os, re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRS = [json.loads(l) for l in open(os.path.join(HERE, "fragmentos.jsonl"), encoding="utf-8")]
out = {}


def marcar(fid, procedencia, autor_real=None, nota=None):
    d = {"procedencia": procedencia}
    if autor_real:
        d["autor_real"] = autor_real
    if nota:
        d["nota"] = nota
    out[fid] = d


# --- 1. Confiar plenamente en la vida: comentarios de Alberto Rizzo ---
rz, hd = re.compile(r"por\s+Alberto\s+Rizzo", re.I), re.compile(r"por\s+el\s+Hermano\s+David", re.I)
libro = [f for f in FRS if f.get("documento_id") == "Confiar plenamente en la vida"]
en_rizzo = True                      # el libro arranca con ficha, créditos y prólogo de Rizzo
for f in libro:
    t = f["texto"]
    m1, m2 = rz.search(t), hd.search(t)
    if m1 and m2:
        kind = "mixta"; en_rizzo = m1.start() > m2.start()
    elif m1:
        kind = "mixta" if m1.start() > 80 else "tercero"; en_rizzo = True
    elif m2:
        kind = "mixta" if m2.start() > 80 else "directa"; en_rizzo = False
    else:
        kind = "tercero" if en_rizzo else "directa"
    if kind == "directa":
        continue
    nota = ("comentario introductorio de Alberto Rizzo" if kind == "tercero" else
            "comentario de Alberto Rizzo y texto de Br. David en el mismo fragmento")
    marcar(f["fragmento_id"], kind, "Alberto Rizzo" if kind == "tercero" else None, nota)
# el prólogo termina con una cita de Br. David entre comillas
for f in libro:
    if f["texto"].startswith("En cada uno de los capítulos, les acerco"):
        marcar(f["fragmento_id"], "mixta", None, "cierre del prólogo de Alberto Rizzo y cita de Br. David")
# biografías, créditos e índice al final: no son palabra de Br. David
for f in libro:
    if (f.get("pagina") or 0) >= 137 or (f.get("pagina") or 99) <= 6:
        marcar(f["fragmento_id"], "tercero", "Alberto Rizzo", "ficha, créditos, biografías o índice del libro")


# --- 2. Lo que señaló Pato (validación de facetas, 13/11) ---
def buscar(cond):
    hits = [f for f in FRS if cond(f)]
    assert len(hits) == 1, f"esperaba 1 fragmento, hay {len(hits)}"
    return hits[0]["fragmento_id"]


marcar(buscar(lambda f: "Umbral del Silencio" in (f.get("titulo") or "") and (f.get("inicio_ms") or -1) // 1000 == 317),
       "cita", "Br. David", "Andy Saporiti lee un texto de Br. David; no está verificado dónde termina la cita")
marcar(buscar(lambda f: "Repensar la Vocaci" in (f.get("titulo") or "") and (f.get("inicio_ms") or -1) // 1000 == 57),
       "tercero", None, "Maite Moreno parafrasea el capítulo sobre la vocación de «Orientación para una vida plena»")
for pref in ("El remedio que proponemos", "Por lo tanto, todo lo que hagamos, incluso nuestro trabajo"):
    marcar(buscar(lambda f, p=pref: "proceso de sanaci" in (f.get("titulo") or "") and f["texto"].startswith(p)),
           "tercero", None, "adapta un texto de Br. David al programa Presencia; no es cita textual")
marcar(buscar(lambda f: f.get("documento_id") == "Orientacion para una vida plena" and f["texto"].startswith("del T.:")),
       "tercero", "Nota del traductor", "nota del traductor, no es texto de Br. David")

with open(os.path.join(HERE, "procedencia.json"), "w", encoding="utf-8") as fh:
    json.dump(out, fh, ensure_ascii=False, indent=1)
from collections import Counter
print(len(out), "fragmentos con excepción:", Counter(v["procedencia"] for v in out.values()))
