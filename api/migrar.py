"""(3/11, revisión 5.2 punto 11) Migraciones de la base, numeradas y registradas.

Archivos: api/migraciones/000_esquema_base.sql (la base completa al 3/11) y después api/migraciones/AAAAMMDD_HHMM_nombre.sql,
en orden. Lo aplicado queda en la tabla `migraciones` (nombre, aplicada, por, nota).

Uso (desde la raíz del repo, con SUPABASE_URL / SUPABASE_KEY en el entorno o en .streamlit/secrets.toml):
  python api/migrar.py                      lista las pendientes (archivos del repo que no están en la tabla)
  python api/migrar.py --aplicar            las aplica en orden y las registra. Necesita SUPABASE_DB_URL (la cadena de conexión de
                                            Postgres del panel de Supabase) y el paquete psycopg; sin eso, imprime el SQL para pegarlo
                                            en el SQL Editor (o pasarlo al MCP apply_migration) y registrarlo con --registrar.
  python api/migrar.py --registrar NOMBRE   anota como aplicada una migración que se corrió a mano (SQL Editor / MCP)
  python api/migrar.py --nueva nombre_corto crea api/migraciones/AAAAMMDD_HHMM_nombre_corto.sql con el encabezado

Para una tabla o columna nueva: `--nueva`, escribir el SQL, aplicarlo (`--aplicar` o SQL Editor + `--registrar`), commitear el archivo.
"""
import datetime, os, re, sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARPETA = os.path.join(RAIZ, "api", "migraciones")
PATRON = re.compile(r"^(000_esquema_base|\d{8}_\d{4}_[a-z0-9_]+)\.sql$")


def archivos():
    return sorted(f[:-4] for f in os.listdir(CARPETA) if PATRON.match(f))


def aplicadas(db):
    try:
        return {r["nombre"]: r for r in db._req("GET", "?select=nombre,aplicada,por&order=aplicada", tabla="migraciones")}
    except RuntimeError as e:
        if "42P01" in str(e) or "does not exist" in str(e) or "PGRST205" in str(e):
            return None      # todavía no existe la tabla: la crea 20261103_0400_migraciones.sql
        raise


def registrar(db, nombre, por=None, nota=None):
    db._req("POST", "", {"nombre": nombre, "por": por or os.environ.get("USERNAME") or os.environ.get("USER") or "migrar.py", "nota": nota},
            tabla="migraciones")


def pendientes(db):
    hechas = aplicadas(db)
    return [a for a in archivos() if hechas is None or a not in hechas], hechas


def aplicar(db, nombre, por=None):
    """Corre el SQL del archivo con psycopg sobre SUPABASE_DB_URL y lo registra. Devuelve True si pudo."""
    sql = open(os.path.join(CARPETA, nombre + ".sql"), encoding="utf-8").read()
    url = os.environ.get("SUPABASE_DB_URL", "").strip()
    try:
        import psycopg
    except ImportError:
        psycopg = None
    if not url or psycopg is None:
        print(f"--- {nombre}: no hay SUPABASE_DB_URL o falta `pip install psycopg`. Pegá esto en el SQL Editor de Supabase y después "
              f"corré `python api/migrar.py --registrar {nombre}`:\n")
        print(sql)
        return False
    with psycopg.connect(url) as con:
        con.execute(sql)
        con.commit()
    registrar(db, nombre, por)
    return True


def nueva(nombre_corto):
    nombre_corto = re.sub(r"[^a-z0-9_]+", "_", nombre_corto.lower()).strip("_")
    nombre = f"{datetime.datetime.now():%Y%m%d_%H%M}_{nombre_corto}"
    ruta = os.path.join(CARPETA, nombre + ".sql")
    with open(ruta, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(f"-- ({datetime.date.today():%d/%m}) {nombre_corto}: qué cambia y por qué (quién lo pidió).\n"
                 f"-- Aplicar con `python api/migrar.py --aplicar` (o SQL Editor + `--registrar {nombre}`). Idempotente (if not exists).\n\n")
    print(f"creada {ruta}")
    return ruta


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--nueva" in argv:
        nueva(argv[argv.index("--nueva") + 1])
        return 0
    sys.path.insert(0, RAIZ)
    import secretos
    secretos.cargar_al_entorno()
    import db
    if not db.disponible():
        print("Sin SUPABASE_URL / SUPABASE_KEY: no puedo mirar la tabla migraciones.")
        return 1
    if "--registrar" in argv:
        nombre = argv[argv.index("--registrar") + 1].removesuffix(".sql")
        if nombre not in archivos():
            print(f"No existe api/migraciones/{nombre}.sql")
            return 1
        registrar(db, nombre, nota="registrada a mano")
        print(f"registrada {nombre}")
        return 0
    pend, hechas = pendientes(db)
    if hechas is None:
        print("La tabla `migraciones` todavía no existe en esta base: aplicar primero 000_esquema_base y 20261103_0400_migraciones.")
    else:
        print(f"aplicadas: {len(hechas)}" + (" · última: " + max(hechas, key=lambda n: hechas[n]["aplicada"]) if hechas else ""))
    if not pend:
        print("pendientes: ninguna. La base está al día con el repo.")
        return 0
    print("pendientes: " + ", ".join(pend))
    if "--aplicar" not in argv:
        return 0
    for nombre in pend:
        if aplicar(db, nombre):
            print(f"aplicada y registrada {nombre}")
        else:
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
