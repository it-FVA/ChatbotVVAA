"""Presencia (tabla presencia, 5/11): quién está mirando o editando una pieza o un recorte ahora.
Una fila por (tipo, item_id, usuario) con `visto`; la pantalla late cada 20 s. Se muestran los vistos en los últimos 60 s; la cola
borra los de más de 10 minutos (limpiar_viejas). Las funciones se llaman a través del paquete (`_db.x`) para las pruebas.
"""
from datetime import datetime, timezone, timedelta

import db as _db

TIPOS = ("pieza", "recorte")
MODOS = ("mira", "edita")
VIGENTE_SEG = 60          # se ve como «acá» si latió hace menos de esto
LIMPIAR_MIN = 10          # la cola borra lo más viejo


def _ahora():
    return datetime.now(timezone.utc)


def _segundos_desde(iso, ahora=None):
    try:
        t = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return max(0, int(((ahora or _ahora()) - t).total_seconds()))
    except Exception:
        return None


def latir(tipo, item_id, usuario, modo="mira"):
    """Upsert de la fila con visto = ahora. Sin Supabase: no hace nada."""
    if not _db.disponible() or tipo not in TIPOS or not item_id or not usuario:
        return None
    fila = {"tipo": tipo, "item_id": str(item_id), "usuario": usuario, "modo": modo if modo in MODOS else "mira",
            "visto": _ahora().isoformat(timespec="seconds")}
    return _db.insertar("presencia", fila, upsert="tipo,item_id,usuario")


def quienes(tipo, item_id, usuario_actual):
    """Los DEMÁS con latido en los últimos 60 s: [{usuario, modo, hace_seg}], los que editan primero."""
    if not _db.disponible() or tipo not in TIPOS or not item_id:
        return []
    ahora = _ahora()
    desde = (ahora - timedelta(seconds=VIGENTE_SEG)).isoformat(timespec="seconds")
    filas = _db.consulta("presencia", [("tipo", "eq", tipo), ("item_id", "eq", str(item_id)), ("visto", "gte", desde)],
                         select="usuario,modo,visto", order="visto.desc", limite=50)
    out = []
    for f in filas:
        seg = _segundos_desde(f.get("visto"), ahora)
        if f.get("usuario") == usuario_actual or seg is None or seg > VIGENTE_SEG:
            continue
        out.append({"usuario": f["usuario"], "modo": f.get("modo") or "mira", "hace_seg": seg})
    out.sort(key=lambda x: (x["modo"] != "edita", x["hace_seg"]))
    return out


def salir(tipo, item_id, usuario):
    if not _db.disponible() or tipo not in TIPOS or not item_id or not usuario:
        return None
    return _db.borrar("presencia", [("tipo", "eq", tipo), ("item_id", "eq", str(item_id)), ("usuario", "eq", usuario)])


def limpiar_viejas(minutos=LIMPIAR_MIN):
    """Borra las filas con visto más viejo que `minutos`. Devuelve cuántas."""
    if not _db.disponible():
        return 0
    corte = (_ahora() - timedelta(minutes=minutos)).isoformat(timespec="seconds")
    return len(_db.borrar("presencia", [("visto", "lt", corte)]) or [])
