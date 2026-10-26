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
  GET   /frases/{id}/previa.jpg        la imagen compuesta (programar_frases.componer con la foto de programar_frases.foto_de_fondo)
  POST  /frases                        {texto, autor}: agregar una frase (validada, sin día)
  PATCH /frases/{id}                   {texto?, autor?, imagen_url?, estado?}: editar texto/autor, foto de fondo (null = la por defecto), saltar/reprogramar
  POST  /frases/{id}/mover             {fecha}: a otro día libre (también asigna una sin día); 409 si está ocupado
  POST  /frases/{id}/sacar             vuelve a «sin día»
  POST  /frases/intercambiar           {id_a, id_b}: se cambian la fecha (si una no tiene día, es «cambiar por otra»)
  POST  /frases/repartir               {modo: orden|azar, desde}: = «Repartir en el año»
  POST  /frases/vaciar                 {confirmo: true}: saca del calendario las que no salieron ni están en la cola
  PUT   /frases/activa                 {activa}: el interruptor (solo admins)
  GET   /frases/mail/estado            (26/10) el canal mail por Perfit: modo, qué falta, la lista, el envío de hoy/mañana y las últimas pruebas
  POST  /frases/mail/prueba            (admins) {fecha?, emails?}: manda la frase de ese día (hoy) a esos mails ahora, con el custom trigger
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
    if not rol["aprueba"]:
        raise HTTPException(403, "Solo para aprobadores.")
    if not db.disponible():
        return {"disponible": False, "admin": rol["admin"], "conteos": {}, "activa": False, "avisos": ["Sin Supabase: no hay frases."]}
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
    return {"disponible": True, "admin": rol["admin"], "conteos": r, "activa": activa, "hoy": hoy.isoformat(),
            "hora": db.obtener_config("frase_hora", pf.HORA_DEFECTO) or pf.HORA_DEFECTO,
            "canales": db.obtener_config("frase_canales") or pf.CANALES_DEFECTO, "foto_defecto": foto_defecto,
            "frases_nuevas_hasta": hasta, "nuevas_sin_dia": nuevas_backlog, "manana": manana, "avisos": avisos}


@router.get("/proximas")
def proximas(dias: int = 14, usuario=Depends(auth.aprobador)):
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
def backlog(q: str = "", limite: int = 300, usuario=Depends(auth.aprobador)):
    """Validadas sin día (asignables) y, aparte, las pendientes de validación de Pato (no asignables)."""
    _con_db()
    ql = (q or "").strip().lower()
    filtro = (lambda f: (not ql) or ql in (f.get("texto") or "").lower() or ql in (f.get("autor") or "").lower())
    sin = [_publica(f) for f in db.frases_sin_fecha(solo_validadas=True) if filtro(f)]
    pend = [_publica(f) for f in db.frases_pendientes_validacion() if filtro(f)]
    limite = max(1, min(int(limite or 300), 2000))
    return {"sin_dia": sin[:limite], "sin_dia_total": len(sin), "pendientes": pend[:limite], "pendientes_total": len(pend)}


@router.get("/mes/{anio}/{mes}")
def mes(anio: int, mes: int, usuario=Depends(auth.aprobador)):
    _con_db()
    if not (1 <= mes <= 12 and 2000 <= anio <= 2100):
        raise HTTPException(400, "Mes inválido.")
    ultimo = calendar.monthrange(anio, mes)[1]
    frases = db.listar_frases(desde=f"{anio:04d}-{mes:02d}-01", hasta=f"{anio:04d}-{mes:02d}-{ultimo:02d}")
    return {"anio": anio, "mes": mes, "dias": ultimo, "hoy": _hoy().isoformat(),
            "primer_dia_semana": datetime.date(anio, mes, 1).weekday(),
            "frases": {f["fecha"]: _publica(f) for f in frases if f.get("fecha")}}


@router.get("/dia/{fecha}")
def dia(fecha: str, usuario=Depends(auth.aprobador)):
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
def previa(fid: str, usuario=Depends(auth.aprobador)):
    """La imagen compuesta chica (frase + autor + logo sobre la foto), como va a salir (frases_ui._vista_previa)."""
    f = _frase(fid)
    cfg, publicar = _cfg()
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
def mail_estado(usuario=Depends(auth.aprobador)):
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
            "lista_prueba": db.obtener_config("frase_mail_prueba") or [], "trigger_key": os.environ.get("PERFIT_TRIGGER_KEY") or "frase_del_dia",
            "limite_por_hora": perfit.LIMITE_POR_HORA, "envios": envios, "pruebas": pruebas,
            "contexto_plantilla": ["frase", "autor", "imagen_url", "fecha", "fecha_texto", "pie", "link"]}


@router.post("/mail/prueba")
def mail_prueba(datos: PruebaMail, request: Request, quien=Depends(auth.admin)):
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
