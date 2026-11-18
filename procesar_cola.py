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
(5/11) Y a banco.sincronizar_desde_config: si hay carpeta de Drive del banco de imágenes (config banco_drive_carpeta), sube lo nuevo a WordPress.
(8/11) Y a metricas.capturar_si_toca: cada hora pide a Meta los números de Instagram y Facebook (no corre con --simular).
(18/11, Franco) Avisos (texto en avisos.py): pieza que falló al publicar (primer error y error definitivo), pieza publicada de
verdad (solo de personas), y una vez por día desde las 08:00 Argentina (_avisos_diarios): calendario de la Frase del día con 5
días o menos con frase, y token de Instagram a 10 días o menos de vencer.
"""
import os, sys, json, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def _cargar_config_local():
    """Fuera de GitHub Actions: toma secrets.toml o clave.env si existen, sin pisar el entorno (secretos.py; avisa si no hay archivo)."""
    import secretos
    secretos.cargar_al_entorno(clave_env=True)


def _avisar_simulada_por_error(p, canal, modo):
    """(17/11) La pieza era real pero el canal está en otro modo en los secrets de GitHub: no salió y nadie se entera.
    Pasó el 17/11 a las 12:01 con el posteo de Facebook de Julián (PUBLICAR_FACEBOOK no estaba en real). Avisa por Slack
    (SLACK_WEBHOOK_URL) y lo deja en el log de la corrida."""
    var = f"PUBLICAR_{canal.upper()}"
    texto = (f"La pieza «{(p.get('titulo') or p.get('texto') or '')[:60]}» de {p.get('usuario') or '?'} para {canal} estaba aprobada "
             f"como real, pero la cola la procesó en modo «{modo or '?'}»: NO salió. Hay que poner {var} = real en GitHub → "
             f"ChatbotVVAA → Settings → Secrets and variables → Actions, y volver a programar la pieza desde la plataforma.")
    print("  !! " + texto)
    try:
        import avisos
        if os.environ.get("SLACK_WEBHOOK_URL"):
            avisos._slack(f"*:warning: Un posteo real quedó en prueba*\n{texto}")
    except Exception as e:
        print(f"  ! no pude avisar por Slack: {e}")


def _avisar_resultado(p, estado, res, intentos):
    """(18/11, Franco) Después de procesar una pieza: si falló, aviso a quien la hizo y a los aprobadores (primer error «se
    reintenta» y error definitivo); si salió de verdad (modo real), aviso a quien la hizo con el link. La Frase del día no avisa al
    publicarse (sale todos los días: sería ruido), pero sí cuando falla. Síncrono: la corrida termina y un hilo no llegaría."""
    try:
        import avisos, db
        res = res if isinstance(res, dict) else {"aviso": str(res)}
        if estado == "error" or (estado == "pendiente" and not res.get("ok") and intentos == 1):   # primer error y definitivo, no el 2.º
            r = avisos.pieza_fallo(db, p, res.get("aviso"), intentos, definitivo=(estado == "error"), sincrono=True)
        elif estado == "publicada" and (p.get("usuario") or "") != FRASE_USUARIO:
            r = avisos.pieza_publicada(db, p, res, sincrono=True)
        else:
            return
        if r:
            print(f"  aviso: " + ", ".join(f"{k} {'ok' if v else 'falló' if v is False else '-'}" for k, v in r.items()))
    except Exception as e:
        print(f"  ! no pude avisar: {type(e).__name__}: {str(e)[:150]}")


FRASE_USUARIO = "frase_del_dia"      # = programar_frases.USUARIO (sin importar el módulo acá: los tests lo reemplazan)
HORA_AVISOS_DIARIOS = 8              # hora Argentina desde la que se revisan los avisos de una vez por día


def dias_con_frase(db, hoy):
    """(18/11) Cuántos días seguidos desde mañana tienen frase asignada (estado programada o saltada) y la fecha del último.
    0 = mañana no tiene (lo mismo que dice la tarjeta «Mañana» del calendario). Devuelve (dias, ultima_fecha)."""
    manana = hoy + datetime.timedelta(days=1)
    con = {f["fecha"][:10] for f in db.listar_frases(desde=manana.isoformat()) if f.get("fecha") and f.get("estado") in ("programada", "saltada")}
    n, d = 0, manana
    while d.isoformat() in con:
        n, d = n + 1, d + datetime.timedelta(days=1)
    return n, (d - datetime.timedelta(days=1)).isoformat() if n else None


def _avisos_diarios(db, ahora=None):
    """Una vez por día (config.avisos_diarios), desde las 08:00 Argentina: (3) la Frase del día con 5 días o menos con frase
    asignada; (4) el token de Instagram a 10 días o menos de vencer (si no se sabe cuándo vence, no avisa). Devuelve líneas para el log."""
    import avisos
    zona = datetime.timezone(datetime.timedelta(hours=-3))
    ahora = (ahora or datetime.datetime.now(datetime.timezone.utc)).astimezone(zona)
    if ahora.hour < HORA_AVISOS_DIARIOS or not os.environ.get("SLACK_WEBHOOK_URL"):
        return []
    hoy = ahora.date()
    out = []
    if avisos.una_vez_por_dia(db, "frases_pocas", hoy):
        if db.obtener_config("frase_activa", False):
            dias, ultima = dias_con_frase(db, hoy)
            if dias <= avisos.FRASES_POCAS_DIAS:
                r = avisos.frases_pocas(dias, ultima)
                avisos.marcar_avisado_hoy(db, "frases_pocas", hoy)
                out.append(f"frases: quedan {dias} días con frase → avisado por Slack ({'ok' if r and r.get('slack') else 'falló'})")
            else:
                out.append(f"frases: quedan {dias} días con frase, sin aviso")
        else:
            out.append("frases: la Frase del día está apagada, sin aviso")
    if avisos.una_vez_por_dia(db, "token_ig", hoy):
        import meta_token
        inf = meta_token.info_token()
        vence = (inf or {}).get("vence")
        if vence is not None:
            dias = (vence - datetime.datetime.now(datetime.timezone.utc)).days
            if dias <= avisos.TOKEN_IG_AVISO_DIAS:
                r = avisos.token_ig_por_vencer(dias, vence)
                avisos.marcar_avisado_hoy(db, "token_ig", hoy)
                out.append(f"token IG: vence en {dias} días → avisado por Slack ({'ok' if r and r.get('slack') else 'falló'})")
            else:
                out.append(f"token IG: vence en {dias} días, sin aviso")
        else:
            out.append("token IG: no se sabe cuándo vence, sin aviso")
    return out


def main():
    _cargar_config_local()
    import canales, db, publicar
    if "--simular" in sys.argv:          # (3/11) TODOS los canales con conector (antes solo WordPress, Instagram y Facebook)
        for k in canales.variables():
            os.environ[k] = "simulado"
    if not db.disponible():
        print("Sin Supabase (SUPABASE_URL / SUPABASE_KEY). Nada que hacer.")
        return 1
    try:   # (5/11) el token de Instagram se renueva solo cuando faltan menos de 30 días
        import meta_token
        meta_token.renovar_token_ig()
    except Exception as e:
        print(f"token IG: error inesperado al renovar: {type(e).__name__}")
    cfg = publicar.Config(os.environ)
    r = cfg.resumen()
    ahora = datetime.datetime.now(datetime.timezone.utc)
    print(f"[{ahora.isoformat(timespec='minutes')}] modos: " + " ".join(f"{k}={v}" for k, v in cfg.modos.items() if k != "newsletter"))
    if not os.environ.get("SUPABASE_KEY_COLA"):
        # (15/10) papelera de conversaciones: borrado definitivo pasados los 30 días. (5/11) Con la clave acotada la cola no toca
        # `conversaciones` (a propósito): lo hace la API al arrancar y una vez por día (api/main.py). Solo queda acá para correr en local.
        try:
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
    try:   # (5/11) presencia: los latidos de más de 10 minutos ya no le sirven a nadie
        n = db.limpiar_viejas()
        if n:
            print(f"presencia: {n} latidos viejos borrados")
    except Exception as e:
        print(f"presencia: no pude limpiar: {e}")
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
        if estado == "simulada" and (p.get("modo") or "") == "real":
            _avisar_simulada_por_error(p, canal, modo)
        _avisar_resultado(p, estado, res, intentos)
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
    try:   # (5/11) banco de imágenes: sube a WordPress lo nuevo de la carpeta de Drive (hasta 30 por corrida). Nunca rompe la cola.
        import banco
        if "--simular" not in sys.argv:
            r = banco.sincronizar_desde_config(cfg)
            if r is not None:
                print(f"banco de imágenes: {r['subidas']} subidas, {r['salteadas']} ya estaban, {r['errores']} con error"
                      + (f", {r['pendientes']} quedan para la próxima" if r["pendientes"] else "")
                      + (f" ({r['simuladas']} simuladas: WordPress no está en modo real)" if r["simuladas"] else ""))
                for d in r["detalle"][:5]:
                    print(f"  ! {d}")
    except Exception as e:
        print(f"banco de imágenes: no pude sincronizar: {type(e).__name__}: {str(e)[:150]}")
    try:   # (18/11, Franco) avisos de una vez por día: frases que se acaban y token de Instagram por vencer. Nunca rompe la cola.
        if "--simular" not in sys.argv:
            for linea in _avisos_diarios(db):
                print(f"avisos diarios: {linea}")
    except Exception as e:
        print(f"avisos diarios: no pude revisar: {type(e).__name__}: {str(e)[:150]}")
    try:   # (8/11, Franco) métricas de Instagram y Facebook: captura si pasó más de 1 hora (las historias pierden sus números a las 24 h). Nunca rompe la cola.
        import metricas
        if "--simular" not in sys.argv:
            m = metricas.capturar_si_toca(cfg)
            if m is not None:
                print("métricas: " + " · ".join(f"{k}: {'ok, ' + str(m[k]['piezas']) + ' piezas' if m[k]['ok'] else m[k]['error']}" for k in ("instagram", "facebook")))
    except Exception as e:
        print(f"métricas: no pude capturar: {type(e).__name__}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
