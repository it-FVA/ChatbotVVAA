"""
programar_frases.py — Encola la «Frase del día» como posteo de Instagram (19/10, reunión: calendario anual).

Corre en la misma pasada que la cola (procesar_cola.py lo llama al final; también se puede correr solo).
Qué hace, en orden:
  1. Cierra el circuito: las frases que ya tienen una fila en la cola (publicacion_id) toman su estado:
     cola 'publicada' → frase 'publicada'; cola 'simulada' → frase 'simulada'; cola 'cancelada'/'error' → la frase
     vuelve a quedar sin fila (se puede volver a encolar o mover).
  2. Si el interruptor `frase_activa` (tabla config) está prendido: para HOY y MAÑANA (hora Argentina), si hay frase
     asignada, en estado 'programada' y sin fila en la cola, arma la imagen (foto de fondo + frase + autor + logo,
     formato cuadrado, con imagen.componer_imagen, el mismo estilo que usa el formulario de publicar), la sube a la
     biblioteca de WordPress (Instagram necesita una URL pública) y deja la pieza en `publicaciones` con estado
     'pendiente' (el estado que lee la cola), **una pieza por canal activo** (config `frase_canales`, hoy ["instagram"];
     facebook también anda porque la cola ya lo publica; el mail será otro canal cuando haya endpoint: se agrega acá y en
     la cola, sin rehacer nada), usuario 'frase_del_dia' y fecha = ese día a la hora `frase_hora` (07:00 por defecto).
     La cola la publica cuando vence, con el modo que tenga PUBLICAR_* en ese momento (simulado = no sale nada).
  3. Rotación (pedido de Franco): si el día no tiene frase, le asigna sola la siguiente de la rotación
     (db.candidatas_rotacion: nunca publicadas primero, después las publicadas de la más antigua a la más reciente),
     así nunca se queda sin frase. Al salir de verdad se guardan ultima_publicada y veces_publicada.
Foto de fondo: la elegida para esa frase (frases.imagen_url) → la por defecto (config frase_imagen) → una del banco
etiquetada «cuadrado» (al azar; 19/10: todavía no hay ninguna). Sin foto, NO se encola: queda anotado en la salida y la
solapa avisa que falta la foto por defecto.

Uso:  python programar_frases.py              (variables del entorno / secrets.toml / clave.env)
      python programar_frases.py --simular    (fuerza Instagram y WordPress a simulado: no sube ni publica nada)
      python programar_frases.py --forzar     (ignora el interruptor frase_activa: para probar en local)
"""
import datetime, os, random, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

USUARIO = "frase_del_dia"
HORA_DEFECTO = "07:00"
CANALES_DEFECTO = ["instagram"]
CANALES_POSIBLES = {"instagram": "Instagram (posteo cuadrado)", "facebook": "Facebook (foto con texto)"}   # "mail": cuando haya endpoint
PIE_DEFECTO = "#FraseDelDía #VivirAgradecidos #Gratitud"
ESTILO_DEFECTO = {"logo": "Amarillo", "posicion_logo": "abajo derecha", "tipografia": None, "posicion": "centro",
                  "alineacion": "centro", "peso": "normal", "formato": "cuadrado"}
ZONA = datetime.timezone(datetime.timedelta(hours=-3))


def hoy_argentina():
    return datetime.datetime.now(ZONA).date()


def caption_de(frase, pie=None):
    """El texto del posteo: la frase, el autor y el pie (hashtags) de config."""
    t = (frase.get("texto") or "").strip()
    if not (t.startswith(("«", "“", '"')) or t.endswith(("»", "”", '"'))):
        t = f"«{t}»"
    partes = [t]
    if frase.get("autor"):
        partes.append(f"— {frase['autor']}")
    pie = PIE_DEFECTO if pie is None else pie
    if pie:
        partes.append(pie)
    return "\n\n".join(partes)


def firma_de(frase):
    return f"— {frase['autor']}" if frase.get("autor") else ""


def foto_de_fondo(frase, cfg, db, publicar):
    """URL de la foto para esta frase, según la prioridad del docstring. (url, de_donde) o (None, aviso)."""
    if frase.get("imagen_url"):
        return frase["imagen_url"], "elegida para la frase"
    defecto = db.obtener_config("frase_imagen")
    if defecto:
        return defecto, "foto por defecto"
    try:   # solo las del banco etiquetadas «cuadrado» (las que carga subir_banco.py); una cualquiera podría ser un retrato o un flyer
        banco = [b for b in publicar.buscar_imagenes_banco(cfg, "cuadrado", n=20) if "cuadrado" in (b.get("titulo") or "").lower()]
    except Exception:
        banco = []
    if banco:
        return random.choice(banco)["url"], "del banco (etiquetada cuadrado), al azar"
    return None, "no hay foto: ni elegida para la frase, ni por defecto (Panel admin → Frase del día → Cómo sale cada día), ni en el banco etiquetada «cuadrado»"


def componer(frase, foto, estilo=None):
    import imagen
    e = dict(ESTILO_DEFECTO, **(estilo or {}))
    return imagen.componer_imagen(foto, frase.get("texto") or "", firma=firma_de(frase), formato=e.get("formato") or "cuadrado",
                                  tipografia=e.get("tipografia"), posicion=e.get("posicion") or "centro",
                                  alineacion=e.get("alineacion") or "centro", peso=e.get("peso") or "normal",
                                  logo=e.get("logo") if e.get("logo") != "Sin logo" else None,
                                  posicion_logo=e.get("posicion_logo") or "abajo derecha")


def encolar_frase(frase, fecha, cfg, db, publicar, hora=None, quien=USUARIO, canales=None):
    """Arma la imagen, la sube a WordPress y deja una pieza por canal en la cola. Devuelve ({canal: publicacion_id}, aviso)."""
    hora = hora or db.obtener_config("frase_hora", HORA_DEFECTO) or HORA_DEFECTO
    canales = [c for c in (canales or db.obtener_config("frase_canales") or CANALES_DEFECTO) if c in CANALES_POSIBLES] or CANALES_DEFECTO
    fecha_iso = f"{fecha.isoformat()}T{hora}:00-03:00"
    foto, de_donde = foto_de_fondo(frase, cfg, db, publicar)
    if not foto:
        return {}, de_donde
    estilo = db.obtener_config("frase_estilo") or {}
    try:
        jpg = componer(frase, foto, estilo)
    except Exception as e:
        return {}, f"no pude componer la imagen: {e}"
    nombre = f"frase-del-dia-{fecha.isoformat()}.jpg"
    res_img = publicar.subir_imagen_wordpress(cfg, jpg, nombre, titulo=f"Frase del día {fecha.strftime('%d/%m/%Y')}",
                                              etiquetas=["frase-del-dia", "pieza-compuesta"], quien=quien,
                                              pieza=(frase.get("texto") or "")[:60])
    imagen_url = res_img.get("url")
    aviso_img = None
    if not imagen_url:
        imagen_url = foto     # WordPress apagado/simulado: va la foto sin la frase encima (igual que el formulario)
        aviso_img = (res_img.get("aviso") or "no se pudo subir la imagen compuesta") + " · sale la foto sin la frase encima"
    pie = db.obtener_config("frase_pie")
    caption = caption_de(frase, pie)
    modos = cfg.resumen()
    piezas = {}
    for canal in canales:
        extra = {"frase_id": frase["id"], "texto_imagen": frase.get("texto"), "formato": "cuadrado", "foto_fondo": foto,
                 "foto_de": de_donde, "frase_del_dia": fecha.isoformat()}
        if aviso_img:
            extra["aviso_imagen"] = aviso_img
        pid = db.encolar_publicacion(quien, canal, modos.get(canal, ""), f"Frase del día {fecha.strftime('%d/%m/%Y')}", caption,
                                     imagen_url, fecha_iso, extra=extra)
        if pid:
            piezas[canal] = pid
    if piezas:
        db.actualizar_frase(frase["id"], {"publicacion_id": piezas.get("instagram") or list(piezas.values())[0],
                                          "piezas": piezas, "estado": "programada"})
    return piezas, (f"encolada para el {fecha_iso[:16].replace('T', ' ')} por {', '.join(piezas)} ({de_donde}"
                    + (f"; {aviso_img}" if aviso_img else "") + ")")


def asignar_siguiente(db, fecha):
    """Rotación: le pone a `fecha` la siguiente frase (nunca publicada primero; después la publicada más antigua). Devuelve la frase o None."""
    for f in db.candidatas_rotacion(hoy_argentina().isoformat()):
        db.actualizar_frase(f["id"], {"fecha": fecha.isoformat(), "estado": "programada", "publicacion_id": None, "piezas": None})
        return db.obtener_frase(f["id"])
    return None


def cerrar_circuito(db):
    """Frases con piezas en la cola: toman el estado de la cola. Publicada de verdad por algún canal → 'publicada' (+ ultima_publicada,
    veces_publicada); todas simuladas → 'simulada'; todas canceladas/error → la frase queda libre para volver a encolarse.
    Devuelve cuántas cambiaron."""
    n = 0
    for f in db.frases_para_marcar_publicadas():
        piezas = f.get("piezas") or ({"instagram": f["publicacion_id"]} if f.get("publicacion_id") else {})
        estados, cuando = {}, None
        for canal, pid in piezas.items():
            p = db.obtener_publicacion(pid)
            estados[canal] = (p or {}).get("estado") or "borrada"
            if p and p.get("estado") == "publicada":
                cuando = p.get("procesado_en") or cuando
        if not estados:
            db.actualizar_frase(f["id"], {"publicacion_id": None, "piezas": None}); n += 1
            continue
        vals = set(estados.values())
        if "publicada" in vals:
            db.actualizar_frase(f["id"], {"estado": "publicada", "ultima_publicada": cuando or db._ahora_iso(),
                                          "veces_publicada": int(f.get("veces_publicada") or 0) + 1}); n += 1
        elif vals <= {"simulada", "cancelada", "error", "borrada"} and "simulada" in vals:
            db.actualizar_frase(f["id"], {"estado": "simulada"}); n += 1
        elif vals <= {"cancelada", "error", "borrada"}:
            db.actualizar_frase(f["id"], {"publicacion_id": None, "piezas": None}); n += 1
    return n


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    from procesar_cola import _cargar_config_local
    _cargar_config_local()
    if "--simular" in argv:
        for k in ("PUBLICAR_INSTAGRAM", "PUBLICAR_WORDPRESS"):
            os.environ[k] = "simulado"
    import db, publicar
    if not db.disponible():
        print("frase del día: sin Supabase, nada que hacer.")
        return 1
    cfg = publicar.Config(os.environ)
    n = cerrar_circuito(db)
    if n:
        print(f"frase del día: {n} frases tomaron el estado de la cola")
    activa = bool(db.obtener_config("frase_activa", False))
    if not activa and "--forzar" not in argv:
        print("frase del día: apagada (config frase_activa). No se encola nada.")
        return 0
    hora = db.obtener_config("frase_hora", HORA_DEFECTO) or HORA_DEFECTO
    hoy = hoy_argentina()
    canales = db.obtener_config("frase_canales") or CANALES_DEFECTO
    print(f"frase del día: activa · hora {hora} · canales {canales} · instagram={cfg.modo_ig} facebook={cfg.modo_fb} wordpress={cfg.modo_wp}")
    for d in (hoy, hoy + datetime.timedelta(days=1)):
        f = db.frase_del_dia(d.isoformat())
        if not f:
            f = asignar_siguiente(db, d)   # rotación: nunca se queda sin frase
            if not f:
                print(f"- {d}: sin frase asignada y no hay ninguna validada para rotar")
                continue
            print(f"- {d}: sin frase: asignada por rotación «{(f.get('texto') or '')[:50]}»"
                  + (f" (ya salió {f['veces_publicada']} vez/veces)" if f.get("veces_publicada") else " (nunca publicada)"))
        if f.get("estado") != "programada" or f.get("publicacion_id"):
            print(f"- {d}: ya está ({f.get('estado')}{', en cola' if f.get('publicacion_id') else ''})")
            continue
        piezas, aviso = encolar_frase(f, d, cfg, db, publicar, hora=hora)
        print(f"- {d}: «{(f.get('texto') or '')[:50]}» → {aviso}" if piezas else f"- {d}: NO encolada: {aviso}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
