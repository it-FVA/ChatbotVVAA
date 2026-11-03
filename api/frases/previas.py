"""Vistas previas: la imagen compuesta de una frase y el mensaje de WhatsApp (prototipo). (3/11: antes en api/frases_rutas.py; montado bajo /frases por api/frases/__init__.py)."""
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


@router.get("/{fid}/previa.jpg")
def previa(fid: str, foto: str = "", usuario=Depends(auth.usuario_actual)):
    """La imagen compuesta chica (frase + autor + logo sobre la foto), como va a salir (frases_ui._vista_previa).
    Con ?foto=<url> la compone con esa foto en vez de la guardada (2/11 tarde: ver cómo quedaría una propuesta)."""
    f = c._frase(fid)
    cfg, publicar = c._cfg()
    if c._url_foto(foto):
        foto, de_donde = c._url_foto(foto), "propuesta (no guardada)"
    else:
        foto, de_donde = pf.foto_de_fondo(f, cfg, db, publicar)
    if not foto:
        raise HTTPException(404, "Sin foto para la vista previa: elegí una para la frase o cargá una por defecto en Configuración.")
    try:
        jpg = pf.componer(f, foto, pf.estilo_de(f, db))
    except Exception as e:
        raise HTTPException(502, f"No pude armar la vista previa: {e}")
    return Response(jpg, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=300", "X-Foto-De": de_donde.encode("ascii", "ignore").decode()})


@router.get("/whatsapp/previa/{fecha}")
def whatsapp_previa(fecha: str, usuario=Depends(auth.usuario_actual)):
    """El mensaje al grupo de la comunidad tal cual se mandaría (publicar.mensaje_whatsapp + la imagen compuesta embebida).
    Prototipo de la reunión del 2/11: todavía no hay forma de mandar desde la cuenta común; el modo lo dice."""
    import base64
    c._con_db()
    d = c._fecha(fecha)
    f = db.frase_del_dia(d.isoformat())
    if not f:
        raise HTTPException(404, f"El {c._fecha_txt(d)} no tiene frase asignada.")
    cfg, publicar = c._cfg()
    imagen, de_donde = "", "sin foto"
    try:
        foto, de_donde = pf.foto_de_fondo(f, cfg, db, publicar)
        if foto:
            jpg = pf.componer(f, foto, pf.estilo_de(f, db))
            imagen = "data:image/jpeg;base64," + base64.b64encode(jpg).decode("ascii")
    except Exception as e:
        de_donde = f"no pude componer la imagen: {e}"
    pid = ((f.get("piezas") or {}).get("whatsapp"))
    p = db.obtener_publicacion(pid) if pid else None
    canales = db.obtener_config("frase_canales") or pf.CANALES_DEFECTO
    return {"fecha": d.isoformat(), "fecha_texto": c._fecha_txt(d), "texto": publicar.mensaje_whatsapp(f.get("texto"), f.get("autor")),
            "imagen": imagen, "imagen_de": de_donde, "grupo": os.environ.get("WHATSAPP_GRUPO") or "Comunidad Vivir Agradecidos",
            "modo": cfg.modo_wa, "canal_prendido": "whatsapp" in canales, "frase": c._publica(f),
            "pieza": {"id": pid, "estado": p.get("estado"), "fecha_programada": p.get("fecha_programada")} if p else None,
            "aviso": ("Prototipo: así saldría en el grupo. Por ahora no se manda: la cuenta común de la fundación no tiene API "
                      "(la reunión descartó WhatsApp Business). Cuando se defina cómo mandar, se prende el modo real sin cambiar esta pantalla.")}
