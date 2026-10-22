"""
PROCESAR LOS CLIPS PEDIDOS (15/10). Corre en GitHub Actions cada 15 minutos (recortar_pendientes.yml):
lee los pedidos con estado 'pedido' en la tabla clips (los hace la gente desde las tarjetas del chat),
corta cada tramo desde el original en Drive (recortar_clip.py), lo sube a WordPress y deja la URL en
la fila ('listo'); si falla, 'error' con el motivo (se ve en el Panel admin).
(19/10) El SRT que se quemó queda en la fila (clips.srt). Si la persona lo corrigió desde «Mis recortes»
(clips.edicion = {"srt": ...}, estado vuelve a 'pedido'), se quema ese tal cual, se sube el video nuevo y se borra el anterior
de WordPress. (19/10, tarde) El mismo JSON trae "inicio_ms"/"fin_ms" (tramo nuevo: se corta con esos tiempos, en vertical se
rearman los subtítulos desde las palabras salvo que también venga "srt", y al terminar los tiempos pasan a las columnas de la
fila) y "estilo" (tipografía, tamaño, colores, negrita, posición de los subtítulos → recortar_clip.estilo_ass). Los recortes
sin "estilo" usan el estilo por defecto del Panel admin (tabla config, clave 'clips_estilo'); el estilo aplicado queda en
clips.estilo. (21/10) "quitar_pausas" (bool) saca los silencios de más de 0,7 s (recortar_clip.quitar_pausas); al terminar queda en el
mismo JSON la marca "sin_pausas" = {"antes", "despues", "pausas"} y en clips.nota «Sin pausas largas: 53 s → 45 s, 12 pausas».

(21/10, noche; fase 1 de la interfaz propia) "segmentos" = [[a_ms, b_ms], ...] absolutos del original: los pedazos del tramo que se
conservan (el editor visual de la web parte el recorte y saca pedazos del medio); recortar_clip.cortar(segmentos=) los pega. La cola
deja "segmentos_hechos" (los que aplicó) y "timeline" (lo que queda del tramo plano en el video final, en segundos: la web lo usa
para llevar un segundo del reproductor al segundo del original). Si no hay "segmentos", todo sigue igual.

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
    try:
        estilo_defecto = db.obtener_config("clips_estilo")   # (19/10) el del Panel admin; None = rc.ESTILO_DEFECTO
    except Exception as e:
        print("  (no pude leer el estilo por defecto, uso el de siempre:", e, ")")
        estilo_defecto = None
    for p in pedidos:
        cid, vid = p["id"], p["video_id"]
        edicion = p.get("edicion") or {}
        # (19/10, tarde) tramo: el de la edición si la persona lo cambió; si no, el de la fila
        ini_ms = int(edicion["inicio_ms"] if edicion.get("inicio_ms") is not None else p["inicio_ms"])
        fin_ms = int(edicion["fin_ms"] if edicion.get("fin_ms") is not None else p["fin_ms"])
        tramo_cambio = (ini_ms, fin_ms) != (int(p["inicio_ms"]), int(p["fin_ms"]))
        ini, fin, fmt = ini_ms / 1000, fin_ms / 1000, p.get("formato") or "horizontal"
        print(f"- {vid} {ini:.1f}-{fin:.1f} {fmt} (pidió {p.get('pedido_por')})" + (" · tramo nuevo" if tramo_cambio else ""), flush=True)
        try:
            if fin_ms - ini_ms < 1000:
                raise RuntimeError(f"tramo inválido ({ini_ms}-{fin_ms} ms)")
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
            # (19/10) edicion = lo que la persona cambió en «✏️ Editar recorte»: "srt" (subtítulos corregidos, se queman tal cual en el
            # vertical; si no hay, se arman desde <id>.palabras.json como siempre, 15/10, solo en vertical), "inicio_ms"/"fin_ms"
            # (ya aplicados arriba) y "estilo" (si no viene, el por defecto del Panel admin).
            srt_editado = (edicion.get("srt") or "").strip() if fmt == "vertical" else ""
            # (21/10) "quitar_pausas" (bool): sacar los silencios largos (recortar_clip.quitar_pausas). "sin_pausas" es la marca que deja
            # esta cola cuando lo hizo ({"antes", "despues", "pausas"} en segundos): la UI la muestra y acá sirve para saber en qué
            # timeline están los subtítulos corregidos (clips.srt es el del último video; la persona solo edita el texto).
            quitar = bool(edicion.get("quitar_pausas"))
            marca_anterior = edicion.get("sin_pausas")
            # (21/10, noche) "segmentos": pedazos del tramo que se conservan (ms absolutos del original); "segmentos_hechos" es la marca
            # que deja esta cola con los que aplicó. Un ValueError acá (ninguno cae en el tramo) deja la fila en error.
            segmentos = rc.normalizar_segmentos(edicion.get("segmentos"), ini_ms, fin_ms)
            seg_hechos = rc.normalizar_segmentos(edicion.get("segmentos_hechos"), ini_ms, fin_ms) if not tramo_cambio else None
            # ¿el SRT corregido está en la timeline del video que se va a armar? Solo si no cambió nada de lo que la mueve
            timeline_igual = not tramo_cambio and quitar == bool(marca_anterior) and segmentos == seg_hechos
            srt_ya_sin_pausas = descartar_srt = False
            if srt_editado and (marca_anterior or edicion.get("segmentos_hechos")):
                if timeline_igual:
                    srt_ya_sin_pausas = True    # mismo tramo, mismos segmentos, mismas pausas: los tiempos del SRT ya son los del video final
                else:
                    # el SRT corregido está en la timeline de otro video (sin pausas o con otros segmentos) y no sirve para este
                    print("  los subtítulos corregidos eran de otra timeline (pausas o segmentos distintos): se rearman desde las palabras")
                    srt_editado, descartar_srt = "", True
            palabras = None if srt_editado else (rc.buscar_palabras(svc, vid) if rc.quiere_subtitulos(fmt) else None)
            estilo = rc.normalizar_estilo(edicion.get("estilo") or estilo_defecto)
            info = {}
            srt_usado = rc.cortar(original, clip, ini, fin, ffmpeg, fmt, palabras, srt_editado or None, estilo,
                                  quitar_pausas=quitar, srt_ya_sin_pausas=srt_ya_sin_pausas, info=info, segmentos=segmentos)
            if srt_usado:
                print("  con subtítulos quemados" + (" (corregidos a mano)" if srt_editado else "") + f" · estilo {estilo}")
            sp = info.get("sin_pausas")
            if sp:
                print(f"  sin pausas: {sp['antes']:.1f} s → {sp['despues']:.1f} s, {sp['pausas']} pausas")
            sg = info.get("segmentos")
            if sg:
                print(f"  segmentos: {sg['antes']:.1f} s → {sg['despues']:.1f} s, {sg['tramos']} pedazos conservados")
            titulo = (p.get("titulo") or vid)[:120] + f" · {int(ini)}-{int(fin)} s" + (" (vertical)" if fmt == "vertical" else "")
            r = publicar.subir_imagen_wordpress(cfg, open(clip, "rb").read(), clip, titulo=titulo,
                                                etiquetas=["clip-exacto", fmt], quien=p.get("pedido_por") or "cola", pieza=titulo)
            if not r.get("url"):
                raise RuntimeError("WordPress: " + str(r.get("aviso")))
            campos = {"estado": "listo", "url": r["url"], "srt": srt_usado or None, "error": None,
                      "estilo": estilo if srt_usado else None,
                      "procesado_en": datetime.datetime.now(datetime.timezone.utc).isoformat()}
            edicion_nueva = {k: v for k, v in edicion.items() if k not in ("inicio_ms", "fin_ms")} if tramo_cambio else dict(edicion)
            if tramo_cambio:
                # el tramo nuevo pasa a las columnas (la tarjeta muestra el tramo real) y sale del JSON de edición
                campos.update({"inicio_ms": ini_ms, "fin_ms": fin_ms})
            notas = []
            if sg:
                # (21/10, noche) marca de qué segmentos se aplicaron (para saber en qué timeline queda el SRT) y nota
                edicion_nueva["segmentos_hechos"] = edicion.get("segmentos")
                notas.append(f"Pedazos sacados del medio: {sg['antes']:.0f} s → {sg['despues']:.0f} s ({sg['tramos']} tramos conservados)")
            else:
                edicion_nueva.pop("segmentos_hechos", None)
            if sp:
                # (21/10) queda la marca de que este video está sin pausas y la nota con cuánto duró antes y después
                edicion_nueva["sin_pausas"] = sp
                notas.append(f"Sin pausas largas: {sp['antes']:.0f} s → {sp['despues']:.0f} s, {sp['pausas']} pausa{'s' if sp['pausas'] != 1 else ''}"
                             + ("" if sp["pausas"] else " (no había ninguna de más de 0,7 s)"))
            else:
                edicion_nueva.pop("sin_pausas", None)
            if info.get("timeline"):
                edicion_nueva["timeline"] = info["timeline"]   # lo que queda del tramo plano en el video final (segundos)
            else:
                edicion_nueva.pop("timeline", None)
            if notas:
                campos["nota"] = ". ".join(notas)
            if descartar_srt:
                edicion_nueva.pop("srt", None)   # que el editor no vuelva a mostrar (ni a aplicar) un SRT de otra timeline
            if edicion_nueva != edicion:
                campos["edicion"] = edicion_nueva or None
            try:
                db.actualizar_clip(cid, campos)
            except RuntimeError as e:
                if tramo_cambio and ("duplicate" in str(e) or "23505" in str(e)):
                    # ya existe otro recorte con ese mismo tramo y formato (índice clips_tramo_idx): el video nuevo quedó subido, se borra
                    publicar.borrar_media_por_url(cfg, r["url"], quien="cola")
                    raise RuntimeError("ya hay otro recorte con ese mismo tramo y formato; borralo o elegí otro tramo")
                raise
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
