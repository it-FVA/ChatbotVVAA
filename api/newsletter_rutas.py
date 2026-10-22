"""Newsletter en la web (22/10): lo que la pantalla `/newsletter` necesita. Es la MISMA lógica que la solapa de Streamlit
(newsletter_ui.py): plantillas, redacción con el bot y armado del HTML viven en newsletter.py (raíz) y se reutilizan tal cual;
guardar borrador y mandar a aprobación usan db.guardar_borrador / db.proponer_publicacion con el mismo `extra`
({"plantilla", "datos"}) que Streamlit, así «Mis publicaciones» y el panel de aprobación los ven igual. El email NO sale de acá:
el HTML aprobado se pega en Perfit.

Rutas (todas con sesión):
  GET  /newsletter/plantillas            {plantillas: {clave: nombre}, vacios: {clave: datos vacíos}} (newsletter.PLANTILLAS / vacio)
  POST /newsletter/html                  {plantilla, datos} → {html, titulo}  (newsletter.armar_html; la vista previa en vivo)
  POST /newsletter/redactar              {plantilla, tema, datos} → {datos, materiales}  (newsletter.redactar: el bot completa los textos)
  GET  /newsletter/borradores            mis borradores de newsletter [{id, titulo, plantilla, creado, guardado_en}]
  GET  /newsletter/borradores/{id}       uno (solo propio) con {plantilla, datos} para retomarlo
  POST /newsletter/borrador              {plantilla, datos, borrador_id?} = «💾 Guardar como borrador» (actualiza si viene borrador_id)
  POST /newsletter/a-aprobar             {plantilla, datos, borrador_id?} = «📨 Enviar a aprobación» (el borrador retomado se elimina)
Las fotos del banco van por GET /banco (chat_rutas) y el recorte para el bloque de video por GET /recortes/{id}.
"""
import datetime, logging
from typing import Any, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from . import auth, roles as _roles
import db            # noqa: E402  (api/__init__ pone la raíz del repo en sys.path)
import newsletter    # noqa: E402

log = logging.getLogger("api")
router = APIRouter(prefix="/newsletter", tags=["newsletter"])


class Contenido(BaseModel):
    plantilla: str = "mensual"
    datos: dict[str, Any] = {}


class Redaccion(Contenido):
    tema: str


class Guardar(Contenido):
    borrador_id: Optional[str] = None


def _plantilla(p):
    p = (p or "mensual").strip().lower()
    if p not in newsletter.PLANTILLAS:
        raise HTTPException(400, "Plantilla desconocida: tiene que ser " + " o ".join(newsletter.PLANTILLAS) + ".")
    return p


def _completar(plantilla, datos):
    """Como newsletter_ui.cargar: los datos sobre la plantilla vacía, para que no falte ninguna clave."""
    base = newsletter.vacio(plantilla)
    for k, v in (datos or {}).items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            base[k] = dict(base[k], **v)
        else:
            base[k] = v
    return base


def _titulo(d):
    return d.get("asunto") or (f"Newsletter {d.get('mes')}" if d.get("mes") else "Newsletter")


def _borrador_propio(pid, usuario):
    r = db._req("GET", f"?id=eq.{quote(str(pid))}&usuario=eq.{quote(usuario)}&canal=eq.newsletter&estado=eq.borrador"
                       f"&select=id,creado,titulo,texto,resultado", tabla="publicaciones")
    return r[0] if r else None


# ---------------- Rutas ----------------
@router.get("/plantillas")
def plantillas(usuario=Depends(auth.usuario_actual)):
    return {"plantillas": dict(newsletter.PLANTILLAS), "vacios": {p: newsletter.vacio(p) for p in newsletter.PLANTILLAS}}


@router.post("/html")
def html(c: Contenido, usuario=Depends(auth.usuario_actual)):
    p = _plantilla(c.plantilla)
    d = _completar(p, c.datos)
    return {"html": newsletter.armar_html(p, d), "titulo": _titulo(d)}


@router.post("/redactar")
def redactar(c: Redaccion, usuario=Depends(auth.usuario_actual)):
    """= «✨ Redactar»: busca material sobre el tema y el bot completa los textos (no toca fechas, links ni fotos)."""
    p = _plantilla(c.plantilla)
    tema = (c.tema or "").strip()
    if not tema:
        raise HTTPException(400, "Falta el tema para que el bot redacte.")
    try:
        nuevo, mats = newsletter.redactar(p, tema, _completar(p, c.datos))
    except Exception as e:
        log.exception("newsletter.redactar")
        raise HTTPException(502, f"No pude redactar: {e}")
    materiales = [{"titulo": m.get("titulo"), "autor": m.get("autor"), "tag": m.get("tag"), "url": m.get("ir") or m.get("url")}
                  for m in (mats or [])]
    return {"datos": nuevo, "materiales": materiales, "html": newsletter.armar_html(p, nuevo)}


@router.get("/borradores")
def borradores(usuario=Depends(auth.usuario_actual)):
    if not db.disponible():
        return []
    out = []
    for p in db.listar_mias(usuario, limite=100):
        if p.get("canal") != "newsletter" or p.get("estado") != "borrador":
            continue
        res = p.get("resultado") or {}
        pieza = res.get("pieza") or {}
        out.append({"id": p["id"], "titulo": p.get("titulo") or "Newsletter", "plantilla": pieza.get("plantilla") or "mensual",
                    "creado": p.get("creado"), "guardado_en": res.get("guardado_en")})
    return out


@router.get("/borradores/{pid}")
def borrador(pid: str, usuario=Depends(auth.usuario_actual)):
    if not db.disponible():
        raise HTTPException(503, "Sin Supabase: no hay borradores.")
    p = _borrador_propio(pid, usuario)
    if not p:
        raise HTTPException(404, "No existe ese borrador de newsletter (o no es tuyo, o ya no es borrador).")
    pieza = (p.get("resultado") or {}).get("pieza") or {}
    plantilla = pieza.get("plantilla") if pieza.get("plantilla") in newsletter.PLANTILLAS else "mensual"
    return {"id": p["id"], "titulo": p.get("titulo"), "plantilla": plantilla, "datos": _completar(plantilla, pieza.get("datos") or {}),
            "creado": p.get("creado")}


@router.post("/borrador")
def guardar_borrador(g: Guardar, usuario=Depends(auth.usuario_actual)):
    if not db.disponible():
        raise HTTPException(503, "No pude guardar el borrador (falta la base de datos).")
    p = _plantilla(g.plantilla)
    d = _completar(p, g.datos)
    html_ = newsletter.armar_html(p, d)
    pid_prev = g.borrador_id if (g.borrador_id and _borrador_propio(g.borrador_id, usuario)) else None
    pid = db.guardar_borrador(usuario, "newsletter", _titulo(d), html_, None, None, {"plantilla": p, "datos": d}, pid=pid_prev)
    if not pid:
        raise HTTPException(503, "No pude guardar el borrador.")
    return {"ok": True, "id": pid, "estado": "borrador",
            "mensaje": "Guardado como borrador." + (" Se actualizó el mismo." if pid_prev else " Lo retomás desde «Retomar un borrador» o Mis publicaciones.")}


@router.post("/a-aprobar")
def enviar_a_aprobacion(g: Guardar, s=Depends(auth.sesion)):
    """Como newsletter_ui: la pieza queda 'a_aprobar' (canal newsletter, modo 'borrador', texto = el HTML). Cuando la aprueban queda
    'lista': el HTML para pegar en Perfit."""
    usuario = s["usuario"]
    if not db.disponible():
        raise HTTPException(503, "No pude guardar la pieza para aprobación (falta la base de datos).")
    p = _plantilla(g.plantilla)
    d = _completar(p, g.datos)
    if not (d.get("asunto") or "").strip():
        raise HTTPException(400, "Falta el asunto del email.")
    html_ = newsletter.armar_html(p, d)
    pid = db.proponer_publicacion(usuario, "newsletter", "borrador", _titulo(d), html_, None, None, extra={"plantilla": p, "datos": d, "origen": "web"})
    if not pid:
        raise HTTPException(503, "No pude guardar la pieza para aprobación.")
    if g.borrador_id:
        try:
            db._req("DELETE", f"?id=eq.{quote(str(g.borrador_id))}&estado=eq.borrador&usuario=eq.{quote(usuario)}", tabla="publicaciones")
        except Exception:
            pass
    rol = auth.rol_sesion(s)
    quien = ", ".join(rol.get("aprobadores") or []) or "un aprobador"
    return {"ok": True, "id": pid, "estado": "a_aprobar",
            "mensaje": f"Quedó pendiente de aprobación ({quien}). Cuando lo aprueben, el HTML queda listo para pegar en Perfit. Lo seguís en «Mis publicaciones»."}
