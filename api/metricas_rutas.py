"""Métricas de campañas y canales (8/11, Franco; pedido de Beto: «que la app sea el centro de métricas de evolución de campañas»).
Pestaña «Métricas» de Administración, solo admins. Contrato con la web: web/maquetas/metricas-contrato.md. La lógica está en
metricas.py (campañas, canales, captura), metricas_meta.py (HTTP contra Meta) y metricas_resumen.py (el resumen con IA).

  GET  /admin/metricas/campanas?dias=90 | mes=AAAA-MM   campañas (Proyectos) con sus piezas por canal y por estado, y las métricas de cada pieza
  GET  /admin/metricas/canales                           una tarjeta por canal: estado de la conexión, últimos números, enlace y lo anotado a mano
  POST /admin/metricas/actualizar                        captura ahora Instagram y Facebook (cuenta de 28 días + piezas de los últimos 60); nunca 500 por Meta
  PUT  /admin/metricas/manual                            anota números a mano de un canal o de una pieza (queda en usuarios_cambios, clave metricas_manual:<ref>)
  GET  /admin/metricas/resumen/{ref}                     el último resumen con IA de una campaña (id de proyecto o «sueltas»), o null
  POST /admin/metricas/resumen                           genera uno nuevo con el modelo auxiliar y lo guarda

La tabla `metricas` se crea con api/migraciones/20261108_1200_metricas.sql (la corre Franco a mano). Sin ella, las lecturas dan 503
con un texto que lo dice.
"""
import os
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
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
    piezas_total: int
    por_canal: dict[str, dict[str, int]]
    por_estado: dict[str, int]
    primera: Optional[str] = None
    ultima: Optional[str] = None
    piezas: list[PiezaCampana]


class Totales(BaseModel):
    piezas: int
    publicada: int
    programada: int
    en_aprobacion: int
    borrador: int
    prueba: int
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
    ultima: Optional[FilaMetrica] = None
    manual: Optional[FilaManual] = None


class CanalesResp(BaseModel):
    actualizado: Optional[str] = None
    canales: list[CanalMetricas]


class ResultadoCanal(BaseModel):
    ok: bool
    piezas: int
    error: Optional[str] = None


class ActualizarResp(BaseModel):
    capturado: str
    instagram: ResultadoCanal
    facebook: ResultadoCanal


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
def ver_campanas(dias: Optional[int] = None, mes: Optional[str] = None, quien=Depends(auth.admin)):
    """Campañas con sus piezas del período (90 días por defecto), agrupadas por estado y canal, y la última métrica de cada pieza."""
    p = periodo(DIAS_DEFECTO if (dias is None and not mes) else dias, mes)
    return _leer(metricas.campanas, p)


@router.get("/canales", response_model=CanalesResp)
def ver_canales(quien=Depends(auth.admin)):
    """Una tarjeta por canal: Instagram y Facebook por la plataforma; YouTube, mail, sitio y WhatsApp con enlace y carga a mano."""
    return _leer(metricas.canales_estado, _config())


@router.post("/actualizar", response_model=ActualizarResp)
def actualizar(quien=Depends(auth.admin)):
    """Captura ahora los números de Instagram y Facebook. Un error de Meta no es un 500: vuelve en `error` de cada canal."""
    if not db.disponible():
        raise HTTPException(503, "Sin Supabase no hay dónde guardar las métricas.")
    return metricas.capturar(_config(), por=quien)


@router.put("/manual", response_model=ManualOut)
def anotar_a_mano(datos: ManualIn, quien=Depends(auth.admin)):
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


@router.get("/resumen/{ref}", response_model=Optional[ResumenOut])
def ver_resumen(ref: str, quien=Depends(auth.admin)):
    """El último resumen con IA guardado de la campaña (id de proyecto o «sueltas»), o null si todavía no hay."""
    import metricas_resumen
    return _leer(metricas_resumen.ultimo, ref)


@router.post("/resumen", response_model=ResumenOut)
def generar_resumen(datos: ResumenIn, quien=Depends(auth.admin)):
    """Genera un resumen nuevo de «¿cómo le fue a esta campaña?» con el modelo auxiliar y lo guarda. El uso queda a nombre de quien lo pidió."""
    import metricas_resumen
    if not db.disponible():
        raise HTTPException(503, "Sin Supabase no hay de dónde sacar las campañas.")
    try:
        return metricas_resumen.generar(datos.ref, datos.dias, quien)
    except metricas_resumen.ResumenNoDisponible as e:
        raise HTTPException(503, str(e))
    except LookupError as e:
        raise HTTPException(404, str(e))
    except RuntimeError as e:
        raise HTTPException(502, str(e))
