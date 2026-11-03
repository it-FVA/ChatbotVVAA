"""Lo que comparten los routers de la Frase del día (api/frases/): modelos Pydantic, helpers de fecha y de forma JSON, y _cfg.
(3/11, revisión 5.2 punto 13) Los routers llaman a estos helpers como `c._x()` para que las pruebas puedan reemplazarlos acá
(monkeypatch.setattr(api.frases._comun, "_cfg", …)).
"""
import datetime
from typing import Optional

from fastapi import HTTPException
from pydantic import BaseModel

import db                       # noqa: E402
import programar_frases as pf   # noqa: E402


ESTADO_TXT = {"programada": "programada", "publicada": "publicada", "simulada": "simulada (la cola la procesó en modo simulado)",
              "saltada": "saltada: ese día no sale nada"}


DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


class Nueva(BaseModel):
    texto: str
    autor: str = ""


class Edicion(BaseModel):
    texto: Optional[str] = None
    autor: Optional[str] = None
    imagen_url: Optional[str] = None      # "" o null con `quitar_imagen` = volver a la foto por defecto
    quitar_imagen: bool = False
    estado: Optional[str] = None          # 'programada' | 'saltada'
    estilo: Optional[dict] = None         # (2/11 noche) {logo, posicion_logo, tipografia, peso, posicion, alineacion}: se guarda tal cual (claves válidas)
    quitar_estilo: bool = False           # volver al estilo global


class Mover(BaseModel):
    fecha: str


class Intercambio(BaseModel):
    id_a: str
    id_b: str


class Reparto(BaseModel):
    modo: str = "orden"
    desde: Optional[str] = None


class Vaciar(BaseModel):
    confirmo: bool = False


class PruebaMail(BaseModel):
    fecha: Optional[str] = None
    emails: Optional[list[str]] = None     # si no vienen, la lista de prueba de config (frase_mail_prueba)


class Activa(BaseModel):
    activa: bool


class Canales(BaseModel):
    canales: list[str]


class Solicitud(BaseModel):
    fecha: str
    frase_id: Optional[str] = None
    texto: Optional[str] = None
    autor: Optional[str] = None
    nota: Optional[str] = None
    imagen_url: Optional[str] = None      # (2/11 tarde) foto de fondo propuesta; sola = cambiar la de la frase que ya está ese día


class Resolver(BaseModel):
    respuesta: Optional[str] = None


def _hoy():
    return pf.hoy_argentina()


def _fecha(s):
    try:
        return datetime.date.fromisoformat(str(s)[:10])
    except Exception:
        raise HTTPException(400, "La fecha tiene que ser AAAA-MM-DD.")


def _fecha_txt(d):
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def _con_db():
    if not db.disponible():
        raise HTTPException(503, "Sin Supabase: no hay frases.")


def _frase(fid):
    _con_db()
    f = db.obtener_frase(fid)
    if not f:
        raise HTTPException(404, "No existe esa frase.")
    return f


def _url_foto(u):
    """Una foto es una URL http(s) (del banco de WordPress o de internet); la misma regla que PATCH /frases/{id}."""
    u = (u or "").strip()
    if u and not u.startswith(("http://", "https://")):
        raise HTTPException(400, "La foto tiene que ser una URL (http…).")
    return u or None


def _cerrada(f):
    """frases_ui: una frase que ya está en la cola o ya salió no se mueve ni se edita desde acá."""
    return (f.get("estado") in ("publicada", "simulada")) or bool(f.get("publicacion_id"))


def _publica(f):
    """La frase como la dibuja la pantalla (texto, autor, estado, rotación, foto)."""
    if not f:
        return None
    return {"id": f["id"], "texto": f.get("texto") or "", "autor": f.get("autor"), "fecha": f.get("fecha"), "estado": f.get("estado") or "programada",
            "estado_texto": ESTADO_TXT.get(f.get("estado") or "programada", f.get("estado")), "validada": bool(f.get("validada")),
            "imagen_url": f.get("imagen_url"), "estilo": f.get("estilo") or None, "publicacion_id": f.get("publicacion_id"), "fuente": f.get("fuente"), "tema": f.get("tema"),
            "orden": f.get("orden"), "ultima_publicada": f.get("ultima_publicada"), "veces_publicada": int(f.get("veces_publicada") or 0),
            "repetida": bool(f.get("ultima_publicada")), "cerrada": _cerrada(f)}


def _cfg():
    import os
    import publicar
    return publicar.Config(os.environ), publicar


def _estilo_opciones():
    """(2/11 noche) Las listas de imagen.py para la solapa «Diseño» del día (las mismas de Diseñar)."""
    import imagen
    return {"logos": list(imagen.LOGOS), "posiciones_logo": list(imagen.POSICIONES_LOGO), "tipografias": list(imagen.TIPOGRAFIAS),
            "pesos": list(imagen.PESOS), "posiciones": list(imagen.POSICIONES), "alineaciones": list(imagen.ALINEACIONES)}
