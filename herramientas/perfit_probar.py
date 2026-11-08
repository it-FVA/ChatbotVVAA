"""Prueba del endpoint de métricas por campaña de Perfit (8/11, Franco; análisis analiticas-por-api-2026-11.md: «sin confirmar»).

Corre con PERFIT_API_KEY y PERFIT_CUENTA en el entorno (GitHub Actions → workflow «perfit-probar», o local con las variables). Imprime
SOLO códigos de estado y las claves de las respuestas: nunca la clave ni datos de contactos. Sirve para decidir si Métricas puede
leer aperturas y clics por campaña desde Perfit o si el mail queda con carga a mano.
"""
import json, os, sys, urllib.error, urllib.parse, urllib.request

API = "https://api.myperfit.com/v2"


def pedir(ruta):
    key, cuenta = os.environ.get("PERFIT_API_KEY", "").strip(), os.environ.get("PERFIT_CUENTA", "").strip()
    req = urllib.request.Request(f"{API}/{cuenta}{ruta}", headers={"Authorization": f"Bearer {key}", "Accept": "application/json",
                                                                   "User-Agent": "FVA chatbot (perfit_probar.py)"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "ignore")[:200]


def forma(x, prof=0):
    """La forma de una respuesta sin sus valores (claves y tipos), para no imprimir datos de personas."""
    if isinstance(x, dict):
        return {k: forma(v, prof + 1) for k, v in list(x.items())[:25]}
    if isinstance(x, list):
        return [forma(x[0], prof + 1)] if x else []
    return type(x).__name__


def main():
    if not os.environ.get("PERFIT_API_KEY") or not os.environ.get("PERFIT_CUENTA"):
        print("faltan PERFIT_API_KEY o PERFIT_CUENTA")
        return 1
    st, d = pedir("/campaigns?limit=3&sortby=id&sortdir=desc")
    print("GET /campaigns ->", st)
    if st != 200:
        print(d)
        return 0
    print(" forma:", json.dumps(forma(d), ensure_ascii=False)[:800])
    items = d.get("data") if isinstance(d, dict) else d
    if not items:
        print(" sin campañas en la cuenta")
        return 0
    cid = items[0].get("id")
    for ruta in (f"/campaigns/{cid}/metrics", f"/campaigns/{cid}/stats", f"/campaigns/{cid}/report", f"/campaigns/{cid}"):
        st, d = pedir(ruta)
        print(f"GET {ruta.replace(str(cid), '{id}')} ->", st, "|", json.dumps(forma(d), ensure_ascii=False)[:700] if st == 200 else str(d)[:200])
    st, d = pedir("/automations?limit=3")
    print("GET /automations ->", st, "|", json.dumps(forma(d), ensure_ascii=False)[:400] if st == 200 else str(d)[:200])
    return 0


if __name__ == "__main__":
    sys.exit(main())
