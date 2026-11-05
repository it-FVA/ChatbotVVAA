"""Presencia y aviso de conflicto (5/11, pedido de Franco: «presencia y avisos»; NO es edición simultánea).

  POST   /presencia/{tipo}/{item_id}   {modo: mira|edita} = latido (la pantalla lo manda cada 20 s). Devuelve {presentes: [...]}
                                        con los DEMÁS que latieron en el último minuto: [{usuario, nombre, modo, hace_seg}].
  DELETE /presencia/{tipo}/{item_id}   al salir de la pantalla.

tipo = pieza | recorte. Sin Realtime ni websockets: la web solo habla con la API y Render gratis no está para conexiones abiertas.
Decisión: basta tener sesión (no se mira el permiso sobre la pieza: solo se exponen nombres de compañeras del mismo equipo).

También acá, para publicar_rutas / newsletter_rutas / recortes: `version_de` y `conflicto` (el control de versión al guardar).
La versión de una pieza es resultado.guardado_en; la de un recorte, edicion.guardado_en. Si el cliente manda `version` y no coincide con
la guardada, la respuesta es 409 {detail, version_actual, editada_por}; sin `version` (clientes viejos) se guarda como siempre.
"""
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import db
from . import auth
from db import presencia as _p

router = APIRouter(prefix="/presencia", tags=["presencia"])

_cache = {"t": 0.0, "nombres": {}}


def nombres():
    """{usuario: nombre} de la tabla usuarios, en memoria 2 minutos (el latido llega cada 20 s por persona)."""
    if time.time() - _cache["t"] > 120:
        try:
            _cache["nombres"] = {u["usuario"]: (u.get("nombre") or "").strip() or u["usuario"] for u in db.listar_usuarios() or []}
        except Exception:
            _cache["nombres"] = {}
        _cache["t"] = time.time()
    return _cache["nombres"]


def nombre_de(usuario):
    return nombres().get(usuario) or usuario


class Latido(BaseModel):
    modo: str = "mira"


def _tipo(tipo):
    if tipo not in _p.TIPOS:
        raise HTTPException(400, "El tipo tiene que ser pieza o recorte.")
    return tipo


@router.post("/{tipo}/{item_id}")
def latir(tipo: str, item_id: str, datos: Latido, usuario=Depends(auth.usuario_actual)):
    _tipo(tipo)
    try:
        db.latir(tipo, item_id, usuario, datos.modo)
        demas = db.quienes(tipo, item_id, usuario)
    except Exception:       # la presencia es un adorno: si la base falla, la pantalla sigue sin chips
        return {"presentes": []}
    return {"presentes": [dict(d, nombre=nombre_de(d["usuario"])) for d in demas]}


@router.delete("/{tipo}/{item_id}")
def salir(tipo: str, item_id: str, usuario=Depends(auth.usuario_actual)):
    _tipo(tipo)
    try:
        db.salir(tipo, item_id, usuario)
    except Exception:
        pass
    return {"ok": True}


# ---------------- Control de versión al guardar ----------------
def hace_texto(iso):
    """«hace 40 segundos», «hace 3 minutos», «hace 2 horas»."""
    seg = _p._segundos_desde(iso)
    if seg is None:
        return "hace un rato"
    if seg < 60:
        n, u = max(seg, 1), "segundo"
    elif seg < 3600:
        n, u = seg // 60, "minuto"
    elif seg < 86400:
        n, u = seg // 3600, "hora"
    else:
        n, u = seg // 86400, "día"
    return f"hace {n} {u}" + ("s" if n != 1 else "")


def conflicto(version, actual, guardo, usuario, que="pieza"):
    """None si se puede guardar (no vino versión, o coincide); si no, la respuesta 409 lista para devolver.
    `actual` = la versión guardada, `guardo` = quién guardó por última vez (usuario o None)."""
    if version in (None, "") or version == actual:
        return None
    este = "este" if que in ("recorte", "newsletter") else "esta"
    if guardo and guardo != usuario:
        msg = f"Otra persona guardó {este} {que} {hace_texto(actual)} ({nombre_de(guardo)})."
    elif guardo:
        msg = f"{este.capitalize()} {que} se guardó {hace_texto(actual)} desde otra pestaña tuya."
    else:
        msg = f"Otra persona guardó {este} {que} {hace_texto(actual)}."
    msg += " Recargá para ver sus cambios antes de guardar los tuyos."
    return JSONResponse({"detail": msg, "version_actual": actual, "editada_por": guardo}, status_code=409)


def version_de_fila(fila):
    """(version, quien guardó) de una fila de publicaciones: resultado.guardado_en y, si la guardó alguien con permiso «editar»,
    resultado.editada_por (si no, la última la guardó su dueña)."""
    res = (fila or {}).get("resultado") or {}
    return res.get("guardado_en"), res.get("editada_por") or (fila or {}).get("usuario")


def version_de_recorte(clip):
    e = (clip or {}).get("edicion") or {}
    return e.get("guardado_en"), e.get("guardado_por") or (clip or {}).get("pedido_por")
