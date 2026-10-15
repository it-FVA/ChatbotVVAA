"""
PROCESAR LOS CLIPS PEDIDOS (15/10). Corre en GitHub Actions cada 15 minutos (recortar_pendientes.yml):
lee los pedidos con estado 'pedido' en la tabla clips (los hace la gente desde las tarjetas del chat),
corta cada tramo desde el original en Drive (recortar_clip.py), lo sube a WordPress y deja la URL en
la fila ('listo'); si falla, 'error' con el motivo (se ve en el Panel admin).

Variables de entorno: SUPABASE_URL, SUPABASE_KEY, DRIVE_TOKEN_JSON, WP_SITE, WP_USER, WP_APP_PASSWORD,
PUBLICAR_WORDPRESS. Local: python procesar_clips.py (lee .streamlit/secrets.toml si faltan).
"""
import os, sys, datetime, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def _cargar_config_local():
    if os.environ.get("SUPABASE_URL") and os.environ.get("DRIVE_TOKEN_JSON"):
        return
    p = os.path.join(HERE, ".streamlit", "secrets.toml")
    if os.path.exists(p):
        import tomllib
        for k, v in tomllib.load(open(p, "rb")).items():
            if isinstance(v, str) and k not in os.environ:
                os.environ[k] = v


def main():
    _cargar_config_local()
    import db, publicar, recortar_clip as rc
    pedidos = db.clips_pedidos()
    print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M}] clips pedidos: {len(pedidos)}")
    if not pedidos:
        return 0
    svc = rc._drive()
    cfg = publicar.Config(os.environ)
    ffmpeg = os.environ.get("FFMPEG") or shutil.which("ffmpeg") or "ffmpeg"
    for p in pedidos:
        cid, vid = p["id"], p["video_id"]
        ini, fin, fmt = p["inicio_ms"] / 1000, p["fin_ms"] / 1000, p.get("formato") or "horizontal"
        print(f"- {vid} {ini:.1f}-{fin:.1f} {fmt} (pidió {p.get('pedido_por')})", flush=True)
        try:
            file_id = rc.buscar_original(svc, vid)
            if not file_id:
                # (15/10) sigue en 'pedido' (no 'error'): se vuelve a intentar en cada corrida hasta que el original esté en Drive
                db.actualizar_clip(cid, {"error": "esperando el original en Drive (todavía no se bajó)"})
                print("  → esperando el original en Drive")
                continue
            original = f"original_{vid}.mp4"
            if not os.path.exists(original):
                rc.descargar_drive(svc, file_id, original)
            clip = f"clip-{vid}-{int(ini)}-{int(fin)}{'-vertical' if fmt == 'vertical' else ''}.mp4"
            palabras = rc.buscar_palabras(svc, vid) if rc.quiere_subtitulos(fmt) else None   # (15/10) subtítulos quemados en el vertical
            if rc.cortar(original, clip, ini, fin, ffmpeg, fmt, palabras):
                print("  con subtítulos quemados")
            titulo = (p.get("titulo") or vid)[:120] + f" · {int(ini)}-{int(fin)} s" + (" (vertical)" if fmt == "vertical" else "")
            r = publicar.subir_imagen_wordpress(cfg, open(clip, "rb").read(), clip, titulo=titulo,
                                                etiquetas=["clip-exacto", fmt], quien=p.get("pedido_por") or "cola", pieza=titulo)
            if not r.get("url"):
                raise RuntimeError("WordPress: " + str(r.get("aviso")))
            db.actualizar_clip(cid, {"estado": "listo", "url": r["url"], "procesado_en": datetime.datetime.now(datetime.timezone.utc).isoformat()})
            print("  → listo:", r["url"])
            os.remove(clip)
        except Exception as e:
            db.actualizar_clip(cid, {"estado": "error", "error": str(e)[:300], "procesado_en": datetime.datetime.now(datetime.timezone.utc).isoformat()})
            print("  → error:", e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
