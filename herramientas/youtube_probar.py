"""Prueba de YouTube (12/11): ¿Google respeta la privacidad que pedimos por API o fuerza «privado»?

Google cerró la revisión de cumplimiento el 12/11 diciendo que «los videos subidos por la API no se marcan privados automáticamente»
(nuestra nota del 16/10 venía de terceros desactualizados). Este script sube un recorte corto que ya está en WordPress como
«no listado» (no aparece en el canal ni en búsquedas; solo con el link) y muestra qué privacidad devolvió YouTube.

Correr desde ChatbotVVAA:  python herramientas/youtube_probar.py
Lee YOUTUBE_TOKEN_JSON del secrets.toml local (secretos.ruta()). No imprime el token.
Después: borrar el video desde YouTube Studio (la API no puede borrarlo con los permisos que tenemos).
"""
import json, sys, os, tomllib, urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import secretos, publicar   # noqa: E402

CLIP = "https://viviragradecidos.org/wp-content/uploads/2026/10/clip-064nr8Yy6M-58-106-vertical.mp4"   # 47 s, ya público en el sitio


class _Cfg:
    def __init__(self, tok):
        self.yt_token_json = json.dumps(tok)


def main():
    tok = json.loads(tomllib.load(open(secretos.ruta(), "rb"))["YOUTUBE_TOKEN_JSON"])
    acc, err = publicar._yt_access_token(_Cfg(tok))
    if not acc:
        print("No pude renovar el permiso de YouTube:", err)
        return 1
    video = urllib.request.urlopen(CLIP, timeout=120).read()
    print(f"clip bajado: {len(video) // 1024} KB")
    meta = {"snippet": {"title": "Prueba técnica de la plataforma (borrar)",
                        "description": "Prueba del 12/11: verificar que YouTube respeta la privacidad pedida por la API. Borrar.",
                        "categoryId": "22"},
            "status": {"privacyStatus": "unlisted", "selfDeclaredMadeForKids": False}}
    req = urllib.request.Request(publicar.YT_UPLOAD_URL, data=json.dumps(meta).encode("utf-8"), method="POST", headers={
        "Authorization": "Bearer " + acc, "Content-Type": "application/json; charset=UTF-8",
        "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(len(video))})
    with urllib.request.urlopen(req, timeout=60) as r:
        up = r.headers.get("Location")
    req2 = urllib.request.Request(up, data=video, method="PUT", headers={"Content-Type": "video/mp4", "Content-Length": str(len(video))})
    with urllib.request.urlopen(req2, timeout=900) as r:
        res = json.load(r)
    st = res.get("status") or {}
    print("id:", res.get("id"), "| link: https://www.youtube.com/watch?v=" + str(res.get("id")))
    print("privacidad pedida: unlisted | privacidad devuelta:", st.get("privacyStatus"), "| estado de subida:", st.get("uploadStatus"))
    print("Si dice «unlisted», YouTube respeta lo que pedimos y se puede pasar PUBLICAR_YOUTUBE a real. Borrá el video desde YouTube Studio.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
