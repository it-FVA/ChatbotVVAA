"""(8/11, Franco) metricas_youtube.py con Google simulado (monkeypatch sobre metricas_youtube._http y publicar._yt_access_token).
Sin red, sin claves. Lo que NO se pudo confirmar contra Google real queda dicho en el docstring del módulo."""
import json

import pytest

import metricas_youtube as my

ACCESS = "ya29.ACCESS-SECRETO-YT"
REFRESH = "1//REFRESH-SECRETO-YT"
CLIENT_SECRET = "SECRETO-CLIENTE-YT"
TOKEN_JSON = json.dumps({"client_id": "cid", "client_secret": CLIENT_SECRET, "refresh_token": REFRESH, "scopes": []})


class Cfg:
    yt_token_json = TOKEN_JSON


@pytest.fixture(autouse=True)
def _limpio(monkeypatch):
    my._olvidar_token()
    monkeypatch.setattr(my.publicar, "_yt_access_token", lambda cfg: (ACCESS, None))
    yield
    my._olvidar_token()


def sim(monkeypatch, respuestas):
    visto = []

    def http(url, method="GET", headers=None, data=None):
        visto.append((url, headers))
        for clave, resp in respuestas:
            if clave in url:
                return resp(url) if callable(resp) else resp
        return None, {"error": {"code": 404, "message": "no simulado"}}
    monkeypatch.setattr(my, "_http", http)
    return visto


CANAL = ({"items": [{"snippet": {"title": "Vivir Agradecidos"}, "statistics": {"subscriberCount": "1200", "viewCount": "98000", "videoCount": "55"}}]}, None)
ANALYTICS = ({"columnHeaders": [{"name": n} for n in ("views", "estimatedMinutesWatched", "averageViewDuration", "subscribersGained", "subscribersLost", "likes", "comments", "shares")],
              "rows": [[3100, 9400, 182, 40, 5, 210, 33, 17]]}, None)
SIN_SCOPE = (None, {"error": {"code": 403, "message": "Request had insufficient authentication scopes.",
                              "errors": [{"reason": "insufficientPermissions"}], "status": "PERMISSION_DENIED"}})


def test_canal_con_analytics(monkeypatch):
    visto = sim(monkeypatch, [("/channels", CANAL), ("youtubeanalytics.googleapis.com/v2/reports", ANALYTICS)])
    d = my.insights_canal_youtube(Cfg(), 28)
    assert d["seguidores"] == 1200 and d["vistas"] == 3100                  # las vistas del período pisan las históricas
    assert (d["me_gusta"], d["comentarios"], d["compartidos"], d["seguidores_nuevos"]) == (210, 33, 17, 40)
    assert d["crudo"]["minutos_vistos"] == 9400 and d["crudo"]["duracion_promedio_seg"] == 182 and d["crudo"]["videos_total"] == 55
    assert d["crudo"]["vistas_es_historico"] is False and d["crudo"]["vistas_total_historico"] == 98000
    assert d["errores"] == []
    url_canal = visto[0][0]
    assert "part=statistics%2Csnippet" in url_canal and "mine=true" in url_canal
    url_rep = visto[1][0]
    assert "ids=channel%3D%3DMINE" in url_rep and "startDate=" in url_rep and "endDate=" in url_rep and "subscribersGained" in url_rep


def test_canal_sin_scope_devuelve_la_data_api(monkeypatch):
    sim(monkeypatch, [("/channels", CANAL), ("youtubeanalytics", SIN_SCOPE)])
    d = my.insights_canal_youtube(Cfg())
    assert d["seguidores"] == 1200 and d["vistas"] == 98000                  # lo de la Data API sigue
    assert d["crudo"]["vistas_es_historico"] is True
    assert d["errores"] == [my.TEXTO_SIN_SCOPE] and my.es_error_de_scope(d["errores"][0])
    assert "autorizar_youtube.py" in d["errores"][0] and "Render" in d["errores"][0]
    assert "me_gusta" not in d and "seguidores_nuevos" not in d              # nunca un 0 inventado


def test_canal_analytics_sin_filas_no_inventa(monkeypatch):
    sim(monkeypatch, [("/channels", CANAL), ("youtubeanalytics", ({"columnHeaders": [{"name": "views"}], "rows": []}, None))])
    d = my.insights_canal_youtube(Cfg())
    assert d["vistas"] == 98000 and d["crudo"]["vistas_es_historico"] is True and d["errores"] == []
    assert "sin filas" in d["crudo"]["analytics"]


def test_canal_suscriptores_ocultos(monkeypatch):
    c = ({"items": [{"statistics": {"hiddenSubscriberCount": True, "subscriberCount": "0", "viewCount": "10", "videoCount": "1"}}]}, None)
    sim(monkeypatch, [("/channels", c), ("youtubeanalytics", SIN_SCOPE)])
    assert "seguidores" not in my.insights_canal_youtube(Cfg())


def test_sin_token(monkeypatch):
    class Sin:
        yt_token_json = ""
    d = my.insights_canal_youtube(Sin())
    assert d["errores"] == ["No hay conexión con YouTube configurada."] and d["crudo"] == {}
    assert my.insights_video_youtube(Sin(), "abc")["errores"] == ["No hay conexión con YouTube configurada."]


def test_google_rechaza_renovar_el_token(monkeypatch):
    monkeypatch.setattr(my.publicar, "_yt_access_token", lambda cfg: (None, {"error": "invalid_grant", "error_description": f"Token revocado {REFRESH}"}))
    d = my.insights_canal_youtube(Cfg())
    assert d["errores"][0].startswith("No pude renovar la conexión con YouTube") and "invalid_grant" not in REFRESH
    assert REFRESH not in json.dumps(d)


def test_canal_error_de_google_y_cuota(monkeypatch):
    sim(monkeypatch, [("/channels", (None, {"error": {"code": 403, "message": "quota", "errors": [{"reason": "quotaExceeded"}]}}))])
    d = my.insights_canal_youtube(Cfg())
    assert "cuota diaria" in d["errores"][0] and not my.es_error_de_scope(d["errores"][0])
    sim(monkeypatch, [("/channels", ({"items": []}, None))])
    assert "otra cuenta" in my.insights_canal_youtube(Cfg())["errores"][0]


VIDEO = ({"items": [{"snippet": {"title": "Gratitud", "publishedAt": "2026-10-01T12:00:00Z"},
                     "contentDetails": {"duration": "PT3M20S"}, "status": {"privacyStatus": "private"},
                     "statistics": {"viewCount": "321", "likeCount": "21", "commentCount": "4"}}]}, None)
ANALYTICS_VIDEO = ({"columnHeaders": [{"name": n} for n in ("views", "estimatedMinutesWatched", "averageViewDuration", "averageViewPercentage", "likes", "shares", "subscribersGained")],
                    "rows": [[320, 410, 77, 38.46, 21, 6, 2]]}, None)


def test_video_normal(monkeypatch):
    visto = sim(monkeypatch, [("/videos", VIDEO), ("youtubeanalytics", ANALYTICS_VIDEO)])
    d = my.insights_video_youtube(Cfg(), "abc123")
    assert (d["vistas"], d["me_gusta"], d["comentarios"], d["compartidos"]) == (321, 21, 4, 6)
    assert d["crudo"]["video"] == {"titulo": "Gratitud", "duracion": "PT3M20S", "duracion_seg": 200, "publicado": "2026-10-01T12:00:00Z", "privacidad": "private"}
    assert d["crudo"]["minutos_vistos"] == 410 and d["crudo"]["duracion_promedio_seg"] == 77 and d["crudo"]["porcentaje_visto"] == 38.5
    assert d["errores"] == []
    assert "id=abc123" in visto[0][0] and "contentDetails" in visto[0][0]
    assert "filters=video%3D%3Dabc123" in visto[1][0] and "startDate=2026-10-01" in visto[1][0]


def test_video_sin_scope_y_sin_analytics(monkeypatch):
    visto = sim(monkeypatch, [("/videos", VIDEO), ("youtubeanalytics", SIN_SCOPE)])
    d = my.insights_video_youtube(Cfg(), "abc123")
    assert d["vistas"] == 321 and "compartidos" not in d and d["errores"] == [my.TEXTO_SIN_SCOPE]
    n = len(visto)
    d = my.insights_video_youtube(Cfg(), "abc123", analytics=False)
    assert len(visto) == n + 1 and d["errores"] == [] and d["vistas"] == 321      # solo la Data API


def test_video_que_no_existe(monkeypatch):
    sim(monkeypatch, [("/videos", ({"items": []}, None))])
    d = my.insights_video_youtube(Cfg(), "zzz")
    assert d["errores"] == [my.TEXTO_VIDEO_NO_EXISTE] and "vistas" not in d
    assert my.insights_video_youtube(Cfg(), "")["errores"] == ["La pieza no tiene el id de YouTube."]
    sim(monkeypatch, [("/videos", (None, {"error": {"code": 500, "message": "backend"}}))])
    assert my.insights_video_youtube(Cfg(), "zzz")["errores"][0].startswith("YouTube no dio los datos del video")


def test_el_token_no_se_filtra(monkeypatch):
    mensaje = f"bad {ACCESS} {REFRESH} {CLIENT_SECRET}"
    visto = sim(monkeypatch, [("/channels", (None, {"error": {"code": 400, "message": mensaje}})),
                              ("/videos", (None, {"error": {"code": 400, "message": mensaje}}))])
    for d in (my.insights_canal_youtube(Cfg()), my.insights_video_youtube(Cfg(), "x")):
        texto = json.dumps(d)
        assert ACCESS not in texto and REFRESH not in texto and CLIENT_SECRET not in texto
    # y el access token viaja en el encabezado, no en la URL
    assert all(ACCESS not in url for url, _h in visto) and visto[0][1]["Authorization"] == f"Bearer {ACCESS}"
    sim(monkeypatch, [("/channels", CANAL), ("youtubeanalytics", ANALYTICS)])
    assert ACCESS not in json.dumps(my.insights_canal_youtube(Cfg()))


def test_el_access_token_se_reutiliza(monkeypatch):
    llamadas = []
    monkeypatch.setattr(my.publicar, "_yt_access_token", lambda cfg: llamadas.append(1) or (ACCESS, None))
    sim(monkeypatch, [("/videos", VIDEO), ("youtubeanalytics", ANALYTICS_VIDEO)])
    my.insights_video_youtube(Cfg(), "a")
    my.insights_video_youtube(Cfg(), "b")
    assert len(llamadas) == 1


def test_duracion():
    assert my._duracion_seg("PT1H2M30S") == 3750 and my._duracion_seg("PT45S") == 45 and my._duracion_seg("") is None
