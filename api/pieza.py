"""(3/11, revisión 5.2 punto 10) El modelo ÚNICO de una pieza, compartido por el chat (api/chat_rutas: /publicaciones/borrador y
/a-aprobar) y por Diseñar (api/publicar_rutas: /publicar/borrador, /a-aprobar y /enviar). Antes había dos modelos Pydantic (Pieza y
PiezaCompleta) y dos `_datos_borrador` que armaban el mismo dict con claves cortas; un campo nuevo se agregaba cuatro veces.

Un campo nuevo en la pieza = un campo acá (y, si se guarda con clave corta en `publicaciones.resultado.pieza`, una entrada en
CLAVES_CORTAS). a_borrador() y desde_fila() lo recorren solos; los tipos de la web salen del OpenAPI (`npm run tipos` en web/).
"""
import re
from typing import Optional

from fastapi import HTTPException
from pydantic import BaseModel

ZONA_HORARIA = "-03:00"            # las fechas del formulario son hora de Argentina

# Campo del modelo → clave corta con la que se guarda en publicaciones.resultado.pieza (borradores y pruebas, desde el 22/10).
# Los campos que no están acá se guardan con su nombre.
CLAVES_CORTAS = {"imagen_url": "url", "imagen_busqueda": "busq", "formato": "fmt", "posicion_logo": "plogo", "tipografia": "tipo",
                 "posicion": "pos", "alineacion": "ali", "usar_compuesta": "usar_comp"}
# Campos que NO van al dict guardado (se derivan o viajan aparte)
NO_SE_GUARDAN = ("borrador_id", "fecha", "hora", "canal")


class Pieza(BaseModel):
    """Todo lo que deja el formulario de Diseñar (= los campos) o el recuadro «Publicar esta pieza» del chat (que manda menos)."""
    canal: str                                  # wordpress | instagram | facebook | youtube (canales.de_disenar())
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
    borrador_id: Optional[str] = None           # si se está retomando un borrador: se actualiza (o se elimina al mandar)
    # (5/11, Franco) Carrusel: las URLs https de las fotos, en orden (2 a 10). imagen_url es la primera (la portada).
    imagenes: Optional[list[str]] = None

    def aplicar_carrusel(self, canal, estricto=True):
        """(5/11, Franco) Valida y normaliza un carrusel. Sin `imagenes` no hace nada y devuelve None. Con `imagenes` devuelve la
        lista limpia, deja imagen_url = la primera y descarta lo que un carrusel no lleva (frase, logo, composición, formato).
        `estricto=False` (guardar borrador): deja guardar con 1 o más fotos, para poder retomarlo a medio armar."""
        if not self.imagenes:
            self.imagenes = None
            return None
        lista = [str(u).strip() for u in self.imagenes if str(u or "").strip()]
        if not lista:
            self.imagenes = None
            return None
        canal = (canal or "").strip().lower()
        if canal not in ("instagram", "facebook") or (canal == "instagram" and "historia" in ((self.formato or ""), (self.vfmt or ""))):
            raise HTTPException(400, "El carrusel solo sale en posteo de Instagram o Facebook.")
        if (self.video_url or "").strip():
            raise HTTPException(400, "Un carrusel no puede llevar un video a la vez.")
        if len(lista) > 10 or (estricto and len(lista) < 2):
            raise HTTPException(400, "Un carrusel lleva entre 2 y 10 fotos.")
        if not all(u.startswith("https://") for u in lista):
            raise HTTPException(400, "Las fotos del carrusel tienen que ser direcciones https.")
        self.imagenes = lista
        self.imagen_url = lista[0]
        self.texto_imagen, self.usar_compuesta, self.formato, self.logo = None, False, None, None
        return lista

    def canal_clave(self):
        return (self.canal or "").strip().lower()

    def fecha_iso(self):
        """'YYYY-MM-DDTHH:MM:SS' como arma el formulario (hora 09:00 si falta), o None si no se programa. 400 si está mal escrita."""
        if not self.fecha:
            return None
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", self.fecha):
            raise HTTPException(400, "La fecha tiene que ser AAAA-MM-DD.")
        hora = (self.hora or "09:00").strip()
        if not re.fullmatch(r"\d{1,2}:\d{2}", hora):
            raise HTTPException(400, "La hora tiene que ser HH:MM.")
        hh, mm = hora.split(":")
        return f"{self.fecha}T{int(hh):02d}:{int(mm):02d}:00"

    def fecha_con_zona(self):
        f = self.fecha_iso()
        return (f + ZONA_HORARIA) if f else None

    def a_borrador(self, canal=None, fecha_iso=None):
        """El dict `pieza` que se guarda en publicaciones.resultado («Guardar borrador», pruebas, piezas a aprobar) y que el
        formulario sabe retomar: claves cortas donde las hay (CLAVES_CORTAS), fecha y hora separadas, origen web."""
        fecha_iso = self.fecha_iso() if fecha_iso is None else fecha_iso
        d = {"canal": canal or self.canal_clave()}
        for campo, valor in self.model_dump().items():
            if campo in NO_SE_GUARDAN:
                continue
            if campo in ("titulo", "texto", "texto_imagen", "imagen_url", "imagen_busqueda"):
                valor = (valor or "").strip() if campo != "texto" else (valor or "")
            if campo == "vfmt" and not self.video_url:
                valor = None
            d[CLAVES_CORTAS.get(campo, campo)] = valor
        d["fecha"] = fecha_iso[:10] if fecha_iso else None
        d["hora"] = fecha_iso[11:16] if fecha_iso else None
        d["origen"] = "web"
        return d

    @classmethod
    def desde_fila(cls, fila, fecha_hora=None):
        """La pieza para precargar el formulario desde cualquier fila de `publicaciones` («Retomar»): el dict guardado si lo hay
        (claves cortas → campos) y, para lo que falte, las columnas de la fila. `fecha_hora`: función que convierte
        fecha_programada en ('YYYY-MM-DD', 'HH:MM') hora Argentina."""
        res = fila.get("resultado") or {}
        g = dict(res.get("pieza") or {})
        largas = {corta: campo for campo, corta in CLAVES_CORTAS.items()}
        datos = {}
        for k, v in g.items():
            campo = largas.get(k, k)
            if campo in cls.model_fields:
                datos[campo] = v
        datos.setdefault("canal", fila.get("canal") or "")
        datos.setdefault("titulo", fila.get("titulo") or "")
        datos.setdefault("texto", fila.get("texto") or "")
        datos.setdefault("imagen_url", fila.get("imagen_url") or "")
        datos.setdefault("texto_imagen", res.get("texto_imagen") or "")
        datos.setdefault("video_url", res.get("video_url"))
        datos.setdefault("imagenes", res.get("imagenes"))
        if not datos.get("formato"):   # (2/11) pruebas anteriores al 2/11 no guardaban el formulario: al menos el formato (historia) se rescata
            fmt = res.get("formato") or ("historia" if res.get("accion") == "historia" else None)
            if fmt:
                datos["formato"] = fmt
        if not datos.get("fecha") and fila.get("fecha_programada") and fecha_hora:
            datos["fecha"], datos["hora"] = fecha_hora(fila.get("fecha_programada"))
        datos["borrador_id"] = fila.get("id")
        limpio = {k: v for k, v in datos.items() if k in cls.model_fields}
        limpio["usar_compuesta"] = bool(limpio.get("usar_compuesta", True)) if limpio.get("usar_compuesta") is not None else True
        # (4/11) una pieza mandada a aprobación antes del 4/11 no guardaba el formulario y su imagen_url ya es la compuesta (la frase
        # está dentro de la foto): al corregirla no se vuelve a poner la frase encima, va la imagen tal cual
        if not g and res.get("texto_imagen") and fila.get("estado") not in ("borrador", "prueba"):
            limpio["usar_compuesta"] = False
        return cls(**{k: (str(v) if v is not None and k not in ("usar_compuesta", "imagenes") else v) for k, v in limpio.items()})
