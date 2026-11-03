"""Solicitudes de cambio (2/11): los creadores piden, los aprobadores resuelven. (3/11: antes en api/frases_rutas.py; montado bajo /frases por api/frases/__init__.py)."""
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
    return {"id": x["id"], "creado": x.get("creado"), "usuario": x.get("usuario"), "fecha": fecha, "fecha_texto": f"{DIAS[d.weekday()]} {c._fecha_txt(d)}",
            "frase": c._publica(frases.get(fid)) if fid else None, "texto": x.get("texto"), "autor": x.get("autor"), "nota": x.get("nota"),
            "imagen_url": x.get("imagen_url"), "solo_foto": bool(x.get("imagen_url")) and not fid and not (x.get("texto") or "").strip(),
            "estado": x.get("estado"), "resuelta_por": x.get("resuelta_por"), "resuelta_en": x.get("resuelta_en"), "respuesta": x.get("respuesta"),
            "actual": c._publica(frases.get("dia:" + fecha)), "pasado": d < c._hoy()}


@router.get("/solicitudes")
def solicitudes(request: Request):
    s = auth.sesion(request)
    rol = auth.rol_sesion(s)
    c._con_db()
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
    c._con_db()
    d = c._fecha(datos.fecha)
    if d <= c._hoy():
        raise HTTPException(400, "Pedí un cambio para mañana en adelante: la frase de hoy ya está en marcha.")
    actual = db.frase_del_dia(d.isoformat())
    if actual and c._cerrada(actual):
        raise HTTPException(409, f"La frase del {c._fecha_txt(d)} ya está en la cola o ya salió: ese día no se puede cambiar.")
    texto = (datos.texto or "").strip()
    fid = (datos.frase_id or "").strip() or None
    imagen = c._url_foto(datos.imagen_url)
    if fid:
        f = c._frase(fid)
        if not f.get("validada"):
            raise HTTPException(409, "Esa frase todavía no está validada.")
        if f.get("fecha") == d.isoformat():
            raise HTTPException(400, "Esa frase ya está en ese día.")
        if c._cerrada(f):
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
            "mensaje": f"Pedido para el {c._fecha_txt(d)}. Lo ve quien aprueba la Frase del día; te avisamos acá cuando lo resuelva."}


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
    c._con_db()
    x = _solicitud_pendiente(sid)
    d = datetime.date.fromisoformat(str(x["fecha"])[:10])
    if d < c._hoy():
        raise HTTPException(409, "Ese día ya pasó: rechazala o pedí otra fecha.")
    actual = db.frase_del_dia(d.isoformat())
    if actual and c._cerrada(actual):
        raise HTTPException(409, f"La frase del {c._fecha_txt(d)} ya está en la cola o ya salió: no se puede cambiar.")
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
    f = c._frase(fid)
    if c._cerrada(f):
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
        return {"ok": True, "solicitud": _solicitud_publica(db.obtener_solicitud_frase(sid)), "mensaje": f"Aceptada: la frase del {c._fecha_txt(d)} sale con la foto propuesta."}
    que = "intercambiada con la que estaba" if actual and f.get("fecha") not in (None, d.isoformat()) else ("puesta en lugar de la que estaba (que volvió al backlog)" if actual else "asignada")
    con_foto = " y con la foto propuesta" if x.get("imagen_url") else ""
    return {"ok": True, "solicitud": _solicitud_publica(db.obtener_solicitud_frase(sid)), "mensaje": f"Aceptada: la frase quedó {que} el {c._fecha_txt(d)}{con_foto}."}


@router.post("/solicitudes/{sid}/rechazar")
def rechazar_solicitud(sid: str, datos: Resolver, quien=Depends(auth.aprobador)):
    c._con_db()
    _solicitud_pendiente(sid)
    db.actualizar_solicitud_frase(sid, {"estado": "rechazada", "resuelta_por": quien, "resuelta_en": db._ahora_iso(), "respuesta": (datos.respuesta or "").strip() or None})
    return {"ok": True, "solicitud": _solicitud_publica(db.obtener_solicitud_frase(sid)), "mensaje": "Rechazada. Quien la pidió ve tu respuesta en su lista."}


@router.post("/solicitudes/{sid}/retirar")
def retirar_solicitud(sid: str, usuario=Depends(auth.usuario_actual)):
    c._con_db()
    x = _solicitud_pendiente(sid)
    if x.get("usuario") != usuario:
        raise HTTPException(403, "Esa solicitud es de otra persona.")
    db.actualizar_solicitud_frase(sid, {"estado": "retirada", "resuelta_por": usuario, "resuelta_en": db._ahora_iso()})
    return {"ok": True, "mensaje": "Retirada."}
