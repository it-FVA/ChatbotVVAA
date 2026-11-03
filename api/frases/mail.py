"""El canal mail por Perfit: estado, prueba al equipo y la vista previa del mail. (3/11: antes en api/frases_rutas.py; montado bajo /frases por api/frases/__init__.py)."""
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
        jpg = pf.componer(f, foto, pf.estilo_de(f, db))
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
    c._con_db()
    import perfit
    est = perfit.probar_conexion()
    hoy = c._hoy()
    man = hoy + datetime.timedelta(days=1)
    envios = {}
    for d in (hoy, man):
        f = db.frase_del_dia(d.isoformat())
        pid = ((f or {}).get("piezas") or {}).get("mail")
        p = db.obtener_publicacion(pid) if pid else None
        envios[d.isoformat()] = {"fecha_texto": c._fecha_txt(d), "frase": c._publica(f) if f else None, "pieza": pid,
                                 "estado": (p or {}).get("estado"), "arranca": (p or {}).get("fecha_programada"),
                                 "conteo": db.resumen_envios(pid) if pid else None}
    canales = db.obtener_config("frase_canales") or pf.CANALES_DEFECTO
    pruebas = db.ultimos_envios(limite=30, prueba=True)
    return {"modo": est["modo"], "faltan": est["faltan"], "lista": est["lista"], "error": est["error"],
            "canal_prendido": "mail" in canales, "inicio": db.obtener_config("frase_mail_inicio", pf.MAIL_INICIO_DEFECTO) or pf.MAIL_INICIO_DEFECTO,
            "hora": db.obtener_config("frase_hora", pf.HORA_DEFECTO) or pf.HORA_DEFECTO,
            "lista_prueba": db.obtener_config("frase_mail_prueba") or [], "trigger_key": os.environ.get("PERFIT_TRIGGER_KEY") or perfit.TRIGGER_KEY_DEFECTO,
            "limite_por_hora": perfit.LIMITE_POR_HORA, "envios": envios, "pruebas": pruebas,
            "contexto_plantilla": ["frase", "autor", "fuente", "url", "fecha", "imagen_url", "fecha_iso", "fecha_texto", "pie", "link"]}


@router.post("/mail/prueba")
def mail_prueba(datos: PruebaMail, request: Request, quien=Depends(auth.aprobador)):
    """Manda la frase del día (o de `fecha`) a los mails de prueba, ya mismo. En modo simulado registra pero no manda."""
    c._con_db()
    import perfit, frase_mail
    fecha = (datos.fecha or c._hoy().isoformat())[:10]
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
    cfg, publicar = c._cfg()
    imagen_url, de_donde = _imagen_publica_para(f, fecha, cfg, publicar)
    r = frase_mail.enviar_prueba(f, fecha, imagen_url, emails, db, perfit, pie=db.obtener_config("frase_pie"))
    r["imagen_de"] = de_donde
    r["quien"] = quien
    if datos.emails:
        db.guardar_config("frase_mail_prueba", emails, quien)
    return r


PLANTILLA_MAIL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "distribucion", "frase_mail_plantilla.html")


@router.get("/mail/previa/{fecha}")
def mail_previa(fecha: str, usuario=Depends(auth.usuario_actual)):
    """El mail de la frase de ese día, armado acá con `distribucion/frase_mail_plantilla.html` y el MISMO contexto que recibe la
    automation de Perfit (frase_mail.contexto_de). Es una reproducción: el mail real lo arma Perfit con su plantilla; para verlo
    exacto está «Probar el mail». La imagen va embebida (data:) para que la vista previa no dependa de WordPress."""
    import base64, html as html_mod
    import frase_mail
    c._con_db()
    d = c._fecha(fecha)
    f = db.frase_del_dia(d.isoformat())
    if not f:
        raise HTTPException(404, f"El {c._fecha_txt(d)} no tiene frase asignada.")
    cfg, publicar = c._cfg()
    imagen = ""
    de_donde = "sin foto"
    try:
        foto, de_donde = pf.foto_de_fondo(f, cfg, db, publicar)
        if foto:
            jpg = pf.componer(f, foto, pf.estilo_de(f, db))
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
    return {"fecha": d.isoformat(), "fecha_texto": c._fecha_txt(d), "html": salida, "contexto": publico, "imagen_de": de_donde,
            "asunto": f"Frase del día · {ctx['fecha_texto']}", "frase": c._publica(f),
            "aviso": "Reproducción con la plantilla local y los mismos datos que recibe Perfit. El mail real lo arma la automation de Perfit; para verlo exacto, mandá una prueba."}
