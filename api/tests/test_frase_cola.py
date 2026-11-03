"""(3/11, revisión 5.2 punto 14) La cola y la Frase del día de punta a punta con una `db` simulada en memoria y sin red:
encolar_frase por canal, sumar canales a una frase ya encolada, frenar y volver a encolar (POST /frases/manana/frenar y /encolar),
el mail en tandas con `perfit` simulado y procesar_cola.main con los conectores simulados. Un canal nuevo se prueba acá sin publicar."""
import datetime, sys, types

import pytest

import canales
import db
import frase_mail
import imagen
import procesar_cola
import programar_frases as pf
import publicar
import api.frases._comun as fr

HOY = datetime.date(2026, 11, 3)
MAN = HOY + datetime.timedelta(days=1)


class DbFalsa:
    """Las tablas publicaciones, frases, config y frase_envios en memoria, con las funciones que usan la cola y la frase."""

    def __init__(self):
        self.pubs, self.frases, self.envios, self.n = {}, {}, [], 0
        self.config = {"frase_activa": True, "frase_imagen": "https://wp/fondo.jpg", "frase_hora": "07:00", "frase_mail_prueba": ["a@x.org", "b@x.org", "c@x.org"]}

    # config y frases
    def disponible(self): return True
    def _ahora_iso(self): return "2026-11-03T10:00:00+00:00"
    def obtener_config(self, k, d=None): return self.config.get(k, d)
    def guardar_config(self, k, v, u=None): self.config[k] = v
    def obtener_frase(self, fid): return dict(self.frases[fid]) if fid in self.frases else None
    def frase_del_dia(self, fecha): return next((dict(f) for f in self.frases.values() if f.get("fecha") == str(fecha)[:10]), None)
    def actualizar_frase(self, fid, campos): self.frases[fid].update(campos)
    def frases_para_marcar_publicadas(self): return [dict(f) for f in self.frases.values() if f.get("estado") == "programada" and f.get("publicacion_id")]
    def candidatas_rotacion(self, hoy): return []
    def listar_solicitudes_frase(self, estado=None, usuario=None, limite=200): return []
    # publicaciones
    def encolar_publicacion(self, usuario, canal, modo, titulo, texto, imagen_url, fecha_programada, extra=None):
        self.n += 1
        pid = f"p{self.n}"
        self.pubs[pid] = {"id": pid, "usuario": usuario, "canal": canal, "modo": modo, "titulo": titulo, "texto": texto, "imagen_url": imagen_url,
                          "fecha_programada": fecha_programada, "estado": "pendiente", "intentos": 0, "resultado": dict(extra or {}, encolada_por=usuario)}
        return pid
    def obtener_publicacion(self, pid): return dict(self.pubs[pid]) if pid in self.pubs else None
    def actualizar_publicacion(self, pid, campos): self.pubs[pid].update(campos)
    def cancelar_publicacion(self, pid, usuario): self.pubs[pid].update(estado="cancelada", resultado={"cancelada_por": usuario})
    def reclamar_publicacion(self, pid, resultado=None):
        if self.pubs[pid]["estado"] != "pendiente":
            return False
        self.pubs[pid]["estado"] = "procesando"
        return True
    def listar_pendientes(self, vencidas=False, limite=50): return [dict(p) for p in self.pubs.values() if p["estado"] == "pendiente"]
    def liberar_procesando_viejas(self, minutos=30): return []
    def vaciar_papelera_vencida(self): return 0
    def publicaciones_por_estado(self, estado, canal=None, limite=20):
        return [dict(p) for p in self.pubs.values() if p["estado"] == estado and (not canal or p["canal"] == canal)]
    # frase_envios
    def crear_envios_frase(self, pid, fecha, emails, prueba=False):
        out = []
        for e in emails:
            self.n += 1
            fila = {"id": f"e{self.n}", "publicacion_id": pid, "fecha": fecha, "email": e, "estado": "pendiente", "prueba": prueba}
            self.envios.append(fila); out.append({"id": fila["id"], "email": e})
        return out
    def envios_pendientes(self, pid, limite=50): return [dict(e) for e in self.envios if e["publicacion_id"] == pid and e["estado"] == "pendiente"][:limite]
    def actualizar_envio(self, eid, campos): next(e for e in self.envios if e["id"] == eid).update(campos)
    def resumen_envios(self, pid=None, fecha=None, prueba=None):
        filas = [e for e in self.envios if (pid is None or e["publicacion_id"] == pid)]
        out = {"pendiente": 0, "enviado": 0, "error": 0}
        for e in filas:
            out[e["estado"]] = out.get(e["estado"], 0) + 1
        out["total"] = len(filas)
        return out


@pytest.fixture
def base(monkeypatch):
    """db simulada montada sobre el paquete db, hoy fijo, imagen compuesta y subida a WordPress simuladas."""
    falsa = DbFalsa()
    for nombre in dir(DbFalsa):
        if not nombre.startswith("__"):
            monkeypatch.setattr(db, nombre, getattr(falsa, nombre))
    monkeypatch.setattr(pf, "hoy_argentina", lambda: HOY)
    monkeypatch.setattr(imagen, "componer_imagen", lambda foto, texto, **k: b"jpg:" + (k.get("formato") or "cuadrado").encode())
    falsa.subidas = []
    def _subir(cfg, datos, nombre, **k):
        if cfg.modo_wp not in ("borrador", "real"):      # como el conector real: en simulado/apagado no sube nada
            return {"ok": False, "modo": cfg.modo_wp, "aviso": f"WordPress está en {cfg.modo_wp}."}
        falsa.subidas.append((nombre, datos))
        return {"ok": True, "url": f"https://wp/{nombre}", "modo": cfg.modo_wp}
    monkeypatch.setattr(publicar, "subir_imagen_wordpress", _subir)
    monkeypatch.setattr(publicar, "_registrar", lambda e: e)
    falsa.frases["f1"] = {"id": "f1", "texto": "La gratitud es la llave.", "autor": "Br. David", "validada": True, "fecha": MAN.isoformat(),
                         "imagen_url": None, "estado": "programada", "publicacion_id": None, "piezas": None, "estilo": None, "veces_publicada": 0}
    return falsa


def _cfg(**modos):
    fuente = {c.variable: modos.get(c.clave, "real") for c in canales.CANALES.values()}
    fuente.update({"WP_SITE": "x.org", "WP_USER": "u", "WP_APP_PASSWORD": "p", "PUBLICAR_WHATSAPP": "simulado", "PUBLICAR_NEWSLETTER": "apagado"})
    return publicar.Config(fuente)


# ---------------- encolar_frase ----------------
def test_encolar_frase_por_canal(base):
    """Una pieza por salida (historia, posteo, Facebook, mail, home, WhatsApp), cada una con su canal real, formato, fecha y texto."""
    piezas, aviso = pf.encolar_frase(base.frases["f1"], MAN, _cfg(), db, publicar, canales=list(canales.SALIDAS_FRASE))
    assert set(piezas) == set(canales.SALIDAS_FRASE) and "encolada para el 2026-11-04 07:00" in aviso
    por = {k: base.pubs[v] for k, v in piezas.items()}
    assert por["historia"]["canal"] == "instagram" and por["historia"]["resultado"]["formato"] == "historia"
    assert por["historia"]["imagen_url"] == "https://wp/frase-del-dia-2026-11-04-historia.jpg" and por["historia"]["titulo"].endswith("(historia)")
    assert por["instagram"]["canal"] == "instagram" and por["instagram"]["resultado"]["formato"] == "cuadrado" and por["instagram"]["imagen_url"] == "https://wp/frase-del-dia-2026-11-04.jpg"
    assert por["facebook"]["canal"] == "facebook" and "«La gratitud es la llave.»" in por["facebook"]["texto"] and "#FraseDelDía" in por["facebook"]["texto"]
    assert por["mail"]["canal"] == "mail" and por["mail"]["fecha_programada"] == "2026-11-03T15:00:00-03:00" and por["mail"]["titulo"].endswith("(mail)")
    assert por["home"]["canal"] == "home" and por["home"]["resultado"]["texto_imagen"] == "La gratitud es la llave." and por["home"]["resultado"]["autor"] == "Br. David"
    assert por["whatsapp"]["canal"] == "whatsapp" and por["whatsapp"]["texto"].startswith("«La gratitud es la llave.»\n— Br. David") and "#" not in por["whatsapp"]["texto"]
    assert all(p["fecha_programada"] == "2026-11-04T07:00:00-03:00" for k, p in por.items() if k != "mail")
    assert all(p["modo"] == ("simulado" if k == "whatsapp" else "real") for k, p in por.items())
    assert all(p["resultado"]["frase_id"] == "f1" and p["resultado"]["frase_del_dia"] == "2026-11-04" for p in por.values())
    # dos imágenes compuestas (cuadrada e historia), la frase apunta a sus piezas y queda programada
    assert [n for n, _ in base.subidas] == ["frase-del-dia-2026-11-04.jpg", "frase-del-dia-2026-11-04-historia.jpg"]
    assert base.subidas[1][1] == b"jpg:historia"
    f = base.frases["f1"]
    assert f["piezas"] == piezas and f["publicacion_id"] == piezas["instagram"] and f["estado"] == "programada"


def test_sumar_canales_a_una_frase_encolada(base):
    """Un canal prendido después (p. ej. la home) se suma sin pisar las piezas que ya estaban ni el publicacion_id."""
    base.frases["f1"].update(piezas={"instagram": "p0"}, publicacion_id="p0")
    piezas, _ = pf.encolar_frase(base.frases["f1"], MAN, _cfg(), db, publicar, canales=["home"])
    assert list(piezas) == ["home"] and base.subidas == []          # la home lleva solo texto: no se compone ni se sube nada
    assert base.frases["f1"]["piezas"] == {"instagram": "p0", "home": piezas["home"]} and base.frases["f1"]["publicacion_id"] == "p0"
    assert base.pubs[piezas["home"]]["imagen_url"] is None


def test_sin_foto_no_se_encola(base, monkeypatch):
    base.config.pop("frase_imagen")
    monkeypatch.setattr(publicar, "buscar_imagenes_banco", lambda cfg, q, n=6: [])
    piezas, aviso = pf.encolar_frase(base.frases["f1"], MAN, _cfg(), db, publicar, canales=["instagram"])
    assert piezas == {} and "no hay foto" in aviso and base.pubs == {}


def test_wordpress_apagado_sale_la_foto_sola(base):
    piezas, aviso = pf.encolar_frase(base.frases["f1"], MAN, _cfg(wordpress="apagado"), db, publicar, canales=["instagram"])
    assert base.pubs[piezas["instagram"]]["imagen_url"] == "https://wp/fondo.jpg" and "sale la foto sin la frase encima" in aviso


# ---------------- frenar y volver a encolar (rutas) ----------------
@pytest.fixture
def rutas(base, monkeypatch):
    base.config["frase_canales"] = ["historia", "mail"]
    monkeypatch.setattr(fr, "_cfg", lambda: (_cfg(), publicar))
    return base


def test_frenar_y_volver_a_encolar(logueado, rutas, monkeypatch):
    base = rutas
    # mañana ya está en la cola por historia y mail
    piezas, _ = pf.encolar_frase(base.frases["f1"], MAN, _cfg(), db, publicar, canales=["historia", "mail"])
    assert base.frases["f1"]["piezas"] == piezas
    # frenar: las dos piezas se cancelan y la frase queda editable (sin piezas)
    r = logueado.post("/frases/manana/frenar")
    assert r.status_code == 200 and r.json()["canceladas"] == 2, r.text
    assert all(base.pubs[p]["estado"] == "cancelada" for p in piezas.values())
    assert base.frases["f1"]["piezas"] is None and base.frases["f1"]["publicacion_id"] is None
    assert logueado.post("/frases/manana/frenar").status_code == 409        # ya no hay nada en la cola
    # volver a encolar: entra por los canales prendidos que falten, con el mismo camino que la cola
    llamadas = []
    monkeypatch.setattr(pf, "encolar_frase", lambda f, d, cfg, _db, pub, hora=None, quien=None, canales=None: llamadas.append((d, quien, canales)) or ({"historia": "n1", "mail": "n2"}, "ok"))
    r = logueado.post("/frases/manana/encolar")
    assert r.status_code == 200 and r.json()["canales"] == ["historia", "mail"], r.text
    assert llamadas == [(MAN, "franco", ["historia", "mail"])]
    # apagada: no se encola
    base.config["frase_activa"] = False
    assert logueado.post("/frases/manana/encolar").status_code == 409


def test_encolar_solo_lo_que_falta_y_frenar_respeta_el_mail_en_curso(logueado, rutas, monkeypatch):
    base = rutas
    piezas, _ = pf.encolar_frase(base.frases["f1"], MAN, _cfg(), db, publicar, canales=["historia", "mail"])
    assert logueado.post("/frases/manana/encolar").status_code == 409        # ya está por todos los canales prendidos
    base.config["frase_canales"] = ["historia", "mail", "home"]
    llamadas = []
    monkeypatch.setattr(pf, "encolar_frase", lambda f, d, cfg, _db, pub, hora=None, quien=None, canales=None: llamadas.append(canales) or ({"home": "n3"}, "ok"))
    assert logueado.post("/frases/manana/encolar").status_code == 200 and llamadas == [["home"]]
    # un mail que ya se está mandando no se frena: queda como pieza viva de la frase
    base.pubs[piezas["mail"]]["estado"] = "enviando"
    r = logueado.post("/frases/manana/frenar")
    assert r.status_code == 200 and r.json()["canceladas"] == 1 and "sigue" in r.json()["mensaje"]
    assert base.frases["f1"]["piezas"] == {"mail": piezas["mail"]} and base.frases["f1"]["publicacion_id"] == piezas["mail"]


# ---------------- el mail en tandas con perfit simulado ----------------
class PerfitFalso:
    def __init__(self, modo="simulado", fallar_en=None):
        self._modo, self.fallar_en, self.disparos = modo, fallar_en, []
    def modo(self): return self._modo
    def configurado(self): return []
    def lista_frase(self): return {"id": 7, "name": "Frases"}
    def contactos_de_lista(self, lista_id, estado="active"): return [{"id": i, "email": f"c{i}@x.org"} for i in range(5)]
    def disparar(self, email, ctx):
        self.disparos.append((email, ctx["frase"]))
        if self.fallar_en and len(self.disparos) == self.fallar_en:
            return {"ok": False, "estado": "limite", "aviso": "Perfit: 429"}
        return {"ok": True, "estado": "enviado", "aviso": "HTTP 200"}


def test_mail_en_tandas(base):
    piezas, _ = pf.encolar_frase(base.frases["f1"], MAN, _cfg(), db, publicar, canales=["mail"])
    p = base.pubs[piezas["mail"]]
    # simulado: la lista de prueba de config, nada se manda
    perfit = PerfitFalso("simulado")
    r = frase_mail.iniciar(p, db, perfit)
    assert r["ok"] and r["estado_cola"] == "enviando" and "3 destinatarios" in r["aviso"]
    assert [e["email"] for e in base.envios] == ["a@x.org", "b@x.org", "c@x.org"]
    p["estado"] = "enviando"
    res = frase_mail.avanzar(db, perfit, max_por_corrida=2)
    assert res[0]["enviados"] == 2 and res[0]["quedan"] == 1 and res[0]["estado"] == "enviando" and perfit.disparos == []
    res = frase_mail.avanzar(db, perfit, max_por_corrida=2)
    assert res[0]["quedan"] == 0 and res[0]["estado"] == "simulada" and base.pubs[piezas["mail"]]["estado"] == "simulada"


def test_mail_real_con_la_lista_de_perfit_y_el_429(base):
    piezas, _ = pf.encolar_frase(base.frases["f1"], MAN, _cfg(), db, publicar, canales=["mail"])
    p = base.pubs[piezas["mail"]]
    perfit = PerfitFalso("real", fallar_en=3)
    r = frase_mail.iniciar(p, db, perfit)
    assert r["ok"] and "5 destinatarios" in r["aviso"] and "lista «Frases» de Perfit" in r["aviso"]
    p["estado"] = "enviando"
    res = frase_mail.avanzar(db, perfit, max_por_corrida=50)
    # el tercer disparo recibe 429: para ahí, los dos primeros quedan enviados y la pieza sigue en envío
    assert res[0]["enviados"] == 2 and res[0]["limite"] is True and res[0]["quedan"] == 3 and base.pubs[piezas["mail"]]["estado"] == "enviando"
    assert [d[1] for d in perfit.disparos] == ["La gratitud es la llave."] * 3
    res = frase_mail.avanzar(db, perfit, max_por_corrida=50)
    assert res[0]["enviados"] == 3 and res[0]["quedan"] == 0 and res[0]["estado"] == "publicada" and base.pubs[piezas["mail"]]["estado"] == "publicada"
    assert base.pubs[piezas["mail"]]["resultado"]["envios"]["enviado"] == 5


# ---------------- procesar_cola.main con los conectores simulados ----------------
def test_procesar_cola_todos_los_canales(base, monkeypatch):
    """Una pieza vencida por cada canal: la cola las toma (procesando), despacha con enviar_pieza y deja el estado que corresponde."""
    llamados = []
    def conector(nombre):
        def fn(cfg, *a, **k):
            llamados.append(nombre)
            return {"ok": True, "modo": cfg.modo(nombre.split("_")[0]) if nombre != "home" else cfg.modo("home")}
        return fn
    for fn in ("publicar_instagram", "publicar_facebook_video", "publicar_wordpress", "publicar_whatsapp", "publicar_frase_home", "publicar_youtube"):
        monkeypatch.setattr(publicar, fn, conector(fn.replace("publicar_", "").replace("frase_", "")))
    monkeypatch.setattr(publicar, "media_id_por_url", lambda cfg, url: 5)
    monkeypatch.setattr(publicar, "bajar_bytes", lambda url, timeout=300: (b"video", None))
    monkeypatch.setitem(sys.modules, "frase_mail", types.SimpleNamespace(iniciar=lambda p, d, pe: {"ok": True, "modo": "real", "estado_cola": "enviando"},
                                                                          avanzar=lambda d, pe: []))
    monkeypatch.setitem(sys.modules, "perfit", types.SimpleNamespace(modo=lambda: "real"))
    monkeypatch.setattr(sys.modules["programar_frases"], "main", lambda a=None: 0)
    monkeypatch.setattr(procesar_cola, "_cargar_config_local", lambda: None)
    monkeypatch.setattr(sys, "argv", ["procesar_cola.py"])
    for c in canales.CANALES.values():
        monkeypatch.setenv(c.variable, "real" if c.clave != "whatsapp" else "simulado")
    monkeypatch.setenv("WP_SITE", "x.org"); monkeypatch.setenv("WP_USER", "u"); monkeypatch.setenv("WP_APP_PASSWORD", "p")
    vencida = "2026-11-03T07:00:00-03:00"
    ids = {}
    ids["instagram"] = db.encolar_publicacion("cola", "instagram", "real", "T", "hola", "https://wp/i.jpg", vencida, extra={"formato": "historia"})
    ids["facebook"] = db.encolar_publicacion("cola", "facebook", "real", "T", "hola", None, vencida, extra={"video_url": "https://wp/v.mp4"})
    ids["wordpress"] = db.encolar_publicacion("cola", "wordpress", "real", "Entrada", "<p>hola</p>", "https://wp/i.jpg", vencida)
    ids["youtube"] = db.encolar_publicacion("cola", "youtube", "real", "Video", "desc", None, vencida, extra={"video_url": "https://wp/v.mp4"})
    ids["home"] = db.encolar_publicacion("cola", "home", "real", "Frase", "hola", None, vencida, extra={"texto_imagen": "La gratitud", "autor": "David"})
    ids["whatsapp"] = db.encolar_publicacion("cola", "whatsapp", "simulado", "Frase", "hola", "https://wp/i.jpg", vencida)
    ids["mail"] = db.encolar_publicacion("cola", "mail", "real", "Frase (mail)", "hola", "https://wp/i.jpg", vencida, extra={"frase_id": "f1"})
    ids["raro"] = db.encolar_publicacion("cola", "telegram", "real", "x", "x", None, vencida)
    assert procesar_cola.main() == 0
    estados = {k: base.pubs[v]["estado"] for k, v in ids.items()}
    assert estados == {"instagram": "publicada", "facebook": "publicada", "wordpress": "publicada", "youtube": "publicada", "home": "publicada",
                       "whatsapp": "simulada", "mail": "enviando", "raro": "pendiente"}
    assert sorted(llamados) == sorted(["instagram", "facebook_video", "wordpress", "youtube", "home", "whatsapp"])
    assert base.pubs[ids["raro"]]["intentos"] == 1 and "desconocido" in base.pubs[ids["raro"]]["resultado"]["ultimo"]["aviso"]
    assert base.pubs[ids["instagram"]]["procesado_en"] and base.pubs[ids["instagram"]]["resultado"]["modo_al_procesar"] == "real"


def test_procesar_cola_reintenta_y_despues_error(base, monkeypatch):
    monkeypatch.setattr(publicar, "publicar_instagram", lambda *a, **k: {"ok": False, "modo": "real", "aviso": "Meta dijo no"})
    monkeypatch.setitem(sys.modules, "frase_mail", types.SimpleNamespace(avanzar=lambda d, pe: []))
    monkeypatch.setitem(sys.modules, "perfit", types.SimpleNamespace())
    monkeypatch.setattr(sys.modules["programar_frases"], "main", lambda a=None: 0)
    monkeypatch.setattr(procesar_cola, "_cargar_config_local", lambda: None)
    monkeypatch.setattr(sys, "argv", ["procesar_cola.py"])
    monkeypatch.setenv("PUBLICAR_INSTAGRAM", "real")
    pid = db.encolar_publicacion("cola", "instagram", "real", "T", "hola", "https://wp/i.jpg", "2026-11-03T07:00:00-03:00")
    for intento in (1, 2):
        procesar_cola.main()
        assert base.pubs[pid]["estado"] == "pendiente" and base.pubs[pid]["intentos"] == intento
    procesar_cola.main()
    assert base.pubs[pid]["estado"] == "error" and base.pubs[pid]["intentos"] == 3 and "Meta dijo no" in base.pubs[pid]["resultado"]["ultimo"]["aviso"]
