"""avisos.py (2/11): sin configuración no hace nada; con Slack arma el mensaje y lo manda; con mail usa SMTP. Todo mockeado."""
import json
import avisos


class _DB:
    def listar_usuarios(self):
        return [{"usuario": "julian", "email": "j@x.org", "rol": "aprobador", "activo": True},
                {"usuario": "beto", "email": "b@x.org", "rol": "admin", "activo": True},
                {"usuario": "lizzie", "email": "l@x.org", "rol": "creador", "activo": True},
                {"usuario": "viejo", "email": "v@x.org", "rol": "aprobador", "activo": False}]


def test_sin_config_no_hace_nada(monkeypatch):
    for k in ("SLACK_WEBHOOK_URL", "SMTP_HOST", "SMTP_USER", "SMTP_PASS"):
        monkeypatch.delenv(k, raising=False)
    assert avisos.pieza_a_aprobar(_DB(), "p1", "lizzie", "instagram", "Hola", "texto", sincrono=True) is None
    assert avisos.configurado() == {"slack": False, "mail": False}


def test_slack_a_aprobadores(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.test/abc")
    monkeypatch.delenv("SMTP_HOST", raising=False)
    mandados = []
    monkeypatch.setattr(avisos, "_slack", lambda texto: mandados.append(texto) or True)
    r = avisos.pieza_a_aprobar(_DB(), "p1", "lizzie", "instagram", "Lo común nos convoca", "texto", formato="vertical", sincrono=True)
    assert r["slack"] is True and r["mail"] is None
    assert "Instagram · vertical" in mandados[0] and "lizzie" in mandados[0] and "/aprobacion" in mandados[0]


def test_mail_a_quien_la_hizo(monkeypatch):
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    monkeypatch.setenv("SMTP_HOST", "smtp.test"); monkeypatch.setenv("SMTP_USER", "u"); monkeypatch.setenv("SMTP_PASS", "p")
    mandados = []
    monkeypatch.setattr(avisos, "_mail", lambda dest, asunto, texto: mandados.append((dest, asunto, texto)) or True)
    r = avisos.pieza_resuelta(_DB(), {"usuario": "lizzie", "canal": "facebook", "titulo": "Prueba"}, "rechazada", "julian", nota="falta la foto", sincrono=True)
    assert r["mail"] is True
    dest, asunto, texto = mandados[0]
    assert dest == ["l@x.org"] and "rechazada" in asunto and "falta la foto" in texto
    # los aprobadores: solo activos con rol aprobador/admin
    assert avisos._emails_aprobadores(_DB()) == ["b@x.org", "j@x.org"]


def test_un_error_no_rompe(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.test/abc")
    def rompe(texto):
        raise RuntimeError("sin red")
    monkeypatch.setattr(avisos, "_slack", rompe)
    r = avisos.pieza_a_aprobar(_DB(), "p1", "lizzie", "wordpress", "T", "x", sincrono=True)
    assert r["slack"] is False
    assert json.dumps(r)   # serializable


def test_pieza_cancelada_avisa_a_quien_la_hizo(monkeypatch):
    """(18/11, Franco) Alguien bajó de la cola una pieza aprobada: aviso a quien la hizo, por Slack y mail, como al aprobar o rechazar."""
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.test/abc")
    monkeypatch.setenv("SMTP_HOST", "smtp.test"); monkeypatch.setenv("SMTP_USER", "u"); monkeypatch.setenv("SMTP_PASS", "p")
    slack, mails = [], []
    monkeypatch.setattr(avisos, "_slack", lambda texto: slack.append(texto) or True)
    monkeypatch.setattr(avisos, "_mail", lambda dest, asunto, texto: mails.append((dest, asunto, texto)) or True)
    pieza = {"usuario": "lizzie", "canal": "instagram", "titulo": "", "texto": "Tres momentos para agradecer", "fecha_programada": "2026-11-18T10:42:00-03:00"}
    r = avisos.pieza_cancelada(_DB(), pieza, "franco", sincrono=True)
    assert r == {"slack": True, "mail": True}
    assert "Pieza cancelada: Instagram — lizzie" in slack[0] and "La canceló franco." in slack[0] and "Iba a salir el 2026-11-18 10:42." in slack[0]
    assert mails[0][0] == ["l@x.org"] and mails[0][1] == "Pieza cancelada: Instagram — lizzie" and "Tres momentos" in mails[0][2]
