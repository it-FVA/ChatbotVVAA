"""Frase del día en la web (22/10): el calendario anual que vivía en el Panel admin de Streamlit (frases_ui.py). MISMA lógica de
negocio: las reglas de rotación, reparto, foto de fondo y composición de la imagen están en programar_frases.py y db.py y se usan tal
cual (no se duplican); acá solo hay validaciones y la forma JSON que dibuja la pantalla `/frase-del-dia`.

Quién: aprobadores y admins (auth.aprobador; pedido de Franco 22/10: no es parte de Administración). El interruptor `frase_activa` y
la configuración de salida (hora, canales, foto por defecto, estilo, pie) son configuración: el interruptor se cambia desde acá solo
siendo admin; lo demás vive en Administración → Configuración (api/admin_rutas.py).

Rutas:
  GET   /frases/resumen                conteos, interruptor, hasta cuándo hay frases nuevas, qué pasa mañana, avisos (cabecera de frases_ui)
  GET   /frases/proximas?dias=14       un renglón por día: fecha, frase (o null) y estado
  GET   /frases/backlog?q=             validadas sin día y pendientes de validación (con buscador)
  GET   /frases/mes/{aaaa}/{mm}        las frases con fecha en ese mes
  GET   /frases/dia/{fecha}            la frase de ese día con su estado en la cola, si está en la cola/salió (cerrada) y la foto que usaría
  GET   /frases/{id}/previa.jpg        la imagen compuesta (programar_frases.componer con la foto de programar_frases.foto_de_fondo);
                                       ?foto=<url> la arma con esa otra foto sin guardar nada (probar / mostrar una propuesta)
  POST  /frases                        {texto, autor}: agregar una frase (validada, sin día)
  PATCH /frases/{id}                   {texto?, autor?, imagen_url?, estado?}: editar texto/autor, foto de fondo (null = la por defecto), saltar/reprogramar
  POST  /frases/{id}/mover             {fecha}: a otro día libre (también asigna una sin día); 409 si está ocupado
  POST  /frases/{id}/sacar             vuelve a «sin día»
  POST  /frases/intercambiar           {id_a, id_b}: se cambian la fecha (si una no tiene día, es «cambiar por otra»)
  POST  /frases/repartir               {modo: orden|azar, desde}: = «Repartir en el año»
  POST  /frases/vaciar                 {confirmo: true}: saca del calendario las que no salieron ni están en la cola
  PUT   /frases/activa                 {activa}: el interruptor (solo admins)
  PUT   /frases/canales                (2/11 tarde, aprobadores) {canales}: por qué canales sale cada día (el checklist de la cabecera; = config frase_canales)
  GET   /frases/mail/estado            (26/10) el canal mail por Perfit: modo, qué falta, la lista, el envío de hoy/mañana y las últimas pruebas
  POST  /frases/mail/prueba            (aprobadores; 2/11 antes solo admins) {fecha?, emails?}: manda la frase de ese día a esos mails ahora
  GET   /frases/mail/previa/{fecha}    (2/11) el mail de ese día armado con la plantilla local (reproducción de la de Perfit): {html, contexto}
  GET   /frases/whatsapp/previa/{fecha} (2/11 tarde) el mensaje al grupo de WhatsApp tal cual saldría (prototipo: texto + imagen embebida, modo)

(2/11, reunión del 2/11) Los creadores de contenido también VEN el calendario (resumen, próximas, mes, día, backlog, vista previa:
auth.usuario_actual) y piden cambios; lo que modifica el calendario sigue siendo de aprobadores:
  GET   /frases/solicitudes            aprobador: las pendientes + las últimas resueltas; creador: las propias
  POST  /frases/solicitudes            {fecha, frase_id? | texto+autor?, imagen_url?, nota?}: «me gustaría que ese día salga esta frase»
                                       y/o «con esta foto de fondo» (2/11 tarde; la foto sola = cambiar la de la frase que ya está ese día)
  POST  /frases/solicitudes/{id}/aceptar   (aprobador) la aplica: crea la frase si es nueva, la mueve al día (o intercambia si está ocupado),
                                       guarda la foto propuesta en la frase
  POST  /frases/solicitudes/{id}/rechazar  (aprobador) {respuesta?}
  POST  /frases/solicitudes/{id}/retirar   (quien la pidió) la saca antes de que la resuelvan
"""
import calendar, datetime, logging, os, re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from . import auth
import db                       # noqa: E402  (api/__init__ pone la raíz del repo en sys.path)
import programar_frases as pf   # noqa: E402

log = logging.getLogger("api")
router = APIRouter(prefix="/frases", tags=["frases"])

ESTADO_TXT = {"programada": "programada", "publicada": "publicada", "simulada": "simulada (la cola la procesó en modo simulado)",
              "saltada": "saltada: ese día no sale nada"}
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


# ---------------- Modelos ----------------
class Nueva(BaseModel):
    texto: str
    autor: str = ""


class Edicion(BaseModel):
    texto: Optional[str] = None
    autor: Optional[str] = None
    imagen_url: Optional[str] = None      # "" o null con `quitar_imagen` = volver a la foto por defecto
    quitar_imagen: bool = False
    estado: Optional[str] = None          # 'programada' | 'saltada'


class Mover(BaseModel):
    fecha: str


class Intercambio(BaseModel):
    id_a: str
    id_b: str


class Reparto(BaseModel):
    modo: str = "orden"
    desde: Optional[str] = None


class Vaciar(BaseModel):
    confirmo: bool = False


class PruebaMail(BaseModel):
    fecha: Optional[str] = None
    emails: Optional[list[str]] = None     # si no vienen, la lista de prueba de config (frase_mail_prueba)


class Activa(BaseModel):
    activa: bool


class Canales(BaseModel):
    canales: list[str]


class Solicitud(BaseModel):
    fecha: str
    frase_id: Optional[str] = None
    texto: Optional[str] = None
    autor: Optional[str] = None
    nota: Optional[str] = None
    imagen_url: Optional[str] = None      # (2/11 tarde) foto de fondo propuesta; sola = cambiar la de la frase que ya está ese día


class Resolver(BaseModel):
    respuesta: Optional[str] = None


# ---------------- Helpers ----------------
def _hoy():
    return pf.hoy_argentina()


def _fecha(s):
    try:
        return datetime.date.fromisoformat(str(s)[:10])
    except Exception:
        raise HTTPException(400, "La fecha tiene que ser AAAA-MM-DD.")


def _fecha_txt(d):
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def _con_db():
    if not db.disponible():
        raise HTTPException(503, "Sin Supabase: no hay frases.")


def _frase(fid):
    _con_db()
    f = db.obtener_frase(fid)
    if not f:
        raise HTTPException(404, "No existe esa frase.")
    return f


def _url_foto(u):
    """Una foto es una URL http(s) (del banco de WordPress o de internet); la misma regla que PATCH /frases/{id}."""
    u = (u or "").strip()
    if u and not u.startswith(("http://", "https://")):
        raise HTTPException(400, "La foto tiene que ser una URL (http…).")
    return u or None


def _cerrada(f):
    """frases_ui: una frase que ya está en la cola o ya salió no se mueve ni se edita desde acá."""
    return (f.get("estado") in ("publicada", "simulada")) or bool(f.get("publicacion_id"))


def _publica(f):
    """La frase como la dibuja la pantalla (texto, autor, estado, rotación, foto)."""
    if not f:
        return None
    return {"id": f["id"], "texto": f.get("texto") or "", "autor": f.get("autor"), "fecha": f.get("fecha"), "estado": f.get("estado") or "programada",
            "estado_texto": ESTADO_TXT.get(f.get("estado") or "programada", f.get("estado")), "validada": bool(f.get("validada")),
            "imagen_url": f.get("imagen_url"), "publicacion_id": f.get("publicacion_id"), "fuente": f.get("fuente"), "tema": f.get("tema"),
            "orden": f.get("orden"), "ultima_publicada": f.get("ultima_publicada"), "veces_publicada": int(f.get("veces_publicada") or 0),
            "repetida": bool(f.get("ultima_publicada")), "cerrada": _cerrada(f)}


def _cfg():
    import os
    import publicar
    return publicar.Config(os.environ), publicar


# ---------------- Lectura ----------------
@router.get("/resumen")
def resumen(request: Request):
    """La cabecera de frases_ui: conteos, interruptor, hasta cuándo alcanzan las nunca publicadas, qué pasa mañana, avisos."""
    s = auth.sesion(request)
    rol = auth.rol_sesion(s)
    # (2/11) los creadores de contenido también ven el calendario (solo lectura + solicitudes); `aprueba` le dice a la pantalla qué mostrar
    if not db.disponible():
        return {"disponible": False, "admin": rol["admin"], "aprueba": rol["aprueba"], "conteos": {}, "activa": False, "avisos": ["Sin Supabase: no hay frases."]}
    r = db.resumen_frases()
    hoy = _hoy()
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
    manana = {"fecha": man.isoformat(), "fecha_texto": _fecha_txt(man), "frase": _publica(prox),
              "en_cola": bool(prox and prox.get("publicacion_id"))}
    if activa and not prox:
        avisos.append(f"Mañana ({_fecha_txt(man)}) no tiene frase asignada: no va a salir nada. Repartí o asigná una.")
    if rol["aprueba"]:
        pendientes = len(db.listar_solicitudes_frase(estado="pendiente"))
    else:
        pendientes = len([x for x in db.listar_solicitudes_frase(usuario=s["usuario"]) if x.get("estado") == "pendiente"])
    return {"disponible": True, "admin": rol["admin"], "aprueba": rol["aprueba"], "solicitudes_pendientes": pendientes,
            "conteos": r, "activa": activa, "hoy": hoy.isoformat(),
            "hora": db.obtener_config("frase_hora", pf.HORA_DEFECTO) or pf.HORA_DEFECTO,
            "canales": db.obtener_config("frase_canales") or pf.CANALES_DEFECTO, "canales_posibles": pf.CANALES_POSIBLES, "foto_defecto": foto_defecto,
            "frases_nuevas_hasta": hasta, "nuevas_sin_dia": nuevas_backlog, "manana": manana, "avisos": avisos}


@router.get("/proximas")
def proximas(dias: int = 14, usuario=Depends(auth.usuario_actual)):
    _con_db()
    dias = max(1, min(int(dias or 14), 60))
    hoy = _hoy()
    hasta = hoy + datetime.timedelta(days=dias - 1)
    por_dia = {f["fecha"]: f for f in db.listar_frases(desde=hoy.isoformat(), hasta=hasta.isoformat())}
    out = []
    for i in range(dias):
        d = hoy + datetime.timedelta(days=i)
        out.append({"fecha": d.isoformat(), "dia": DIAS[d.weekday()], "frase": _publica(por_dia.get(d.isoformat()))})
    return out


@router.get("/backlog")
def backlog(q: str = "", limite: int = 300, usuario=Depends(auth.usuario_actual)):
    """Validadas sin día (asignables) y, aparte, las pendientes de validación de Pato (no asignables)."""
    _con_db()
    ql = (q or "").strip().lower()
    filtro = (lambda f: (not ql) or ql in (f.get("texto") or "").lower() or ql in (f.get("autor") or "").lower())
    sin = [_publica(f) for f in db.frases_sin_fecha(solo_validadas=True) if filtro(f)]
    pend = [_publica(f) for f in db.frases_pendientes_validacion() if filtro(f)]
    limite = max(1, min(int(limite or 300), 2000))
    return {"sin_dia": sin[:limite], "sin_dia_total": len(sin), "pendientes": pend[:limite], "pendientes_total": len(pend)}


@router.get("/mes/{anio}/{mes}")
def mes(anio: int, mes: int, usuario=Depends(auth.usuario_actual)):
    _con_db()
    if not (1 <= mes <= 12 and 2000 <= anio <= 2100):
        raise HTTPException(400, "Mes inválido.")
    ultimo = calendar.monthrange(anio, mes)[1]
    frases = db.listar_frases(desde=f"{anio:04d}-{mes:02d}-01", hasta=f"{anio:04d}-{mes:02d}-{ultimo:02d}")
    return {"anio": anio, "mes": mes, "dias": ultimo, "hoy": _hoy().isoformat(),
            "primer_dia_semana": datetime.date(anio, mes, 1).weekday(),
            "frases": {f["fecha"]: _publica(f) for f in frases if f.get("fecha")}}


@router.get("/dia/{fecha}")
def dia(fecha: str, usuario=Depends(auth.usuario_actual)):
    _con_db()
    d = _fecha(fecha)
    f = db.frase_del_dia(d.isoformat())
    out = {"fecha": d.isoformat(), "fecha_texto": _fecha_txt(d), "dia": DIAS[d.weekday()], "pasado": d < _hoy(), "frase": _publica(f), "cola": None, "foto": None}
    if f:
        if f.get("publicacion_id"):
            p = db.obtener_publicacion(f["publicacion_id"])
            if p:
                res = p.get("resultado") or {}
                out["cola"] = {"estado": p.get("estado"), "fecha_programada": p.get("fecha_programada"), "permalink": ((res.get("ultimo") or {}).get("permalink"))}
        try:
            cfg, publicar = _cfg()
            foto, de_donde = pf.foto_de_fondo(f, cfg, db, publicar)
            out["foto"] = {"url": foto, "de_donde": de_donde}
        except Exception as e:
            out["foto"] = {"url": None, "de_donde": f"no pude ver la foto: {e}"}
    return out


@router.get("/{fid}/previa.jpg")
def previa(fid: str, foto: str = "", usuario=Depends(auth.usuario_actual)):
    """La imagen compuesta chica (frase + autor + logo sobre la foto), como va a salir (frases_ui._vista_previa).
    Con ?foto=<url> la compone con esa foto en vez de la guardada (2/11 tarde: ver cómo quedaría una propuesta)."""
    f = _frase(fid)
    cfg, publicar = _cfg()
    if _url_foto(foto):
        foto, de_donde = _url_foto(foto), "propuesta (no guardada)"
    else:
        foto, de_donde = pf.foto_de_fondo(f, cfg, db, publicar)
    if not foto:
        raise HTTPException(404, "Sin foto para la vista previa: elegí una para la frase o cargá una por defecto en Configuración.")
    try:
        jpg = pf.componer(f, foto, db.obtener_config("frase_estilo") or {})
    except Exception as e:
        raise HTTPException(502, f"No pude armar la vista previa: {e}")
    return Response(jpg, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=300", "X-Foto-De": de_donde.encode("ascii", "ignore").decode()})


# ---------------- Escritura ----------------
@router.post("", status_code=201)
def crear(datos: Nueva, usuario=Depends(auth.aprobador)):
    _con_db()
    texto = (datos.texto or "").strip()
    if not texto:
        raise HTTPException(400, "Falta el texto de la frase.")
    try:
        fid = db.crear_frase(texto, datos.autor, validada=True, origen="manual")
    except Exception as e:
        raise HTTPException(409, f"No pude agregarla (¿ya existe una igual?): {str(e)[:160]}")
    return {"ok": True, "id": fid, "frase": _publica(db.obtener_frase(fid))}


@router.patch("/{fid}")
def editar(fid: str, datos: Edicion, usuario=Depends(auth.aprobador)):
    f = _frase(fid)
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
    if datos.estado is not None:
        if datos.estado not in ("programada", "saltada"):
            raise HTTPException(400, "El estado solo puede ser 'programada' o 'saltada'.")
        if not f.get("fecha"):
            raise HTTPException(409, "Esa frase no tiene día: no se puede saltar.")
        campos["estado"] = datos.estado
    if not campos:
        raise HTTPException(400, "No cambiaste nada.")
    if _cerrada(f) and any(k in campos for k in ("texto", "autor", "estado", "imagen_url")):
        raise HTTPException(409, "Esta frase ya está en la cola o ya salió: no se edita desde acá. Para frenarla, cancelá la pieza en la cola.")
    try:
        db.actualizar_frase(fid, campos)
    except Exception as e:
        raise HTTPException(409, f"No pude guardar (¿ya existe otra frase con ese texto?): {str(e)[:160]}")
    return {"ok": True, "frase": _publica(db.obtener_frase(fid))}


@router.post("/{fid}/mover")
def mover(fid: str, datos: Mover, usuario=Depends(auth.aprobador)):
    """A otro día (tiene que estar libre y no ser pasado). Sirve también para asignar una frase sin día."""
    f = _frase(fid)
    d = _fecha(datos.fecha)
    if _cerrada(f):
        raise HTTPException(409, "Esta frase ya está en la cola o ya salió: no se mueve desde acá.")
    if not f.get("validada"):
        raise HTTPException(409, "Esa frase todavía no está validada: no se puede poner en el calendario.")
    if d < _hoy():
        raise HTTPException(400, "Ese día ya pasó.")
    if f.get("fecha") == d.isoformat():
        raise HTTPException(400, "Ya está en ese día.")
    if not db.mover_frase(fid, d.isoformat()):
        raise HTTPException(409, f"El {_fecha_txt(d)} ya tiene frase. Usá «Intercambiar» si querés cambiarlas de lugar.")
    if f.get("estado") == "saltada":
        db.actualizar_frase(fid, {"estado": "programada"})
    return {"ok": True, "frase": _publica(db.obtener_frase(fid)), "mensaje": f"Movida al {_fecha_txt(d)}."}


@router.post("/{fid}/sacar")
def sacar(fid: str, usuario=Depends(auth.aprobador)):
    f = _frase(fid)
    if _cerrada(f):
        raise HTTPException(409, "Esta frase ya está en la cola o ya salió: no se saca desde acá.")
    if not f.get("fecha"):
        raise HTTPException(400, "Esa frase no tiene día.")
    db.actualizar_frase(fid, {"fecha": None, "estado": "programada"})
    return {"ok": True, "frase": _publica(db.obtener_frase(fid)), "mensaje": "Volvió a «sin día»; el día quedó libre."}


@router.post("/intercambiar")
def intercambiar(datos: Intercambio, usuario=Depends(auth.aprobador)):
    """Las dos se cambian la fecha. Si una no tiene día, es «cambiar por otra» (la del día vuelve a sin día)."""
    a, b = _frase(datos.id_a), _frase(datos.id_b)
    if a["id"] == b["id"]:
        raise HTTPException(400, "Son la misma frase.")
    for f in (a, b):
        if _cerrada(f):
            raise HTTPException(409, "Una de las frases ya está en la cola o ya salió: no se puede intercambiar.")
        if not f.get("validada"):
            raise HTTPException(409, "Una de las frases no está validada: no puede ir al calendario.")
    if not a.get("fecha") and not b.get("fecha"):
        raise HTTPException(400, "Ninguna de las dos tiene día: no hay nada que intercambiar.")
    for f in (a, b):
        if f.get("fecha") and datetime.date.fromisoformat(f["fecha"]) < _hoy():
            raise HTTPException(400, "Una de las fechas ya pasó.")
    db.intercambiar_frases(a["id"], b["id"])
    na, nb = db.obtener_frase(a["id"]), db.obtener_frase(b["id"])
    for f in (na, nb):
        if f.get("estado") == "saltada" and not f.get("fecha"):
            db.actualizar_frase(f["id"], {"estado": "programada"})
    return {"ok": True, "a": _publica(na), "b": _publica(nb), "mensaje": "Intercambiadas."}


@router.post("/repartir")
def repartir(datos: Reparto, usuario=Depends(auth.aprobador)):
    """= «📅 Repartir en el año» (programar_frases.repartir + guardar_reparto): a las candidatas de la rotación les asigna un día cada
    una desde `desde`, sin pisar fechas ocupadas."""
    _con_db()
    modo = "azar" if datos.modo == "azar" else "orden"
    desde = _fecha(datos.desde) if datos.desde else _hoy() + datetime.timedelta(days=1)
    if desde < _hoy():
        raise HTTPException(400, "La fecha de inicio no puede ser pasada.")
    frases = db.candidatas_rotacion(_hoy().isoformat())
    ocupadas = db.fechas_ocupadas(desde.isoformat(), (desde + datetime.timedelta(days=3 * 365)).isoformat())
    reparto = pf.repartir(frases, desde, ocupadas, modo)
    n = pf.guardar_reparto(db, reparto)
    ultimo = reparto[-1][1] if reparto else desde
    return {"ok": True, "cantidad": n, "desde": desde.isoformat(), "hasta": ultimo.isoformat(),
            "mensaje": f"Listo: {n} frases repartidas, del {_fecha_txt(desde)} al {_fecha_txt(ultimo)}. Las fechas que ya tenían frase no se tocaron."}


@router.post("/vaciar")
def vaciar(datos: Vaciar, usuario=Depends(auth.aprobador)):
    _con_db()
    if not datos.confirmo:
        raise HTTPException(400, "Hay que confirmar: saca TODAS las frases del calendario que todavía no salieron.")
    n = 0
    for f in db.listar_frases(desde=_hoy().isoformat()):
        if f.get("estado") in ("programada", "saltada") and f.get("fecha") and not f.get("publicacion_id"):
            db.actualizar_frase(f["id"], {"fecha": None, "estado": "programada"})
            n += 1
    return {"ok": True, "cantidad": n, "mensaje": f"{n} frases volvieron a «sin día». Las que ya están en la cola o salieron no se tocaron."}


@router.put("/activa")
def activa(datos: Activa, usuario=Depends(auth.admin)):
    """El interruptor «Frase del día activa». Es configuración (config frase_activa): solo admins."""
    _con_db()
    db.guardar_config("frase_activa", bool(datos.activa), usuario)
    return {"ok": True, "activa": bool(datos.activa), "mensaje": "Frase del día " + ("activada: cada mañana sale la frase de ese día." if datos.activa else "apagada: el calendario se arma igual pero no sale nada.")}


# ---------------- (26/10) Frase del día por mail, con el custom trigger de Perfit ----------------
@router.put("/canales")
def canales(datos: Canales, quien=Depends(auth.aprobador)):
    """(2/11, Franco) Por qué canales sale la frase cada día, desde la cabecera de Frase del día (antes solo en Configuración, admins).
    Misma regla que admin_rutas: canales válidos, al menos uno, en el orden de CANALES_POSIBLES."""
    _con_db()
    elegidos = [c for c in pf.CANALES_POSIBLES if c in datos.canales]
    if not elegidos:
        raise HTTPException(400, "Dejá al menos un canal prendido (o apagá la Frase del día con el interruptor).")
    db.guardar_config("frase_canales", elegidos, quien)
    corto = {"historia": "historia de Instagram", "instagram": "posteo de Instagram", "facebook": "Facebook", "mail": "mail", "home": "sitio web", "whatsapp": "WhatsApp"}
    return {"ok": True, "canales": elegidos, "mensaje": "Sale por " + ", ".join(corto.get(c, c) for c in elegidos) + ". Vale desde la próxima frase que se encole; la de mañana, si ya está en la cola, suma los canales nuevos en la próxima pasada."}


def _imagen_publica_para(f, fecha, cfg, publicar):
    """La URL pública de la imagen compuesta de esa frase: la de la pieza en cola si existe; si no, la compone y la sube a WordPress
    (en WordPress simulado/apagado, va la foto de fondo sola, igual que hace la cola)."""
    piezas = f.get("piezas") or {}
    for canal in ("mail", "instagram", "facebook", "historia"):
        pid = piezas.get(canal)
        if pid:
            p = db.obtener_publicacion(pid)
            if p and p.get("imagen_url"):
                return p["imagen_url"], f"la pieza {canal} en cola"
    foto, de_donde = pf.foto_de_fondo(f, cfg, db, publicar)
    if not foto:
        raise HTTPException(409, "Sin foto para la frase: elegí una o cargá una por defecto en Configuración.")
    try:
        jpg = pf.componer(f, foto, db.obtener_config("frase_estilo") or {})
    except Exception as e:
        raise HTTPException(502, f"No pude componer la imagen: {e}")
    r = publicar.subir_imagen_wordpress(cfg, jpg, f"frase-del-dia-{str(fecha)[:10]}-prueba.jpg", titulo=f"Frase del día {str(fecha)[:10]} (prueba de mail)",
                                        etiquetas=["frase-del-dia", "pieza-compuesta", "prueba"], quien="prueba-mail", pieza=(f.get("texto") or "")[:60])
    if r.get("url"):
        return r["url"], "compuesta y subida a WordPress para la prueba"
    return foto, "la foto de fondo sola (WordPress en modo " + str(r.get("modo")) + ")"


@router.get("/mail/estado")
def mail_estado(usuario=Depends(auth.usuario_actual)):
    """Cómo está el canal mail: modo, qué secretos faltan, la lista de Perfit, el envío de hoy y mañana (tandas) y las últimas pruebas."""
    _con_db()
    import perfit
    est = perfit.probar_conexion()
    hoy = _hoy()
    man = hoy + datetime.timedelta(days=1)
    envios = {}
    for d in (hoy, man):
        f = db.frase_del_dia(d.isoformat())
        pid = ((f or {}).get("piezas") or {}).get("mail")
        p = db.obtener_publicacion(pid) if pid else None
        envios[d.isoformat()] = {"fecha_texto": _fecha_txt(d), "frase": _publica(f) if f else None, "pieza": pid,
                                 "estado": (p or {}).get("estado"), "arranca": (p or {}).get("fecha_programada"),
                                 "conteo": db.resumen_envios(pid) if pid else None}
    canales = db.obtener_config("frase_canales") or pf.CANALES_DEFECTO
    pruebas = db.ultimos_envios(limite=30, prueba=True)
    return {"modo": est["modo"], "faltan": est["faltan"], "lista": est["lista"], "error": est["error"],
            "canal_prendido": "mail" in canales, "inicio": db.obtener_config("frase_mail_inicio", pf.MAIL_INICIO_DEFECTO) or pf.MAIL_INICIO_DEFECTO,
            "lista_prueba": db.obtener_config("frase_mail_prueba") or [], "trigger_key": os.environ.get("PERFIT_TRIGGER_KEY") or perfit.TRIGGER_KEY_DEFECTO,
            "limite_por_hora": perfit.LIMITE_POR_HORA, "envios": envios, "pruebas": pruebas,
            "contexto_plantilla": ["frase", "autor", "fuente", "url", "fecha", "imagen_url", "fecha_iso", "fecha_texto", "pie", "link"]}


@router.post("/mail/prueba")
def mail_prueba(datos: PruebaMail, request: Request, quien=Depends(auth.aprobador)):
    """Manda la frase del día (o de `fecha`) a los mails de prueba, ya mismo. En modo simulado registra pero no manda."""
    _con_db()
    import perfit, frase_mail
    fecha = (datos.fecha or _hoy().isoformat())[:10]
    try:
        datetime.date.fromisoformat(fecha)
    except ValueError:
        raise HTTPException(400, "La fecha tiene que ser AAAA-MM-DD.")
    f = db.frase_del_dia(fecha)
    if not f:
        raise HTTPException(404, f"El {fecha} no tiene frase asignada.")
    emails = datos.emails if datos.emails else (db.obtener_config("frase_mail_prueba") or [])
    emails = [e.strip().lower() for e in emails if isinstance(e, str) and "@" in e]
    if not emails:
        raise HTTPException(400, "No hay mails de prueba: cargalos en Administración → Configuración → Frase del día, o mandalos en el pedido.")
    cfg, publicar = _cfg()
    imagen_url, de_donde = _imagen_publica_para(f, fecha, cfg, publicar)
    r = frase_mail.enviar_prueba(f, fecha, imagen_url, emails, db, perfit, pie=db.obtener_config("frase_pie"))
    r["imagen_de"] = de_donde
    r["quien"] = quien
    if datos.emails:
        db.guardar_config("frase_mail_prueba", emails, quien)
    return r


# ---------------- Solicitudes de cambio (2/11): los creadores piden, los aprobadores resuelven ----------------
def _solicitud_publica(x, frases=None):
    """La solicitud con la frase pedida (si existe) y la que hoy ocupa ese día, para que la pantalla muestre el cambio completo."""
    frases = frases if frases is not None else {}
    fid = x.get("frase_id")
    if fid and fid not in frases:
        frases[fid] = db.obtener_frase(fid)
    fecha = str(x.get("fecha"))[:10]
    if ("dia:" + fecha) not in frases:
        frases["dia:" + fecha] = db.frase_del_dia(fecha)
    d = datetime.date.fromisoformat(fecha)
    return {"id": x["id"], "creado": x.get("creado"), "usuario": x.get("usuario"), "fecha": fecha, "fecha_texto": f"{DIAS[d.weekday()]} {_fecha_txt(d)}",
            "frase": _publica(frases.get(fid)) if fid else None, "texto": x.get("texto"), "autor": x.get("autor"), "nota": x.get("nota"),
            "imagen_url": x.get("imagen_url"), "solo_foto": bool(x.get("imagen_url")) and not fid and not (x.get("texto") or "").strip(),
            "estado": x.get("estado"), "resuelta_por": x.get("resuelta_por"), "resuelta_en": x.get("resuelta_en"), "respuesta": x.get("respuesta"),
            "actual": _publica(frases.get("dia:" + fecha)), "pasado": d < _hoy()}


@router.get("/solicitudes")
def solicitudes(request: Request):
    s = auth.sesion(request)
    rol = auth.rol_sesion(s)
    _con_db()
    cache = {}
    if rol["aprueba"]:
        pend = db.listar_solicitudes_frase(estado="pendiente")
        otras = [x for x in db.listar_solicitudes_frase(limite=60) if x.get("estado") != "pendiente"][:30]
        return {"aprueba": True, "pendientes": [_solicitud_publica(x, cache) for x in pend], "resueltas": [_solicitud_publica(x, cache) for x in otras]}
    mias = db.listar_solicitudes_frase(usuario=s["usuario"], limite=60)
    return {"aprueba": False, "pendientes": [_solicitud_publica(x, cache) for x in mias if x.get("estado") == "pendiente"],
            "resueltas": [_solicitud_publica(x, cache) for x in mias if x.get("estado") != "pendiente"]}


@router.post("/solicitudes", status_code=201)
def solicitar(datos: Solicitud, usuario=Depends(auth.usuario_actual)):
    """«Me gustaría que el <día> salga esta frase»: una validada que ya existe (del backlog o de otro día) o una nueva (texto + autor).
    (2/11 tarde) Y/o «con esta foto de fondo»: imagen_url sola cambia la foto de la frase que ya está ese día."""
    _con_db()
    d = _fecha(datos.fecha)
    if d <= _hoy():
        raise HTTPException(400, "Pedí un cambio para mañana en adelante: la frase de hoy ya está en marcha.")
    actual = db.frase_del_dia(d.isoformat())
    if actual and _cerrada(actual):
        raise HTTPException(409, f"La frase del {_fecha_txt(d)} ya está en la cola o ya salió: ese día no se puede cambiar.")
    texto = (datos.texto or "").strip()
    fid = (datos.frase_id or "").strip() or None
    imagen = _url_foto(datos.imagen_url)
    if fid:
        f = _frase(fid)
        if not f.get("validada"):
            raise HTTPException(409, "Esa frase todavía no está validada.")
        if f.get("fecha") == d.isoformat():
            raise HTTPException(400, "Esa frase ya está en ese día.")
        if _cerrada(f):
            raise HTTPException(409, "Esa frase ya está en la cola o ya salió: no se puede mover.")
        texto = None
    elif texto:
        pass
    elif imagen and actual:
        texto = None      # solo la foto, para la frase que ya está ese día
    elif imagen:
        raise HTTPException(400, "Ese día no tiene frase todavía: elegí también cuál querés que salga con esa foto.")
    else:
        raise HTTPException(400, "Elegí una frase de la lista, escribí una nueva o proponé una foto de fondo.")
    sid = db.crear_solicitud_frase(usuario, d.isoformat(), frase_id=fid, texto=texto, autor=(datos.autor or "").strip() or None, nota=(datos.nota or "").strip() or None,
                                   imagen_url=imagen)
    if not sid:
        raise HTTPException(503, "No pude guardar la solicitud.")
    return {"ok": True, "id": sid, "solicitud": _solicitud_publica(db.obtener_solicitud_frase(sid)),
            "mensaje": f"Pedido para el {_fecha_txt(d)}. Lo ve quien aprueba la Frase del día; te avisamos acá cuando lo resuelva."}


def _solicitud_pendiente(sid):
    x = db.obtener_solicitud_frase(sid)
    if not x:
        raise HTTPException(404, "No existe esa solicitud.")
    if x.get("estado") != "pendiente":
        raise HTTPException(409, f"Esa solicitud ya está {x.get('estado')}.")
    return x


@router.post("/solicitudes/{sid}/aceptar")
def aceptar_solicitud(sid: str, datos: Resolver, quien=Depends(auth.aprobador)):
    """La aplica al calendario con las mismas reglas que mover / intercambiar / crear, y la marca aceptada."""
    _con_db()
    x = _solicitud_pendiente(sid)
    d = datetime.date.fromisoformat(str(x["fecha"])[:10])
    if d < _hoy():
        raise HTTPException(409, "Ese día ya pasó: rechazala o pedí otra fecha.")
    actual = db.frase_del_dia(d.isoformat())
    if actual and _cerrada(actual):
        raise HTTPException(409, f"La frase del {_fecha_txt(d)} ya está en la cola o ya salió: no se puede cambiar.")
    fid = x.get("frase_id")
    solo_foto = not fid and not (x.get("texto") or "").strip() and bool(x.get("imagen_url"))
    if solo_foto:
        if not actual:
            raise HTTPException(409, "Ese día ya no tiene frase: la foto propuesta era para la que estaba. Rechazala o asigná una frase primero.")
        fid = actual["id"]
    if not fid:
        try:
            fid = db.crear_frase((x.get("texto") or "").strip(), x.get("autor"), validada=True, origen=f"solicitud:{x.get('usuario')}")
        except Exception as e:
            raise HTTPException(409, f"No pude crear la frase (¿ya existe una igual?): {str(e)[:160]}")
    f = _frase(fid)
    if _cerrada(f):
        raise HTTPException(409, "La frase pedida ya está en la cola o ya salió: no se puede mover.")
    if f.get("fecha") != d.isoformat():
        if actual:
            db.intercambiar_frases(fid, actual["id"])
            na = db.obtener_frase(actual["id"])
            if na.get("estado") == "saltada" and not na.get("fecha"):
                db.actualizar_frase(na["id"], {"estado": "programada"})
        else:
            db.mover_frase(fid, d.isoformat())
    if f.get("estado") == "saltada":
        db.actualizar_frase(fid, {"estado": "programada"})
    if x.get("imagen_url"):
        db.actualizar_frase(fid, {"imagen_url": x["imagen_url"]})
    db.actualizar_solicitud_frase(sid, {"estado": "aceptada", "resuelta_por": quien, "resuelta_en": db._ahora_iso(), "respuesta": (datos.respuesta or "").strip() or None, "frase_id": fid})
    if solo_foto:
        return {"ok": True, "solicitud": _solicitud_publica(db.obtener_solicitud_frase(sid)), "mensaje": f"Aceptada: la frase del {_fecha_txt(d)} sale con la foto propuesta."}
    que = "intercambiada con la que estaba" if actual and f.get("fecha") not in (None, d.isoformat()) else ("puesta en lugar de la que estaba (que volvió al backlog)" if actual else "asignada")
    con_foto = " y con la foto propuesta" if x.get("imagen_url") else ""
    return {"ok": True, "solicitud": _solicitud_publica(db.obtener_solicitud_frase(sid)), "mensaje": f"Aceptada: la frase quedó {que} el {_fecha_txt(d)}{con_foto}."}


@router.post("/solicitudes/{sid}/rechazar")
def rechazar_solicitud(sid: str, datos: Resolver, quien=Depends(auth.aprobador)):
    _con_db()
    _solicitud_pendiente(sid)
    db.actualizar_solicitud_frase(sid, {"estado": "rechazada", "resuelta_por": quien, "resuelta_en": db._ahora_iso(), "respuesta": (datos.respuesta or "").strip() or None})
    return {"ok": True, "solicitud": _solicitud_publica(db.obtener_solicitud_frase(sid)), "mensaje": "Rechazada. Quien la pidió ve tu respuesta en su lista."}


@router.post("/solicitudes/{sid}/retirar")
def retirar_solicitud(sid: str, usuario=Depends(auth.usuario_actual)):
    _con_db()
    x = _solicitud_pendiente(sid)
    if x.get("usuario") != usuario:
        raise HTTPException(403, "Esa solicitud es de otra persona.")
    db.actualizar_solicitud_frase(sid, {"estado": "retirada", "resuelta_por": usuario, "resuelta_en": db._ahora_iso()})
    return {"ok": True, "mensaje": "Retirada."}


# ---------------- (2/11 tarde) Prototipo WhatsApp: cómo saldría la frase en el grupo ----------------
@router.get("/whatsapp/previa/{fecha}")
def whatsapp_previa(fecha: str, usuario=Depends(auth.usuario_actual)):
    """El mensaje al grupo de la comunidad tal cual se mandaría (publicar.mensaje_whatsapp + la imagen compuesta embebida).
    Prototipo de la reunión del 2/11: todavía no hay forma de mandar desde la cuenta común; el modo lo dice."""
    import base64
    _con_db()
    d = _fecha(fecha)
    f = db.frase_del_dia(d.isoformat())
    if not f:
        raise HTTPException(404, f"El {_fecha_txt(d)} no tiene frase asignada.")
    cfg, publicar = _cfg()
    imagen, de_donde = "", "sin foto"
    try:
        foto, de_donde = pf.foto_de_fondo(f, cfg, db, publicar)
        if foto:
            jpg = pf.componer(f, foto, db.obtener_config("frase_estilo") or {})
            imagen = "data:image/jpeg;base64," + base64.b64encode(jpg).decode("ascii")
    except Exception as e:
        de_donde = f"no pude componer la imagen: {e}"
    pid = ((f.get("piezas") or {}).get("whatsapp"))
    p = db.obtener_publicacion(pid) if pid else None
    canales = db.obtener_config("frase_canales") or pf.CANALES_DEFECTO
    return {"fecha": d.isoformat(), "fecha_texto": _fecha_txt(d), "texto": publicar.mensaje_whatsapp(f.get("texto"), f.get("autor")),
            "imagen": imagen, "imagen_de": de_donde, "grupo": os.environ.get("WHATSAPP_GRUPO") or "Comunidad Vivir Agradecidos",
            "modo": cfg.modo_wa, "canal_prendido": "whatsapp" in canales, "frase": _publica(f),
            "pieza": {"id": pid, "estado": p.get("estado"), "fecha_programada": p.get("fecha_programada")} if p else None,
            "aviso": ("Prototipo: así saldría en el grupo. Por ahora no se manda: la cuenta común de la fundación no tiene API "
                      "(la reunión descartó WhatsApp Business). Cuando se defina cómo mandar, se prende el modo real sin cambiar esta pantalla.")}


# ---------------- Vista previa del mail (2/11, pedido de Alberto y Julián) ----------------
PLANTILLA_MAIL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "distribucion", "frase_mail_plantilla.html")


@router.get("/mail/previa/{fecha}")
def mail_previa(fecha: str, usuario=Depends(auth.usuario_actual)):
    """El mail de la frase de ese día, armado acá con `distribucion/frase_mail_plantilla.html` y el MISMO contexto que recibe la
    automation de Perfit (frase_mail.contexto_de). Es una reproducción: el mail real lo arma Perfit con su plantilla; para verlo
    exacto está «Probar el mail». La imagen va embebida (data:) para que la vista previa no dependa de WordPress."""
    import base64, html as html_mod
    import frase_mail
    _con_db()
    d = _fecha(fecha)
    f = db.frase_del_dia(d.isoformat())
    if not f:
        raise HTTPException(404, f"El {_fecha_txt(d)} no tiene frase asignada.")
    cfg, publicar = _cfg()
    imagen = ""
    de_donde = "sin foto"
    try:
        foto, de_donde = pf.foto_de_fondo(f, cfg, db, publicar)
        if foto:
            jpg = pf.componer(f, foto, db.obtener_config("frase_estilo") or {})
            imagen = "data:image/jpeg;base64," + base64.b64encode(jpg).decode("ascii")
    except Exception as e:
        de_donde = f"no pude componer la imagen: {e}"
    ctx = frase_mail.contexto_de(f, d.isoformat(), imagen, pie=db.obtener_config("frase_pie"))
    try:
        plantilla = open(PLANTILLA_MAIL, encoding="utf-8").read()
    except OSError:
        raise HTTPException(500, "Falta distribucion/frase_mail_plantilla.html.")
    salida = re.sub(r"\$\{(\w+)\}", lambda m: (ctx.get(m.group(1), "") if m.group(1) == "imagen_url" else html_mod.escape(str(ctx.get(m.group(1), "")))), plantilla)
    publico = dict(ctx, imagen_url=("(imagen compuesta)" if imagen else ""))
    return {"fecha": d.isoformat(), "fecha_texto": _fecha_txt(d), "html": salida, "contexto": publico, "imagen_de": de_donde,
            "asunto": f"Frase del día · {ctx['fecha_texto']}", "frase": _publica(f),
            "aviso": "Reproducción con la plantilla local y los mismos datos que recibe Perfit. El mail real lo arma la automation de Perfit; para verlo exacto, mandá una prueba."}
