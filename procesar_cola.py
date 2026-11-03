"""
procesar_cola.py — Saca de la cola las piezas que ya tienen que salir (25/9).

Lee de Supabase las publicaciones con estado 'pendiente' y fecha_programada <= ahora, y las
publica con publicar.enviar_pieza (el despacho único, registro canales.py) usando el switch por canal que haya EN ESE MOMENTO
en el entorno: PUBLICAR_<CANAL> = apagado | simulado | borrador | real
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
    """Fuera de GitHub Actions: toma secrets.toml o clave.env si existen, sin pisar el entorno (secretos.py; avisa si no hay archivo)."""
    import secretos
    secretos.cargar_al_entorno(clave_env=True)


def main():
    _cargar_config_local()
    import canales, db, publicar
    if "--simular" in sys.argv:          # (3/11) TODOS los canales con conector (antes solo WordPress, Instagram y Facebook)
        for k in canales.variables():
            os.environ[k] = "simulado"
    if not db.disponible():
        print("Sin Supabase (SUPABASE_URL / SUPABASE_KEY). Nada que hacer.")
        return 1
    cfg = publicar.Config(os.environ)
    r = cfg.resumen()
    ahora = datetime.datetime.now(datetime.timezone.utc)
    print(f"[{ahora.isoformat(timespec='minutes')}] modos: " + " ".join(f"{k}={v}" for k, v in cfg.modos.items() if k != "newsletter"))
    try:   # (15/10) papelera de conversaciones: borrado definitivo pasados los 30 días
        n = db.vaciar_papelera_vencida()
        if n:
            print(f"papelera: {n} conversaciones borradas definitivamente (más de {db.PAPELERA_DIAS} días)")
    except Exception as e:
        print(f"papelera: no pude vaciar: {e}")
    try:   # (3/11) una corrida que murió dejó piezas en 'procesando': vuelven a la cola
        for pid in db.liberar_procesando_viejas():
            print(f"- {pid} estaba 'procesando' hace más de 30 min: vuelve a pendiente")
    except Exception as e:
        print(f"no pude revisar las piezas en 'procesando': {e}")
    pend = db.listar_pendientes(vencidas=True)
    print(f"pendientes vencidas: {len(pend)}")
    for p in pend:
        pid, canal, texto = p["id"], p["canal"], p.get("texto") or ""
        imagen, titulo = p.get("imagen_url"), p.get("titulo") or ""
        intentos = int(p.get("intentos") or 0) + 1
        print(f"- {pid} · {canal} · {p.get('fecha_programada')} · «{(titulo or texto)[:50]}» (intento {intentos})")
        try:   # (3/11) se marca 'procesando' ANTES de llamar al conector: si otra corrida se solapa, no la publica dos veces
            if not db.reclamar_publicacion(pid, p.get("resultado")):
                print("  → la tomó otra corrida; la salteo")
                continue
        except Exception as e:
            print(f"  ! no pude marcarla 'procesando' ({e}); no la publico ahora, queda pendiente")
            continue
        try:   # (3/11) un solo despacho por canal para la cola, el envío directo y la aprobación: publicar.enviar_pieza (registro canales.py)
            res = publicar.enviar_pieza(cfg, p, quien="cola")
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
