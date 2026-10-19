"""
PROCESAR LOS CLIPS PEDIDOS (15/10). Corre en GitHub Actions cada 15 minutos (recortar_pendientes.yml):
lee los pedidos con estado 'pedido' en la tabla clips (los hace la gente desde las tarjetas del chat),
corta cada tramo desde el original en Drive (recortar_clip.py), lo sube a WordPress y deja la URL en
la fila ('listo'); si falla, 'error' con el motivo (se ve en el Panel admin).
(19/10) El SRT que se quemó queda en la fila (clips.srt). Si la persona lo corrigió desde «Mis recortes»
(clips.edicion = {"srt": ...}, estado vuelve a 'pedido'), se quema ese tal cual, se sube el video nuevo y se borra el anterior
de WordPress. El mismo JSON va a traer después "inicio_ms"/"fin_ms" (trim) y "estilo" (subtítulos): se aplican acá.

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
            # (19/10) edicion = lo que la persona cambió en «✏️ Editar recorte»: hoy solo "srt" (subtítulos corregidos, se queman
            # tal cual en el vertical); si no hay, se arman desde <id>.palabras.json como siempre (15/10, solo en vertical).
            # Previsto: "inicio_ms"/"fin_ms" (trim) y "estilo" (tipografía/color/tamaño/posición) → pasarlos a rc.cortar.
            edicion = p.get("edicion") or {}
            srt_editado = (edicion.get("srt") or "").strip() if fmt == "vertical" else ""
            palabras = None if srt_editado else (rc.buscar_palabras(svc, vid) if rc.quiere_subtitulos(fmt) else None)
            srt_usado = rc.cortar(original, clip, ini, fin, ffmpeg, fmt, palabras, srt_editado or None)
            if srt_usado:
                print("  con subtítulos quemados" + (" (corregidos a mano)" if srt_editado else ""))
            titulo = (p.get("titulo") or vid)[:120] + f" · {int(ini)}-{int(fin)} s" + (" (vertical)" if fmt == "vertical" else "")
            r = publicar.subir_imagen_wordpress(cfg, open(clip, "rb").read(), clip, titulo=titulo,
                                                etiquetas=["clip-exacto", fmt], quien=p.get("pedido_por") or "cola", pieza=titulo)
            if not r.get("url"):
                raise RuntimeError("WordPress: " + str(r.get("aviso")))
            db.actualizar_clip(cid, {"estado": "listo", "url": r["url"], "srt": srt_usado or None, "error": None,
                                     "procesado_en": datetime.datetime.now(datetime.timezone.utc).isoformat()})
            print("  → listo:", r["url"])
            url_vieja = p.get("url")
            if url_vieja and url_vieja != r["url"]:
                # (19/10) regenerado: el archivo anterior se borra de WordPress para no acumular (ya quedó la URL nueva en la fila)
                ok, aviso = publicar.borrar_media_por_url(cfg, url_vieja, quien="cola")
                print("  archivo anterior:", "borrado" if ok else aviso)
            os.remove(clip)
        except Exception as e:
            db.actualizar_clip(cid, {"estado": "error", "error": str(e)[:300], "procesado_en": datetime.datetime.now(datetime.timezone.utc).isoformat()})
            print("  → error:", e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
