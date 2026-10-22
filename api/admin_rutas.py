"""Administración (22/10, pantallas Dashboard · Servicios y costos · Configuración de la web; solo admins).

Lo que la web necesita además de api/salud.py y api/cuentas.py. Misma lógica que el Dashboard de Streamlit
(publicar_ui.uso_admin, costo_openai_admin, servicios_admin), sin Streamlit:

  GET  /admin/resumen                 la portada: «¿funciona?» (última corrida guardada de Salud), costo del mes y del anterior
  GET  /admin/uso?dias=28 | mes=AAAA-MM   quién usó el bot: por persona (también quien no hizo nada), por semana, lo último
  GET  /admin/costos?dias=28 | mes=AAAA-MM   consumo de OpenAI: total, por persona, por día, por modelo y para qué, últimos 6 meses
  GET  /admin/servicios · PUT /admin/servicios · DELETE /admin/servicios/{id}   inventario de servicios y costos fijos
  GET  /admin/config · PUT /admin/config    precios de OpenAI, presupuesto, umbrales, uso manual de Vercel, Frase del día

Reglas de la casa:
- El costo de OpenAI es una ESTIMACIÓN con los precios de config openai_precios (US$ por millón de tokens), con la misma
  fórmula que publicar_ui._costo (api.salud._costo_fila). Un modelo sin precio suma tokens pero no plata, y se dice cuál.
- Nada se inventa: los montos de servicios no confirmados van marcados; los límites de los planes llevan su fuente (salud.py).
- Todo cambio de configuración o de un servicio queda en usuarios_cambios (quién, qué clave, de qué valor a cuál).
- Fechas en hora Argentina (UTC-3): el mes empieza a las 03:00 UTC, como en publicar_ui.
"""
import re, datetime as dt
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from . import auth, config
from .salud import _costo_fila, _hoy_argentina
import db          # noqa: E402  (api/__init__ pone la raíz del repo en sys.path)

router = APIRouter(prefix="/admin", tags=["administracion"])

SERVICIO = {"frase_del_dia", "bot", "cola", "prueba"}       # usuarios que no son personas (publicar_ui._SERVICIO)
REGISTRO_DESDE = "2026-10-21"                                # desde cuándo se registra cada llamada a OpenAI (uso_openai)
ZONA_AR = dt.timezone(dt.timedelta(hours=-3))
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
QUE_TEXTO = {"chat": "chat (respuestas con herramientas)", "auxiliar": "auxiliar (reranker, títulos, traducciones, newsletter)",
             "embedding": "embedding (búsqueda)"}

# Frase del día: los mismos valores que programar_frases.py (se importa si se puede; si no, copia de los defaults).
try:
    import programar_frases as _pf
    FRASE_HORA_DEFECTO, FRASE_CANALES, FRASE_PIE_DEFECTO = _pf.HORA_DEFECTO, dict(_pf.CANALES_POSIBLES), _pf.PIE_DEFECTO
except Exception:                                            # pragma: no cover
    FRASE_HORA_DEFECTO = "07:00"
    FRASE_CANALES = {"instagram": "Instagram (posteo cuadrado)", "facebook": "Facebook (foto con texto)"}
    FRASE_PIE_DEFECTO = "#FraseDelDía #VivirAgradecidos #Gratitud"

# Lo que se puede cambiar desde Configuración, con la explicación corta que muestra la pantalla.
CLAVES_CONFIG = {
    "openai_precios": "Precio por millón de tokens de cada modelo (entrada, salida, caché), con la fuente y la fecha. Sirven para ESTIMAR el costo; el número real es el de la factura de OpenAI.",
    "presupuesto_openai_usd": "Presupuesto mensual de OpenAI en US$ que fija la Fundación (no es un límite de OpenAI). Al pasar el umbral, Salud avisa. 0 = sin presupuesto.",
    "umbrales_planes": "Porcentaje del límite del plan gratuito a partir del cual conviene pasar a plan pago (por proveedor o «default» para todos).",
    "vercel_uso_manual": "GB transferidos este mes según vercel.com → Usage. La API no puede leerlo sola (sin VERCEL_TOKEN): se carga a mano.",
    "frase_activa": "Interruptor de la Frase del día: prendido, la cola encola cada día la frase asignada como posteo.",
    "frase_hora": "Hora de salida (Argentina). La cola corre cada 15 minutos: sale en la pasada siguiente.",
    "frase_canales": "Canales por los que sale la frase cada día (una pieza por canal).",
    "frase_imagen": "URL de la foto de fondo por defecto, para los días sin foto elegida. Sin foto, ese día no se encola.",
    "frase_pie": "Texto que va al final del posteo, después de la frase y el autor (hashtags).",
    "clips_estilo": "Estilo por defecto de los subtítulos de los recortes verticales nuevos (se edita con los controles del editor).",
}
AVISOS_PRECIOS = {"gpt-5.6-sol": "Precio promocional vigente al menos hasta el 21/11/2026 (según la fuente cargada el 21/10): revisarlo después de esa fecha."}


# ---------------- helpers ----------------
def _admin(usuario=Depends(auth.admin)):
    return usuario


def _ahora():
    return dt.datetime.now(dt.timezone.utc)


def _fecha(valor):
    if not valor:
        return None
    try:
        d = dt.datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def _dia_ar(iso):
    """'AAAA-MM-DD' en hora Argentina de un ISO UTC (sin fecha: '?')."""
    d = _fecha(iso)
    return d.astimezone(ZONA_AR).strftime("%Y-%m-%d") if d else "?"


def _mes_ar(iso):
    return _dia_ar(iso)[:7]


def mes_texto(ym):
    try:
        a, m = ym.split("-")
        return f"{MESES[int(m) - 1]} {a}"
    except Exception:
        return ym


def _inicio_fin_mes(ym):
    """(primer día, primer día del mes siguiente) de 'AAAA-MM'."""
    a, m = int(ym[:4]), int(ym[5:7])
    return dt.date(a, m, 1), dt.date(a + (m == 12), (m % 12) + 1, 1)


def periodo(dias: Optional[int], mes: Optional[str]):
    """Normaliza el período pedido. Devuelve {tipo, dias|mes, desde, hasta (exclusivo, o None), texto}; las fechas ISO UTC
    (el día argentino empieza a las 03:00 UTC)."""
    if mes:
        if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", mes):
            raise HTTPException(400, "El mes tiene que ser AAAA-MM.")
        ini, fin = _inicio_fin_mes(mes)
        return {"tipo": "mes", "mes": mes, "desde": f"{ini.isoformat()}T03:00:00Z", "hasta": f"{fin.isoformat()}T03:00:00Z",
                "texto": mes_texto(mes), "dias": max((min(fin, _hoy_argentina() + dt.timedelta(days=1)) - ini).days, 0)}
    d = 28 if dias is None else int(dias)
    if not 1 <= d <= 365:
        raise HTTPException(400, "dias tiene que estar entre 1 y 365.")
    desde = (_ahora() - dt.timedelta(days=d)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"tipo": "dias", "dias": d, "desde": desde, "hasta": None, "texto": f"últimos {d} días"}


def _en_periodo(iso, p):
    """¿La fecha ISO cae dentro del período? (Para el modo mes: uso_actividad solo filtra por días; acá se recorta.)"""
    if p["tipo"] == "dias":
        return True
    d = _fecha(iso)
    return bool(d) and p["desde"] <= d.strftime("%Y-%m-%dT%H:%M:%SZ") < p["hasta"]


def _semana_lunes(iso):
    d = _fecha(iso)
    if not d:
        return "?"
    dia = d.astimezone(ZONA_AR).date()
    return (dia - dt.timedelta(days=dia.weekday())).isoformat()


def _personas():
    """Las personas conocidas: tabla usuarios (con nombre, rol, activo) y, mientras conviven, las de secrets. Sin los usuarios
    de servicio (frase_del_dia, cola…)."""
    out = {}
    try:
        for f in (db.listar_usuarios() if db.disponible() else []):
            u = f.get("usuario")
            if u and u not in SERVICIO:
                out[u] = {"usuario": u, "nombre": f.get("nombre"), "rol": f.get("rol"), "activo": f.get("activo", True),
                          "ultimo_login": f.get("ultimo_login"), "en_tabla": True}
    except Exception:
        pass
    for u in config.usuarios():
        if u not in out and u not in SERVICIO:
            out[u] = {"usuario": u, "nombre": None, "rol": None, "activo": True, "ultimo_login": None, "en_tabla": False}
    return out


def _filas_uso(p):
    return db.uso_openai(desde=p["desde"], hasta=p["hasta"]) if p["tipo"] == "mes" else db.uso_openai(p["dias"])


# ---------------- costos ----------------
def calcular_costos(filas, precios):
    """La parte de cálculo de publicar_ui.costo_openai_admin sobre una lista de filas de uso_openai. Devuelve el bloque
    completo (total, por persona, por día, por modelo y para qué, modelos sin precio)."""
    costos = [_costo_fila(f, precios) for f in filas]
    total = sum(c for c in costos if c is not None)
    sin_precio = sorted({(f.get("modelo") or "?") for f, c in zip(filas, costos) if c is None})
    pp, pdia, pmod = {}, {}, {}
    for f, c in zip(filas, costos):
        u = f.get("usuario") or "(sistema)"
        d = pp.setdefault(u, {"usuario": u, "llamadas": 0, "chats": 0, "tokens_entrada": 0, "tokens_salida": 0, "tokens_cache": 0, "usd": 0.0})
        d["llamadas"] += 1
        d["chats"] += 1 if f.get("que") == "chat" else 0
        d["tokens_entrada"] += f.get("tokens_entrada") or 0
        d["tokens_salida"] += f.get("tokens_salida") or 0
        d["tokens_cache"] += f.get("tokens_cache") or 0
        d["usd"] += c or 0.0
        dia = _dia_ar(f.get("creado"))
        pdia.setdefault(dia, {})
        pdia[dia][u] = pdia[dia].get(u, 0.0) + (c or 0.0)
        k = (f.get("modelo") or "?", f.get("que") or "?")
        m = pmod.setdefault(k, {"modelo": k[0], "que": k[1], "que_texto": QUE_TEXTO.get(k[1], k[1]), "llamadas": 0, "tokens_entrada": 0,
                                "tokens_salida": 0, "tokens_cache": 0, "usd": 0.0, "con_precio": c is not None})
        m["llamadas"] += 1
        m["tokens_entrada"] += f.get("tokens_entrada") or 0
        m["tokens_salida"] += f.get("tokens_salida") or 0
        m["tokens_cache"] += f.get("tokens_cache") or 0
        m["usd"] += c or 0.0
    personas = sorted(pp.values(), key=lambda x: -x["usd"])
    for d in personas:
        d["usd"] = round(d["usd"], 4)
        d["parte"] = round(d["usd"] / total, 4) if total else 0.0
        d["usd_por_chat"] = round(d["usd"] / d["chats"], 4) if d["chats"] else None
    dias_con_uso = sorted(pdia)
    return {"total_usd": round(total, 4), "llamadas": len(filas), "personas": len(pp),
            "tokens": {"entrada": sum(f.get("tokens_entrada") or 0 for f in filas), "salida": sum(f.get("tokens_salida") or 0 for f in filas),
                       "cache": sum(f.get("tokens_cache") or 0 for f in filas)},
            "promedio_dia_con_uso_usd": round(total / len(dias_con_uso), 4) if dias_con_uso else None,
            "por_persona": personas,
            "por_dia": [{"dia": d, "por_persona": {u: round(v, 4) for u, v in pdia[d].items()}, "usd": round(sum(pdia[d].values()), 4)} for d in dias_con_uso],
            "por_modelo": sorted((dict(m, usd=round(m["usd"], 4)) for m in pmod.values()), key=lambda x: -x["usd"]),
            "modelos_sin_precio": sin_precio}


def _meses_recientes(n=6):
    hoy = _hoy_argentina()
    out, ini = [], hoy.replace(day=1)
    for _ in range(n):
        out.append(ini.strftime("%Y-%m"))
        ini = (ini - dt.timedelta(days=1)).replace(day=1)
    return out                                            # del más reciente al más viejo


def serie_mensual(filas, precios, meses):
    """Costo, tokens, llamadas y personas por mes (hora Argentina) para los meses pedidos, aunque estén en cero."""
    pm = {m: {"mes": m, "texto": mes_texto(m), "usd": 0.0, "tokens": 0, "llamadas": 0, "_pers": {}} for m in meses}
    for f in filas:
        ym = _mes_ar(f.get("creado"))
        if ym not in pm:
            continue
        d = pm[ym]
        c = _costo_fila(f, precios) or 0.0
        d["llamadas"] += 1
        d["tokens"] += (f.get("tokens_entrada") or 0) + (f.get("tokens_salida") or 0)
        d["usd"] += c
        u = f.get("usuario") or "(sistema)"
        d["_pers"][u] = d["_pers"].get(u, 0.0) + c
    out = []
    for m in meses:
        d = pm[m]
        top = sorted(d["_pers"].items(), key=lambda kv: -kv[1])
        out.append({"mes": m, "texto": d["texto"], "usd": round(d["usd"], 4), "tokens": d["tokens"], "llamadas": d["llamadas"],
                    "personas": len(d["_pers"]), "por_persona": {u: round(v, 4) for u, v in d["_pers"].items()},
                    "quien_mas": {"usuario": top[0][0], "usd": round(top[0][1], 4)} if top else None})
    return out


@router.get("/costos")
def costos(dias: Optional[int] = None, mes: Optional[str] = None, quien=Depends(_admin)):
    """Consumo de OpenAI del período (?dias=7|28|90 o ?mes=AAAA-MM) + la serie de los últimos 6 meses."""
    p = periodo(dias, mes)
    if not db.disponible():
        return {"periodo": p, "registro_desde": REGISTRO_DESDE, "precios": {}, "sin_supabase": True, **calcular_costos([], {}), "meses": []}
    try:
        precios = db.obtener_config("openai_precios") or {}
        filas = _filas_uso(p)
        meses = _meses_recientes(6)
        ini6, _ = _inicio_fin_mes(meses[-1])
        filas6 = db.uso_openai(desde=f"{ini6.isoformat()}T03:00:00Z")
    except Exception as e:
        raise HTTPException(503, f"No pude leer el consumo: {str(e)[:160]}")
    r = calcular_costos(filas, precios)
    r.update({"periodo": p, "registro_desde": REGISTRO_DESDE, "meses": serie_mensual(filas6, precios, meses),
              "precios": {m: {k: v for k, v in (pz or {}).items()} for m, pz in precios.items() if isinstance(pz, dict)},
              "avisos_precios": {m: t for m, t in AVISOS_PRECIOS.items() if m in precios},
              "nota": "Estimación con los precios de Configuración (US$ por millón de tokens); el número real es el de la factura de OpenAI. "
                      "Se registra cada llamada desde el " + REGISTRO_DESDE + "."})
    return r


# ---------------- uso ----------------
@router.get("/uso")
def uso(dias: Optional[int] = None, mes: Optional[str] = None, quien=Depends(_admin)):
    """«¿Hubo movimiento?» (publicar_ui.uso_admin): por persona, también quien no hizo nada; por semana; lo último; y el
    costo de OpenAI de cada persona en el mismo período."""
    p = periodo(dias, mes)
    personas = _personas()
    if not db.disponible():
        return {"periodo": p, "resumen": {"personas_activas": 0, "personas_total": len(personas), "conversaciones": 0, "piezas": 0, "recortes": 0},
                "personas": [dict(v, ultima_vez=None, conversaciones=0, mensajes=0, piezas=0, recortes=0, costo_usd=0.0, parte_costo=0.0, lo_ultimo=None) for v in personas.values()],
                "por_semana": [], "ultimas": {"conversaciones": [], "piezas": [], "recortes": []}, "sin_supabase": True}
    try:
        datos = db.uso_actividad(p["dias"]) if p["dias"] else {"conversaciones": [], "publicaciones": [], "clips": []}
        ultima = db.uso_ultima_vez()
        precios = db.obtener_config("openai_precios") or {}
        filas = _filas_uso(p)
    except Exception as e:
        raise HTTPException(503, f"No pude leer la actividad: {str(e)[:160]}")
    convs = [c for c in datos["conversaciones"] if c.get("usuario") not in SERVICIO and _en_periodo(c.get("actualizado") or c.get("creado"), p)]
    pubs = [x for x in datos["publicaciones"] if x.get("usuario") not in SERVICIO and _en_periodo(x.get("creado"), p)]
    clips = [k for k in datos["clips"] if _en_periodo(k.get("creado"), p)]
    for u in {c.get("usuario") for c in convs} | {x.get("usuario") for x in pubs} | {k.get("pedido_por") for k in clips}:
        if u and u not in personas and u not in SERVICIO:
            personas[u] = {"usuario": u, "nombre": None, "rol": None, "activo": True, "ultimo_login": None, "en_tabla": False}
    costo = calcular_costos(filas, precios)
    costo_por = {d["usuario"]: d for d in costo["por_persona"]}

    filas_p = []
    for u, info in personas.items():
        cu = [c for c in convs if c.get("usuario") == u]
        pu = [x for x in pubs if x.get("usuario") == u]
        ku = [k for k in clips if k.get("pedido_por") == u]
        candidatos = ([("conversación", c.get("titulo") or "Conversación", c.get("actualizado")) for c in cu]
                      + [("pieza", f"{x.get('canal') or ''} · {(x.get('titulo') or '')[:60]} · {x.get('estado') or ''}", x.get("creado")) for x in pu]
                      + [("recorte", f"{k.get('formato') or ''} · {(k.get('titulo') or '')[:60]} · {k.get('estado') or ''}", k.get("creado")) for k in ku])
        ult = max(candidatos, key=lambda t: t[2] or "") if candidatos else None
        c = costo_por.get(u)
        filas_p.append(dict(info, ultima_vez=ultima.get(u), conversaciones=len(cu), mensajes=sum(x.get("n_mensajes") or 0 for x in cu),
                            piezas=len(pu), recortes=len(ku), costo_usd=(c or {}).get("usd", 0.0), parte_costo=(c or {}).get("parte", 0.0),
                            llamadas=(c or {}).get("llamadas", 0),
                            lo_ultimo={"tipo": ult[0], "texto": ult[1], "cuando": ult[2]} if ult else None))
    filas_p.sort(key=lambda f: (f["ultima_vez"] or "", f["usuario"]), reverse=True)

    por_semana = {}
    for c in convs:
        s = _semana_lunes(c.get("creado") or c.get("actualizado"))
        por_semana.setdefault(s, {})
        por_semana[s][c["usuario"]] = por_semana[s].get(c["usuario"], 0) + 1
    activos = {c.get("usuario") for c in convs} | {x.get("usuario") for x in pubs} | {k.get("pedido_por") for k in clips}
    activos = {u for u in activos if u and u not in SERVICIO}
    return {
        "periodo": p,
        "resumen": {"personas_activas": len(activos), "personas_total": len(personas), "conversaciones": len(convs),
                    "mensajes": sum(c.get("n_mensajes") or 0 for c in convs), "piezas": len(pubs), "recortes": len(clips),
                    "costo_usd": costo["total_usd"]},
        "personas": filas_p,
        "sin_actividad": [f["usuario"] for f in filas_p if not (f["conversaciones"] or f["piezas"] or f["recortes"])],
        "por_semana": [{"semana": s, "por_persona": por_semana[s], "total": sum(por_semana[s].values())} for s in sorted(por_semana)],
        "ultimas": {"conversaciones": [{"usuario": c.get("usuario"), "titulo": (c.get("titulo") or "Conversación")[:90], "cuando": c.get("actualizado"), "mensajes": c.get("n_mensajes") or 0, "id": c.get("id")} for c in convs[:25]],
                    "piezas": [{"usuario": x.get("usuario"), "canal": x.get("canal"), "titulo": (x.get("titulo") or "")[:80], "estado": x.get("estado"), "cuando": x.get("creado")} for x in pubs[:15]],
                    "recortes": [{"usuario": k.get("pedido_por"), "formato": k.get("formato"), "titulo": (k.get("titulo") or "")[:80], "estado": k.get("estado"), "cuando": k.get("creado"), "id": k.get("id")} for k in clips[:15]]},
        "nota": "Horas de Argentina. Una conversación cuenta en el período si se tocó en él; piezas y recortes, por su fecha de creación.",
    }


# ---------------- resumen (portada) ----------------
def _salud_resumen():
    """La última corrida guardada de Salud (sin las filas de arranque): estado, cuántos avisos y errores, cuándo."""
    try:
        hist = db.listar_salud(30)
    except Exception as e:
        return {"estado": "sin_dato", "detalle": f"No pude leer salud_historial: {str(e)[:120]}"}
    arranques_24h = 0
    for h in hist:
        if h.get("estado") == "arranque":
            mins = (_ahora() - (_fecha(h.get("creado")) or _ahora())).total_seconds() / 60
            arranques_24h += 1 if mins <= 24 * 60 else 0
            continue
        d = h.get("detalle") or {}
        cheq = d.get("chequeos") or []
        cap = d.get("capacidad") or []
        mal = [{"nombre": c.get("nombre"), "estado": c.get("estado"), "detalle": c.get("detalle")} for c in cheq if c.get("estado") != "ok"]
        cap_mal = [{"nombre": c.get("nombre"), "estado": c.get("estado"), "porcentaje": c.get("porcentaje")} for c in cap if c.get("estado") in ("aviso", "error")]
        creado = _fecha(h.get("creado"))
        return {"estado": h.get("estado"), "creado": h.get("creado"),
                "hace_min": int((_ahora() - creado).total_seconds() / 60) if creado else None,
                "chequeos": len(cheq), "errores": sum(1 for c in mal if c["estado"] == "error"), "avisos": sum(1 for c in mal if c["estado"] == "aviso"),
                "mal": mal, "capacidad_mal": cap_mal, "arranques_24h": arranques_24h}
    return {"estado": "sin_dato", "detalle": "Todavía no hay ninguna corrida guardada de Salud: abrí la pantalla Salud para correr los chequeos."}


def _fijo_servicios():
    servicios = db.listar_servicios()
    activos = [s for s in servicios if s.get("activo")]
    return {"servicios_activos": len(activos), "servicios_total": len(servicios),
            "fijo_usd": round(sum(float(s.get("costo_mensual_usd") or 0) for s in activos), 2),
            "fijo_confirmado_usd": round(sum(float(s.get("costo_mensual_usd") or 0) for s in activos if s.get("confirmado")), 2),
            "sin_confirmar": [s["nombre"] for s in activos if not s.get("confirmado")],
            "sin_monto": [s["nombre"] for s in activos if s.get("costo_mensual_usd") is None],
            "con_costo": [{"nombre": s["nombre"], "usd": float(s.get("costo_mensual_usd") or 0), "confirmado": bool(s.get("confirmado"))} for s in activos if float(s.get("costo_mensual_usd") or 0) > 0]}


@router.get("/resumen")
def resumen(quien=Depends(_admin)):
    """La portada del Dashboard: ¿funciona? (última corrida de Salud), costo del mes (OpenAI estimado + fijos) y el anterior."""
    if not db.disponible():
        return {"salud": {"estado": "sin_dato", "detalle": "Sin Supabase."}, "costo": None, "registro_desde": REGISTRO_DESDE, "sin_supabase": True}
    meses = _meses_recientes(2)
    try:
        precios = db.obtener_config("openai_precios") or {}
        presupuesto = db.obtener_config("presupuesto_openai_usd")
        ini_ant, _ = _inicio_fin_mes(meses[-1])
        filas = db.uso_openai(desde=f"{ini_ant.isoformat()}T03:00:00Z")
        fijo = _fijo_servicios()
    except Exception as e:
        raise HTTPException(503, f"No pude leer los datos: {str(e)[:160]}")
    serie = serie_mensual(filas, precios, meses)
    actual, anterior = serie[0], serie[1]
    hoy = _hoy_argentina()
    try:
        presupuesto = float(presupuesto) if presupuesto not in (None, "", 0, "0") else None
    except (TypeError, ValueError):
        presupuesto = None
    sin_precio = sorted({(f.get("modelo") or "?") for f in filas if _costo_fila(f, precios) is None})
    return {
        "salud": _salud_resumen(),
        "costo": {"mes": actual["mes"], "mes_texto": actual["texto"], "openai_usd": actual["usd"], "openai_llamadas": actual["llamadas"],
                  "openai_por_persona": actual["por_persona"], "proyeccion_30_dias_usd": round(actual["usd"] / max(hoy.day, 1) * 30, 2),
                  "dia_del_mes": hoy.day, "presupuesto_usd": presupuesto,
                  "total_usd": round(actual["usd"] + fijo["fijo_usd"], 2),
                  "anterior": {"mes": anterior["mes"], "mes_texto": anterior["texto"], "openai_usd": anterior["usd"], "openai_llamadas": anterior["llamadas"],
                               "total_usd": round(anterior["usd"] + fijo["fijo_usd"], 2)},
                  "modelos_sin_precio": sin_precio, **fijo,
                  "nota": "OpenAI: estimación con los precios de Configuración sobre lo registrado desde el " + REGISTRO_DESDE +
                          ". Fijos: suma de los costos mensuales cargados en Servicios (los activos); los no confirmados cuentan igual y están marcados."},
        "registro_desde": REGISTRO_DESDE,
    }


# ---------------- servicios ----------------
class Servicio(BaseModel):
    id: Optional[str] = None
    nombre: str
    proveedor: Optional[str] = None
    para_que: Optional[str] = None
    plan: Optional[str] = None
    costo_mensual_usd: Optional[float] = None          # None = no se sabe (se muestra «sin monto»)
    confirmado: bool = False
    desde: Optional[str] = None                        # AAAA-MM-DD
    url: Optional[str] = None
    notas: Optional[str] = None
    activo: bool = True


def _limpio(s):
    return (s or "").strip() or None


@router.get("/servicios")
def servicios(quien=Depends(_admin)):
    if not db.disponible():
        return {"servicios": [], "sin_supabase": True}
    try:
        lista = db.listar_servicios()
        fijo = _fijo_servicios()
        precios = db.obtener_config("openai_precios") or {}
        ini = _hoy_argentina().replace(day=1)
        filas = db.uso_openai(desde=f"{ini.isoformat()}T03:00:00Z")
    except Exception as e:
        raise HTTPException(503, f"No pude leer los servicios: {str(e)[:160]}")
    openai_mes = round(sum(c for c in (_costo_fila(f, precios) for f in filas) if c is not None), 4)
    return dict(fijo, servicios=lista, mes=ini.strftime("%Y-%m"), mes_texto=mes_texto(ini.strftime("%Y-%m")), openai_mes_usd=openai_mes,
                total_mes_usd=round(fijo["fijo_usd"] + openai_mes, 2))


@router.put("/servicios")
def guardar_servicio(datos: Servicio, quien=Depends(_admin)):
    """Alta (sin id) o edición (con id). Queda registrado en usuarios_cambios."""
    if not db.disponible():
        raise HTTPException(503, "Sin Supabase no hay dónde guardar.")
    nombre = _limpio(datos.nombre)
    if not nombre:
        raise HTTPException(400, "Falta el nombre del servicio.")
    if datos.costo_mensual_usd is not None and datos.costo_mensual_usd < 0:
        raise HTTPException(400, "El costo no puede ser negativo.")
    if datos.desde and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", datos.desde.strip()):
        raise HTTPException(400, "«Desde» tiene que ser una fecha AAAA-MM-DD.")
    fila = {"nombre": nombre, "proveedor": _limpio(datos.proveedor), "para_que": _limpio(datos.para_que), "plan": _limpio(datos.plan),
            "costo_mensual_usd": round(datos.costo_mensual_usd, 2) if datos.costo_mensual_usd is not None else None,
            "confirmado": bool(datos.confirmado), "desde": _limpio(datos.desde), "url": _limpio(datos.url), "notas": _limpio(datos.notas),
            "activo": bool(datos.activo)}
    if datos.id:
        fila["id"] = datos.id
    try:
        r = db.guardar_servicio(fila, quien)
    except Exception as e:
        raise HTTPException(503, f"No pude guardar: {str(e)[:160]}")
    guardado = (r or [fila])[0] if isinstance(r, list) else fila
    db.registrar_cambio_usuario(quien, "servicio_editar" if datos.id else "servicio_alta", nombre,
                                {"plan": fila["plan"], "costo_mensual_usd": fila["costo_mensual_usd"], "confirmado": fila["confirmado"], "activo": fila["activo"]})
    return {"ok": True, "servicio": guardado}


@router.delete("/servicios/{sid}")
def borrar_servicio(sid: str, quien=Depends(_admin)):
    if not db.disponible():
        raise HTTPException(503, "Sin Supabase.")
    nombre = next((s.get("nombre") for s in db.listar_servicios() if str(s.get("id")) == sid), None)
    if nombre is None:
        raise HTTPException(404, "No existe ese servicio.")
    try:
        db.borrar_servicio(sid)
    except Exception as e:
        raise HTTPException(503, f"No pude borrar: {str(e)[:160]}")
    db.registrar_cambio_usuario(quien, "servicio_baja", nombre, {"id": sid})
    return {"ok": True}


# ---------------- configuración ----------------
class CambiosConfig(BaseModel):
    cambios: dict[str, Any]


def _filas_config():
    """Las filas de la tabla config con quién y cuándo las cambió (db.obtener_config solo trae el valor)."""
    return db._req("GET", "?select=clave,valor,actualizado,por&order=clave", tabla="config") or []


@router.get("/config")
def leer_config(quien=Depends(_admin)):
    """Todo lo que se edita en Configuración, con quién y cuándo lo cambió, los defaults y las explicaciones."""
    valores = {}
    if db.disponible():
        try:
            for f in _filas_config():
                if f.get("clave") in CLAVES_CONFIG:
                    valores[f["clave"]] = {"valor": f.get("valor"), "actualizado": f.get("actualizado"), "por": f.get("por")}
        except Exception as e:
            raise HTTPException(503, f"No pude leer la configuración: {str(e)[:160]}")
    modelos_vistos = []
    if db.disponible():
        try:
            modelos_vistos = sorted({(f.get("modelo") or "?") for f in db.uso_openai(90)})
        except Exception:
            modelos_vistos = []
    return {"valores": valores, "explicaciones": CLAVES_CONFIG, "avisos_precios": AVISOS_PRECIOS,
            "defaults": {"frase_hora": FRASE_HORA_DEFECTO, "frase_pie": FRASE_PIE_DEFECTO, "frase_canales": ["instagram"], "umbral": 70},
            "frase_canales_posibles": FRASE_CANALES, "modelos_vistos": modelos_vistos,
            "proveedores_umbral": ["default", "supabase", "render", "vercel", "openai"]}


def _validar(clave, v):
    """Devuelve el valor limpio o levanta 400. Solo las claves de CLAVES_CONFIG (clips_estilo va por /recortes/estilo-defecto)."""
    if clave == "openai_precios":
        if not isinstance(v, dict):
            raise HTTPException(400, "openai_precios tiene que ser {modelo: {entrada, salida, cache, fuente}}.")
        out = {}
        for modelo, p in v.items():
            if not isinstance(p, dict) or not str(modelo).strip():
                raise HTTPException(400, f"Precio inválido para {modelo!r}.")
            lim = {}
            for k in ("entrada", "salida", "cache"):
                x = p.get(k)
                if x in (None, ""):
                    if k == "cache":
                        continue
                    raise HTTPException(400, f"{modelo}: falta el precio de {k}.")
                try:
                    x = float(x)
                except (TypeError, ValueError):
                    raise HTTPException(400, f"{modelo}: el precio de {k} tiene que ser un número.")
                if x < 0:
                    raise HTTPException(400, f"{modelo}: el precio de {k} no puede ser negativo.")
                lim[k] = x
            fuente = (p.get("fuente") or "").strip()
            if not fuente:
                raise HTTPException(400, f"{modelo}: falta la fuente del precio (de dónde salió y cuándo). Nada sin fuente.")
            lim["fuente"] = fuente
            if p.get("fecha"):
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(p["fecha"])):
                    raise HTTPException(400, f"{modelo}: la fecha tiene que ser AAAA-MM-DD.")
                lim["fecha"] = str(p["fecha"])
            if p.get("nota"):
                lim["nota"] = str(p["nota"]).strip()
            out[str(modelo).strip()] = lim
        return out
    if clave == "presupuesto_openai_usd":
        try:
            x = float(v or 0)
        except (TypeError, ValueError):
            raise HTTPException(400, "El presupuesto tiene que ser un número.")
        if x < 0:
            raise HTTPException(400, "El presupuesto no puede ser negativo.")
        return x
    if clave == "umbrales_planes":
        if not isinstance(v, dict):
            raise HTTPException(400, "umbrales_planes tiene que ser {proveedor: porcentaje}.")
        out = {}
        for k, x in v.items():
            try:
                x = float(x)
            except (TypeError, ValueError):
                raise HTTPException(400, f"Umbral de {k} inválido.")
            if not 1 <= x <= 100:
                raise HTTPException(400, f"Umbral de {k}: tiene que ser un porcentaje de 1 a 100.")
            out[str(k)] = x
        return out
    if clave == "vercel_uso_manual":
        gb = v.get("gb") if isinstance(v, dict) else v
        try:
            gb = float(gb)
        except (TypeError, ValueError):
            raise HTTPException(400, "Los GB tienen que ser un número.")
        if gb < 0:
            raise HTTPException(400, "Los GB no pueden ser negativos.")
        return {"gb": gb, "fecha": _ahora().isoformat(timespec="seconds")}      # «por» se agrega al guardar
    if clave == "frase_activa":
        if not isinstance(v, bool):
            raise HTTPException(400, "frase_activa tiene que ser true o false.")
        return v
    if clave == "frase_hora":
        if not isinstance(v, str) or not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", v.strip()):
            raise HTTPException(400, "La hora tiene que ser HH:MM (Argentina).")
        return v.strip()
    if clave == "frase_canales":
        if not isinstance(v, list) or not v or any(c not in FRASE_CANALES for c in v):
            raise HTTPException(400, f"Canales válidos: {', '.join(FRASE_CANALES)} (al menos uno).")
        return [c for c in FRASE_CANALES if c in v]
    if clave == "frase_imagen":
        s = (v or "").strip() if isinstance(v, str) else ""
        if s and not re.match(r"^https?://", s):
            raise HTTPException(400, "La foto tiene que ser una URL (https://…).")
        return s or None
    if clave == "frase_pie":
        if not isinstance(v, str):
            raise HTTPException(400, "El pie tiene que ser texto.")
        return v.strip()
    raise HTTPException(400, f"La clave {clave} no se cambia desde acá.")


@router.put("/config")
def guardar_config(datos: CambiosConfig, quien=Depends(_admin)):
    """Guarda cada clave de `cambios` (validada) con db.guardar_config y registra quién cambió qué (usuarios_cambios,
    acción «config», de → a). clips_estilo se guarda con PUT /recortes/estilo-defecto."""
    if not db.disponible():
        raise HTTPException(503, "Sin Supabase no hay dónde guardar la configuración.")
    if not datos.cambios:
        raise HTTPException(400, "No vino nada para cambiar.")
    limpios = {}
    for clave, v in datos.cambios.items():
        if clave not in CLAVES_CONFIG or clave == "clips_estilo":
            raise HTTPException(400, f"La clave {clave} no se cambia desde acá.")
        limpios[clave] = _validar(clave, v)
    guardadas = {}
    for clave, v in limpios.items():
        if clave == "vercel_uso_manual":
            v = dict(v, por=quien)
        try:
            antes = db.obtener_config(clave)
        except Exception:
            antes = None
        try:
            db.guardar_config(clave, v, quien)
        except Exception as e:
            raise HTTPException(503, f"No pude guardar {clave}: {str(e)[:160]}")
        db.registrar_cambio_usuario(quien, "config", clave, {"de": antes, "a": v})
        guardadas[clave] = v
    return {"ok": True, "guardadas": guardadas}
