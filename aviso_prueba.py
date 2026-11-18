"""
aviso_prueba.py — Manda a Slack un aviso de prueba con el texto real de avisos.py, para ver cómo se lee (18/11, pedido de Franco).
Solo Slack (SLACK_WEBHOOK_URL); nunca mail, nunca toca la base. El título dice «PRUEBA» para que nadie lo tome en serio.

Uso:  python aviso_prueba.py [cual]      cual = fallo (default) | publicada | frases | token | mail | todos
En local no hay webhook: corre en GitHub Actions con el botón «Run workflow» de .github/workflows/aviso_prueba.yml
(o `gh workflow run aviso_prueba.yml -f cual=todos`).
"""
import datetime
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


class _SinUsuarios:
    def listar_usuarios(self):
        return []


def main(cual="fallo"):
    for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASS"):      # por las dudas: solo Slack
        os.environ.pop(k, None)
    import avisos
    if not avisos.configurado()["slack"]:
        print("Sin SLACK_WEBHOOK_URL: no hay a dónde mandar. En GitHub: Actions → aviso-de-prueba → Run workflow.")
        return 1
    db = _SinUsuarios()
    pieza = {"usuario": "franco", "canal": "instagram", "titulo": "PRUEBA del aviso (ignorar)", "fecha_programada": "2026-11-18T18:00:00-03:00"}
    que = {
        "fallo": lambda: avisos.pieza_fallo(db, pieza, "prueba: Meta respondió 400 (ejemplo)", 3, definitivo=True, sincrono=True),
        "publicada": lambda: avisos.pieza_publicada(db, pieza, {"permalink": "https://www.instagram.com/vivir.agradecidos/"}, sincrono=True),
        "frases": lambda: avisos.frases_pocas(3, "2026-11-21"),
        "token": lambda: avisos.token_ig_por_vencer(9, datetime.datetime(2026, 11, 27, tzinfo=datetime.timezone.utc)),
        "mail": lambda: avisos.frase_mail_terminado(dict(pieza, resultado={"frase_del_dia": "2026-11-18", "ultimo": "tanda: 50 enviados, 2 errores"}),
                                                    {"enviado": 2200, "error": 3, "pendiente": 0, "total": 2203}),
    }
    nombres = list(que) if cual == "todos" else [cual]
    for n in nombres:
        if n not in que:
            print(f"no conozco «{n}»; opciones: {', '.join(que)}, todos")
            return 1
        print(f"{n}: {que[n]()}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "fallo"))
