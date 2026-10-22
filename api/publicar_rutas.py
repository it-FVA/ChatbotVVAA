"""Publicar, Mis publicaciones y Aprobación desde la web (fase 3 del plan de interfaz propia, 22/10).

Es la MISMA lógica de negocio que publicar_ui.py (formulario / _enviar / mis_publicaciones / panel_aprobacion), sin inventar
otra: se reutilizan publicar.py (conectores), imagen.py (la foto con la frase encima) y db.py (tabla `publicaciones`). Si cambia
una regla allá, cambiarla acá. Lo que ya existía en chat_rutas.py (banco, modos, borrador y a-aprobar «cortos» de la pieza
propuesta) se reutiliza; acá están las versiones completas con el diseño de la foto, el envío real/simulado y el panel.

Rutas (todas con sesión):
  GET    /publicar/opciones                  logos, tipografías, pesos, posiciones, formatos, canales con su modo (real y el que ve esta persona)
  POST   /banco/subir                        (multipart `archivo`) sube una imagen a la biblioteca de WordPress (publicar.subir_imagen_wordpress)
  POST   /publicar/componer                  la foto con la frase encima, para la vista previa (imagen.componer_imagen); devuelve image/jpeg
  POST   /publicar/borrador                  = «💾 Guardar borrador» con TODOS los campos del formulario (diseño incluido)
  POST   /publicar/a-aprobar                 = «📨 Enviar a aprobación» (sube la imagen compuesta a WordPress y deja la pieza a_aprobar)
  POST   /publicar/enviar                    = «Enviar a <canal>» / «👁 Ver simulado»: {modo: real|simulado}; real solo para quien publica directo
  GET    /publicaciones/{id}                 una pieza (dueño o aprobador) con el dict `pieza` para retomar el borrador
  DELETE /publicaciones/{id}                 = «🗑 Eliminar» (db.eliminar_publicacion: solo propias y en estado eliminable)
  GET    /aprobacion/para-aprobar            (aprobadores) las piezas a_aprobar + el modo real de cada canal
  POST   /aprobacion/{id}/aprobar            {fecha, hora}: = «✅ Aprobar y programar» (newsletter: queda `lista`)
  POST   /aprobacion/{id}/rechazar           {nota}
  GET    /aprobacion/cola                    las piezas pendientes (db.listar_pendientes)  · POST /aprobacion/{id}/cancelar
  GET    /aprobacion/registro                el registro completo sin subidas/pruebas/borradores (NO_SON_PIEZAS)
  GET    /aprobacion/papelera                conversaciones borradas por cualquiera · POST /aprobacion/papelera/{id}/restaurar
  (Clips: GET /recortes?todos=1, POST /recortes/{id}/reintentar y GET/PUT /recortes/estilo-defecto ya existen en api/recortes.py.)
"""
import os, re, io, copy, hashlib, logging, datetime, contextvars, threading
from collections import OrderedDict
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel

from . import auth
from . import chat_rutas as cr
import db            # noqa: E402  (api/__init__ pone la raíz del repo en sys.path)
import publicar      # noqa: E402
import imagen        # noqa: E402

log = logging.getLogger("api")
router = APIRouter(tags=["publicar"])

CANALES = cr.CANALES                       # {"wordpress": "WordPress", ...}
ZONA_HORARIA = cr.ZONA_HORARIA             # "-03:00"
# publicar_ui.CANAL_TXT (16/10, Franco): la entrada en WordPress se llama «Blogpost»; el «Newsletter» es el mail a la comunidad.
CANAL_TXT = {"wordpress": "Blogpost", "instagram": "Instagram", "facebook": "Facebook", "youtube": "YouTube", "newsletter": "Newsletter"}
# publicar_ui.ESTADO_TXT (sin los emojis: la web pone el icono)
ESTADO_TXT = {"a_aprobar": "pendiente de aprobación", "pendiente": "aprobada · programada", "rechazada": "rechazada",
              "publicada": "publicada", "simulada": "simulada", "error": "error", "cancelada": "cancelada",
              "subida": "imagen subida", "draft": "borrador en WordPress", "programada": "programada",
              "PUBLICADO": "publicada", "borrador": "borrador", "prueba": "prueba (simulado)",
              "lista": "lista para enviar (pegar en Perfit)"}
NO_SON_PIEZAS = ("subida", "prueba", "borrador", "simulada", "simulado")   # fuera del registro del panel (publicar_ui)
FORMATO_POR_CANAL = {"facebook": "cuadrado", "instagram": "vertical"}       # publicar_ui.FORMATO_POR_CANAL
FIRMA_DEFECTO = "— Br. David"
MAX_IMAGEN_BYTES = 12 * 1024 * 1024
_CACHE_COMPUESTAS: "OrderedDict[str, bytes]" = OrderedDict()                 # publicar_ui._componer cacheaba por contenido
_CACHE_MAX = 24
_candado = threading.Lock()


# ---------------- Modelos de entrada ----------------
class PiezaCompleta(BaseModel):
    """Todo lo que deja el formulario de Publicar de la web (= los campos de publicar_ui.formulario)."""
    canal: str                                  # wordpress | instagram | facebook | youtube
    titulo: str = ""
    texto: str = ""
    imagen_url: Optional[str] = None            # foto del banco, URL pegada o la subida con POST /banco/subir
    imagen_busqueda: Optional[str] = None
    fecha: Optional[str] = None                 # 'YYYY-MM-DD'
    hora: Optional[str] = None                  # 'HH:MM'
    # Diseño de la foto (Instagram / Facebook)
    texto_imagen: Optional[str] = None
    firma: Optional[str] = None
    formato: Optional[str] = None               # cuadrado | vertical | historia
    tipografia: Optional[str] = None
    peso: Optional[str] = None                  # normal | fina | negrita
    posicion: Optional[str] = None              # centro | arriba | abajo
    alineacion: Optional[str] = None            # centro | izquierda
    logo: Optional[str] = None                  # nombre de imagen.LOGOS ('Sin logo' = ninguno)
    posicion_logo: Optional[str] = None
    usar_compuesta: bool = True                 # «Publicar así»: destildado = va la foto sola
    # Pieza de video (un recorte que ya está en WordPress)
    video_url: Optional[str] = None
    video_formato: Optional[str] = None         # horizontal | vertical (el del recorte)
    vfmt: Optional[str] = None                  # reel | historia (formato en Instagram)
    borrador_id: Optional[str] = None           # si se está retomando un borrador


class Envio(PiezaCompleta):
    modo: str = "simulado"                      # 'real' (= «Enviar a <canal>», solo quien publica directo) | 'simulado' (= «Ver simulado»)


class Componer(BaseModel):
    imagen_url: str
    texto_imagen: str = ""
    firma: Optional[str] = FIRMA_DEFECTO
    formato: str = "cuadrado"
    tipografia: Optional[str] = None
    peso: str = "normal"
    posicion: str = "centro"
    alineacion: str = "centro"
    logo: Optional[str] = None
    posicion_logo: str = "abajo derecha"


class Aprobar(BaseModel):
    fecha: Optional[str] = None                 # 'YYYY-MM-DD'; sin fecha = hoy (como el date_input del panel)
    hora: Optional[str] = None                  # 'HH:MM'


class Rechazar(BaseModel):
    nota: str = ""


# ---------------- Registro de publicar.py → tabla publicaciones (publicar_ui._hook_registro) ----------------
# publicar.REGISTRAR_EXTRA es un global del módulo: acá se instala UNA vez y lee de una contextvar quién está enviando
# (la API atiende varias personas a la vez; Streamlit lo reasignaba en cada redibujo).
_contexto = contextvars.ContextVar("publicar_contexto", default=None)


def _hook_registro(entrada):
    ctx = _contexto.get()
    if not ctx:
        return
    # (22/10) una subida de imagen que NO pasó (modo simulado/apagado) o un borrado de media no son piezas: en Streamlit quedaban
    # como filas «prueba» del canal wordpress sin texto y confundían en «Mis publicaciones»
    if entrada.get("accion") in ("subir_imagen", "borrar_media") and entrada.get("resultado") != "subida":
        return
    pieza = entrada.get("pieza") or {}
    db.registrar_publicacion(
        usuario=ctx["usuario"], canal=entrada.get("canal", ""), modo=entrada.get("modo", ""),
        titulo=(pieza.get("title") or entrada.get("titulo") or ctx.get("titulo") or "")[:200],
        texto=(pieza.get("content") or pieza.get("caption") or pieza.get("message") or pieza.get("description") or "")[:5000],
        imagen_url=pieza.get("image_url") or entrada.get("url"),
        fecha_programada=_con_zona(pieza.get("date") or pieza.get("fecha_programada") or ctx.get("fecha")),
        estado="prueba" if entrada.get("modo") == "simulado" else str(entrada.get("resultado", ""))[:60],
        resultado=dict({k: v for k, v in entrada.items() if k not in ("pieza",)},
                       texto_imagen=ctx.get("texto_imagen") or None, origen="web"))


publicar.REGISTRAR_EXTRA = _hook_registro


def _con_zona(fecha):
    """publicar_ui._con_zona: la fecha del formulario es hora Argentina sin zona; en la base va con -03:00."""
    if fecha and len(fecha) >= 16 and fecha[-6] not in "+-" and not fecha.endswith("Z"):
        return fecha + ZONA_HORARIA
    return fecha


# ---------------- Helpers ----------------
def _rol(request: Request):
    s = auth.sesion(request)
    return s["usuario"], auth.rol_sesion(s)


def _cfg_real():
    return publicar.Config(os.environ)


def _cfg_simulada(cfg):
    """publicar_ui._cfg: quien no publica en real tiene todos los canales en simulado (los apagados siguen apagados)."""
    c = copy.copy(cfg)
    for a in ("modo_wp", "modo_ig", "modo_fb", "modo_yt"):
        if getattr(c, a) != "apagado":
            setattr(c, a, "simulado")
    return c


def _va_a_la_cola(canal, modo):
    """publicar_ui._va_a_la_cola. canal: nombre visible (Instagram...)."""
    if modo in ("apagado",):
        return False
    if canal == "Instagram":
        return True
    if canal == "Facebook":
        return modo != "real"
    return False


def _sin_firma_repetida(texto_imagen, firma):
    t = (texto_imagen or "").rstrip()
    f = (firma or "").strip()
    if f and t.endswith(f):
        t = t[: -len(f)].rstrip(" \n—-–")
    return t


def _fecha_iso(fecha, hora):
    return cr._fecha_iso(cr.Pieza(canal="instagram", fecha=fecha, hora=hora))


def _fecha_hora_de_iso(fp):
    fp = str(fp or "")
    return (fp[:10] if len(fp) >= 10 else None), (fp[11:16] if len(fp) >= 16 else None)


def _normalizar_diseno(p: PiezaCompleta, canal):
    """Los valores del diseño con los defaults de publicar_ui.formulario; None en lo que no aplica."""
    con_frase = bool((p.texto_imagen or "").strip())
    logo = p.logo if p.logo in imagen.LOGOS else ("Sin logo" if p.logo is None else "Sin logo")
    formato = p.formato if p.formato in imagen.FORMATOS else FORMATO_POR_CANAL.get(canal, "cuadrado")
    if con_frase:
        tipografia = p.tipografia if p.tipografia in imagen.TIPOGRAFIAS else imagen.TIPOGRAFIA_DEFAULT
        peso = p.peso if p.peso in imagen.PESOS else "normal"
        posicion = p.posicion if p.posicion in imagen.POSICIONES else "centro"
        alineacion = p.alineacion if p.alineacion in imagen.ALINEACIONES else "centro"
    else:
        tipografia, peso, posicion, alineacion = imagen.TIPOGRAFIA_DEFAULT, "normal", "centro", "centro"
    return {"con_frase": con_frase, "logo": logo, "con_logo": logo != "Sin logo", "formato": formato, "tipografia": tipografia,
            "peso": peso, "posicion": posicion, "alineacion": alineacion,
            "posicion_logo": p.posicion_logo if p.posicion_logo in imagen.POSICIONES_LOGO else "abajo derecha",
            "firma": (p.firma if p.firma is not None else FIRMA_DEFECTO).strip() if con_frase else ""}


def _componer_cacheado(fuente_url, texto_imagen, firma, formato, tipografia, posicion, alineacion, logo, posicion_logo, peso):
    clave = "|".join(str(x) for x in (fuente_url, texto_imagen, firma, formato, tipografia, posicion, alineacion, logo, posicion_logo, peso))
    with _candado:
        if clave in _CACHE_COMPUESTAS:
            _CACHE_COMPUESTAS.move_to_end(clave)
            return _CACHE_COMPUESTAS[clave]
    datos = imagen.componer_imagen(fuente_url, texto_imagen, firma=firma, formato=formato, tipografia=tipografia, posicion=posicion,
                                   alineacion=alineacion, peso=peso, logo=logo, posicion_logo=posicion_logo)
    with _candado:
        _CACHE_COMPUESTAS[clave] = datos
        while len(_CACHE_COMPUESTAS) > _CACHE_MAX:
            _CACHE_COMPUESTAS.popitem(last=False)
    return datos


def _compuesta_de(p: PiezaCompleta, canal, avisos):
    """La imagen con la frase (y/o el logo) encima, como arma publicar_ui.formulario antes de enviar; None si no corresponde."""
    if canal not in ("instagram", "facebook") or not (p.imagen_url or "").strip() or p.video_url:
        return None, None
    d = _normalizar_diseno(p, canal)
    if not (d["con_frase"] or d["con_logo"]) or not p.usar_compuesta:
        return None, d
    try:
        datos = _componer_cacheado((p.imagen_url or "").strip(), _sin_firma_repetida((p.texto_imagen or "").strip(), d["firma"]) if d["con_frase"] else "",
                                   d["firma"], d["formato"], d["tipografia"], d["posicion"], d["alineacion"],
                                   d["logo"] if d["con_logo"] else None, d["posicion_logo"], d["peso"])
        return datos, d
    except Exception as e:
        avisos.append(f"No pude componer la imagen: {e}. Se sigue con la foto sola.")
        return None, d


def _subir_compuesta(cfg, compuesta, titulo, texto, usuario, avisos):
    """La imagen compuesta tiene que estar en internet para IG/FB: va a la biblioteca de WordPress (publicar_ui._enviar)."""
    nombre = f"pieza-{datetime.date.today().isoformat()}-{(titulo or texto)[:40]}".strip()
    nombre = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in nombre).strip("-") + ".jpg"
    res_img = publicar.subir_imagen_wordpress(cfg, compuesta, nombre, titulo=titulo or texto[:60], quien=usuario,
                                              pieza=titulo or texto[:60], etiquetas=["pieza-compuesta"])
    if res_img.get("url"):
        return res_img["url"]
    avisos.append((res_img.get("aviso") or "No se pudo subir la imagen compuesta.") + " Se publica la foto sin la frase encima."
                  + (" (Para que funcione, WordPress tiene que estar en modo borrador o real.)" if res_img.get("modo") in ("apagado", "simulado") else ""))
    return None


def _validar(p: PiezaCompleta, simulado=False):
    canal = (p.canal or "").strip().lower()
    if canal not in CANALES:
        raise HTTPException(400, "Elegí el canal (Blogpost, Instagram, Facebook o YouTube). El newsletter se arma en su editor.")
    if not (p.texto or "").strip():
        raise HTTPException(400, "Falta el texto de la pieza.")
    if canal in ("wordpress", "youtube") and not (p.titulo or "").strip():
        raise HTTPException(400, f"En {CANAL_TXT[canal]} hace falta un título.")
    if canal == "youtube" and not (p.video_url or "").strip() and not simulado:
        raise HTTPException(400, "En YouTube hace falta el video: publicá un recorte (desde «Mis recortes» → Publicar). Subir un archivo de video sigue en Publicar de Streamlit.")
    return canal


def _datos_borrador(p: PiezaCompleta, canal, fecha_iso):
    """El dict `pieza` que guarda publicar_ui («💾 Guardar borrador») y que formulario() sabe retomar, con el diseño completo."""
    return {"canal": canal, "titulo": p.titulo or "", "texto": p.texto or "", "texto_imagen": p.texto_imagen or "",
            "video_url": p.video_url or None, "video_formato": p.video_formato or None, "vfmt": p.vfmt if p.video_url else None,
            "url": (p.imagen_url or "").strip(), "busq": p.imagen_busqueda or "", "firma": p.firma,
            "fmt": p.formato, "logo": p.logo, "plogo": p.posicion_logo, "tipo": p.tipografia, "peso": p.peso,
            "pos": p.posicion, "ali": p.alineacion, "usar_comp": bool(p.usar_compuesta),
            "fecha": fecha_iso[:10] if fecha_iso else None, "hora": fecha_iso[11:16] if fecha_iso else None,
            "origen": "web"}


def pieza_de_fila(p):
    """publicar_ui._pieza_de_borrador + lo que la web necesita para precargar el formulario desde cualquier fila."""
    res = p.get("resultado") or {}
    d = dict(res.get("pieza") or {})
    d["_pid"] = p["id"]
    d.setdefault("canal", p.get("canal"))
    d.setdefault("titulo", p.get("titulo") or "")
    d.setdefault("texto", p.get("texto") or "")
    d.setdefault("url", p.get("imagen_url") or "")
    d.setdefault("texto_imagen", res.get("texto_imagen") or "")
    d.setdefault("video_url", res.get("video_url"))
    if not d.get("fecha") and p.get("fecha_programada"):
        d["fecha"], d["hora"] = _fecha_hora_de_iso(p.get("fecha_programada"))
    d["imagen_busqueda"] = d.get("busq") or ""
    return d


def decorar(p):
    """Campos derivados que dibuja «Mis publicaciones» / el panel (los que calcula publicar_ui._fila_publicacion)."""
    res = p.get("resultado") or {}
    est = p.get("estado") or ""
    ultimo = res.get("ultimo") if isinstance(res.get("ultimo"), dict) else {}
    p["estado_texto"] = ESTADO_TXT.get(est, est)
    p["canal_texto"] = CANAL_TXT.get((p.get("canal") or "").lower(), p.get("canal") or "")
    p["video_url"] = res.get("video_url")
    p["texto_imagen"] = res.get("texto_imagen")
    p["formato"] = res.get("formato")
    p["nota"] = res.get("nota")
    p["propuesta_por"] = res.get("propuesta_por")
    p["aprobada_por"], p["aprobada_en"] = res.get("aprobada_por"), res.get("aprobada_en")
    p["rechazada_por"], p["rechazada_en"] = res.get("rechazada_por"), res.get("rechazada_en")
    p["cancelada_por"] = res.get("cancelada_por")
    p["plantilla"] = (res.get("pieza") or {}).get("plantilla") or res.get("plantilla") if p.get("canal") == "newsletter" else None
    # «ver publicación ↗»: el permalink (IG/FB) o el link (WP/YT) de lo que efectivamente salió
    p["ver_url"] = ultimo.get("permalink") or ultimo.get("link") or res.get("permalink") or res.get("link") or None
    p["link_editar"] = ultimo.get("link_editar") or res.get("link_editar") or None
    p["error_texto"] = str(ultimo.get("aviso", ""))[:200] if est == "error" else None
    p["eliminable"] = est in db.ELIMINABLES
    p["retomable"] = est == "borrador"
    return p


def _fila(pid):
    if not db.disponible():
        raise HTTPException(503, "Sin Supabase: no hay publicaciones.")
    r = db._req("GET", f"?id=eq.{quote(str(pid))}&select=id,creado,usuario,canal,modo,titulo,texto,imagen_url,estado,fecha_programada,procesado_en,resultado",
                tabla="publicaciones")
    if not r:
        raise HTTPException(404, "No existe esa pieza.")
    return r[0]


# ---------------- Opciones y banco ----------------
@router.get("/publicar/opciones")
def opciones(request: Request):
    """Para el formulario: las listas de imagen.py (logos, tipografías, pesos, posiciones, alineaciones, formatos), el modo real de
    cada canal y el que ve esta persona (publicar_ui._cfg: quien no publica en real ve todo simulado), si puede mandar a
    aprobación por canal, y su rol."""
    usuario, rol = _rol(request)
    r = cr.modos()
    canales = {}
    for c, nombre in CANALES.items():
        modo_real = r.get(c, "apagado")
        modo = modo_real if rol.get("publica") or modo_real == "apagado" else "simulado"
        canales[c] = {"nombre": nombre, "texto_canal": CANAL_TXT[c], "modo_real": modo_real, "modo": modo,
                      "texto": cr.MODO_TXT.get(modo, modo), "a_aprobar": cr._puede_proponer(c, r),
                      "configurado": bool(r.get({"wordpress": "wp_configurado", "instagram": "ig_configurado",
                                                 "facebook": "fb_configurado", "youtube": "yt_configurado"}[c]))}
    return {"canales": canales, "publica": bool(rol.get("publica")), "aprueba": bool(rol.get("aprueba")), "rol": rol.get("nombre"),
            "aprobadores": rol.get("aprobadores") or [], "usuario": usuario,
            "logos": list(imagen.LOGOS), "logos_url": {k: v for k, v in imagen.LOGOS.items() if v},
            "posiciones_logo": list(imagen.POSICIONES_LOGO), "tipografias": list(imagen.TIPOGRAFIAS), "tipografia_defecto": imagen.TIPOGRAFIA_DEFAULT,
            "pesos": list(imagen.PESOS), "posiciones": list(imagen.POSICIONES), "alineaciones": list(imagen.ALINEACIONES),
            "formatos": {k: list(v) for k, v in imagen.FORMATOS.items()}, "formato_por_canal": FORMATO_POR_CANAL,
            "firma_defecto": FIRMA_DEFECTO, "zona": ZONA_HORARIA}


@router.post("/banco/subir")
async def subir_al_banco(archivo: UploadFile = File(...), titulo: str = Form(""), pieza: str = Form(""), usuario=Depends(auth.usuario_actual)):
    """= «…o subí un archivo (va al banco de WordPress)»: publicar.subir_imagen_wordpress con el modo real de WordPress.
    En simulado/apagado no sube nada y lo dice (para Instagram/Facebook la imagen tiene que estar en internet)."""
    tipo = (archivo.content_type or "").lower()
    if not tipo.startswith("image/"):
        raise HTTPException(400, "Solo imágenes (jpg, png, webp).")
    datos = await archivo.read()
    if not datos:
        raise HTTPException(400, "El archivo está vacío.")
    if len(datos) > MAX_IMAGEN_BYTES:
        raise HTTPException(413, "La imagen pesa más de 12 MB.")
    nombre = re.sub(r"[^A-Za-z0-9._-]+", "-", archivo.filename or "imagen.jpg").strip("-") or "imagen.jpg"
    try:
        res = publicar.subir_imagen_wordpress(_cfg_real(), datos, nombre, titulo=titulo or nombre, quien=usuario, pieza=pieza or titulo or nombre)
    except Exception as e:
        raise HTTPException(502, f"No pude subir la imagen a WordPress: {e}")
    return {"ok": bool(res.get("url")), "url": res.get("url"), "id": res.get("id"), "modo": res.get("modo"),
            "aviso": res.get("aviso") or ("Imagen subida a la biblioteca de medios (ya queda en el banco)." if res.get("url") else None)}


@router.post("/publicar/componer")
def componer(datos: Componer, usuario=Depends(auth.usuario_actual)):
    """La vista previa de la foto con la frase (imagen.componer_imagen, mismos parámetros que el formulario de Streamlit).
    Devuelve el JPEG. Sin frase ni logo, devuelve la foto recortada al formato."""
    url = (datos.imagen_url or "").strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "Hace falta la URL de la foto (del banco o una que ya esté en internet).")
    formato = datos.formato if datos.formato in imagen.FORMATOS else "cuadrado"
    logo = datos.logo if datos.logo in imagen.LOGOS and imagen.LOGOS.get(datos.logo) else None
    texto = (datos.texto_imagen or "").strip()
    firma = (datos.firma if datos.firma is not None else FIRMA_DEFECTO).strip() if texto else ""
    try:
        jpg = _componer_cacheado(url, _sin_firma_repetida(texto, firma), firma, formato,
                                 datos.tipografia if datos.tipografia in imagen.TIPOGRAFIAS else imagen.TIPOGRAFIA_DEFAULT,
                                 datos.posicion if datos.posicion in imagen.POSICIONES else "centro",
                                 datos.alineacion if datos.alineacion in imagen.ALINEACIONES else "centro",
                                 logo, datos.posicion_logo if datos.posicion_logo in imagen.POSICIONES_LOGO else "abajo derecha",
                                 datos.peso if datos.peso in imagen.PESOS else "normal")
    except Exception as e:
        raise HTTPException(502, f"No pude componer la imagen: {e}")
    return Response(jpg, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=600"})


# ---------------- Guardar borrador · Enviar a aprobación · Enviar / Ver simulado ----------------
@router.post("/publicar/borrador")
def guardar_borrador(p: PiezaCompleta, usuario=Depends(auth.usuario_actual)):
    """= «💾 Guardar borrador»: guarda todo (diseño incluido) sin mandar nada; se retoma desde «Mis publicaciones» → Borradores.
    Con borrador_id actualiza el mismo (como Streamlit: «al guardar se actualiza el mismo»)."""
    if not db.disponible():
        raise HTTPException(503, "No pude guardar el borrador (falta la base de datos).")
    canal = (p.canal or "").strip().lower()
    if canal not in CANALES:
        raise HTTPException(400, "Elegí el canal para guardar el borrador.")
    fecha_iso = _fecha_iso(p.fecha, p.hora)
    if p.borrador_id:
        fila = _fila(p.borrador_id)
        if fila.get("usuario") != usuario or fila.get("estado") != "borrador":
            raise HTTPException(409, "Ese borrador ya no existe (o no es tuyo): se guarda uno nuevo si volvés a intentar sin el id.")
    pid = db.guardar_borrador(usuario, canal, p.titulo or "", p.texto or "", (p.imagen_url or "").strip() or None,
                              (fecha_iso + ZONA_HORARIA) if fecha_iso else None, _datos_borrador(p, canal, fecha_iso), pid=p.borrador_id)
    if not pid:
        raise HTTPException(503, "No pude guardar el borrador.")
    return {"ok": True, "id": pid, "estado": "borrador", "mensaje": "Guardado como borrador. Lo retomás desde «Mis publicaciones», filtro Borradores."}


def _borrar_borrador(borrador_id, usuario):
    """Como Streamlit: al enviar o mandar a aprobación, el borrador que se estaba retomando se elimina."""
    if not borrador_id:
        return
    try:
        db._req("DELETE", f"?id=eq.{quote(str(borrador_id))}&estado=eq.borrador&usuario=eq.{quote(usuario)}", tabla="publicaciones")
    except Exception as e:
        log.warning("No pude borrar el borrador %s: %s", borrador_id, e)


@router.post("/publicar/a-aprobar")
def enviar_a_aprobacion(p: PiezaCompleta, request: Request):
    """= «📨 Enviar a aprobación» (publicar_ui._enviar con aprobacion=True): sube la imagen compuesta a WordPress (si hay frase o
    logo y WordPress está en borrador/real) y deja la pieza 'a_aprobar' con texto_imagen, formato y video_url para la cola."""
    usuario, rol = _rol(request)
    if not db.disponible():
        raise HTTPException(503, "No pude guardar la pieza para aprobación (falta la base de datos).")
    canal = _validar(p)
    r = cr.modos()
    if not cr._puede_proponer(canal, r):
        if canal == "youtube":
            raise HTTPException(400, "YouTube no pasa por aprobación: lo publica directo quien tiene permiso (o se sube desde YouTube Studio).")
        raise HTTPException(400, f"{CANAL_TXT[canal]} está en modo {r.get(canal, 'apagado')}: no hay a dónde mandar la pieza cuando la aprueben. Guardala como borrador.")
    fecha_iso = _fecha_iso(p.fecha, p.hora)
    nombre = CANALES[canal]
    texto = p.texto if canal == "wordpress" else cr._texto_plano(p.texto)
    avisos = []
    imagen_url = (p.imagen_url or "").strip() or None
    compuesta, diseno = _compuesta_de(p, canal, avisos)
    token = _contexto.set({"usuario": usuario, "titulo": p.titulo, "texto_imagen": p.texto_imagen, "fecha": fecha_iso})
    try:
        if compuesta is not None:
            url = _subir_compuesta(_cfg_real(), compuesta, p.titulo or "", texto, usuario, avisos)
            if url:
                imagen_url = url
    finally:
        _contexto.reset(token)
    formato = (p.vfmt if p.video_url else (diseno or {}).get("formato")) if canal in ("instagram", "facebook") else None
    try:
        pid = db.proponer_publicacion(usuario, canal, r.get(canal), p.titulo or "", texto, imagen_url,
                                      (fecha_iso + ZONA_HORARIA) if fecha_iso else None,
                                      extra={"texto_imagen": (p.texto_imagen or None), "formato": formato or None,
                                             "video_url": (p.video_url or None), "origen": "web"})
    except Exception as e:
        raise HTTPException(503, f"No pude guardar la pieza para aprobación: {e}")
    if not pid:
        raise HTTPException(503, "No pude guardar la pieza para aprobación.")
    _borrar_borrador(p.borrador_id, usuario)
    quien = ", ".join(rol.get("aprobadores") or []) or "un aprobador"
    return {"ok": True, "id": pid, "estado": "a_aprobar", "modo": "aprobacion", "imagen_url": imagen_url, "avisos": avisos,
            "mensaje": f"Quedó pendiente de aprobación ({quien}). Si la aprueban, sale por {nombre}"
                       + (f" el {fecha_iso[:16].replace('T', ' ')}" if fecha_iso else " en la próxima corrida de la cola") + "."}


@router.post("/publicar/enviar")
def enviar(p: Envio, request: Request):
    """= «Enviar a <canal>» (modo real, solo quien publica directo) y «👁 Ver simulado» (modo simulado: arma la pieza tal cual
    saldría y la muestra; no manda nada y queda como 'prueba' en el registro). Es publicar_ui._enviar: sube la imagen compuesta
    a WordPress, encola si hay fecha y el canal no programa solo, o llama al conector. Devuelve el resultado del conector."""
    usuario, rol = _rol(request)
    simulado = (p.modo or "simulado") != "real"
    if not simulado and not rol.get("publica"):
        raise HTTPException(403, "Tu rol no publica directo: mandá la pieza a aprobación.")
    canal = _validar(p, simulado=simulado)
    nombre = CANALES[canal]
    cfg_real = _cfg_real()
    cfg = _cfg_simulada(cfg_real) if simulado else cfg_real
    modo = cfg.resumen()[canal]
    if modo == "apagado":
        raise HTTPException(400, f"{CANAL_TXT[canal]} está apagado. No se puede hacer nada por este canal.")
    fecha_iso = _fecha_iso(p.fecha, p.hora)
    texto = p.texto if canal == "wordpress" else cr._texto_plano(p.texto)
    titulo = (p.titulo or "").strip()
    avisos = []
    imagen_url = (p.imagen_url or "").strip() or None
    compuesta, diseno = _compuesta_de(p, canal, avisos)
    formato = (p.vfmt if p.video_url else (diseno or {}).get("formato")) if canal in ("instagram", "facebook") else None
    video_url = (p.video_url or "").strip() or None
    token = _contexto.set({"usuario": usuario, "titulo": titulo, "texto_imagen": p.texto_imagen, "fecha": fecha_iso})
    try:
        if compuesta is not None:
            # (publicar_ui._enviar recibe la cfg del envío) en «Ver simulado» la cfg es la simulada: no sube nada y avisa
            url = _subir_compuesta(cfg, compuesta, titulo, texto, usuario, avisos)
            if url:
                imagen_url = url
        if fecha_iso and _va_a_la_cola(nombre, modo):
            try:
                pid = db.encolar_publicacion(usuario, canal, modo, titulo, texto, imagen_url, fecha_iso + ZONA_HORARIA,
                                             extra={"texto_imagen": p.texto_imagen or None, "formato": formato or None, "video_url": video_url, "origen": "web"})
            except Exception as e:
                raise HTTPException(503, f"No pude guardar la pieza en la cola: {e}")
            if not pid:
                raise HTTPException(503, "No pude guardar la pieza en la cola (¿falta Supabase?).")
            _borrar_borrador(p.borrador_id, usuario)
            cuando = fecha_iso[:16].replace("T", " ")
            return {"ok": True, "modo": modo, "encolada": True, "id": pid, "estado": "pendiente", "imagen_url": imagen_url, "avisos": avisos,
                    "aviso": f"Quedó en la cola para el {cuando}. Ese día sale sola por {nombre}, con el modo que tenga el canal en ese momento (hoy: {modo}). "
                             "Se puede cancelar desde Aprobación → En cola.",
                    "pieza": {"image_url": imagen_url, ("caption" if canal == "instagram" else "message"): texto, "fecha_programada": fecha_iso}}
        try:
            if video_url and canal == "instagram":
                res = publicar.publicar_instagram_video(cfg, video_url, texto, quien=usuario, historia=(formato == "historia"))
            elif video_url and canal == "facebook":
                res = publicar.publicar_facebook_video(cfg, video_url, texto, quien=usuario, fecha=fecha_iso, titulo=titulo)
            elif video_url and canal == "youtube":
                datos, err = (None, None)
                if cfg.modo_yt in ("privado", "real"):
                    datos, err = publicar.bajar_bytes(video_url)
                if err:
                    res = {"ok": False, "modo": cfg.modo_yt, "aviso": f"No pude bajar el recorte de WordPress: {err}"}
                else:
                    res = publicar.publicar_youtube(cfg, datos or b"", titulo, texto, quien=usuario, fecha=fecha_iso,
                                                    nombre_archivo=video_url.rsplit("/", 1)[-1] or "clip.mp4")
            elif canal == "wordpress":
                imagen_id = publicar.media_id_por_url(cfg, imagen_url) if (imagen_url and not simulado) else None
                res = publicar.publicar_wordpress(cfg, titulo, publicar.html_video(video_url, texto) if video_url else texto,
                                                  imagen_id=imagen_id, quien=usuario, fecha=fecha_iso)
            elif canal == "instagram":
                res = publicar.publicar_instagram(cfg, imagen_url or "", texto, quien=usuario, historia=(formato == "historia"))
            elif canal == "youtube":
                res = publicar.publicar_youtube(cfg, b"", titulo, texto, quien=usuario, fecha=fecha_iso)
            else:
                res = publicar.publicar_facebook(cfg, imagen_url, texto, quien=usuario, fecha=fecha_iso)
        except HTTPException:
            raise
        except Exception as e:
            log.exception("publicar")
            res = {"ok": False, "modo": modo, "aviso": f"No pude publicar: {e}"}
    finally:
        _contexto.reset(token)
    if res.get("ok"):
        _borrar_borrador(p.borrador_id, usuario)
    salida = {k: v for k, v in res.items() if k in ("ok", "modo", "aviso", "estado", "id", "link", "link_editar", "permalink", "privacidad", "pieza")}
    salida.update(encolada=False, imagen_url=imagen_url, avisos=avisos, simulado=(modo == "simulado"),
                  texto_final=texto, formato=formato, video_url=video_url)
    return salida


# ---------------- Mis publicaciones: una pieza, retomar, eliminar ----------------
@router.get("/publicaciones/{pid}")
def una_publicacion(pid: str, request: Request):
    """La pieza (dueño o aprobador) decorada, más `pieza`: el dict con que el formulario se precarga («✏️ Retomar»)."""
    usuario, rol = _rol(request)
    p = _fila(pid)
    if p.get("usuario") != usuario and not rol.get("aprueba"):
        raise HTTPException(403, "Esa pieza es de otra persona.")
    p = decorar(p)
    p["pieza"] = pieza_de_fila(p)
    return p


@router.delete("/publicaciones/{pid}")
def eliminar_publicacion(pid: str, usuario=Depends(auth.usuario_actual)):
    """= «🗑 Eliminar»: borra de verdad, solo si es propia y está en un estado eliminable (db.ELIMINABLES)."""
    if not db.disponible():
        raise HTTPException(503, "Sin Supabase: no hay publicaciones.")
    if not db.eliminar_publicacion(pid, usuario):
        raise HTTPException(409, "Esa pieza no se puede eliminar (no es tuya o ya salió / está en proceso).")
    return {"ok": True}


# ---------------- Aprobación (publicar_ui.panel_aprobacion) ----------------
@router.get("/aprobacion/para-aprobar")
def para_aprobar(usuario=Depends(auth.aprobador)):
    """Las piezas a_aprobar (más viejas primero) con los datos de la vista previa, y el modo REAL de cada canal (el panel lo muestra:
    «el canal hoy está en modo X»). Sugerencia de fecha/hora como el panel: la pedida, o hoy + 20 min."""
    if not db.disponible():
        return {"piezas": [], "modos": {}}
    r = cr.modos()
    ahora = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-3))) + datetime.timedelta(minutes=20)
    piezas = []
    for p in db.listar_a_aprobar():
        p = decorar(p)
        f, h = _fecha_hora_de_iso(p.get("fecha_programada"))
        p["fecha_sugerida"], p["hora_sugerida"] = (f or ahora.strftime("%Y-%m-%d")), (h or ahora.strftime("%H:%M"))
        piezas.append(p)
    return {"piezas": piezas, "modos": {c: r.get(c, "apagado") for c in CANALES}}


@router.post("/aprobacion/{pid}/aprobar")
def aprobar(pid: str, datos: Aprobar, usuario=Depends(auth.aprobador)):
    """= «✅ Aprobar y programar»: pasa a 'pendiente' con la fecha/hora elegida (editable) y el modo real del canal; la cola la saca
    ese día (corre cada 15 min). Newsletter: queda 'lista' (el HTML se descarga y se pega en Perfit)."""
    p = _fila(pid)
    if p.get("estado") != "a_aprobar":
        raise HTTPException(409, f"Esa pieza ya no está pendiente de aprobación (estado: {ESTADO_TXT.get(p.get('estado'), p.get('estado'))}).")
    res = p.get("resultado") or {}
    canal = p.get("canal") or ""
    ahora = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    if canal == "newsletter":
        db.actualizar_publicacion(pid, {"estado": "lista", "resultado": dict(res, aprobada_por=usuario, aprobada_en=ahora)})
        return {"ok": True, "estado": "lista", "mensaje": "Aprobado. El HTML queda en «Mis publicaciones» de quien lo propuso y en el Registro, para descargar y pegar en Perfit."}
    fecha = datos.fecha or datetime.date.today().isoformat()
    hora = datos.hora or "09:00"
    fecha_iso = _fecha_iso(fecha, hora)
    modo = cr.modos().get(canal, "")
    db.aprobar_publicacion(pid, usuario, fecha_iso + ZONA_HORARIA, modo, res)
    return {"ok": True, "estado": "pendiente", "fecha_programada": fecha_iso + ZONA_HORARIA, "modo": modo,
            "mensaje": f"Aprobada. Sale por la cola el {fecha_iso[:16].replace('T', ' ')} (la cola corre cada 15 min)."}


@router.post("/aprobacion/{pid}/rechazar")
def rechazar(pid: str, datos: Rechazar, usuario=Depends(auth.aprobador)):
    """= «✖ Rechazar» con nota: quien la propuso lo ve en «Mis publicaciones» → Rechazadas."""
    p = _fila(pid)
    if p.get("estado") != "a_aprobar":
        raise HTTPException(409, "Esa pieza ya no está pendiente de aprobación.")
    db.rechazar_publicacion(pid, usuario, (datos.nota or "").strip(), p.get("resultado") or {})
    return {"ok": True, "estado": "rechazada", "mensaje": "Rechazada. Quien la propuso lo ve en «Mis publicaciones»."}


@router.get("/aprobacion/cola")
def cola(usuario=Depends(auth.aprobador)):
    """= «🗓 En cola»: las piezas pendientes, por fecha."""
    if not db.disponible():
        return []
    return [decorar(p) for p in db.listar_pendientes()]


@router.post("/aprobacion/{pid}/cancelar")
def cancelar(pid: str, usuario=Depends(auth.aprobador)):
    """= «Cancelar» de la cola: estado 'cancelada' con quién la canceló."""
    p = _fila(pid)
    if p.get("estado") != "pendiente":
        raise HTTPException(409, "Solo se cancela una pieza que está en la cola.")
    db.cancelar_publicacion(pid, usuario)
    return {"ok": True, "estado": "cancelada"}


@router.get("/aprobacion/registro")
def registro(usuario=Depends(auth.aprobador)):
    """= «📒 Registro»: quién creó cada pieza, quién la aprobó o rechazó y qué pasó (las últimas 60, sin subidas ni pruebas ni borradores)."""
    if not db.disponible():
        return []
    return [decorar(p) for p in db.listar_registro() if p.get("estado") not in NO_SON_PIEZAS]


@router.get("/aprobacion/papelera")
def papelera(usuario=Depends(auth.aprobador)):
    """= «🗑 Papelera»: conversaciones que alguien borró; se restauran durante db.PAPELERA_DIAS días."""
    if not db.disponible():
        return {"conversaciones": [], "dias": db.PAPELERA_DIAS}
    return {"conversaciones": db.listar_papelera() or [], "dias": db.PAPELERA_DIAS}


@router.post("/aprobacion/papelera/{cid}/restaurar")
def restaurar_de_papelera(cid: str, usuario=Depends(auth.aprobador)):
    """= «↩ Restaurar»: vuelve a aparecer en la lista de esa persona."""
    if not db.disponible():
        raise HTTPException(503, "Sin Supabase.")
    db.restaurar_conversacion(cid)
    return {"ok": True}
