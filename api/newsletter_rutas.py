"""Newsletter en la web (22/10): lo que la pantalla `/newsletter` necesita. Plantillas, redacción con el bot y armado del HTML viven en newsletter.py (raíz) y se reutilizan tal cual;
guardar borrador y mandar a aprobación usan db.guardar_borrador / db.proponer_publicacion con el mismo `extra`
({"plantilla", "datos"}) de siempre, así «Mis publicaciones» y el panel de aprobación los ven igual. El email NO sale de acá:
el HTML aprobado se pega en Perfit.

Rutas (todas con sesión):
  GET  /newsletter/plantillas            {plantillas: {clave: nombre}, vacios: {clave: datos vacíos}} (newsletter.PLANTILLAS / vacio)
  POST /newsletter/html                  {plantilla, datos} → {html, titulo}  (newsletter.armar_html; la vista previa en vivo)
  POST /newsletter/cabecera              {foto_url, titulo, color?} → image/jpeg: la cabecera 1600×500 con el título encima (vista previa)
  POST /newsletter/cabecera?subir=1      la misma, subida a la biblioteca de WordPress → {url, color} para cabecera_url
  POST /newsletter/redactar              {plantilla, tema, datos} → {datos, materiales}  (newsletter.redactar: el bot completa los textos)
  GET  /newsletter/borradores            mis borradores de newsletter [{id, titulo, plantilla, creado, guardado_en}]
  GET  /newsletter/borradores/{id}       uno con {plantilla, datos} para retomarlo: un borrador o una rechazada (4/11) de quien
                                         lo puede editar (la dueña, un aprobador o quien tiene «editar» por una carpeta)
  POST /newsletter/borrador              {plantilla, datos, borrador_id?} = «💾 Guardar» (actualiza el mismo si viene borrador_id)
  POST /newsletter/a-aprobar             {plantilla, datos, borrador_id?} = «📨 Enviar a aprobación» (4/11: el retomado pasa a
                                         a_aprobar en la misma fila, mismo id y misma carpeta)
Los permisos y el circuito de una rechazada son los de Publicar (publicar_rutas.permiso_pieza / _borrador_ajeno / CORREGIBLES).
Las fotos del banco van por GET /banco (chat_rutas) y el recorte para el bloque de video por GET /recortes/{id}.
"""
import datetime, logging, os
from typing import Any, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
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


class Cabecera(BaseModel):
    foto_url: str
    titulo: str = ""
    color: Optional[str] = None     # "blanco" | "azul" para forzar; si no, sale del fondo


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


def _editable(pid, usuario, rol):
    """(4/11) La fila de newsletter que se retoma y su dueña, si quien edita la puede tocar (la misma regla que Publicar). Con «ver»
    o si no es un newsletter, un borrador o una rechazada: 409."""
    from .publicar_rutas import CORREGIBLES, _borrador_ajeno
    fila = db.obtener_publicacion(pid)
    if not fila or fila.get("canal") != "newsletter" or fila.get("estado") not in CORREGIBLES:
        raise HTTPException(409, "Ese borrador de newsletter ya no existe o ya no se puede editar (está en aprobación o salió).")
    duena = _borrador_ajeno(pid, usuario, rol)
    if not duena:
        raise HTTPException(409, "Ese newsletter es de otra persona y no tenés permiso para editarlo. Podés verlo desde la carpeta.")
    return fila, duena


def _contenido_de(fila):
    """El {plantilla, datos} guardado: en un borrador va en resultado.pieza; una propuesta anterior al 4/11 los tenía sueltos."""
    res = fila.get("resultado") or {}
    pieza = res.get("pieza") or {"plantilla": res.get("plantilla"), "datos": res.get("datos")}
    plantilla = pieza.get("plantilla") if pieza.get("plantilla") in newsletter.PLANTILLAS else "mensual"
    return plantilla, _completar(plantilla, pieza.get("datos") or {})


# ---------------- Rutas ----------------
@router.get("/plantillas")
def plantillas(usuario=Depends(auth.usuario_actual)):
    return {"plantillas": dict(newsletter.PLANTILLAS), "vacios": {p: newsletter.vacio(p) for p in newsletter.PLANTILLAS},
            "tipos_recurso": {k: {"emoji": e, "nombre": n} for k, (e, n) in newsletter.TIPOS_RECURSO.items()}}


@router.post("/cabecera")
def cabecera(c: Cabecera, subir: bool = False, usuario=Depends(auth.usuario_actual)):
    """(23/10, prueba de Julián) La foto elegida recortada a 1600×500 con el título del newsletter encima; la letra va
    blanca sobre fondo oscuro y azul #00323f sobre fondo claro. Sin `subir`: la imagen para la vista previa. Con `subir`:
    se sube a la biblioteca de WordPress (como cualquier foto de una pieza) y devuelve la URL para cabecera_url."""
    import imagen, publicar    # noqa: E402
    url = (c.foto_url or "").strip()
    if not url.startswith("http"):
        raise HTTPException(400, "Elegí primero una foto del banco (o pegá su URL).")
    try:
        datos, color = imagen.componer_cabecera(url, c.titulo, color=c.color)
    except Exception as e:
        log.warning("cabecera: %s", e)
        raise HTTPException(502, f"No pude armar la cabecera con esa foto: {e}")
    if not subir:
        return Response(content=datos, media_type="image/jpeg", headers={"X-Color": color, "Cache-Control": "no-store"})
    cfg = publicar.Config(os.environ)
    nombre = f"newsletter-cabecera-{datetime.date.today().isoformat()}.jpg"
    r = publicar.subir_imagen_wordpress(cfg, datos, nombre, titulo=(c.titulo or "Cabecera del newsletter"),
                                        etiquetas=["newsletter", "cabecera"], quien=usuario, pieza="newsletter")
    if not r.get("url"):
        raise HTTPException(502, r.get("aviso") or "WordPress no devolvió la URL de la cabecera.")
    return {"url": r["url"], "color": color}


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
    # (23/10) Firma las llamadas a OpenAI con la persona (uso_openai): sin esto quedaban como «(sistema)» en el Dashboard.
    import nucleo    # noqa: E402
    try:
        with nucleo.como(usuario):     # (3/11) ContextVar en vez de la variable global con candado
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
def borrador(pid: str, s=Depends(auth.sesion)):
    """Para retomar. (4/11) También una rechazada y el de otra persona con permiso «editar»: devuelve de quién es y el rechazo."""
    usuario = s["usuario"]
    if not db.disponible():
        raise HTTPException(503, "Sin Supabase: no hay borradores.")
    p, duena = _editable(pid, usuario, auth.rol_sesion(s))
    res = p.get("resultado") or {}
    plantilla, datos = _contenido_de(p)
    rechazo = {"por": res.get("rechazada_por"), "en": res.get("rechazada_en"), "nota": res.get("nota")} if res.get("rechazada_por") else None
    return {"id": p["id"], "titulo": p.get("titulo"), "plantilla": plantilla, "datos": datos, "creado": p.get("creado"),
            "estado": p.get("estado"), "duena": duena, "propia": duena == usuario, "rechazo": rechazo, "editada_por": res.get("editada_por")}


@router.post("/borrador")
def guardar_borrador(g: Guardar, s=Depends(auth.sesion)):
    """(4/11) Con borrador_id guarda los cambios en la misma fila, también si es una rechazada (pasa a borrador y conserva el
    rechazo) o de otra persona con permiso «editar» (sigue siendo de ella, queda quién lo editó). Sin permiso: 409."""
    usuario = s["usuario"]
    if not db.disponible():
        raise HTTPException(503, "No pude guardar el borrador (falta la base de datos).")
    p = _plantilla(g.plantilla)
    d = _completar(p, g.datos)
    html_ = newsletter.armar_html(p, d)
    duena, conservar = usuario, None
    if g.borrador_id:
        fila, duena = _editable(g.borrador_id, usuario, auth.rol_sesion(s))
        conservar = db.historial_de(fila.get("resultado"))
        if conservar.get("rechazada_por"):
            conservar.update(corregida_por=usuario, corregida_en=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"))
    pid = db.guardar_borrador(duena, "newsletter", _titulo(d), html_, None, None, {"plantilla": p, "datos": d}, pid=g.borrador_id or None,
                              por=usuario, conservar=conservar)
    if not pid:
        raise HTTPException(503, "No pude guardar el borrador.")
    if not g.borrador_id:
        mensaje = "Guardado como borrador. Lo retomás desde «Retomar un borrador» o Mis publicaciones."
    elif duena != usuario:
        mensaje = f"Cambios guardados. El newsletter sigue siendo de {duena} y queda en la misma carpeta."
    else:
        mensaje = "Cambios guardados en el mismo borrador."
    return {"ok": True, "id": pid, "estado": "borrador", "mensaje": mensaje}


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
    extra = {"plantilla": p, "datos": d, "origen": "web", "pieza": {"plantilla": p, "datos": d}}
    if g.borrador_id:
        # (4/11) como en Publicar: el borrador o la rechazada que se corrige pasa a a_aprobar en la MISMA fila (mismo id, misma
        # carpeta, el rechazo queda en el historial), a nombre de su dueña
        fila, duena = _editable(g.borrador_id, usuario, auth.rol_sesion(s))
        pid = db.reproponer_publicacion(g.borrador_id, duena, "newsletter", "borrador", _titulo(d), html_, None, None, extra=extra,
                                        por=usuario, previo=fila.get("resultado"))
    else:
        pid = db.proponer_publicacion(usuario, "newsletter", "borrador", _titulo(d), html_, None, None, extra=extra)
    if not pid:
        raise HTTPException(503, "No pude guardar la pieza para aprobación.")
    import avisos as _avisos
    _avisos.pieza_a_aprobar(db, pid, usuario, "newsletter", _titulo(d), None)   # (2/11) Slack / mail a los aprobadores
    rol = auth.rol_sesion(s)
    quien = ", ".join(rol.get("aprobadores") or []) or "un aprobador"
    return {"ok": True, "id": pid, "estado": "a_aprobar",
            "mensaje": f"Quedó pendiente de aprobación ({quien}). Cuando lo aprueben, el HTML queda listo para pegar en Perfit. Lo seguís en «Mis publicaciones»."}
