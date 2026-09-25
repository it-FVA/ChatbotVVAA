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
  - programado: .github/workflows/cola.yml lo ejecuta una vez por hora con los secrets del repo.
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
    pend = db.listar_pendientes(vencidas=True)
    print(f"pendientes vencidas: {len(pend)}")
    for p in pend:
        pid, canal, texto = p["id"], p["canal"], p.get("texto") or ""
        imagen, titulo = p.get("imagen_url"), p.get("titulo") or ""
        intentos = int(p.get("intentos") or 0) + 1
        print(f"- {pid} · {canal} · {p.get('fecha_programada')} · «{(titulo or texto)[:50]}» (intento {intentos})")
        try:
            if canal == "instagram":
                res = publicar.publicar_instagram(cfg, imagen or "", texto, quien="cola")
            elif canal == "facebook":
                res = publicar.publicar_facebook(cfg, imagen, texto, quien="cola")
            elif canal == "wordpress":
                res = publicar.publicar_wordpress(cfg, titulo, texto, quien="cola")
            else:
                res = {"ok": False, "aviso": f"canal desconocido: {canal}"}
        except Exception as e:
            res = {"ok": False, "aviso": f"excepción: {e}"}
        modo = res.get("modo") or r.get(canal, "")
        if res.get("ok") and modo == "real":
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
        if estado != "pendiente":
            campos["procesado_en"] = ahora.isoformat()
        try:
            db.actualizar_publicacion(pid, campos)
        except Exception as e:
            print(f"  ! no pude actualizar la fila: {e}")
        print(f"  → {estado}: {str(res.get('aviso', ''))[:120]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
