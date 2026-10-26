"""
procesar_cola.py — Saca de la cola las piezas que ya tienen que salir (25/9).

Lee de Supabase las publicaciones con estado 'pendiente' y fecha_programada <= ahora, y las
publica con publicar.py usando el switch por canal que haya EN ESE MOMENTO en el entorno:
    PUBLICAR_INSTAGRAM / PUBLICAR_FACEBOOK / PUBLICAR_WORDPRESS = apagado | simulado | borrador | real
Regla dura heredada de publicar.py: sin `real` exacto no se llama a ningún endpoint de publicar.
Resultado por pieza: estado 'publicada' (real), 'simulada' (simulado/borrador) o 'error'; queda
`procesado_en` y `resultado` (respuesta de la API o el aviso). Una pieza con error se reintenta
en la próxima corrida hasta 3 veces; después queda en 'error'.

Corre:
  - solo, desde la terminal:  python procesar_cola.py            (usa las variables del entorno
                              o el clave.env / secrets.toml que encuentre al lado)
  - a modo de prueba:         python procesar_cola.py --simular  (fuerza todos los canales a simulado)
  - programado: .github/workflows/cola.yml lo ejecuta cada 15 min con los secrets del repo.
Al final de cada pasada llama a programar_frases.main() (19/10): la «Frase del día» se encola desde ahí.
"""
import os, sys, json, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def _cargar_config_local():
    """Fuera de GitHub Actions: toma secrets.toml o clave.env si existen, sin pisar el entorno."""
    st = os.path.join(HERE, ".streamlit", "secrets.toml")
    if os.path.exists(st):
        try:
            import toml
            for k, v in toml.load(st).items():
                if isinstance(v, (str, int, float)) and k not in os.environ:
                    os.environ[k] = str(v)
        except Exception:
            pass
    env = os.path.join(HERE, "..", "fva-transcripcion", "clave.env")
    if os.path.exists(env):
        for line in open(env, encoding="utf-8"):
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                if k.strip() not in os.environ:
                    os.environ[k.strip()] = v.strip().strip('"')


def main():
    _cargar_config_local()
    if "--simular" in sys.argv:
        for k in ("PUBLICAR_INSTAGRAM", "PUBLICAR_FACEBOOK", "PUBLICAR_WORDPRESS"):
            os.environ[k] = "simulado"
    import db, publicar
    if not db.disponible():
        print("Sin Supabase (SUPABASE_URL / SUPABASE_KEY). Nada que hacer.")
        return 1
    cfg = publicar.Config(os.environ)
    r = cfg.resumen()
    ahora = datetime.datetime.now(datetime.timezone.utc)
    print(f"[{ahora.isoformat(timespec='minutes')}] modos: wordpress={r['wordpress']} instagram={r['instagram']} facebook={r['facebook']}")
    try:   # (15/10) papelera de conversaciones: borrado definitivo pasados los 30 días
        n = db.vaciar_papelera_vencida()
        if n:
            print(f"papelera: {n} conversaciones borradas definitivamente (más de {db.PAPELERA_DIAS} días)")
    except Exception as e:
        print(f"papelera: no pude vaciar: {e}")
    pend = db.listar_pendientes(vencidas=True)
    print(f"pendientes vencidas: {len(pend)}")
    for p in pend:
        pid, canal, texto = p["id"], p["canal"], p.get("texto") or ""
        imagen, titulo = p.get("imagen_url"), p.get("titulo") or ""
        intentos = int(p.get("intentos") or 0) + 1
        print(f"- {pid} · {canal} · {p.get('fecha_programada')} · «{(titulo or texto)[:50]}» (intento {intentos})")
        video_url = (p.get("resultado") or {}).get("video_url")   # (16/10) pieza de video (recorte)
        try:
            if video_url and canal == "instagram":
                historia = ((p.get("resultado") or {}).get("formato") == "historia")
                res = publicar.publicar_instagram_video(cfg, video_url, texto, quien="cola", historia=historia)
            elif video_url and canal == "facebook":
                res = publicar.publicar_facebook_video(cfg, video_url, texto, quien="cola", titulo=titulo)
            elif video_url and canal == "youtube":
                datos, err = publicar.bajar_bytes(video_url)
                res = ({"ok": False, "aviso": f"no pude bajar el recorte: {err}"} if err else
                       publicar.publicar_youtube(cfg, datos, titulo, texto, quien="cola", nombre_archivo=video_url.rsplit("/", 1)[-1]))
            elif canal == "instagram":
                historia = ((p.get("resultado") or {}).get("formato") == "historia")
                res = publicar.publicar_instagram(cfg, imagen or "", texto, quien="cola", historia=historia)
            elif canal == "facebook":
                res = publicar.publicar_facebook(cfg, imagen, texto, quien="cola")
            elif canal == "mail":
                # (26/10) Frase del día por mail: arma la lista de destinatarios y la pieza queda 'enviando'; las tandas
                # las manda frase_mail.avanzar al final de cada pasada (200 por hora, límite de Perfit)
                import frase_mail, perfit
                res = frase_mail.iniciar(p, db, perfit)
            elif canal == "wordpress":
                # (13/10) piezas aprobadas: la imagen ya está en la biblioteca; va como destacada
                # (16/10) con video_url, el recorte va al principio de la entrada
                res = publicar.publicar_wordpress(cfg, titulo, publicar.html_video(video_url, texto) if video_url else texto, quien="cola",
                                                  imagen_id=publicar.media_id_por_url(cfg, imagen) if imagen else None)
            else:
                res = {"ok": False, "aviso": f"canal desconocido: {canal}"}
        except Exception as e:
            res = {"ok": False, "aviso": f"excepción: {e}"}
        modo = res.get("modo") or r.get(canal, "")
        if res.get("ok") and res.get("estado_cola") == "enviando":
            estado = "enviando"           # mail: sigue en tandas; cierra frase_mail.avanzar
        elif res.get("ok") and modo == "real":
            estado = "publicada"
        elif res.get("ok"):
            estado = "simulada"
        elif intentos >= 3:
            estado = "error"
        else:
            estado = "pendiente"          # se reintenta en la próxima corrida
        campos = {"estado": estado, "intentos": intentos,
                  "resultado": dict((p.get("resultado") or {}), ultimo=res if isinstance(res, dict) else str(res),
                                    modo_al_procesar=modo)}
        if estado not in ("pendiente", "enviando"):
            campos["procesado_en"] = ahora.isoformat()
        try:
            db.actualizar_publicacion(pid, campos)
        except Exception as e:
            print(f"  ! no pude actualizar la fila: {e}")
        print(f"  → {estado}: {str(res.get('aviso', ''))[:120]}")
    try:   # (19/10) Frase del día: cierra el circuito de las ya encoladas y encola la de hoy/mañana si está activa
        import programar_frases
        programar_frases.main(["--simular"] if "--simular" in sys.argv else [])
    except Exception as e:
        print(f"frase del día: no pude programar: {e}")
    try:   # (26/10) Frase del día por mail: la siguiente tanda de las piezas 'mail' en envío (50 por pasada = 200 por hora)
        import frase_mail, perfit
        for x in frase_mail.avanzar(db, perfit):
            print(f"frase por mail: {x['id']} → {x['enviados']} enviados, {x['errores']} errores, quedan {x['quedan']}"
                  + (" · Perfit pidió esperar (429)" if x["limite"] else "") + f" · {x['estado']}")
    except Exception as e:
        print(f"frase por mail: no pude avanzar: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
