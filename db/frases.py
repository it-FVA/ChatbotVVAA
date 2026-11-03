"""Frase del día: tablas frases, frase_envios (mail en tandas) y frase_solicitudes (pedidos de cambio).
(3/11, revisión 5.2 punto 12) Antes en db.py. Las funciones se llaman entre sí y a _req a través del paquete (`_db.x`), así
`monkeypatch.setattr(db, "x", …)` en las pruebas vale para todas. Los parámetros de los filtros van escapados con _q.
"""
import json, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timezone, timedelta

import db as _db
from ._cliente import _q


# ---------------- Frase del día (19/10, reunión: calendario anual en el Panel admin) ----------------
# Tabla frases(id, texto, autor, origen 'sheet'|'manual', validada, fecha date única, imagen_url, estado
#              'programada'|'publicada'|'saltada', publicacion_id, orden, fuente, tema, creado, actualizado).
# Las carga importar_frases.py desde el Sheet Frases_consolidadas_591; solo las validadas entran al calendario.
# programar_frases.py (misma pasada de Actions que la cola) encola la frase de cada día como posteo de Instagram.
# (19/10, tarde) Rotación: ultima_publicada / veces_publicada (solo salidas reales) y piezas {canal: publicacion_id}
# (migración frases_rotacion_y_canales). Cuando no quedan validadas sin día, vuelven las ya publicadas, la más antigua primero.
CAMPOS_FRASE = "id,texto,autor,origen,validada,fecha,imagen_url,estado,publicacion_id,orden,fuente,tema,creado,ultima_publicada,veces_publicada,piezas,estilo"


def listar_frases(desde=None, hasta=None, limite=2000):
    """Frases con fecha en [desde, hasta] (date o 'AAAA-MM-DD'); sin filtros, todas (incluidas las sin fecha)."""
    if not _db.disponible():
        return []
    q = f"?select={CAMPOS_FRASE}&order=fecha.asc.nullslast,orden.asc&limit={limite}"
    if desde:
        q += f"&fecha=gte.{_q(desde)}"
    if hasta:
        q += f"&fecha=lte.{_q(hasta)}"
    return _db._req("GET", q, tabla="frases") or []


def frases_sin_fecha(solo_validadas=True, limite=2000):
    if not _db.disponible():
        return []
    q = f"?select={CAMPOS_FRASE}&fecha=is.null&order=orden.asc&limit={limite}"
    if solo_validadas:
        q += "&validada=is.true"
    return _db._req("GET", q, tabla="frases") or []


def frase_del_dia(fecha):
    """La frase asignada a esa fecha (date o 'AAAA-MM-DD'), o None."""
    if not _db.disponible():
        return None
    r = _db._req("GET", f"?select={CAMPOS_FRASE}&fecha=eq.{_q(fecha)}", tabla="frases")
    return r[0] if r else None


def obtener_frase(fid):
    r = _db._req("GET", f"?select={CAMPOS_FRASE}&id=eq.{_q(fid)}", tabla="frases")
    return r[0] if r else None


def actualizar_frase(fid, campos):
    if not _db.disponible():
        return None
    return _db._req("PATCH", f"?id=eq.{_q(fid)}", dict(campos, actualizado=_db._ahora_iso()), tabla="frases")


def crear_frase(texto, autor, validada=True, origen="manual", fecha=None, fuente=None, tema=None, orden=None):
    if not _db.disponible():
        return None
    fila = {"texto": texto.strip(), "autor": (autor or "").strip() or None, "validada": bool(validada), "origen": origen,
            "fecha": fecha, "fuente": fuente, "tema": tema, "orden": orden}
    r = _db._req("POST", "", fila, tabla="frases")
    return r[0]["id"] if r else None


def upsert_frases(filas, on_conflict="texto"):
    """Carga en lote (importar_frases.py): por texto (índice único); si ya existe, actualiza autor/fuente/tema/orden/validada
    sin tocar fecha, imagen ni estado. Devuelve la cantidad de filas enviadas."""
    if not _db.disponible() or not filas:
        return 0
    url, key = _db._cfg()
    data = json.dumps(filas, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(f"{url}/rest/v1/frases?on_conflict={on_conflict}", data=data, method="POST", headers={
        "apikey": key, "Authorization": "Bearer " + key, "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            r.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Supabase {e.code}: {e.read().decode('utf-8','ignore')[:300]}")
    return len(filas)


def mover_frase(fid, fecha_nueva):
    """Le pone otra fecha a una frase (o None = la saca del calendario). Si la fecha está ocupada, devuelve False."""
    if fecha_nueva and _db.frase_del_dia(fecha_nueva):
        return False
    _db.actualizar_frase(fid, {"fecha": fecha_nueva})
    return True


def intercambiar_frases(fid_a, fid_b):
    """Las dos frases se cambian la fecha entre sí (una puede no tener fecha: entonces es «cambiar por otra»).
    Tres pasos porque la fecha es única: a → null, b → fecha_a, a → fecha_b."""
    a, b = _db.obtener_frase(fid_a), _db.obtener_frase(fid_b)
    if not a or not b:
        return False
    fa, fb = a.get("fecha"), b.get("fecha")
    _db.actualizar_frase(fid_a, {"fecha": None})
    _db.actualizar_frase(fid_b, {"fecha": fa})
    _db.actualizar_frase(fid_a, {"fecha": fb})
    return True


def fechas_ocupadas(desde, hasta):
    if not _db.disponible():
        return set()
    r = _db._req("GET", f"?select=fecha&fecha=gte.{_q(desde)}&fecha=lte.{_q(hasta)}", tabla="frases") or []
    return {x["fecha"] for x in r if x.get("fecha")}


def candidatas_rotacion(hoy, limite=3000):
    """Las frases que pueden ir a un día nuevo, en el orden de la rotación: validadas, nunca publicadas primero (sin día,
    o con un día ya pasado en que no salieron de verdad), después las publicadas de la más antigua a la más reciente.
    Una frase con día futuro no es candidata (ya está en el calendario)."""
    if not _db.disponible():
        return []
    q = (f"?select={CAMPOS_FRASE}&validada=is.true&or=(fecha.is.null,fecha.lt.{hoy})"
         f"&order=ultima_publicada.asc.nullsfirst,orden.asc&limit={limite}")
    cand = _db._req("GET", q, tabla="frases") or []
    # una con día pasado pero todavía en la cola (hoy) no se toca
    return [f for f in cand if not (f.get("fecha") and f.get("publicacion_id") and f.get("estado") == "programada")]


def frases_pendientes_validacion(limite=2000):
    if not _db.disponible():
        return []
    return _db._req("GET", f"?select={CAMPOS_FRASE}&validada=is.false&order=orden.asc&limit={limite}", tabla="frases") or []


def frases_para_marcar_publicadas():
    """Frases con publicacion_id y estado 'programada': programar_frases.py mira la fila de la cola y las marca."""
    if not _db.disponible():
        return []
    return _db._req("GET", f"?select={CAMPOS_FRASE}&estado=eq.programada&publicacion_id=not.is.null", tabla="frases") or []


def resumen_frases():
    """Conteos para la cabecera de la solapa: total, validadas, con fecha, publicadas."""
    if not _db.disponible():
        return {}
    todas = _db._req("GET", "?select=validada,fecha,estado,ultima_publicada", tabla="frases") or []
    return {"total": len(todas), "validadas": sum(1 for f in todas if f.get("validada")),
            "con_fecha": sum(1 for f in todas if f.get("fecha")),
            "publicadas": sum(1 for f in todas if f.get("estado") == "publicada"),
            "alguna_vez_publicadas": sum(1 for f in todas if f.get("ultima_publicada")),
            "sin_fecha_validadas": sum(1 for f in todas if f.get("validada") and not f.get("fecha")),
            "pendientes_validar": sum(1 for f in todas if not f.get("validada"))}


def crear_envios_frase(publicacion_id, fecha, emails, prueba=False):
    """Deja un renglón 'pendiente' por mail (de a 500). Devuelve [{id, email}]."""
    if not _db.disponible() or not emails:
        return []
    out = []
    for i in range(0, len(emails), 500):
        filas = [{"publicacion_id": publicacion_id, "fecha": str(fecha)[:10], "email": e, "estado": "pendiente", "prueba": bool(prueba)}
                 for e in emails[i:i + 500]]
        r = _db._req("POST", "?select=id,email", filas, tabla="frase_envios") or []
        out.extend({"id": x["id"], "email": x["email"]} for x in r)
    return out


def envios_pendientes(publicacion_id, limite=50):
    if not _db.disponible():
        return []
    return _db._req("GET", f"?publicacion_id=eq.{urllib.parse.quote(str(publicacion_id))}&estado=eq.pendiente&select=id,email&order=creado.asc&limit={int(limite)}",
                tabla="frase_envios") or []


def actualizar_envio(eid, campos):
    if not _db.disponible():
        return None
    return _db._req("PATCH", f"?id=eq.{urllib.parse.quote(str(eid))}", campos, tabla="frase_envios")


PAGINA = 1000      # el tope de filas por pedido de Supabase (max-rows)


def resumen_envios(publicacion_id=None, fecha=None, prueba=None):
    """{pendiente: n, enviado: n, error: n, total: n} de una pieza (o de una fecha)."""
    if not _db.disponible():
        return {}
    q = "?select=estado"
    if publicacion_id:
        q += f"&publicacion_id=eq.{urllib.parse.quote(str(publicacion_id))}"
    if fecha:
        q += f"&fecha=eq.{_q(str(fecha)[:10])}"
    if prueba is not None:
        q += f"&prueba=is.{'true' if prueba else 'false'}"
    # (3/11) Supabase devuelve como mucho 1.000 filas por pedido aunque se pida más: con una lista de 2.241, el conteo veía
    # solo 1.000 y, cuando esas ya estaban enviadas, la pieza se daba por terminada con 1.241 pendientes (pasó con la del 3/11).
    # Se pagina de a 1.000, en un orden fijo, hasta traer todas.
    filas, desde = [], 0
    while True:
        tanda = _db._req("GET", q + f"&order=id&limit={PAGINA}&offset={desde}", tabla="frase_envios") or []
        filas.extend(tanda)
        if len(tanda) < PAGINA:
            break
        desde += PAGINA
    out = {"pendiente": 0, "enviado": 0, "error": 0}
    for f in filas:
        out[f.get("estado") or "pendiente"] = out.get(f.get("estado") or "pendiente", 0) + 1
    out["total"] = len(filas)
    return out


def ultimos_envios(fecha=None, limite=50, prueba=None):
    if not _db.disponible():
        return []
    q = f"?select=id,publicacion_id,fecha,email,estado,prueba,enviado_en,error,creado&order=creado.desc&limit={int(limite)}"
    if fecha:
        q += f"&fecha=eq.{_q(str(fecha)[:10])}"
    if prueba is not None:
        q += f"&prueba=is.{'true' if prueba else 'false'}"
    return _db._req("GET", q, tabla="frase_envios") or []


# ---------------- Frase del día: solicitudes de cambio (2/11): tabla frase_solicitudes ----------------
# Un creador de contenido pide «que tal día salga tal frase» (una existente o una nueva); un aprobador la acepta (se aplica al
# calendario) o la rechaza con una respuesta. Lo usa api/frases_rutas.py.
CAMPOS_SOLICITUD = "id,creado,usuario,fecha,frase_id,texto,autor,nota,imagen_url,estado,resuelta_por,resuelta_en,respuesta"


def crear_solicitud_frase(usuario, fecha, frase_id=None, texto=None, autor=None, nota=None, imagen_url=None):
    if not _db.disponible():
        return None
    r = _db._req("POST", "", {"usuario": usuario, "fecha": str(fecha)[:10], "frase_id": frase_id, "texto": texto, "autor": autor, "nota": nota, "imagen_url": imagen_url},
             tabla="frase_solicitudes")
    return r[0]["id"] if r else None


def obtener_solicitud_frase(sid):
    if not _db.disponible():
        return None
    r = _db._req("GET", f"?select={CAMPOS_SOLICITUD}&id=eq.{urllib.parse.quote(str(sid))}", tabla="frase_solicitudes")
    return r[0] if r else None


def listar_solicitudes_frase(estado=None, usuario=None, limite=200):
    if not _db.disponible():
        return []
    q = f"?select={CAMPOS_SOLICITUD}&order=creado.desc&limit={int(limite)}"
    if estado:
        q += f"&estado=eq.{urllib.parse.quote(estado)}"
    if usuario:
        q += f"&usuario=eq.{urllib.parse.quote(usuario)}"
    return _db._req("GET", q, tabla="frase_solicitudes") or []


def actualizar_solicitud_frase(sid, campos):
    if not _db.disponible():
        return None
    return _db._req("PATCH", f"?id=eq.{urllib.parse.quote(str(sid))}", campos, tabla="frase_solicitudes")
