"""El interruptor, los canales por los que sale la frase y la tarjeta «Mañana» (encolar / frenar). (3/11: antes en api/frases_rutas.py; montado bajo /frases por api/frases/__init__.py)."""
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


@router.put("/activa")
def activa(datos: Activa, usuario=Depends(auth.admin)):
    """El interruptor «Frase del día activa». Es configuración (config frase_activa): solo admins."""
    c._con_db()
    db.guardar_config("frase_activa", bool(datos.activa), usuario)
    return {"ok": True, "activa": bool(datos.activa), "mensaje": "Frase del día " + ("activada: cada mañana sale la frase de ese día." if datos.activa else "apagada: el calendario se arma igual pero no sale nada.")}


@router.put("/canales")
def canales(datos: Canales, quien=Depends(auth.aprobador)):
    """(2/11, Franco) Por qué canales sale la frase cada día, desde la cabecera de Frase del día (antes solo en Configuración, admins).
    Misma regla que admin_rutas: canales válidos, al menos uno, en el orden de CANALES_POSIBLES."""
    c._con_db()
    elegidos = [c for c in pf.CANALES_POSIBLES if c in datos.canales]
    if not elegidos:
        raise HTTPException(400, "Dejá al menos un canal prendido (o apagá la Frase del día con el interruptor).")
    db.guardar_config("frase_canales", elegidos, quien)
    corto = {"historia": "historia de Instagram", "instagram": "posteo de Instagram", "facebook": "Facebook", "mail": "mail", "home": "sitio web", "whatsapp": "WhatsApp"}
    return {"ok": True, "canales": elegidos, "mensaje": "Sale por " + ", ".join(corto.get(c, c) for c in elegidos) + ". Vale desde la próxima frase que se encole; la de mañana, si ya está en la cola, suma los canales nuevos en la próxima pasada."}


def _manana():
    d = c._hoy() + datetime.timedelta(days=1)
    f = db.frase_del_dia(d.isoformat())
    if not f:
        raise HTTPException(404, f"Mañana ({c._fecha_txt(d)}) no tiene frase asignada: asigná una en el calendario.")
    return d, f


def _piezas_vivas(f):
    out = {}
    for k, pid in (f.get("piezas") or {}).items():
        p = db.obtener_publicacion(pid) if pid else None
        if p and p.get("estado") in ("pendiente", "procesando", "enviando"):
            out[k] = pid
    return out


@router.post("/manana/encolar")
def manana_encolar(quien=Depends(auth.aprobador)):
    """(2/11, Franco) «Volver a encolar»: la frase de mañana entra en la cola por los canales prendidos que todavía no tienen pieza
    viva (p. ej. después de «Frenar mañana»). Mismo camino que la cola (programar_frases.encolar_frase)."""
    c._con_db()
    if not db.obtener_config("frase_activa", False):
        raise HTTPException(409, "La Frase del día está apagada: prendela primero (lo hace un admin) y después encolá.")
    d, f = _manana()
    if f.get("estado") != "programada":
        raise HTTPException(409, "La frase de mañana está salteada: volvé a programarla desde el día.")
    vivas = _piezas_vivas(f)
    canales = [c for c in (db.obtener_config("frase_canales") or pf.CANALES_DEFECTO) if c in pf.CANALES_POSIBLES]
    faltan = [c for c in canales if c not in vivas]
    if not faltan:
        raise HTTPException(409, "Mañana ya está en la cola por todos los canales prendidos.")
    # las piezas canceladas se sacan de la frase para que no cuenten como «ya encolada»
    db.actualizar_frase(f["id"], {"piezas": vivas or None, "publicacion_id": f.get("publicacion_id") if f.get("publicacion_id") in vivas.values() else (list(vivas.values())[0] if vivas else None)})
    f = db.obtener_frase(f["id"])
    cfg, publicar = c._cfg()
    hora = db.obtener_config("frase_hora", pf.HORA_DEFECTO) or pf.HORA_DEFECTO
    nuevas, aviso = pf.encolar_frase(f, d, cfg, db, publicar, hora=hora, quien=quien, canales=faltan)
    if not nuevas:
        raise HTTPException(409, f"No pude encolar: {aviso}")
    return {"ok": True, "canales": list(nuevas), "mensaje": f"Mañana ({c._fecha_txt(d)}) en cola por {', '.join(nuevas)}. {aviso}"}


@router.post("/manana/frenar")
def manana_frenar(quien=Depends(auth.aprobador)):
    """(2/11, Franco) «Frenar mañana»: cancela las piezas pendientes de la frase de mañana. La frase queda en el día y se puede
    volver a encolar. Un mail que ya está enviándose no se frena desde acá (Aprobación → En cola)."""
    c._con_db()
    d, f = _manana()
    n = 0
    quedan = {}
    for k, pid in (f.get("piezas") or {}).items():
        p = db.obtener_publicacion(pid) if pid else None
        if not p:
            continue
        if p.get("estado") == "pendiente":
            db.cancelar_publicacion(pid, quien)
            n += 1
        elif p.get("estado") == "enviando":
            quedan[k] = pid
    if not n and not quedan:
        raise HTTPException(409, "Mañana no tiene piezas en la cola.")
    db.actualizar_frase(f["id"], {"piezas": quedan or None, "publicacion_id": list(quedan.values())[0] if quedan else None})
    return {"ok": True, "canceladas": n, "mensaje": f"Frenada: {n} pieza{'s' if n != 1 else ''} de mañana cancelada{'s' if n != 1 else ''}." + (" El mail ya se estaba enviando y sigue." if quedan else "")}
