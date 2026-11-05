"""Banco de imágenes (5/11): sincronización Drive → WordPress con un Drive simulado, deducción de etiquetas y formato, búsqueda
con la marca `banco-fva`, la ruta de fotos con `banco_solo` y las rutas de administración. Nada toca Drive, WordPress ni Supabase."""
import pytest

import banco
import db
import publicar


# ---------------- Drive simulado: carpetas anidadas ----------------
CARPETA = "application/vnd.google-apps.folder"


class DriveSimulado:
    """files().list(q="'<id>' in parents …", pageToken) con paginación de 2 en 2; files().get_media(...).execute() → bytes."""

    def __init__(self, arbol, pagina=2):
        self.arbol, self.pagina, self.bajados = arbol, pagina, []

    def files(self):
        return self

    def list(self, q="", pageToken=None, **kw):
        padre = q.split("'")[1]
        permitidos = {CARPETA, "image/jpeg", "image/png", "image/webp"}      # lo que pide la consulta de banco.listar_imagenes
        hijos = [f for f in self.arbol.get(padre, []) if f["mimeType"] in permitidos]
        ini = int(pageToken or 0)
        resto = hijos[ini:ini + self.pagina]
        r = {"files": resto}
        if ini + self.pagina < len(hijos):
            r["nextPageToken"] = str(ini + self.pagina)
        return type("R", (), {"execute": lambda s: r})()

    def get_media(self, fileId, **kw):
        self.bajados.append(fileId)
        return type("R", (), {"execute": lambda s: b"\xff\xd8jpeg"})()


def _img(i, nombre, mod="2026-11-01T10:00:00.000Z", mime="image/jpeg"):
    return {"id": i, "name": nombre, "mimeType": mime, "modifiedTime": mod}


def _carpeta(i, nombre):
    return {"id": i, "name": nombre, "mimeType": CARPETA}


@pytest.fixture
def drive():
    return DriveSimulado({
        "RAIZ": [_img("a1", "flor_mano_1080x1080.jpg"), _carpeta("c1", "Vertical"), _carpeta("c2", "Brother David"),
                 _img("a2", "notas.txt", mime="text/plain-no-listada")],
        "c1": [_img("b1", "amanecer_montaña_1080x1920.jpg"), _img("b2", "mar-calma.PNG", mime="image/png"), _carpeta("c3", "Día de la madre")],
        "c3": [_img("d1", "abrazo_abuela.webp", mime="image/webp")],
        "c2": [_img("e1", "circulo_brother_1920x1080.jpg")],
    })


class Cfg:
    modo_wp = "real"
    wp_site = "ejemplo.org"
    wp_user = "u"
    wp_pass = "p"


@pytest.fixture
def mundo(monkeypatch):
    est = {"subidas": [], "guardadas": [], "siguiente": 100, "falla": set()}

    def subir(cfg, ruta, nombre, titulo="", etiquetas=None, quien="", pieza="", banco=False):
        assert banco is True
        if nombre in est["falla"]:
            return {"ok": False, "modo": "real", "aviso": "WordPress no aceptó la imagen"}
        est["siguiente"] += 1
        est["subidas"].append({"nombre": nombre, "titulo": titulo, "etiquetas": etiquetas, "ruta_existia": True})
        return {"ok": True, "modo": "real", "id": est["siguiente"], "url": f"https://ejemplo.org/{est['siguiente']}.jpg"}

    monkeypatch.setattr(publicar, "subir_imagen_wordpress", subir)
    return est


def sincronizar(drive, mundo, registro=None, **kw):
    registro = {} if registro is None else registro
    guardar = lambda *a: mundo["guardadas"].append(a)
    return banco.sincronizar_banco(Cfg(), drive, "RAIZ", registro, guardar=guardar, **kw), registro


# ---------------- deducción de etiquetas y formato ----------------
@pytest.mark.parametrize("nombre,carpetas,etiquetas,formato", [
    ("flor_mano_1080x1080.jpg", [], ["flor", "mano"], "cuadrado"),
    ("amanecer_montaña_1080x1920.jpg", ["Vertical"], ["amanecer", "montaña"], "vertical"),
    ("circulo-brother_1920x1080.jpg", ["Brother David"], ["brother", "david", "circulo"], "horizontal"),
    ("abrazo_abuela.webp", ["Vertical", "Día de la madre"], ["día", "madre", "abrazo", "abuela"], "vertical"),   # sin medidas: lo dice la carpeta
    ("mar de calma 3.jpg", [], ["mar", "calma"], None),                                                   # sin medidas ni carpeta: sin formato
    ("foto_final_copia_sol.jpg", ["Horizontal"], ["sol"], "horizontal"),
])
def test_deducir(nombre, carpetas, etiquetas, formato):
    assert banco.deducir(nombre, carpetas) == (etiquetas, formato)


def test_medidas_ganan_a_la_carpeta():
    assert banco.deducir("sol_1080x1080.jpg", ["Vertical"])[1] == "cuadrado"


@pytest.mark.parametrize("valor,id_", [
    ("https://drive.google.com/drive/folders/1AbC_dEf-123456789?usp=sharing", "1AbC_dEf-123456789"),
    ("https://drive.google.com/drive/u/0/folders/1AbC_dEf-123456789", "1AbC_dEf-123456789"),
    ("https://drive.google.com/open?id=1AbC_dEf-123456789", "1AbC_dEf-123456789"),
    ("  1AbC_dEf-123456789  ", "1AbC_dEf-123456789"),
    ("", None), ("hola mundo", None), ("https://ejemplo.org/algo", None), (None, None),
])
def test_extraer_carpeta_id(valor, id_):
    assert banco.extraer_carpeta_id(valor) == id_


# ---------------- sincronización ----------------
def test_recorre_carpetas_anidadas_y_sube_con_etiquetas(drive, mundo):
    r, registro = sincronizar(drive, mundo)
    assert (r["subidas"], r["salteadas"], r["errores"]) == (5, 0, 0)            # el .txt ni se lista (mimeType)
    por_nombre = {s["nombre"]: s for s in mundo["subidas"]}
    assert por_nombre["flor_mano_1080x1080.jpg"]["titulo"] == "flor mano"
    assert por_nombre["flor_mano_1080x1080.jpg"]["etiquetas"] == ["flor", "mano", "cuadrado"]
    assert por_nombre["abrazo_abuela.webp"]["etiquetas"] == ["día", "madre", "abrazo", "abuela", "vertical"]
    assert por_nombre["circulo_brother_1920x1080.jpg"]["etiquetas"][-1] == "horizontal"
    # registro: en memoria y en la tabla (guardar)
    assert set(registro) == {"a1", "b1", "b2", "d1", "e1"} and registro["b1"]["modified_time"] == "2026-11-01T10:00:00.000Z"
    guardada = next(g for g in mundo["guardadas"] if g[0] == "b1")
    assert guardada[1] == "amanecer_montaña_1080x1920.jpg" and guardada[3] > 100 and guardada[5] == "vertical" and guardada[6] == ["amanecer", "montaña"]
    assert sorted(drive.bajados) == ["a1", "b1", "b2", "d1", "e1"]


def test_no_resube_lo_registrado(drive, mundo):
    sincronizar(drive, mundo)
    mundo["subidas"].clear()
    drive.bajados.clear()
    r, _ = sincronizar(drive, mundo, registro={i: {"modified_time": "2026-11-01T10:00:00.000Z"} for i in ("a1", "b1", "b2", "d1", "e1")})
    assert (r["subidas"], r["salteadas"]) == (0, 5) and mundo["subidas"] == [] and drive.bajados == []


def test_resube_si_cambio_modified_time(drive, mundo):
    registro = {i: {"modified_time": "2026-11-01T10:00:00.000Z"} for i in ("a1", "b1", "b2", "d1", "e1")}
    drive.arbol["c2"][0]["modifiedTime"] = "2026-11-04T09:00:00.000Z"
    r, registro = sincronizar(drive, mundo, registro=registro)
    assert (r["subidas"], r["salteadas"]) == (1, 4)
    assert [s["nombre"] for s in mundo["subidas"]] == ["circulo_brother_1920x1080.jpg"]
    assert registro["e1"]["modified_time"] == "2026-11-04T09:00:00.000Z"


def test_tope_por_corrida(mundo):
    drive = DriveSimulado({"RAIZ": [_img(f"i{n}", f"foto{n}_1080x1080.jpg") for n in range(45)]}, pagina=20)
    r, registro = sincronizar(drive, mundo)
    assert (r["subidas"], r["pendientes"]) == (30, 15) and banco.TOPE_CORRIDA == 30 and len(registro) == 30
    r2, _ = sincronizar(drive, mundo, registro=registro)                          # la siguiente corrida sigue con el resto
    assert (r2["subidas"], r2["salteadas"], r2["pendientes"]) == (15, 30, 0)


def test_error_de_una_no_frena_las_demas(drive, mundo):
    mundo["falla"].add("amanecer_montaña_1080x1920.jpg")
    r, registro = sincronizar(drive, mundo)
    assert (r["subidas"], r["errores"]) == (4, 1) and "b1" not in registro
    assert "amanecer_montaña_1080x1920.jpg" in r["detalle"][0]


def test_error_al_bajar_o_al_guardar_tampoco_frena(drive, mundo):
    def descargar(svc, fid, destino):
        if fid == "a1":
            raise OSError("se cortó")
        open(destino, "wb").write(b"x")
    def guardar(drive_id, *a):
        if drive_id == "e1":
            raise RuntimeError("Supabase caído")
    r = banco.sincronizar_banco(Cfg(), drive, "RAIZ", {}, descargar=descargar, guardar=guardar)
    assert (r["subidas"], r["errores"]) == (3, 2)


def test_simulado_no_registra(drive, monkeypatch, mundo):
    monkeypatch.setattr(publicar, "subir_imagen_wordpress", lambda *a, **k: {"ok": True, "modo": "simulado", "id": None, "url": None})
    r, registro = sincronizar(drive, mundo)
    assert (r["subidas"], r["simuladas"], r["errores"]) == (0, 5, 0) and registro == {} and mundo["guardadas"] == []


def test_wordpress_apagado_no_baja_nada(drive, mundo):
    class Apagado(Cfg):
        modo_wp = "apagado"
    r = banco.sincronizar_banco(Apagado(), drive, "RAIZ", {}, guardar=lambda *a: None)
    assert r["subidas"] == 0 and drive.bajados == [] and r["detalle"]


# ---------------- la marca en la descripción ----------------
def test_subir_imagen_con_banco_agrega_la_marca(monkeypatch):
    enviados = []

    class Cfg2(Cfg):
        pass

    def http(url, metodo="GET", headers=None, datos=None, **kw):
        enviados.append((metodo, url, datos))
        return ({"id": 7, "source_url": "https://ejemplo.org/7.jpg"}, None)

    monkeypatch.setattr(publicar, "_http", http)
    monkeypatch.setattr(publicar, "_registrar", lambda x: None)
    monkeypatch.setattr(publicar, "_wp_headers", lambda cfg, extra=None: dict(extra or {}))
    res = publicar.subir_imagen_wordpress(Cfg2(), b"abc", "sol.jpg", titulo="sol", etiquetas=["sol", "cuadrado"], banco=True)
    assert res["ok"] and res["id"] == 7
    import json
    meta = json.loads(enviados[1][2])
    assert "banco-fva" in meta["description"] and "cuadrado" in meta["description"]
    # sin banco=True (las llamadas de siempre) no lleva la marca
    enviados.clear()
    publicar.subir_imagen_wordpress(Cfg2(), b"abc", "sol.jpg", titulo="sol", etiquetas=["sol"])
    assert "banco-fva" not in json.loads(enviados[1][2])["description"]


# ---------------- búsqueda ----------------
@pytest.fixture
def busquedas(monkeypatch):
    llamadas = []

    def http(url, headers=None, **kw):
        import urllib.parse
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("search", [""])[0]
        llamadas.append(q)
        if q == "amanecer banco-fva cuadrado" or q == "banco-fva":
            return ([{"id": 1, "source_url": "https://e/1.jpg", "title": {"rendered": "amanecer"}}], None)
        return ([], None)

    monkeypatch.setattr(publicar, "_http", http)
    return llamadas


def test_busqueda_solo_banco_agrega_marca_y_formato(busquedas):
    r = publicar.buscar_imagenes_banco(Cfg(), "amanecer", n=3, solo_banco=True, formato="cuadrado")
    assert busquedas == ["amanecer banco-fva cuadrado"] and r[0]["id"] == 1


def test_busqueda_solo_banco_palabra_por_palabra_siempre_con_marca(busquedas):
    publicar.buscar_imagenes_banco(Cfg(), "mar calma", solo_banco=True)
    assert busquedas == ["mar calma banco-fva", "mar banco-fva", "calma banco-fva"]


def test_busqueda_solo_banco_sin_consulta_es_la_marca_sola(busquedas):
    assert publicar.buscar_imagenes_banco(Cfg(), "", solo_banco=True)[0]["id"] == 1
    assert busquedas == ["banco-fva"]


def test_busqueda_de_siempre_no_cambia(busquedas):
    publicar.buscar_imagenes_banco(Cfg(), "mar calma")
    assert busquedas == ["mar calma", "mar", "calma"]


# ---------------- la ruta de fotos ----------------
@pytest.fixture
def ruta_fotos(monkeypatch):
    estado = {"config": {}, "llamadas": []}
    monkeypatch.setattr(db, "obtener_config", lambda clave, defecto=None: estado["config"].get(clave, defecto))

    def buscar(cfg, consulta, n=6, solo_banco=False, formato=None):
        estado["llamadas"].append((consulta, solo_banco, formato))
        if solo_banco:
            return [{"id": 9, "url": "u", "miniatura": "m", "titulo": "del banco"}] if consulta in ("", "amanecer") else []
        return [{"id": 5, "url": "u", "miniatura": "m", "titulo": "cuadrado de la biblioteca"}]

    monkeypatch.setattr(publicar, "buscar_imagenes_banco", buscar)
    monkeypatch.setattr(publicar, "imagenes_recientes_banco", lambda cfg, n=6: [{"id": 6, "url": "u", "miniatura": "m", "titulo": "reciente"}])
    return estado


def test_ruta_de_fotos_sin_banco_solo_es_como_siempre(logueado, ruta_fotos):
    r = logueado.get("/banco?consulta=amanecer&formato=cuadrado").json()
    assert [f["id"] for f in r] == [5] and r[0]["fuente"] == "biblioteca"
    assert all(solo is False for _, solo, _ in ruta_fotos["llamadas"])


def test_ruta_de_fotos_respeta_banco_solo(logueado, ruta_fotos):
    ruta_fotos["config"]["banco_solo"] = True
    r = logueado.get("/banco?consulta=amanecer&formato=cuadrado").json()
    assert [f["id"] for f in r] == [9] and r[0]["fuente"] == "banco"
    assert ruta_fotos["llamadas"] == [("amanecer", True, "cuadrado")]


def test_banco_solo_sin_resultados_devuelve_las_ultimas_del_banco(logueado, ruta_fotos):
    ruta_fotos["config"]["banco_solo"] = True
    r = logueado.get("/banco?consulta=nada+que+ver&formato=historia").json()
    assert [f["id"] for f in r] == [9] and r[0]["fuente"] == "banco"                  # nunca la biblioteca entera
    assert ruta_fotos["llamadas"] == [("nada que ver", True, "vertical"), ("", True, "vertical")]   # historia → vertical


def test_banco_solo_banco_vacio_no_cae_a_la_biblioteca(logueado, ruta_fotos, monkeypatch):
    ruta_fotos["config"]["banco_solo"] = True
    monkeypatch.setattr(publicar, "buscar_imagenes_banco", lambda *a, **k: [])
    assert logueado.get("/banco?consulta=x").json() == []


# ---------------- administración ----------------
@pytest.fixture
def admin(monkeypatch):
    est = {"config": {}, "cambios": []}
    monkeypatch.setattr(db, "disponible", lambda: True)
    monkeypatch.setattr(db, "obtener_config", lambda clave, defecto=None: est["config"].get(clave, defecto))
    monkeypatch.setattr(db, "guardar_config", lambda clave, valor, usuario=None: est["config"].__setitem__(clave, valor))
    monkeypatch.setattr(db, "registrar_cambio_usuario", lambda *a, **k: None)
    monkeypatch.setattr(db, "banco_resumen", lambda: {"total": 3, "por_formato": {"cuadrado": 2, "vertical": 1}, "ultima": "2026-11-05T12:00:00+00:00"})
    return est


def test_config_banco_extrae_el_id_de_la_url(logueado, admin):
    r = logueado.put("/admin/config", json={"cambios": {"banco_drive_carpeta": "https://drive.google.com/drive/folders/1AbC_dEf-123456789?usp=sharing", "banco_solo": True}})
    assert r.status_code == 200, r.text
    assert admin["config"] == {"banco_drive_carpeta": "1AbC_dEf-123456789", "banco_solo": True}
    assert logueado.put("/admin/config", json={"cambios": {"banco_drive_carpeta": ""}}).status_code == 200


@pytest.mark.parametrize("cambios", [{"banco_drive_carpeta": "no es un link"}, {"banco_drive_carpeta": 5}, {"banco_solo": "si"}])
def test_config_banco_rechaza_lo_invalido(logueado, admin, cambios):
    assert logueado.put("/admin/config", json={"cambios": cambios}).status_code == 400 and admin["config"] == {}


def test_get_admin_banco(logueado, admin):
    admin["config"].update(banco_drive_carpeta="1AbC_dEf-123456789", banco_solo=True)
    d = logueado.get("/admin/banco").json()
    assert d == {"total": 3, "por_formato": {"cuadrado": 2, "vertical": 1}, "ultima_sincronizacion": "2026-11-05T12:00:00+00:00",
                 "carpeta_configurada": True, "solo_banco": True}


def test_post_sincronizar(logueado, admin, monkeypatch):
    monkeypatch.setattr(banco, "sincronizar_desde_config", lambda cfg, svc=None: {"subidas": 2, "salteadas": 1, "errores": 0, "pendientes": 0, "simuladas": 0, "detalle": []})
    assert logueado.post("/admin/banco/sincronizar").json()["subidas"] == 2
    monkeypatch.setattr(banco, "sincronizar_desde_config", lambda cfg, svc=None: None)
    r = logueado.post("/admin/banco/sincronizar")
    assert r.status_code == 400 and "Configuración" in r.json()["detail"]


def test_banco_solo_admins(cliente):
    assert cliente.get("/admin/banco").status_code in (401, 403)
    assert cliente.post("/admin/banco/sincronizar").status_code in (401, 403)


# ---------------- la cola ----------------
def test_la_cola_sincroniza_y_nunca_se_rompe(monkeypatch, capsys):
    import sys, procesar_cola
    monkeypatch.setattr(procesar_cola, "_cargar_config_local", lambda: None)
    monkeypatch.setattr(sys, "argv", ["procesar_cola.py"])
    monkeypatch.setattr(db, "disponible", lambda: True)
    monkeypatch.setattr(db, "vaciar_papelera_vencida", lambda: 0)
    monkeypatch.setattr(db, "liberar_procesando_viejas", lambda minutos=30: [])
    monkeypatch.setattr(db, "listar_pendientes", lambda vencidas=False, limite=50: [])
    monkeypatch.setitem(sys.modules, "programar_frases", type("M", (), {"main": staticmethod(lambda a: None)}))
    monkeypatch.setitem(sys.modules, "frase_mail", type("M", (), {"avanzar": staticmethod(lambda d, p: [])}))
    monkeypatch.setitem(sys.modules, "perfit", type("M", (), {}))
    monkeypatch.setitem(sys.modules, "meta_token", type("M", (), {"renovar_token_ig": staticmethod(lambda: None)}))
    monkeypatch.setattr(banco, "sincronizar_desde_config", lambda cfg, svc=None: {"subidas": 3, "salteadas": 1, "errores": 0, "pendientes": 2, "simuladas": 0, "detalle": []})
    assert procesar_cola.main() == 0
    assert "banco de imágenes: 3 subidas, 1 ya estaban, 0 con error, 2 quedan para la próxima" in capsys.readouterr().out

    def roto(cfg, svc=None):
        raise RuntimeError("Drive no responde")
    monkeypatch.setattr(banco, "sincronizar_desde_config", roto)
    assert procesar_cola.main() == 0
    assert "no pude sincronizar" in capsys.readouterr().out
