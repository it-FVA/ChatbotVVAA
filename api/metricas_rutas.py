"""Métricas de campañas y canales (8/11, Franco; pedido de Beto: «que la app sea el centro de métricas de evolución de campañas»).
Pestaña «Métricas» de Gestión (Aprobación; 8/11, Franco): quienes aprueban y admins. Contrato con la web: web/maquetas/metricas-contrato.md. La lógica está en
metricas.py (campañas, canales, captura), metricas_meta.py (HTTP contra Meta) y metricas_asesor.py (el asesor de campañas con IA).

  GET  /admin/metricas/campanas?dias=90 | mes=AAAA-MM   campañas (Proyectos) con sus piezas por canal y por estado, y las métricas de cada pieza
  GET  /admin/metricas/canales                           una tarjeta por canal: estado de la conexión, últimos números, enlace y lo anotado a mano, últimas piezas y la mejor (12/11)
  GET  /admin/metricas/serie?canal=instagram&dias=28     (12/11) un punto por día de los números del canal: la tendencia de la tarjeta
  POST /admin/metricas/actualizar                        captura ahora Instagram, Facebook, YouTube, el sitio y el mail (Perfit) (cuenta de 28 días + piezas de los últimos 60); nunca 500 por las plataformas
  GET  /admin/metricas/wordpress/autorizar               (8/11) redirige (302) a WordPress.com para conectar el sitio; el `state` va firmado y vence a los 10 minutos
  GET  /admin/metricas/wordpress/callback?code&state     (8/11) vuelve de WordPress.com: canjea el código, guarda el token y redirige a la web (?wordpress=ok | error&motivo=)
  DELETE /admin/metricas/wordpress                       (8/11) desconecta el sitio (borra el token guardado)
  PUT  /admin/metricas/manual                            anota números a mano de un canal o de una pieza (queda en usuarios_cambios, clave metricas_manual:<ref>)
  GET  /admin/metricas/resumen/{ref}                     el último resumen con IA de una campaña (id de proyecto o «sueltas»), o null
  POST /admin/metricas/resumen                           genera uno nuevo con el modelo auxiliar y lo guarda
  GET  /admin/metricas/asesor/apertura?dias=90           el mensaje con que el asesor recibe al abrir la pestaña (se genera una vez por día)
  POST /admin/metricas/asesor                            conversa con el asesor de campañas: {mensajes: [{rol, texto}], dias} → {texto, fuentes, falto}

La tabla `metricas` se crea con api/migraciones/20261108_1200_metricas.sql (la corre Franco a mano). Sin ella, las lecturas dan 503
con un texto que lo dice.
"""
import os, secrets, urllib.parse
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from . import auth
import db            # noqa: E402  (api/__init__ pone la raíz del repo en sys.path)
import metricas      # noqa: E402
from .admin_rutas import periodo   # noqa: E402

router = APIRouter(prefix="/admin/metricas", tags=["metricas"])

DIAS_DEFECTO = 90
FALTA_TABLA = "No pude leer las métricas (¿falta aplicar la migración 20261108_1200_metricas?): "


# ---------------- modelos de respuesta (la web genera tiposApi.d.ts desde acá) ----------------
class Periodo(BaseModel):
    tipo: str
    dias: Optional[int] = None
    mes: Optional[str] = None
    desde: str
    hasta: Optional[str] = None
    texto: str


class MetricasPieza(BaseModel):
    """Los números normalizados que haya (todas las claves son opcionales: lo que la plataforma no da, no está) + de dónde salen."""
    model_config = {"extra": "allow"}
    alcance: Optional[int] = None
    vistas: Optional[int] = None
    me_gusta: Optional[int] = None
    comentarios: Optional[int] = None
    guardados: Optional[int] = None
    compartidos: Optional[int] = None
    clics: Optional[int] = None
    interacciones: Optional[int] = None
    respuestas: Optional[int] = None
    fuente: str
    capturado: Optional[str] = None


class PiezaCampana(BaseModel):
    id: str
    canal: str
    canal_texto: str
    titulo: str
    estado: Optional[str] = None
    estado_grupo: str
    fecha: Optional[str] = None
    ver_url: Optional[str] = None
    formato: Optional[str] = None
    usuario: Optional[str] = None
    modo: Optional[str] = None
    metricas: Optional[MetricasPieza] = None


class Campana(BaseModel):
    id: str
    nombre: Optional[str] = None
    emoji: Optional[str] = None
    color: Optional[str] = None
    dueno: Optional[str] = None
    creado: Optional[str] = None
    descripcion: Optional[str] = None             # (12/11) la del Proyecto, o null; la Frase del día automática lleva la suya
    piezas_total: int
    por_canal: dict[str, dict[str, int]]
    por_estado: dict[str, int]
    primera: Optional[str] = None
    ultima: Optional[str] = None
    piezas: list[PiezaCampana]


class Totales(BaseModel):
    piezas: int
    publicada: int
    saliendo: int                  # (12/11) mail que está saliendo en tandas; cuenta como hecha
    programada: int
    en_aprobacion: int
    borrador: int
    prueba: int
    cancelada: int                 # (12/11) canceladas a propósito; no cuentan como hechas ni como «no salió»
    no_salio: int
    por_canal: dict[str, int]


class CampanasResp(BaseModel):
    periodo: Periodo
    campanas: list[Campana]
    sueltas: Campana
    totales: Totales


class FilaMetrica(BaseModel):
    """Una captura: `datos` lleva los números normalizados, `crudo` (lo que devolvió la plataforma) y `errores`."""
    datos: dict[str, Any]
    periodo_desde: Optional[str] = None
    periodo_hasta: Optional[str] = None
    capturado: Optional[str] = None
    fuente: Optional[str] = None


class FilaAnterior(BaseModel):
    """(12/11) La captura por API de hace ~28 días (entre 20 y 40), con solo los números normalizados."""
    datos: dict[str, float]
    periodo_desde: Optional[str] = None
    periodo_hasta: Optional[str] = None
    capturado: Optional[str] = None


class PiezaCanal(BaseModel):
    """(12/11, Franco) Una pieza publicada de un canal, para «Lo último que salió» y «La que mejor anduvo» de la tarjeta."""
    id: str
    titulo: str
    formato: Optional[str] = None
    fecha: Optional[str] = None
    campana: Optional[str] = None                 # nombre de la campaña, o null si es suelta
    ver_url: Optional[str] = None
    metricas: Optional[MetricasPieza] = None


class FilaManual(FilaMetrica):
    nota: Optional[str] = None
    por: Optional[str] = None


class CanalMetricas(BaseModel):
    clave: str
    texto: str
    icono: str
    modo: str
    configurado: bool
    api: str                       # disponible | sin_permiso | no_hay | pendiente | error
    nota_api: str
    enlace: Optional[str] = None
    enlace_texto: Optional[str] = None
    conectado: bool = False                       # (8/11) solo el sitio: ¿hay una conexión con WordPress.com guardada?
    conectar_url: Optional[str] = None            # (8/11) solo el sitio: ruta de esta API que lleva a WordPress.com (la web la abre con un link normal)
    ultima: Optional[FilaMetrica] = None
    manual: Optional[FilaManual] = None
    anterior: Optional[FilaAnterior] = None       # (12/11) null si no hay captura de hace 20-40 días
    ultimas_piezas: list[PiezaCanal] = []         # (12/11) hasta 3 piezas publicadas, las más recientes (sin los usuarios excluidos)
    mejor_pieza: Optional[PiezaCanal] = None      # (12/11) la de mayor alcance (si no, vistas, si no, aperturas) de los últimos 28 días; null si ninguna tiene números
    tasas: dict[str, Optional[float]] = {}        # (12/11) cocientes con 3 decimales o null: alcance_sobre_seguidores, interacciones_sobre_alcance, aperturas_sobre_enviados, clics_sobre_enviados, visitas_por_dia


class CanalesResp(BaseModel):
    actualizado: Optional[str] = None
    canales: list[CanalMetricas]


class PuntoSerie(BaseModel):
    dia: str                                      # AAAA-MM-DD, hora Argentina
    datos: dict[str, float]                       # los números normalizados de la última captura de ese día


class SerieResp(BaseModel):
    canal: str
    dias: int
    puntos: list[PuntoSerie]


class ResultadoCanal(BaseModel):
    ok: bool
    piezas: int
    error: Optional[str] = None


class ActualizarResp(BaseModel):
    capturado: str
    instagram: ResultadoCanal
    facebook: ResultadoCanal
    youtube: ResultadoCanal                      # (8/11, Franco)
    sitio: ResultadoCanal                        # (8/11, Franco) estadísticas de WordPress.com
    mail: ResultadoCanal                         # (8/11, Franco) Perfit: cuenta de 28 días + envíos de la Frase del día


class ManualIn(BaseModel):
    ambito: str                                  # canal | pieza
    ref: str                                     # clave del canal o id de la pieza
    canal: Optional[str] = None
    periodo_desde: Optional[str] = None          # AAAA-MM-DD
    periodo_hasta: Optional[str] = None
    datos: dict[str, Any]
    nota: Optional[str] = None


class ManualOut(BaseModel):
    id: Optional[str] = None
    ambito: str
    ref: str
    canal: Optional[str] = None
    datos: dict[str, Any]
    periodo_desde: Optional[str] = None
    periodo_hasta: Optional[str] = None
    nota: Optional[str] = None
    por: Optional[str] = None
    capturado: Optional[str] = None


class ResumenIn(BaseModel):
    ref: str                                     # id de la campaña o «sueltas»
    dias: int = Field(DIAS_DEFECTO, ge=1, le=365)


class Mensaje(BaseModel):
    rol: Literal["usuario", "asesor"]
    texto: str


class AsesorIn(BaseModel):
    mensajes: list[Mensaje] = Field(..., min_length=1)       # los últimos 12 de la conversación; el último es del usuario
    dias: int = Field(DIAS_DEFECTO, ge=1, le=365)


class AsesorOut(BaseModel):
    texto: str
    fuentes: list[str]
    falto: list[str]


class AperturaOut(AsesorOut):
    capturado: Optional[str] = None
    nuevo: bool


class ResumenOut(BaseModel):
    ref: str
    nombre: Optional[str] = None
    texto: str
    fuentes: list[str]
    falto: list[str]
    comparado_con: Optional[str] = None
    modelo: str
    capturado: Optional[str] = None


# ---------------- helpers ----------------
def _config():
    import publicar
    return publicar.Config(os.environ)


def _leer(fn, *a):
    """Las lecturas de la base: un RuntimeError (Supabase caído o tabla sin migrar) se vuelve 503 con texto para la persona."""
    try:
        return fn(*a)
    except RuntimeError as e:
        raise HTTPException(503, FALTA_TABLA + str(e)[:160])


# ---------------- rutas ----------------
@router.get("/campanas", response_model=CampanasResp)
def ver_campanas(dias: Optional[int] = None, mes: Optional[str] = None, quien=Depends(auth.aprobador_o_admin)):
    """Campañas con sus piezas del período (90 días por defecto), agrupadas por estado y canal, y la última métrica de cada pieza."""
    p = periodo(DIAS_DEFECTO if (dias is None and not mes) else dias, mes)
    return _leer(metricas.campanas, p)


@router.get("/canales", response_model=CanalesResp)
def ver_canales(quien=Depends(auth.aprobador_o_admin)):
    """Una tarjeta por canal: Instagram, Facebook y YouTube por la plataforma; mail, sitio y WhatsApp con enlace y carga a mano."""
    return _leer(metricas.canales_estado, _config())


@router.get("/serie", response_model=SerieResp)
def ver_serie(canal: str, dias: int = Query(28, ge=1, le=120), quien=Depends(auth.aprobador_o_admin)):
    """(12/11, Franco) La tendencia de un canal: un punto por día (la última captura por API de ese día), de los últimos `dias`. Cada punto trae el total
    de los 28 días que terminaban ese día. Vacía si todavía no hay capturas."""
    if canal not in metricas.CLAVES_CANAL:
        raise HTTPException(400, "Ese canal no existe: " + ", ".join(metricas.CLAVES_CANAL) + ".")
    return {"canal": canal, "dias": dias, "puntos": _leer(metricas.serie, canal, dias)}


@router.post("/actualizar", response_model=ActualizarResp)
def actualizar(quien=Depends(auth.aprobador_o_admin)):
    """Captura ahora los números de Instagram, Facebook y YouTube. Un error de la plataforma no es un 500: vuelve en `error` de cada canal."""
    if not db.disponible():
        raise HTTPException(503, "Sin Supabase no hay dónde guardar las métricas.")
    return metricas.capturar(_config(), por=quien)


@router.put("/manual", response_model=ManualOut)
def anotar_a_mano(datos: ManualIn, quien=Depends(auth.aprobador_o_admin)):
    """Anota números a mano (fuente 'manual'). Las claves y los enteros ≥ 0 se validan acá; queda en usuarios_cambios."""
    if not db.disponible():
        raise HTTPException(503, "Sin Supabase no hay dónde guardar.")
    try:
        antes = db.ultimas_metricas(datos.ambito, refs=[datos.ref], fuente="manual").get((datos.ref, "manual"))
        fila = metricas.guardar_manual(quien, datos.ambito, datos.ref, datos.canal, datos.periodo_desde, datos.periodo_hasta, datos.datos, datos.nota)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(503, FALTA_TABLA + str(e)[:160])
    db.registrar_cambio_usuario(quien, "config", f"metricas_manual:{datos.ref}", {"de": (antes or {}).get("datos"), "a": fila.get("datos") if fila else None})
    return fila


def _asesor(fn, *a):
    """Llama al asesor y traduce sus errores: sin clave de OpenAI 503, sin pregunta 400, sin campaña 404, falla del modelo 502."""
    import metricas_asesor
    if not db.disponible():
        raise HTTPException(503, "Sin Supabase no hay de dónde sacar las campañas.")
    try:
        return fn(metricas_asesor, *a)
    except metricas_asesor.ResumenNoDisponible as e:
        raise HTTPException(503, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except LookupError as e:
        raise HTTPException(404, str(e))
    except RuntimeError as e:
        msg = str(e)
        raise HTTPException(503 if msg.startswith("Supabase") else 502, FALTA_TABLA + msg[:160] if msg.startswith("Supabase") else msg)


@router.get("/resumen/{ref}", response_model=Optional[ResumenOut])
def ver_resumen(ref: str, quien=Depends(auth.aprobador_o_admin)):
    """El último resumen con IA guardado de la campaña (id de proyecto o «sueltas»), o null si todavía no hay."""
    import metricas_asesor
    return _leer(metricas_asesor.ultimo, ref)


@router.post("/resumen", response_model=ResumenOut)
def generar_resumen(datos: ResumenIn, quien=Depends(auth.aprobador_o_admin)):
    """Genera un resumen nuevo de «¿cómo le fue a esta campaña?» (una pregunta fija al asesor) y lo guarda. El uso queda a nombre de quien lo pidió."""
    return _asesor(lambda m, *a: m.resumen_campana(*a), datos.ref, datos.dias, quien, _config())


@router.get("/asesor/apertura", response_model=AperturaOut)
def apertura_asesor(dias: int = Query(DIAS_DEFECTO, ge=1, le=365), forzar: bool = False, quien=Depends(auth.aprobador_o_admin)):
    """El mensaje proactivo del asesor al abrir la pestaña. Se reutiliza el guardado de hoy mientras los datos no cambien (campañas,
    piezas, números por canal); si cambió algo, o con `forzar=1` («Volver a mirar»), se arma de nuevo. (8/11, Franco)"""
    return _asesor(lambda m, *a: m.apertura(*a, forzar=forzar), dias, quien, _config())


@router.post("/asesor", response_model=AsesorOut)
def preguntar_al_asesor(datos: AsesorIn, quien=Depends(auth.aprobador_o_admin)):
    """Conversa con el asesor de campañas. La conversación no se guarda: la web manda los últimos mensajes cada vez."""
    from .admin_rutas import periodo as _periodo
    msgs = [m.model_dump() for m in datos.mensajes][-12:]
    r = _asesor(lambda m, *a: m.responder(*a), msgs, _periodo(datos.dias, None), quien, _config())
    return {k: r[k] for k in ("texto", "fuentes", "falto")}


# ---------------- conectar el sitio con WordPress.com (8/11, Franco) ----------------
# Flujo «authorization code» de WordPress.com (https://developer.wordpress.com/docs/oauth2/), dos clics desde la pantalla:
#   1. la web abre GET /wordpress/autorizar (link normal, con la cookie de admin) → 302 a WordPress.com con un `state` firmado;
#   2. la persona toca «Aprobar» allá y WordPress.com vuelve a GET /wordpress/callback?code&state.
# El callback NO exige la cookie de admin: llega desde otro sitio y la cookie de sesión puede no viajar (SameSite). Lo que lo autoriza es
# el `state`: lo firmamos nosotros con el secreto de sesión (auth.firmar_estado, otra «sal»), lleva el usuario (aprobador o admin) que lo pidió y
# vence a los 10 minutos. Sin un `state` válido → 400 y no se canjea nada. El token nunca se imprime ni se devuelve.
PROPOSITO_WPCOM = "wpcom"
VIGENCIA_STATE_SEG = 10 * 60


def _base_api(request: Request):
    """La dirección pública de la API: API_URL_PUBLICA si está, si no la del pedido. Tiene que dar la MISMA redirect URL al autorizar y al canjear."""
    b = os.environ.get("API_URL_PUBLICA", "").strip().rstrip("/")
    return b or str(request.base_url).rstrip("/")


def _redirect_uri(request: Request):
    return _base_api(request) + router.prefix + "/wordpress/callback"


def _url_web():
    """A dónde vuelve la persona: WEB_URL, si no el primer origen de CORS_ORIGENES."""
    w = os.environ.get("WEB_URL", "").strip()
    if not w:
        w = next((o.strip() for o in os.environ.get("CORS_ORIGENES", "").split(",") if o.strip()), "")
    return (w or "http://localhost:5173").rstrip("/")


def _volver(ok=True, motivo=None):
    q = {"wordpress": "ok"} if ok else {"wordpress": "error", "motivo": (motivo or "No pude conectar con WordPress.com.")[:140]}
    return RedirectResponse(f"{_url_web()}/aprobacion/metricas?{urllib.parse.urlencode(q)}", status_code=302)


@router.get("/wordpress/autorizar", include_in_schema=False)
def wordpress_autorizar(request: Request, quien=Depends(auth.aprobador_o_admin)):
    """Primer clic: manda a la persona a WordPress.com a aprobar la lectura de las estadísticas del sitio."""
    import metricas_wordpress as mw
    cfg = _config()
    if not (getattr(cfg, "wpcom_client_id", "") and getattr(cfg, "wpcom_client_secret", "")):
        return _volver(False, mw.TEXTO_SIN_APP)
    state = auth.firmar_estado({"u": quien, "n": secrets.token_urlsafe(8)}, PROPOSITO_WPCOM)
    return RedirectResponse(mw.url_autorizacion(cfg, _redirect_uri(request), state), status_code=302)


@router.get("/wordpress/callback", include_in_schema=False)
def wordpress_callback(request: Request, code: str = "", state: str = "", error: str = "", error_description: str = ""):
    """Segundo paso: WordPress.com vuelve acá. Valida el `state`, canjea el código, guarda el token y redirige a la web."""
    import metricas_wordpress as mw
    datos = auth.leer_estado(state, PROPOSITO_WPCOM, VIGENCIA_STATE_SEG) if state else None
    quien = datos.get("u") if isinstance(datos, dict) else None
    if not quien:
        raise HTTPException(400, "El pedido de conexión venció o no es válido: volvé a tocar «Conectar con WordPress.com» en Métricas.")
    try:                         # el usuario que lo pidió tiene que seguir aprobando o administrando, y estar activo (8/11, Franco)
        fila = auth._fila(quien)
        r = auth.rol_sesion({"usuario": quien}) if fila else None
        if fila and (not fila.get("activo", True) or not (r["admin"] or r["aprueba"])):
            raise HTTPException(400, "El usuario que pidió la conexión ya no aprueba ni administra.")
    except HTTPException:
        raise
    except Exception:
        pass
    if error:
        return _volver(False, "WordPress.com no dio el permiso." if error == "access_denied" else f"WordPress.com respondió: {error_description or error}")
    if not db.disponible():
        return _volver(False, "Sin Supabase no hay dónde guardar la conexión.")
    tok, err = mw.canjear_codigo(_config(), code, _redirect_uri(request))
    if not tok:
        return _volver(False, err)
    try:
        previo = mw.token_guardado()
        reg = mw.guardar_token(tok, quien)
        db.registrar_cambio_usuario(quien, "config", mw.CLAVE_TOKEN, {"de": "conectado" if previo else "sin conexión", "a": "conectado",
                                                                     "sitio": reg.get("blog_url")})       # nunca el token
    except Exception as e:
        return _volver(False, f"No pude guardar la conexión: {type(e).__name__}")
    return _volver(True)


@router.delete("/wordpress")
def wordpress_desconectar(quien=Depends(auth.aprobador_o_admin)):
    """Desconecta el sitio: borra el token guardado. Las estadísticas ya guardadas quedan; para volver a leer hay que conectar de nuevo."""
    import metricas_wordpress as mw
    if not db.disponible():
        raise HTTPException(503, "Sin Supabase no hay dónde guardar.")
    previo = mw.token_guardado()
    try:
        mw.borrar_token(quien)
    except RuntimeError as e:
        raise HTTPException(503, str(e)[:160])
    db.registrar_cambio_usuario(quien, "config", mw.CLAVE_TOKEN, {"de": "conectado" if previo else "sin conexión", "a": "desconectado"})
    return {"ok": True}
