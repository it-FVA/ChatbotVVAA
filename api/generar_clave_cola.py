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


def main(argv):
    secreto = os.environ.get("SUPABASE_JWT_SECRET", "").strip()
    if not secreto:
        print("Falta SUPABASE_JWT_SECRET en el entorno (Supabase → Project Settings → API → JWT Secret).", file=sys.stderr)
        return 1
    anios = int(argv[argv.index("--anios") + 1]) if "--anios" in argv else 5
    print(generar(secreto, anios=anios))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
