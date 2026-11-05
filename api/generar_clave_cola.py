"""(3/11, revisión 5.3 punto 21) Genera la clave acotada de la cola: un JWT (HS256) con role = «cola», firmado con el JWT Secret de
Supabase. El rol «cola» lo crea api/migraciones/manual_cola_rol.sql.

Uso (el secreto va SOLO en una variable de entorno de tu terminal, nunca en un archivo del repo):
    PowerShell:  $env:SUPABASE_JWT_SECRET = "..."; python api/generar_clave_cola.py
    bash:        SUPABASE_JWT_SECRET=... python api/generar_clave_cola.py
Imprime la clave una vez y no la guarda. Vence a los 5 años (--anios N para cambiarlo). Cargarla en GitHub → Settings → Secrets and
variables → Actions como SUPABASE_KEY_COLA (pasos completos en el encabezado de manual_cola_rol.sql).
"""
import base64, hashlib, hmac, json, os, sys, time


def _b64(datos: bytes) -> str:
    return base64.urlsafe_b64encode(datos).rstrip(b"=").decode("ascii")


def generar(secreto: str, rol: str = "cola", anios: int = 5, ahora=None) -> str:
    """El JWT firmado. `ahora` (segundos) solo lo usan las pruebas."""
    t = int(ahora if ahora is not None else time.time())
    cabecera = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    cuerpo = _b64(json.dumps({"role": rol, "iss": "supabase", "iat": t, "exp": t + int(anios * 365 * 24 * 3600)}, separators=(",", ":")).encode())
    firma = hmac.new(secreto.encode("utf-8"), f"{cabecera}.{cuerpo}".encode("ascii"), hashlib.sha256).digest()
    return f"{cabecera}.{cuerpo}.{_b64(firma)}"


def probar(clave, url):
    """(5/11) Prueba la clave contra la base: config tiene que responder 200 y usuarios 401/403. Devuelve (ok, detalle)."""
    import urllib.request, urllib.error
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from db._cliente import ANON_KEY     # el gateway exige una apikey conocida; el rol cola va solo en Bearer (5/11)
    def pedir(tabla):
        req = urllib.request.Request(f"{url.rstrip('/')}/rest/v1/{tabla}?select=*&limit=1",
                                     headers={"apikey": os.environ.get("SUPABASE_ANON_KEY", "").strip() or ANON_KEY,
                                              "Authorization": f"Bearer {clave}"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.status, ""
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace")[:160]
        except Exception as e:
            return f"error: {e}", ""
    (c, cm), (u, um) = pedir("config"), pedir("usuarios")
    ok = c == 200 and u in (401, 403)
    return ok, f"config → {c} (esperado 200){' ' + cm if not ok and cm else ''}, usuarios → {u} (esperado 401 o 403)"


def main(argv):
    secreto = os.environ.get("SUPABASE_JWT_SECRET", "").strip()
    if not secreto and sys.stdin.isatty():
        # (5/11) Más cómodo para Franco: lo pide por teclado sin mostrarlo (Supabase → Project Settings → JWT Keys →
        # solapa «Legacy JWT Secret» → Reveal → copiar).
        import getpass
        secreto = getpass.getpass("Pegá el Legacy JWT Secret de Supabase (no se muestra) y Enter: ").strip()
    if not secreto:
        print("Falta SUPABASE_JWT_SECRET en el entorno (Supabase → Project Settings → JWT Keys → Legacy JWT Secret).", file=sys.stderr)
        return 1
    anios = int(argv[argv.index("--anios") + 1]) if "--anios" in argv else 5
    clave = generar(secreto, anios=anios)
    url = os.environ.get("SUPABASE_URL", "").strip()
    if not url:
        try:
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            import secretos
            secretos.cargar_al_entorno()
            url = os.environ.get("SUPABASE_URL", "").strip()
        except Exception:
            pass
    if url:
        ok, detalle = probar(clave, url)
        print(("OK, la clave funciona: " if ok else "ATENCIÓN, la clave no pasó la prueba: ") + detalle)
        if not ok:
            print("Si config dice «JWT cryptographic operation failed», el secreto pegado no es el que verifica los JWT del proyecto (solapa Legacy JWT Secret → Reveal). Si dice «permission denied», el rol cola no está aplicado.", file=sys.stderr)
            return 2
    else:
        print("Sin SUPABASE_URL: no pude probar la clave, la imprimo igual.")
    destino = os.path.join(os.path.expanduser("~"), "Desktop", "SUPABASE_KEY_COLA.txt")
    try:
        with open(destino, "w", encoding="utf-8") as f:
            f.write(clave + chr(10))
        print(f"La clave quedó en {destino}: abrilo, copiá todo y pegalo en GitHub → Settings → Secrets → Actions → New repository secret → nombre SUPABASE_KEY_COLA. Después borrá el archivo.")
    except OSError:
        print(clave)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
