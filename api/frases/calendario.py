"""El calendario: lectura (resumen, próximas, backlog, mes, día) y escritura (crear, editar, mover, sacar, intercambiar, repartir, vaciar). (3/11: antes en api/frases_rutas.py; montado bajo /frases por api/frases/__init__.py)."""
import calendar, datetime, logging, os, re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from .. import auth
from . import _comun as c
from ._comun import DIAS, MESES, ESTADO_TXT, Nueva, Edicion, Mover, Intercambio, Reparto, Vaciar, PruebaMail, Activa, Canales, Solicitud, Resolver   # noqa: F401
import db                       # noqa: E402  (api/__init__ pone la raíz del repo en sys.path)
import programar_frases as pf   # noqa: E402
import canales as _canales      # noqa: E402  (hay una ruta llamada `canales` en manana.py)

log = logging.getLogger("api")
router = APIRouter()


@router.get("/resumen")
def resumen(request: Request):
    """La cabecera de frases_ui: conteos, interruptor, hasta cuándo alcanzan las nunca publicadas, qué pasa mañana, avisos."""
    s = auth.sesion(request)
    rol = auth.rol_sesion(s)
    # (2/11) los creadores de contenido también ven el calendario (solo lectura + solicitudes); `aprueba` le dice a la pantalla qué mostrar
    if not db.disponible():
        return {"disponible": False, "admin": rol["admin"], "aprueba": rol["aprueba"], "conteos": {}, "activa": False, "avisos": ["Sin Supabase: no hay frases."]}
    r = db.resumen_frases()
    hoy = c._hoy()
    programadas = [f for f in db.listar_frases(desde=hoy.isoformat()) if f.get("estado") in ("programada", "saltada")]
    r["programadas"] = len(programadas)
    activa = bool(db.obtener_config("frase_activa", False))
    nuevas_prog = [f["fecha"] for f in programadas if not f.get("ultima_publicada")]
    nuevas_backlog = sum(1 for f in db.frases_sin_fecha(solo_validadas=True) if not f.get("ultima_publicada"))
    hasta = None
    if nuevas_prog or nuevas_backlog:
        fin = datetime.date.fromisoformat(max(nuevas_prog)) if nuevas_prog else hoy
        hasta = (fin + datetime.timedelta(days=nuevas_backlog)).isoformat()
    man = hoy + datetime.timedelta(days=1)
    prox = db.frase_del_dia(man.isoformat())
    avisos = []
    if not r.get("total"):
        avisos.append("Todavía no hay frases cargadas. Correr `python importar_frases.py` (lee el Sheet Frases_consolidadas_591).")
    foto_defecto = db.obtener_config("frase_imagen") or None
    if not foto_defecto:
        avisos.append("Falta la foto de fondo por defecto (Administración → Configuración). Sin una foto elegida para el día o una por defecto, la frase de ese día no se encola.")
    # (2/11 tarde, Franco) la tarjeta «Mañana»: una fila por canal con prendido, modo y la pieza de mañana si existe
    canales_on = db.obtener_config("frase_canales") or pf.CANALES_DEFECTO
    try:
        cfg, _pub = c._cfg()
        modos = cfg.resumen()          # (3/11) todos los canales del registro, mail incluido
    except Exception:
        modos = {}
    piezas_man = (prox or {}).get("piezas") or {}
    filas = []
    for k, nombre in pf.CANALES_POSIBLES.items():
        pid = piezas_man.get(k)
        p = db.obtener_publicacion(pid) if pid else None
        filas.append({"canal": k, "nombre": nombre, "prendido": k in canales_on,
                      "modo": modos.get(_canales.canal_de_salida(k)[0], "apagado"),
                      "pieza": {"id": pid, "estado": p.get("estado"), "fecha_programada": p.get("fecha_programada")} if p else None})
    manana = {"fecha": man.isoformat(), "fecha_texto": c._fecha_txt(man), "dia": DIAS[man.weekday()], "frase": c._publica(prox),
              "en_cola": any(f["pieza"] and f["pieza"]["estado"] in ("pendiente", "procesando", "enviando") for f in filas), "canales": filas}
    if activa and not prox:
        avisos.append(f"Mañana ({c._fecha_txt(man)}) no tiene frase asignada: no va a salir nada. Repartí o asigná una.")
    if rol["aprueba"]:
        pendientes = len(db.listar_solicitudes_frase(estado="pendiente"))
    else:
        pendientes = len([x for x in db.listar_solicitudes_frase(usuario=s["usuario"]) if x.get("estado") == "pendiente"])
    return {"disponible": True, "admin": rol["admin"], "aprueba": rol["aprueba"], "solicitudes_pendientes": pendientes,
            "conteos": r, "activa": activa, "hoy": hoy.isoformat(),
            "hora": db.obtener_config("frase_hora", pf.HORA_DEFECTO) or pf.HORA_DEFECTO,
            "canales": db.obtener_config("frase_canales") or pf.CANALES_DEFECTO, "canales_posibles": pf.CANALES_POSIBLES, "foto_defecto": foto_defecto,
            "estilo_opciones": c._estilo_opciones(), "estilo_global": dict(pf.ESTILO_DEFECTO, **(db.obtener_config("frase_estilo") or {})),
            "frases_nuevas_hasta": hasta, "nuevas_sin_dia": nuevas_backlog, "manana": manana, "avisos": avisos}


@router.get("/proximas")
def proximas(dias: int = 14, usuario=Depends(auth.usuario_actual)):
    c._con_db()
    dias = max(1, min(int(dias or 14), 60))
    hoy = c._hoy()
    hasta = hoy + datetime.timedelta(days=dias - 1)
    por_dia = {f["fecha"]: f for f in db.listar_frases(desde=hoy.isoformat(), hasta=hasta.isoformat())}
    out = []
    for i in range(dias):
        d = hoy + datetime.timedelta(days=i)
        out.append({"fecha": d.isoformat(), "dia": DIAS[d.weekday()], "frase": c._publica(por_dia.get(d.isoformat()))})
    return out


@router.get("/backlog")
def backlog(q: str = "", limite: int = 300, usuario=Depends(auth.usuario_actual)):
    """Validadas sin día (asignables) y, aparte, las pendientes de validación de Pato (no asignables)."""
    c._con_db()
    ql = (q or "").strip().lower()
    filtro = (lambda f: (not ql) or ql in (f.get("texto") or "").lower() or ql in (f.get("autor") or "").lower())
    sin = [c._publica(f) for f in db.frases_sin_fecha(solo_validadas=True) if filtro(f)]
    pend = [c._publica(f) for f in db.frases_pendientes_validacion() if filtro(f)]
    limite = max(1, min(int(limite or 300), 2000))
    return {"sin_dia": sin[:limite], "sin_dia_total": len(sin), "pendientes": pend[:limite], "pendientes_total": len(pend)}


@router.get("/mes/{anio}/{mes}")
def mes(anio: int, mes: int, usuario=Depends(auth.usuario_actual)):
    c._con_db()
    if not (1 <= mes <= 12 and 2000 <= anio <= 2100):
        raise HTTPException(400, "Mes inválido.")
    ultimo = calendar.monthrange(anio, mes)[1]
    frases = db.listar_frases(desde=f"{anio:04d}-{mes:02d}-01", hasta=f"{anio:04d}-{mes:02d}-{ultimo:02d}")
    return {"anio": anio, "mes": mes, "dias": ultimo, "hoy": c._hoy().isoformat(),
            "primer_dia_semana": datetime.date(anio, mes, 1).weekday(),
            "frases": {f["fecha"]: c._publica(f) for f in frases if f.get("fecha")}}


@router.get("/dia/{fecha}")
def dia(fecha: str, usuario=Depends(auth.usuario_actual)):
    c._con_db()
    d = c._fecha(fecha)
    f = db.frase_del_dia(d.isoformat())
    out = {"fecha": d.isoformat(), "fecha_texto": c._fecha_txt(d), "dia": DIAS[d.weekday()], "pasado": d < c._hoy(), "frase": c._publica(f), "cola": None, "foto": None}
    if f:
        if f.get("publicacion_id"):
            p = db.obtener_publicacion(f["publicacion_id"])
            if p:
                res = p.get("resultado") or {}
                out["cola"] = {"estado": p.get("estado"), "fecha_programada": p.get("fecha_programada"), "permalink": ((res.get("ultimo") or {}).get("permalink"))}
        try:
            cfg, publicar = c._cfg()
            foto, de_donde = pf.foto_de_fondo(f, cfg, db, publicar)
            out["foto"] = {"url": foto, "de_donde": de_donde}
        except Exception as e:
            out["foto"] = {"url": None, "de_donde": f"no pude ver la foto: {e}"}
    return out


# POST /frases (sin sub-ruta): la registra api/frases/__init__.py con add_api_route, porque un router sin prefijo no admite path vacío
def crear(datos: Nueva, usuario=Depends(auth.aprobador)):
    c._con_db()
    texto = (datos.texto or "").strip()
    if not texto:
        raise HTTPException(400, "Falta el texto de la frase.")
    try:
        fid = db.crear_frase(texto, datos.autor, validada=True, origen="manual")
    except Exception as e:
        raise HTTPException(409, f"No pude agregarla (¿ya existe una igual?): {str(e)[:160]}")
    return {"ok": True, "id": fid, "frase": c._publica(db.obtener_frase(fid))}


@router.patch("/{fid}")
def editar(fid: str, datos: Edicion, usuario=Depends(auth.aprobador)):
    f = c._frase(fid)
    campos = {}
    if datos.texto is not None:
        if not datos.texto.strip():
            raise HTTPException(400, "La frase no puede quedar vacía.")
        campos["texto"] = datos.texto.strip()
    if datos.autor is not None:
        campos["autor"] = datos.autor.strip() or None
    if datos.quitar_imagen:
        campos["imagen_url"] = None
    elif datos.imagen_url is not None:
        u = datos.imagen_url.strip()
        if u and not u.startswith(("http://", "https://")):
            raise HTTPException(400, "La foto tiene que ser una URL (http…).")
        campos["imagen_url"] = u or None
    if datos.quitar_estilo:
        campos["estilo"] = None
    elif datos.estilo is not None:
        import imagen
        validos = {"logo": imagen.LOGOS, "posicion_logo": imagen.POSICIONES_LOGO, "tipografia": imagen.TIPOGRAFIAS,
                   "peso": imagen.PESOS, "posicion": imagen.POSICIONES, "alineacion": imagen.ALINEACIONES}
        limpio = {}
        for k, v in datos.estilo.items():
            if k not in validos:
                raise HTTPException(400, f"Clave de estilo desconocida: {k}.")
            if v in (None, ""):
                continue
            if v not in validos[k]:
                raise HTTPException(400, f"Valor inválido para {k}: {v}.")
            limpio[k] = v
        campos["estilo"] = limpio or None
    if datos.estado is not None:
        if datos.estado not in ("programada", "saltada"):
            raise HTTPException(400, "El estado solo puede ser 'programada' o 'saltada'.")
        if not f.get("fecha"):
            raise HTTPException(409, "Esa frase no tiene día: no se puede saltar.")
        campos["estado"] = datos.estado
    if not campos:
        raise HTTPException(400, "No cambiaste nada.")
    if c._cerrada(f) and any(k in campos for k in ("texto", "autor", "estado", "imagen_url")):
        raise HTTPException(409, "Esta frase ya está en la cola o ya salió: no se edita desde acá. Para frenarla, cancelá la pieza en la cola.")
    try:
        db.actualizar_frase(fid, campos)
    except Exception as e:
        raise HTTPException(409, f"No pude guardar (¿ya existe otra frase con ese texto?): {str(e)[:160]}")
    return {"ok": True, "frase": c._publica(db.obtener_frase(fid))}


@router.post("/{fid}/mover")
def mover(fid: str, datos: Mover, usuario=Depends(auth.aprobador)):
    """A otro día (tiene que estar libre y no ser pasado). Sirve también para asignar una frase sin día."""
    f = c._frase(fid)
    d = c._fecha(datos.fecha)
    if c._cerrada(f):
        raise HTTPException(409, "Esta frase ya está en la cola o ya salió: no se mueve desde acá.")
    if not f.get("validada"):
        raise HTTPException(409, "Esa frase todavía no está validada: no se puede poner en el calendario.")
    if d < c._hoy():
        raise HTTPException(400, "Ese día ya pasó.")
    if f.get("fecha") == d.isoformat():
        raise HTTPException(400, "Ya está en ese día.")
    if not db.mover_frase(fid, d.isoformat()):
        raise HTTPException(409, f"El {c._fecha_txt(d)} ya tiene frase. Usá «Intercambiar» si querés cambiarlas de lugar.")
    if f.get("estado") == "saltada":
        db.actualizar_frase(fid, {"estado": "programada"})
    return {"ok": True, "frase": c._publica(db.obtener_frase(fid)), "mensaje": f"Movida al {c._fecha_txt(d)}."}


@router.post("/{fid}/sacar")
def sacar(fid: str, usuario=Depends(auth.aprobador)):
    f = c._frase(fid)
    if c._cerrada(f):
        raise HTTPException(409, "Esta frase ya está en la cola o ya salió: no se saca desde acá.")
    if not f.get("fecha"):
        raise HTTPException(400, "Esa frase no tiene día.")
    db.actualizar_frase(fid, {"fecha": None, "estado": "programada"})
    return {"ok": True, "frase": c._publica(db.obtener_frase(fid)), "mensaje": "Volvió a «sin día»; el día quedó libre."}


@router.post("/intercambiar")
def intercambiar(datos: Intercambio, usuario=Depends(auth.aprobador)):
    """Las dos se cambian la fecha. Si una no tiene día, es «cambiar por otra» (la del día vuelve a sin día)."""
    a, b = c._frase(datos.id_a), c._frase(datos.id_b)
    if a["id"] == b["id"]:
        raise HTTPException(400, "Son la misma frase.")
    for f in (a, b):
        if c._cerrada(f):
            raise HTTPException(409, "Una de las frases ya está en la cola o ya salió: no se puede intercambiar.")
        if not f.get("validada"):
            raise HTTPException(409, "Una de las frases no está validada: no puede ir al calendario.")
    if not a.get("fecha") and not b.get("fecha"):
        raise HTTPException(400, "Ninguna de las dos tiene día: no hay nada que intercambiar.")
    for f in (a, b):
        if f.get("fecha") and datetime.date.fromisoformat(f["fecha"]) < c._hoy():
            raise HTTPException(400, "Una de las fechas ya pasó.")
    db.intercambiar_frases(a["id"], b["id"])
    na, nb = db.obtener_frase(a["id"]), db.obtener_frase(b["id"])
    for f in (na, nb):
        if f.get("estado") == "saltada" and not f.get("fecha"):
            db.actualizar_frase(f["id"], {"estado": "programada"})
    return {"ok": True, "a": c._publica(na), "b": c._publica(nb), "mensaje": "Intercambiadas."}


@router.post("/repartir")
def repartir(datos: Reparto, usuario=Depends(auth.aprobador)):
    """= «📅 Repartir en el año» (programar_frases.repartir + guardar_reparto): a las candidatas de la rotación les asigna un día cada
    una desde `desde`, sin pisar fechas ocupadas."""
    c._con_db()
    modo = "azar" if datos.modo == "azar" else "orden"
    desde = c._fecha(datos.desde) if datos.desde else c._hoy() + datetime.timedelta(days=1)
    if desde < c._hoy():
        raise HTTPException(400, "La fecha de inicio no puede ser pasada.")
    frases = db.candidatas_rotacion(c._hoy().isoformat())
    ocupadas = db.fechas_ocupadas(desde.isoformat(), (desde + datetime.timedelta(days=3 * 365)).isoformat())
    reparto = pf.repartir(frases, desde, ocupadas, modo)
    n = pf.guardar_reparto(db, reparto)
    ultimo = reparto[-1][1] if reparto else desde
    return {"ok": True, "cantidad": n, "desde": desde.isoformat(), "hasta": ultimo.isoformat(),
            "mensaje": f"Listo: {n} frases repartidas, del {c._fecha_txt(desde)} al {c._fecha_txt(ultimo)}. Las fechas que ya tenían frase no se tocaron."}


@router.post("/vaciar")
def vaciar(datos: Vaciar, usuario=Depends(auth.aprobador)):
    c._con_db()
    if not datos.confirmo:
        raise HTTPException(400, "Hay que confirmar: saca TODAS las frases del calendario que todavía no salieron.")
    n = 0
    for f in db.listar_frases(desde=c._hoy().isoformat()):
        if f.get("estado") in ("programada", "saltada") and f.get("fecha") and not f.get("publicacion_id"):
            db.actualizar_frase(f["id"], {"fecha": None, "estado": "programada"})
            n += 1
    return {"ok": True, "cantidad": n, "mensaje": f"{n} frases volvieron a «sin día». Las que ya están en la cola o salieron no se tocaron."}
