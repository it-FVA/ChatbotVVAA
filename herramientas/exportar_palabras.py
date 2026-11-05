"""
EXPORTAR LAS PALABRAS CON TIEMPOS PARA LOS SUBTÍTULOS DE LOS CLIPS (15/10; movido a herramientas/ el 5/11).
Para cada video del corpus, del crudo de AssemblyAI (<crudos>/<id>.assemblyai.json, que no está en git: 660 MB y
vive en el repo hermano fva-transcripcion) saca solo [palabra, inicio_ms, fin_ms] y lo guarda como
<id>.palabras.json en la carpeta de Drive "VIVIR AGRADECIDOS/chatbot/Videos originales" (la misma de los mp4,
se sincroniza sola). De ahí lo lee recortar_clip.py en GitHub Actions para quemar los subtítulos. Unos 30 KB por video.

Uso: python herramientas/exportar_palabras.py [carpeta_de_crudos] [--destino carpeta]   (salta los que ya están)
Carpeta de crudos: argumento, o variable de entorno FVA_CRUDOS, o ../fva-transcripcion/youtube/crudos.
Destino: --destino, o variable FVA_PALABRAS_DESTINO, o la carpeta de Drive de arriba (la de Drive).
"""
import os, json, glob, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
CRUDOS_DEFAULT = os.path.join(HERE, "..", "..", "fva-transcripcion", "youtube", "crudos")
DESTINO_DEFAULT = r"G:\Mi unidad\VIVIR AGRADECIDOS\chatbot\Videos originales"


def main(crudos=None, destino=None):
    crudos = crudos or os.environ.get("FVA_CRUDOS") or CRUDOS_DEFAULT
    destino = destino or os.environ.get("FVA_PALABRAS_DESTINO") or DESTINO_DEFAULT
    if not os.path.isdir(crudos):
        raise SystemExit(f"No encuentro la carpeta de crudos: {crudos}")
    os.makedirs(destino, exist_ok=True)
    n = ya = sin = 0
    for p in sorted(glob.glob(os.path.join(crudos, "*.assemblyai.json"))):
        vid = os.path.basename(p)[:-len(".assemblyai.json")]
        salida = os.path.join(destino, f"{vid}.palabras.json")
        if os.path.exists(salida):
            ya += 1
            continue
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
        palabras = [[w["text"], w["start"], w["end"]] for w in (d.get("words") or []) if w.get("text")]
        if not palabras:
            sin += 1
            continue
        with open(salida, "w", encoding="utf-8") as f:
            json.dump(palabras, f, ensure_ascii=False, separators=(",", ":"))
        n += 1
    print(f"exportados {n} · ya estaban {ya} · sin palabras {sin}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Exporta las palabras con tiempos (subtítulos de los clips) desde los crudos de AssemblyAI.")
    ap.add_argument("crudos", nargs="?", help="carpeta con los <id>.assemblyai.json (default: FVA_CRUDOS o ../fva-transcripcion/youtube/crudos)")
    ap.add_argument("--destino", help="carpeta donde dejar los <id>.palabras.json (default: FVA_PALABRAS_DESTINO o la de Drive)")
    a = ap.parse_args()
    main(a.crudos, a.destino)
