"""Importa UNA vez los usuarios de secrets ([usuarios] / USUARIOS_JSON) a la tabla `usuarios` de Supabase, con la
contraseña actual hasheada (bcrypt) y el rol que hoy dicen las listas APROBADORES / ADMINS. Idempotente: a quien
ya está en la tabla no lo toca (ni la clave ni el rol); solo informa.

Correr desde la raíz del repo, con el secrets.toml de producción en .streamlit/ (o FVA_SECRETS=/ruta):

    python api/importar_usuarios.py --dry-run     # muestra qué haría, sin escribir
    python api/importar_usuarios.py               # importa

Después de importar, Streamlit sigue leyendo secrets (no cambia nada ahí) y la API entra por la tabla. Cuando
todos estén en la tabla y Streamlit se apague, se saca el fallback a secrets de api/auth.py y USUARIOS_JSON.
Nunca imprime contraseñas.
"""
import os, sys, argparse

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from api import config, roles as _roles           # noqa: E402
config.cargar()
import db                                         # noqa: E402
from api import cuentas                           # noqa: E402


def rol_de(usuario):
    r = _roles.roles(usuario, None)
    return "admin" if r["admin"] else ("aprobador" if r["aprueba"] else "creador")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="no escribe nada")
    args = ap.parse_args()
    usuarios = config.usuarios()
    if not usuarios:
        print("No hay usuarios en secrets ([usuarios] / USUARIOS_JSON). Nada que importar.")
        return 1
    if not db.disponible():
        print("Falta SUPABASE_URL / SUPABASE_KEY.")
        return 1
    try:
        existentes = {f["usuario"]: f for f in db.listar_usuarios()}
    except RuntimeError as e:
        print(f"No pude leer la tabla usuarios ({e}). ¿Se corrió la migración api/migraciones/usuarios_y_lista_blanca.sql?")
        return 1
    nuevos, saltados = 0, 0
    for usuario, clave in sorted(usuarios.items()):
        u = usuario.strip().lower()
        rol = rol_de(u)
        if u in existentes:
            print(f"  = {u:<16} ya está en la tabla (rol {existentes[u]['rol']}); no se toca")
            saltados += 1
            continue
        email = u if "@" in u else None
        print(f"  + {u:<16} rol {rol:<9} {'(email ' + email + ')' if email else ''} {'[dry-run]' if args.dry_run else ''}")
        if not args.dry_run:
            db.crear_usuario(u, email=email, rol=rol, clave_hash=cuentas.hashear(str(clave)), creado_por="importar_usuarios")
            db.registrar_cambio_usuario("importar_usuarios", "importar", u, {"rol": rol})
        nuevos += 1
    print(f"\n{nuevos} para importar, {saltados} ya estaban." if args.dry_run else f"\nImportados {nuevos}, ya estaban {saltados}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
