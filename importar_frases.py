"""
importar_frases.py — Carga el Sheet «Frases_consolidadas_591» en la tabla `frases` de Supabase (19/10).

El Sheet (carpeta maestra de Drive) tiene las columnas Frase · Autor · Fuente · Tema / subtema. No hay una
columna «Validada»: lo que distingue las 491 frases que ya salieron en su momento (validadas de hecho) de las
87 nuevas que esperan el OK de Pato es la columna Fuente: «Frase del día recuperada» = validada;
«Frases de notebook lm» = pendiente. Si algún día agregan una columna Validada (sí/no, x, true…), manda esa.

Se lee con el token de Drive que ya está en los secrets (DRIVE_TOKEN_JSON, solo lectura; el mismo de
subir_banco.py): la hoja no es pública, la URL de export pide login. Exporta como CSV y hace upsert por texto:
correrlo de nuevo actualiza autor/fuente/tema/orden/validada y NO toca fecha, imagen ni estado de las que ya
están en el calendario.

Uso:   python importar_frases.py            (lee .streamlit/secrets.toml o clave.env, como procesar_cola.py)
       python importar_frases.py --csv archivo.csv   (de un CSV ya bajado)
       python importar_frases.py --solo-contar       (no escribe nada)
"""
import csv, io, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
SHEET_ID = "1JBG4m2dBpsoZu5nE8Il1ElqMpEChbyYfixm52NnaN1A"
FUENTE_VALIDADA = "frase del día recuperada"
SI = {"si", "sí", "x", "true", "1", "ok", "validada", "aprobada", "yes"}


def _col(hdr, *nombres):
    bajo = [str(h or "").strip().lower() for h in hdr]
    for n in nombres:
        for i, h in enumerate(bajo):
            if h.startswith(n):
                return i
    return None


def leer_csv(texto):
    """CSV → [{texto, autor, fuente, tema, validada, orden}]."""
    filas = list(csv.reader(io.StringIO(texto.lstrip("\ufeff"))))
    hdr, datos = filas[0], [f for f in filas[1:] if any(c.strip() for c in f)]
    ci_t, ci_a = _col(hdr, "frase", "texto"), _col(hdr, "autor")
    ci_f, ci_tema, ci_v = _col(hdr, "fuente"), _col(hdr, "tema"), _col(hdr, "valid")
    out, vistos = [], set()
    for n, f in enumerate(datos, start=1):
        g = lambda i: (f[i].strip() if i is not None and i < len(f) else "")
        texto = g(ci_t)
        if not texto or texto in vistos:
            continue
        vistos.add(texto)
        fuente = g(ci_f)
        if ci_v is not None:
            validada = g(ci_v).lower() in SI
        else:
            validada = fuente.lower().startswith(FUENTE_VALIDADA)
        out.append({"texto": texto, "autor": g(ci_a) or None, "fuente": fuente or None, "tema": g(ci_tema) or None,
                    "validada": validada, "origen": "sheet", "orden": n})
    return out


def bajar_sheet():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    tok = os.environ.get("DRIVE_TOKEN_JSON", "")
    if not tok:
        raise SystemExit("Falta DRIVE_TOKEN_JSON (el token de Drive de los secrets).")
    creds = Credentials.from_authorized_user_info(json.loads(tok))
    svc = build("drive", "v3", credentials=creds, cache_discovery=False)
    meta = svc.files().get(fileId=SHEET_ID, fields="name,modifiedTime").execute()
    print(f"Sheet «{meta['name']}» (modificado {meta['modifiedTime'][:16]})")
    return svc.files().export(fileId=SHEET_ID, mimeType="text/csv").execute().decode("utf-8-sig")


def main():
    from procesar_cola import _cargar_config_local
    _cargar_config_local()
    if "--csv" in sys.argv:
        texto = open(sys.argv[sys.argv.index("--csv") + 1], encoding="utf-8-sig").read()
    else:
        texto = bajar_sheet()
    frases = leer_csv(texto)
    validadas = sum(1 for f in frases if f["validada"])
    print(f"{len(frases)} frases en el Sheet · {validadas} validadas · {len(frases) - validadas} pendientes de validar")
    if "--solo-contar" in sys.argv:
        return 0
    import db
    if not db.disponible():
        print("Sin Supabase (SUPABASE_URL / SUPABASE_KEY).")
        return 1
    for i in range(0, len(frases), 200):
        db.upsert_frases(frases[i:i + 200])
    r = db.resumen_frases()
    print(f"Tabla frases: {r.get('total')} en total · {r.get('validadas')} validadas · {r.get('con_fecha')} con fecha · "
          f"{r.get('publicadas')} publicadas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
