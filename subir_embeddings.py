"""
subir_embeddings.py — Sube los embeddings del corpus a Supabase (pgvector), tabla fragmentos_emb (22/10/2026).

Para qué: que la API pueda buscar con VECTORES=supabase (y LEXICO=supabase) sin tener fragmentos_openai.npy (52 MB)
ni el índice BM25 (245 MB) en memoria. Ver nucleo.py (modo supabase) y api/migraciones/fragmentos_emb_pgvector.sql.

Qué sube, por cada posición idx de fragmentos.jsonl: idx, fragmento_id, documento_id, texto y el vector de 512 de
fragmentos_openai.npy (la columna tsv para la búsqueda léxica la calcula Postgres sola).

Idempotente: upsert por idx (Prefer: resolution=merge-duplicates); se puede cortar y volver a correr. Al final verifica
que el conteo en la tabla sea igual al del corpus y que una muestra de fragmento_id coincida.

Uso (con SUPABASE_URL y SUPABASE_KEY en el entorno o en .streamlit/secrets.toml):
    python subir_embeddings.py                 # sube todo (lotes de 400)
    python subir_embeddings.py --desde 12000   # retoma desde esa posición
    python subir_embeddings.py --verificar     # solo compara conteos y una muestra
"""
import os, sys, json, time, argparse, random, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def _cargar_secrets():
    p = os.path.join(HERE, ".streamlit", "secrets.toml")
    if os.path.exists(p):
        import tomllib
        with open(p, "rb") as f:
            for k, v in tomllib.load(f).items():
                if not isinstance(v, dict):
                    os.environ.setdefault(k, str(v))


def _req(method, path, body=None, headers=None, timeout=120):
    url, key = os.environ["SUPABASE_URL"].rstrip("/"), os.environ["SUPABASE_KEY"]
    h = {"apikey": key, "Authorization": "Bearer " + key, "Content-Type": "application/json"}
    h.update(headers or {})
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(f"{url}/rest/v1/{path}", data=data, method=method, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8"), dict(r.headers)


def contar():
    st, _, h = _req("GET", "fragmentos_emb?select=idx&limit=1", headers={"Prefer": "count=exact", "Range-Unit": "items", "Range": "0-0"})
    rango = h.get("Content-Range") or h.get("content-range") or ""
    return int(rango.split("/")[-1]) if "/" in rango and rango.split("/")[-1] != "*" else -1


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--lote", type=int, default=400)
    ap.add_argument("--desde", type=int, default=0)
    ap.add_argument("--verificar", action="store_true")
    args = ap.parse_args(argv)
    _cargar_secrets()
    if not (os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_KEY")):
        raise SystemExit("Faltan SUPABASE_URL / SUPABASE_KEY.")
    import numpy as np
    frs = [json.loads(l) for l in open(os.path.join(HERE, "fragmentos.jsonl"), encoding="utf-8")]
    emb = np.load(os.path.join(HERE, "fragmentos_openai.npy"))
    assert len(frs) == emb.shape[0], f"el corpus tiene {len(frs)} fragmentos y el .npy {emb.shape[0]} vectores"
    print(f"Corpus: {len(frs)} fragmentos, vectores {emb.shape} {emb.dtype}")

    if not args.verificar:
        t0 = time.time()
        for ini in range(args.desde, len(frs), args.lote):
            fin = min(ini + args.lote, len(frs))
            filas = [{"idx": i, "fragmento_id": frs[i]["fragmento_id"], "documento_id": frs[i].get("documento_id"),
                      "texto": frs[i].get("texto") or "", "embedding": [round(float(x), 7) for x in emb[i]]}
                     for i in range(ini, fin)]
            for intento in range(4):
                try:
                    _req("POST", "fragmentos_emb?on_conflict=idx", filas,
                         headers={"Prefer": "resolution=merge-duplicates,return=minimal"})
                    break
                except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
                    det = e.read().decode("utf-8", "ignore")[:200] if isinstance(e, urllib.error.HTTPError) else str(e)
                    print(f"  lote {ini}-{fin}: fallo {intento + 1}/4: {det}")
                    time.sleep(3 * (intento + 1))
            else:
                raise SystemExit(f"No pude subir el lote {ini}-{fin}. Retomar con --desde {ini}")
            print(f"  {fin}/{len(frs)} ({time.time() - t0:.0f} s)", flush=True)

    # verificación: conteo y una muestra de ids
    n = contar()
    print(f"Filas en fragmentos_emb: {n} · corpus: {len(frs)} · {'OK' if n == len(frs) else 'NO COINCIDE'}")
    muestra = random.Random(7).sample(range(len(frs)), 20)
    st, cuerpo, _ = _req("GET", f"fragmentos_emb?select=idx,fragmento_id&idx=in.({','.join(map(str, muestra))})")
    ids = {f["idx"]: f["fragmento_id"] for f in json.loads(cuerpo)}
    malos = [i for i in muestra if ids.get(i) != frs[i]["fragmento_id"]]
    print(f"Muestra de 20 ids: {'OK' if not malos else 'difieren en ' + str(malos)}")
    if n != len(frs) or malos:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
