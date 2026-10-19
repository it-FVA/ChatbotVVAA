"""
frases_ui.py — Solapa «📅 Frase del día» del Panel admin (19/10, reunión: idea de Franco, Beto de acuerdo).

Un calendario anual de frases: una por día, que sale sola cada mañana como posteo de Instagram con una foto
de fondo (pedido de Beto: "con una fotito, no solo texto"). Las frases vienen del Sheet Frases_consolidadas_591
(importar_frases.py → tabla `frases`); solo las validadas entran al calendario.

Pantalla (19/10, tarde: + pedidos de Franco: próximas 14 días, backlog visible, rotación cuando se acaba el año):
  - «Próximas 14 días»: fecha, frase y estado de lo que va a salir.
  - cabecera: conteos (backlog · programadas · publicadas), interruptor «Frase del día activa» (config frase_activa, apagado por defecto), hora de salida
    (config frase_hora), foto por defecto, logo y pie del caption (config frase_imagen / frase_estilo / frase_pie).
  - «Repartir en el año»: asigna un día a cada candidata a partir de mañana, con el criterio de la rotación (primero las
    nunca publicadas en el orden del Sheet o al azar sin repetir autor, después las publicadas de la más antigua a la más
    reciente), sin pisar fechas ya asignadas. Línea «hay frases nuevas hasta el …; después vuelve a empezar».
  - «Backlog»: validadas sin día y, aparte, las pendientes de validación de Pato (sin día asignable), con buscador.
  - calendario por mes (12 meses desde hoy): grilla de días con la frase recortada, el autor y el estado; «Ver» abre
    el detalle del día debajo: frase completa, editar texto/autor, mover a otra fecha, intercambiar con otra fecha,
    cambiar por otra frase (buscador entre las validadas sin fecha), foto de fondo (banco de WordPress, igual que el
    formulario de publicar), vista previa de la imagen compuesta, saltar ese día, sacar del calendario.
    Streamlit no tiene arrastrar y soltar: «mover» e «intercambiar» lo resuelven.
Lo que sale cada día lo arma programar_frases.py (misma pasada que la cola).
"""
import calendar
import datetime
import random

import streamlit as st

import db
import programar_frases as pf

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
DIAS = ["Lu", "Ma", "Mi", "Ju", "Vi", "Sá", "Do"]
ESTADO_ICONO = {"programada": "🗓", "publicada": "📣", "simulada": "👁", "saltada": "⏭"}
ESTADO_TXT = {"programada": "programada", "publicada": "publicada", "simulada": "simulada (la cola la procesó en modo simulado)",
              "saltada": "saltada: ese día no sale nada"}


def _hoy():
    return pf.hoy_argentina()


def _fecha_txt(d):
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def _recortar(t, n=70):
    t = (t or "").strip().replace("\n", " ")
    return t if len(t) <= n else t[:n - 1].rstrip() + "…"


# ---------------- Repartir ----------------

def repartir(frases, desde, ocupadas, modo="orden", semilla=None):
    """Asigna una fecha a cada frase a partir de `desde`, saltando `ocupadas`. Primero las nunca publicadas (modo 'orden' = del
    Sheet, 'azar' = mezcladas sin repetir autor dos días seguidos cuando se puede), después las ya publicadas de la más antigua
    a la más reciente (rotación). Devuelve [(frase, fecha)]. No escribe nada."""
    nuevas = sorted([f for f in frases if not f.get("ultima_publicada")], key=lambda f: (f.get("orden") is None, f.get("orden") or 0))
    viejas = sorted([f for f in frases if f.get("ultima_publicada")], key=lambda f: f["ultima_publicada"])
    if modo == "azar":
        random.Random(semilla).shuffle(nuevas)
    out, d, autor_prev = [], desde, None
    for pendientes in (nuevas, viejas):
        while pendientes:
            if d.isoformat() in ocupadas:
                d += datetime.timedelta(days=1)
                continue
            elegida = pendientes[0]
            if modo == "azar" and autor_prev and pendientes is nuevas:
                for f in pendientes:
                    if (f.get("autor") or "") != autor_prev:
                        elegida = f
                        break
            pendientes.remove(elegida)
            out.append((elegida, d))
            autor_prev = elegida.get("autor") or ""
            d += datetime.timedelta(days=1)
    return out


def _guardar_reparto(reparto):
    filas = [{"id": f["id"], "texto": f["texto"], "fecha": d.isoformat(), "estado": "programada", "publicacion_id": None, "piezas": None,
              "actualizado": db._ahora_iso()} for f, d in reparto]
    for i in range(0, len(filas), 200):
        db.upsert_frases(filas[i:i + 200], on_conflict="id")
    return len(filas)


# ---------------- Cabecera y configuración ----------------

def _cabecera(usuario):
    r = db.resumen_frases()
    activa = bool(db.obtener_config("frase_activa", False))
    hoy = _hoy()
    programadas = [f for f in db.listar_frases(desde=hoy.isoformat()) if f.get("estado") in ("programada", "saltada")]
    r["programadas"] = len(programadas)
    c1, c2 = st.columns([3, 2])
    c1.markdown(f"**Backlog: {r.get('sin_fecha_validadas', 0)}** validadas sin día · **Programadas: {r['programadas']}** · "
                f"**Publicadas: {r.get('publicadas', 0)}** · {r.get('pendientes_validar', 0)} pendientes de validar (Pato) · "
                f"{r.get('validadas', 0)} validadas de {r.get('total', 0)} cargadas")
    nuevas_prog = [f["fecha"] for f in programadas if not f.get("ultima_publicada")]
    nuevas_backlog = sum(1 for f in db.frases_sin_fecha(solo_validadas=True) if not f.get("ultima_publicada"))
    if nuevas_prog or nuevas_backlog:
        fin = datetime.date.fromisoformat(max(nuevas_prog)) if nuevas_prog else hoy
        fin = fin + datetime.timedelta(days=nuevas_backlog)
        st.caption(f"Con las {r.get('validadas', 0)} validadas, hay frases nuevas hasta el **{fin.strftime('%d/%m/%Y')}**"
                   + (f" ({nuevas_backlog} todavía sin día)" if nuevas_backlog else "")
                   + "; después vuelve a empezar por las más antiguas publicadas. Nunca se queda sin frase: si un día está vacío, "
                     "la cola le asigna sola la siguiente de la rotación.")
    else:
        st.caption("Ya salieron todas las validadas al menos una vez: siguen en rotación, de la más antigua a la más reciente.")
    nueva = c2.toggle("Frase del día activa (sale sola cada mañana)", value=activa, key="fd_activa",
                      help="Apagada: el calendario se arma igual pero no sale nada. Prendida: cada día la frase de ese día se encola "
                           "como posteo de Instagram (hoy en el modo que tenga PUBLICAR_INSTAGRAM: simulado = no sale nada).")
    if nueva != activa:
        db.guardar_config("frase_activa", bool(nueva), usuario)
        st.toast("Frase del día " + ("activada." if nueva else "apagada."))
    if not r.get("total"):
        st.info("Todavía no hay frases cargadas. Correr `python importar_frases.py` (lee el Sheet Frases_consolidadas_591).")
    man = _hoy() + datetime.timedelta(days=1)
    prox = db.frase_del_dia(man.isoformat())
    if not db.obtener_config("frase_imagen"):
        st.warning("Falta la **foto de fondo por defecto** (abajo, en «Cómo sale cada día»). Sin una foto elegida para el día o una por defecto, "
                   "la frase de ese día no se encola.")
    if activa:
        if prox and prox.get("estado") == "programada":
            st.caption(f"Mañana ({_fecha_txt(man)}) sale: «{_recortar(prox['texto'], 90)}» — {prox.get('autor') or ''}"
                       + (" · ya está en la cola." if prox.get("publicacion_id") else " · la cola la encola en su próxima pasada."))
        elif prox and prox.get("estado") == "saltada":
            st.caption(f"Mañana ({_fecha_txt(man)}) está salteado: no sale nada.")
        else:
            st.warning(f"Mañana ({_fecha_txt(man)}) no tiene frase asignada: no va a salir nada. Repartí o asigná una.")
    return r


def _proximas(dias=14):
    hoy = _hoy()
    hasta = hoy + datetime.timedelta(days=dias - 1)
    por_dia = {f["fecha"]: f for f in db.listar_frases(desde=hoy.isoformat(), hasta=hasta.isoformat())}
    with st.expander(f"🔜 Próximas {dias} días", expanded=True):
        lineas = []
        for i in range(dias):
            d = hoy + datetime.timedelta(days=i)
            f = por_dia.get(d.isoformat())
            if f:
                est = f.get("estado") or "programada"
                extra = " ↻ repetida" if f.get("ultima_publicada") else ""
                lineas.append(f"| {DIAS[d.weekday()]} {d.strftime('%d/%m')} | {_recortar(f['texto'], 95)} — _{f.get('autor') or ''}_ | {ESTADO_ICONO.get(est, '')} {est}{extra} |")
            else:
                lineas.append(f"| {DIAS[d.weekday()]} {d.strftime('%d/%m')} | _sin frase (la cola asigna la siguiente de la rotación)_ | — |")
        st.markdown("| Día | Frase | Estado |\n|---|---|---|\n" + "\n".join(lineas))


def _backlog():
    with st.expander("📚 Backlog (validadas sin día · pendientes de validación)", expanded=False):
        q = st.text_input("Buscar por texto o autor", key="fd_backlog_q", placeholder="ej. gratitud, Brother David")
        ql = q.strip().lower()
        filtro = (lambda f: (not ql) or ql in (f.get("texto") or "").lower() or ql in (f.get("autor") or "").lower())
        sin = [f for f in db.frases_sin_fecha(solo_validadas=True) if filtro(f)]
        pend = [f for f in db.frases_pendientes_validacion() if filtro(f)]
        tb1, tb2 = st.tabs([f"✅ Validadas sin día ({len(sin)})", f"🕓 Pendientes de validación ({len(pend)})"])
        with tb1:
            if not sin:
                st.caption("No hay validadas sin día" + (" que coincidan." if ql else ": están todas en el calendario."))
            for f in sin[:200]:
                st.markdown(f"- {_recortar(f['texto'], 160)} — _{f.get('autor') or ''}_"
                            + (f" · ↻ salió {f['veces_publicada']} vez/veces" if f.get("veces_publicada") else ""))
            if len(sin) > 200:
                st.caption(f"…y {len(sin) - 200} más (afiná la búsqueda).")
        with tb2:
            st.caption("Las nuevas del Sheet esperan el OK de Pato: no se pueden asignar a un día hasta que estén validadas "
                       "(se marcan en el Sheet y se vuelve a correr importar_frases.py).")
            for f in pend[:200]:
                st.markdown(f"- {_recortar(f['texto'], 160)} — _{f.get('autor') or ''}_ · 🕓 pendiente")


def _configuracion(usuario):
    import imagen as _im
    with st.expander("⚙️ Cómo sale cada día (hora, foto por defecto, logo, pie del posteo)", expanded=False):
        hora_txt = db.obtener_config("frase_hora", pf.HORA_DEFECTO) or pf.HORA_DEFECTO
        try:
            h0 = datetime.time(int(hora_txt[:2]), int(hora_txt[3:5]))
        except Exception:
            h0 = datetime.time(7, 0)
        estilo = dict(pf.ESTILO_DEFECTO, **(db.obtener_config("frase_estilo") or {}))
        c1, c2, c3 = st.columns(3)
        hora = c1.time_input("Hora de salida (Argentina)", value=h0, key="fd_hora", step=900,
                             help="La cola corre cada 15 minutos: sale en la pasada siguiente a esta hora.")
        logos = list(_im.LOGOS)
        logo = c2.selectbox("Logo", logos, index=logos.index(estilo["logo"]) if estilo.get("logo") in logos else 1, key="fd_logo")
        plogos = list(_im.POSICIONES_LOGO)
        plogo = c3.selectbox("Posición del logo", plogos, index=plogos.index(estilo["posicion_logo"]) if estilo.get("posicion_logo") in plogos else 0,
                             key="fd_plogo", disabled=(logo == "Sin logo"))
        d1, d2, d3 = st.columns(3)
        tipos = list(_im.TIPOGRAFIAS)
        tipo = d1.selectbox("Tipografía", tipos, index=tipos.index(estilo["tipografia"]) if estilo.get("tipografia") in tipos else 0, key="fd_tipo")
        pesos = list(_im.PESOS)
        peso = d2.selectbox("Peso", pesos, index=pesos.index(estilo["peso"]) if estilo.get("peso") in pesos else 0, key="fd_peso")
        poss = list(_im.POSICIONES)
        pos = d3.selectbox("Posición del texto", poss, index=poss.index(estilo["posicion"]) if estilo.get("posicion") in poss else 0, key="fd_pos")
        pie = st.text_input("Pie del posteo (va después de la frase y el autor)", value=db.obtener_config("frase_pie", pf.PIE_DEFECTO) or "",
                            key="fd_pie")
        canales_act = [c for c in (db.obtener_config("frase_canales") or pf.CANALES_DEFECTO) if c in pf.CANALES_POSIBLES]
        canales = st.multiselect("Canales por los que sale cada día", list(pf.CANALES_POSIBLES), default=canales_act, key="fd_canales",
                                 format_func=lambda c: pf.CANALES_POSIBLES[c],
                                 help="Una pieza por canal en la cola. El mail se agrega acá cuando haya herramienta de envío (Julián audita Perfit).")
        st.markdown("**Foto de fondo por defecto** (para los días que no tienen una foto elegida)")
        foto_def = db.obtener_config("frase_imagen") or ""
        url_def = st.text_input("URL de la foto (del banco de WordPress o de internet)", value=foto_def, key="fd_foto_def",
                                help="Si queda vacío, se usa una foto del banco etiquetada «cuadrado» al azar; si no hay ninguna (hoy no hay), ese día no se encola.")
        if url_def.strip():
            st.image(url_def.strip(), width=160)
        if st.button("💾 Guardar", key="fd_guardar_cfg", type="primary"):
            db.guardar_config("frase_hora", hora.strftime("%H:%M"), usuario)
            db.guardar_config("frase_estilo", {"logo": logo, "posicion_logo": plogo, "tipografia": tipo, "peso": peso, "posicion": pos,
                                               "alineacion": "centro", "formato": "cuadrado"}, usuario)
            db.guardar_config("frase_pie", pie.strip(), usuario)
            db.guardar_config("frase_imagen", url_def.strip() or None, usuario)
            db.guardar_config("frase_canales", canales or pf.CANALES_DEFECTO, usuario)
            st.success("Guardado. Vale para las frases que se encolen de ahora en más.")


def _acciones(usuario, r):
    with st.expander("🔀 Repartir en el año · vaciar · agregar una frase", expanded=not r.get("con_fecha")):
        sin = r.get("sin_fecha_validadas", 0)
        c1, c2, c3 = st.columns([2, 2, 1])
        modo = c1.radio("Orden", ["En el orden del Sheet", "Al azar (sin repetir autor dos días seguidos)"], key="fd_modo",
                        horizontal=False)
        desde = c2.date_input("A partir del", value=_hoy() + datetime.timedelta(days=1), min_value=_hoy(), key="fd_desde")
        c3.markdown(f"<br>**{sin}** validadas sin día", unsafe_allow_html=True)
        st.caption("Reparte primero las nunca publicadas; cuando se acaban, siguen las ya publicadas de la más antigua a la más reciente.")
        if c3.button("📅 Repartir en el año", key="fd_repartir", type="primary"):
            frases = db.candidatas_rotacion(_hoy().isoformat())
            ocupadas = db.fechas_ocupadas(desde.isoformat(), (desde + datetime.timedelta(days=3 * 365)).isoformat())
            reparto = repartir(frases, desde, ocupadas, "azar" if modo.startswith("Al azar") else "orden")
            n = _guardar_reparto(reparto)
            ultimo = reparto[-1][1] if reparto else desde
            st.success(f"Listo: {n} frases repartidas, del {_fecha_txt(desde)} al {_fecha_txt(ultimo)}. Las fechas que ya tenían frase no se tocaron.")
            st.rerun()
        st.divider()
        v1, v2 = st.columns([3, 1])
        conf = v1.checkbox("Confirmo: sacar TODAS las frases del calendario que todavía no salieron (vuelven a «sin día»; las publicadas quedan).",
                           key="fd_vaciar_ok")
        if v2.button("🗑 Vaciar el calendario", key="fd_vaciar", disabled=not conf):
            n = 0
            for f in db.listar_frases(desde=_hoy().isoformat()):
                if f.get("estado") in ("programada", "saltada") and f.get("fecha") and not f.get("publicacion_id"):
                    db.actualizar_frase(f["id"], {"fecha": None, "estado": "programada"})
                    n += 1
            st.success(f"{n} frases volvieron a «sin día». Las que ya están en la cola o salieron no se tocaron.")
            st.rerun()
        st.divider()
        st.markdown("**➕ Agregar una frase nueva** (queda validada y sin día; después la asignás desde el calendario)")
        n1, n2 = st.columns([3, 1])
        txt = n1.text_area("Frase", key="fd_nueva_txt", height=80)
        aut = n2.text_input("Autor", key="fd_nueva_autor")
        if st.button("Agregar", key="fd_nueva_ok", disabled=not txt.strip()):
            try:
                db.crear_frase(txt, aut, validada=True, origen="manual")
                st.success("Agregada.")
                st.rerun()
            except Exception as e:
                st.error(f"No pude agregarla (¿ya existe una igual?): {e}")


# ---------------- Calendario ----------------

def _meses_disponibles():
    hoy = _hoy()
    out = []
    y, m = hoy.year, hoy.month
    for _ in range(12):
        out.append((y, m))
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return out


def _calendario(frases_mes, y, m):
    """Grilla del mes: cada día con la frase recortada, el autor y el estado; botón «Ver» abre el detalle."""
    hoy = _hoy()
    por_dia = {f["fecha"]: f for f in frases_mes if f.get("fecha")}
    cols = st.columns(7)
    for c, nombre in zip(cols, DIAS):
        c.markdown(f"<div style='text-align:center;color:#888;font-size:0.85em'>{nombre}</div>", unsafe_allow_html=True)
    for semana in calendar.Calendar(firstweekday=0).monthdayscalendar(y, m):
        cols = st.columns(7)
        for c, dia in zip(cols, semana):
            if not dia:
                continue
            d = datetime.date(y, m, dia)
            iso = d.isoformat()
            f = por_dia.get(iso)
            with c.container(border=True):
                marca = " ·hoy" if d == hoy else ""
                if f:
                    ic = ESTADO_ICONO.get(f.get("estado"), "🗓") + (" ↻" if f.get("ultima_publicada") else "")
                    st.markdown(f"**{dia}**{marca} {ic}")
                    st.caption(_recortar(f["texto"], 60) + (f"\n\n_{f.get('autor') or ''}_" if f.get("autor") else ""))
                else:
                    st.markdown(f"**{dia}**{marca}")
                    st.caption("sin frase" if d >= hoy else "—")
                if st.button("Ver", key=f"fd_ver_{iso}", width="stretch"):
                    st.session_state["fd_dia"] = iso
                    st.rerun()


# ---------------- Detalle de un día ----------------

def _buscador(key, excluir_id=None):
    """Buscador por texto entre las validadas sin fecha. Devuelve la frase elegida o None."""
    q = st.text_input("Buscar entre las frases validadas sin día (texto o autor)", key=f"{key}_q", placeholder="ej. gratitud, Brother David")
    cand = db.frases_sin_fecha(solo_validadas=True)
    if q.strip():
        ql = q.strip().lower()
        cand = [f for f in cand if ql in (f.get("texto") or "").lower() or ql in (f.get("autor") or "").lower()]
    cand = [f for f in cand if f["id"] != excluir_id][:30]
    if not cand:
        st.caption("No hay frases sin día que coincidan.")
        return None
    etiquetas = [f"{_recortar(f['texto'], 90)} — {f.get('autor') or ''}" for f in cand]
    i = st.selectbox(f"{len(cand)} coincidencias (se muestran hasta 30)", range(len(cand)), format_func=lambda i: etiquetas[i], key=f"{key}_sel")
    return cand[i]


def _vista_previa(frase, usuario):
    """La imagen compuesta chica (frase + autor + logo sobre la foto), como va a salir."""
    import publicar_ui
    cfg = publicar_ui._cfg(usuario)
    import publicar
    foto, de_donde = pf.foto_de_fondo(frase, cfg, db, publicar)
    if not foto:
        st.caption("Sin foto para la vista previa: elegí una abajo o cargá una por defecto en «Cómo sale cada día».")
        return
    estilo = db.obtener_config("frase_estilo") or {}
    try:
        jpg = pf.componer(frase, foto, estilo)
        st.image(jpg, width=300, caption=f"Así saldría (foto: {de_donde})")
    except Exception as e:
        st.caption(f"No pude armar la vista previa: {e}")


def _detalle(iso, usuario):
    import publicar_ui
    d = datetime.date.fromisoformat(iso)
    f = db.frase_del_dia(iso)
    st.markdown(f"### 📌 {_fecha_txt(d)}")
    if not f:
        st.caption("Este día no tiene frase. Elegí una de las validadas sin día:")
        eleg = _buscador(f"fd_asig_{iso}")
        if eleg and st.button("Asignar a este día", key=f"fd_asig_ok_{iso}", type="primary"):
            if db.mover_frase(eleg["id"], iso):
                st.success("Asignada.")
                st.rerun()
            else:
                st.error("Ese día ya tiene frase (recargá).")
        return
    est = f.get("estado") or "programada"
    c1, c2 = st.columns([3, 2])
    with c1:
        st.markdown(f"> {f['texto']}")
        st.markdown(f"**{f.get('autor') or '(sin autor)'}** · {ESTADO_ICONO.get(est, '')} {ESTADO_TXT.get(est, est)}"
                    + (f" · ↻ ya salió {f['veces_publicada']} vez/veces (última {str(f['ultima_publicada'])[:10]})" if f.get("ultima_publicada") else "")
                    + (f" · fuente: {f['fuente']}" if f.get("fuente") else "") + (f" · tema: {f['tema']}" if f.get("tema") else ""))
        if f.get("publicacion_id"):
            p = db.obtener_publicacion(f["publicacion_id"])
            if p:
                st.caption(f"En la cola: estado **{p.get('estado')}**, sale el {str(p.get('fecha_programada') or '')[:16].replace('T', ' ')}"
                           + (f" · [ver publicación ↗]({((p.get('resultado') or {}).get('ultimo') or {}).get('permalink')})"
                              if ((p.get('resultado') or {}).get('ultimo') or {}).get('permalink') else ""))
    with c2:
        _vista_previa(f, usuario)
    cerrada = est in ("publicada", "simulada") or bool(f.get("publicacion_id"))
    if cerrada:
        st.info("Esta frase ya está en la cola o ya salió: no se mueve ni se edita desde acá. (Para frenarla, cancelá la pieza en «🗓 En cola».)")
        return
    t_txt, t_mover, t_cambiar, t_foto, t_saltar = st.tabs(["✏️ Texto", "📆 Mover / intercambiar", "🔁 Cambiar por otra", "🖼 Foto de fondo", "⏭ Saltar / sacar"])
    with t_txt:
        nt = st.text_area("Frase", value=f["texto"], key=f"fd_txt_{f['id']}", height=120)
        na = st.text_input("Autor", value=f.get("autor") or "", key=f"fd_aut_{f['id']}")
        if st.button("💾 Guardar el texto", key=f"fd_txt_ok_{f['id']}", disabled=(nt.strip() == f["texto"] and na.strip() == (f.get("autor") or ""))):
            try:
                db.actualizar_frase(f["id"], {"texto": nt.strip(), "autor": na.strip() or None})
                st.success("Guardado.")
                st.rerun()
            except Exception as e:
                st.error(f"No pude guardar (¿ya existe otra frase con ese texto?): {e}")
    with t_mover:
        m1, m2 = st.columns(2)
        with m1:
            st.markdown("**Mover a otra fecha** (la fecha destino tiene que estar libre)")
            nd = st.date_input("Nueva fecha", value=d, min_value=_hoy(), key=f"fd_mov_{f['id']}")
            if st.button("Mover", key=f"fd_mov_ok_{f['id']}", disabled=(nd == d)):
                if db.mover_frase(f["id"], nd.isoformat()):
                    st.session_state["fd_dia"] = nd.isoformat()
                    st.success(f"Movida al {_fecha_txt(nd)}.")
                    st.rerun()
                else:
                    st.error(f"El {_fecha_txt(nd)} ya tiene frase. Usá «Intercambiar» si querés cambiarlas de lugar.")
        with m2:
            st.markdown("**Intercambiar con la frase de otra fecha**")
            od = st.date_input("Fecha con la que se intercambia", value=d + datetime.timedelta(days=1), min_value=_hoy(), key=f"fd_int_{f['id']}")
            otra = db.frase_del_dia(od.isoformat()) if od != d else None
            if otra:
                st.caption(f"Ese día tiene: «{_recortar(otra['texto'], 80)}» — {otra.get('autor') or ''}")
                if otra.get("publicacion_id") or otra.get("estado") in ("publicada", "simulada"):
                    st.caption("⚠ Esa frase ya está en la cola o ya salió: no se puede intercambiar.")
                    otra = None
            elif od != d:
                st.caption("Ese día no tiene frase: usá «Mover».")
            if st.button("Intercambiar", key=f"fd_int_ok_{f['id']}", disabled=not otra):
                db.intercambiar_frases(f["id"], otra["id"])
                st.success(f"Intercambiadas: esta pasa al {_fecha_txt(od)} y la otra viene al {_fecha_txt(d)}.")
                st.rerun()
    with t_cambiar:
        st.caption("La frase de este día vuelve a «sin día» y entra la que elijas.")
        eleg = _buscador(f"fd_camb_{f['id']}", excluir_id=f["id"])
        if eleg and st.button("Poner esta en su lugar", key=f"fd_camb_ok_{f['id']}", type="primary"):
            db.intercambiar_frases(f["id"], eleg["id"])
            st.success("Cambiada.")
            st.rerun()
    with t_foto:
        cfg = publicar_ui._cfg(usuario)
        st.caption("Foto del banco de imágenes de WordPress (las etiquetadas «cuadrado» primero). Sin elección, va la foto por defecto.")
        if f.get("imagen_url"):
            st.image(f["imagen_url"], width=160, caption="Foto elegida para esta frase")
            if st.button("Volver a la foto por defecto", key=f"fd_foto_def_{f['id']}"):
                db.actualizar_frase(f["id"], {"imagen_url": None})
                st.rerun()
        b1, b2 = st.columns([4, 1])
        consulta = b1.text_input("Buscar en el banco", key=f"fd_busq_{f['id']}", placeholder="ej. amanecer montaña calma", label_visibility="collapsed")
        if b2.button("Buscar", key=f"fd_busq_ok_{f['id']}", width="stretch"):
            st.session_state.get("banco_cache", {}).pop(f"fd_{f['id']}|{consulta.strip().lower()}|cuadrado", None)
        cand = publicar_ui._banco(cfg, consulta, f"fd_{f['id']}", "cuadrado")
        if cand:
            cols = st.columns(len(cand))
            for i, (c, img) in enumerate(zip(cols, cand)):
                c.image(img["miniatura"], width="stretch")
                c.caption((img["titulo"] or f"#{img['id']}")[:28])
                if c.button("Usar", key=f"fd_usar_{f['id']}_{img['id']}", width="stretch"):
                    db.actualizar_frase(f["id"], {"imagen_url": img["url"]})
                    st.rerun()
        else:
            st.caption("El banco no devolvió nada para esa búsqueda.")
        url_manual = st.text_input("…o pegá la URL de una imagen que ya está en internet", key=f"fd_url_{f['id']}")
        if url_manual.strip() and st.button("Usar esa URL", key=f"fd_url_ok_{f['id']}"):
            db.actualizar_frase(f["id"], {"imagen_url": url_manual.strip()})
            st.rerun()
    with t_saltar:
        s1, s2 = st.columns(2)
        with s1:
            if est == "saltada":
                st.caption("Este día está salteado: no sale nada. La frase queda guardada en este día.")
                if st.button("↩ Volver a programarla", key=f"fd_resaltar_{f['id']}"):
                    db.actualizar_frase(f["id"], {"estado": "programada"})
                    st.rerun()
            else:
                st.caption("Saltar: ese día no sale nada; la frase queda en su lugar (marcada ⏭) y se puede volver a programar.")
                if st.button("⏭ Saltar ese día", key=f"fd_saltar_{f['id']}"):
                    db.actualizar_frase(f["id"], {"estado": "saltada"})
                    st.success("Salteado.")
                    st.rerun()
        with s2:
            st.caption("Sacar del calendario: la frase vuelve a «sin día» y el día queda libre (lo llena «Repartir» o una asignación a mano).")
            if st.button("Sacar del calendario", key=f"fd_sacar_{f['id']}"):
                db.actualizar_frase(f["id"], {"fecha": None, "estado": "programada"})
                st.session_state.pop("fd_dia", None)
                st.rerun()


# ---------------- Entrada ----------------

def render(usuario):
    st.caption("Una frase por día, que sale sola cada mañana como posteo de Instagram con una foto de fondo. "
               "Las frases vienen del Sheet Frases_consolidadas_591 (solo las validadas). El mail no entra todavía (Julián está auditando Perfit).")
    try:
        _proximas()
        r = _cabecera(usuario)
    except Exception as e:
        st.error(f"No pude leer las frases: {e}")
        return
    _configuracion(usuario)
    _acciones(usuario, r)
    _backlog()
    meses = _meses_disponibles()
    etiquetas = [f"{MESES[m - 1].capitalize()} {y}" for y, m in meses]
    sel = st.selectbox("Mes", range(len(meses)), format_func=lambda i: etiquetas[i], key="fd_mes")
    y, m = meses[sel]
    ultimo = calendar.monthrange(y, m)[1]
    frases_mes = db.listar_frases(desde=f"{y:04d}-{m:02d}-01", hasta=f"{y:04d}-{m:02d}-{ultimo:02d}")
    st.caption("🗓 programada · 📣 publicada · 👁 simulada · ⏭ salteada · ↻ ya salió antes (rotación)")
    _calendario(frases_mes, y, m)
    dia = st.session_state.get("fd_dia")
    if dia:
        st.divider()
        _detalle(dia, usuario)
