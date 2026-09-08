"""
PROTOTIPO — Búsqueda híbrida (BM25 léxico + vectorial + fusión RRF).
Experimento para comparar, sobre el corpus real, tres formas de recuperar:
  1) VECTORIAL solo (lo que usamos hoy)
  2) BM25 solo (palabra exacta)
  3) HÍBRIDA (fusión RRF de las dos)

No modifica nada del sistema. Es solo para ver diferencias y decidir con ejemplos.

Uso local (desde la carpeta del repo, con el venv que ya tiene 'openai'):
    pip install rank_bm25
    python prototipo_hibrida.py

Necesita la OPENAI_API_KEY en el entorno (o en .streamlit/secrets.toml) para
vectorizar la consulta. Si no está, corre igual mostrando solo BM25.
"""
import os, re, json, unicodedata
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
EMB_MODEL = "text-embedding-3-small"
DIM = 512

# --- credenciales: del entorno o del secrets.toml local ---
def _cargar_key():
    if os.environ.get("OPENAI_API_KEY"):
        return
    try:
        import tomllib
        with open(os.path.join(HERE, ".streamlit", "secrets.toml"), "rb") as f:
            os.environ["OPENAI_API_KEY"] = tomllib.load(f).get("OPENAI_API_KEY", "")
    except Exception:
        pass

# --- normalización de texto para BM25 (minúsculas, sin acentos, sin puntuación) ---
_STOP = set("de la que el en y a los las un una por con para su al lo como mas más "
            "o e su sus le les se nos me mi tu si no ni es son ser fue este esta esto "
            "del entre sobre desde hasta muy ya cuando donde porque pero tambien también".split())

def _norm(t):
    t = unicodedata.normalize("NFKD", t.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9ñ ]+", " ", t)

def _tok(t):
    return [w for w in _norm(t).split() if w not in _STOP and len(w) > 2]

def cargar():
    frs = [json.loads(l) for l in open(os.path.join(HERE, "fragmentos.jsonl"), encoding="utf-8")]
    emb = np.load(os.path.join(HERE, "fragmentos_openai.npy"))
    return frs, emb

def embed(q):
    from openai import OpenAI
    cl = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    v = cl.embeddings.create(model=EMB_MODEL, input=[q], dimensions=DIM).data[0].embedding
    v = np.array(v, dtype=np.float32)
    return v / (np.linalg.norm(v) + 1e-9)

def rrf(rankings, k=60, tope=10):
    """Reciprocal Rank Fusion: fusiona varias listas ordenadas de índices."""
    puntos = {}
    for ranking in rankings:
        for pos, idx in enumerate(ranking):
            puntos[idx] = puntos.get(idx, 0.0) + 1.0 / (k + pos + 1)
    return [i for i, _ in sorted(puntos.items(), key=lambda x: -x[1])[:tope]]

def linea(frs, idx):
    r = frs[idx]
    tag = {"libro": "LIBRO", "youtube": "CLIP", "web": "ARTIC"}.get(r.get("fuente"), r.get("fuente"))
    txt = re.sub(r"\s+", " ", (r.get("texto") or ""))[:95]
    autor = (r.get("autor") or "")[:14]
    titulo = (r.get("titulo") or "")[:34]
    return f"    [{tag}] {autor:14} | {titulo:34} | {txt}"

def main():
    _cargar_key()
    frs, emb = cargar()
    print(f"Corpus: {len(frs)} fragmentos, embeddings {emb.shape}\n")

    # BM25 sobre todo el corpus
    from rank_bm25 import BM25Okapi
    print("Indexando BM25… (una vez)")
    bm25 = BM25Okapi([_tok(r.get("texto", "")) for r in frs])

    hay_key = bool(os.environ.get("OPENAI_API_KEY"))
    consultas = [
        "esperanza (distinta de la expectativa)",
        "día del voluntariado, servir a los demás",
        "gratuidad, todo es regalo",
    ]
    for q in consultas:
        print("\n" + "=" * 100)
        print("CONSULTA:", q)
        bm_scores = bm25.get_scores(_tok(q))
        bm_rank = list(np.argsort(-bm_scores)[:10])

        print("\n  ── BM25 (palabra exacta) ──")
        for i in bm_rank[:5]:
            print(linea(frs, int(i)))

        if hay_key:
            try:
                qv = embed(q)
                sims = emb @ qv
                vec_rank = list(np.argsort(-sims)[:10])
                print("\n  ── VECTORIAL (lo de hoy) ──")
                for i in vec_rank[:5]:
                    print(linea(frs, int(i)))
                hib = rrf([vec_rank, bm_rank])
                print("\n  ── HÍBRIDA (RRF) ──")
                for i in hib[:5]:
                    print(linea(frs, int(i)))
            except Exception as e:
                print("  (no pude vectorizar la consulta:", str(e)[:120], ")")
        else:
            print("\n  (sin OPENAI_API_KEY: muestro solo BM25)")

if __name__ == "__main__":
    main()
