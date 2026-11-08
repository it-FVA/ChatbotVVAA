"""
db — Acceso a Supabase (Postgres por REST), partido por dominio (3/11, revisión 5.2 punto 12; antes un solo db.py de 1.047 líneas).

    db/_cliente.py       _req (la llamada cruda), consulta/insertar/actualizar/borrar (escapan siempre), _rpc, ping, _q, _ahora_iso
    db/conversaciones.py db/publicaciones.py  db/clips.py  db/config.py  db/frases.py  db/usuarios.py  db/uso.py  db/servicios.py
    db/salud.py  db/vectores.py  db/proyectos.py  db/banco.py  db/metricas.py       una tabla (o un grupo de tablas) por módulo

`import db` sigue funcionando igual: todas las funciones públicas se reexportan acá (db.listar_pendientes, db.obtener_config…),
y las privadas que usan los scripts y las pruebas (db._req, db._cfg, db._rpc, db._ahora_iso, db._q). Dentro del paquete las
funciones se llaman entre sí a través de `db.x`, así `monkeypatch.setattr(db, "x", …)` en las pruebas vale para todas.

Config por entorno/secrets: SUPABASE_URL, SUPABASE_KEY (service_role key). Sin credenciales, disponible() da False y la app
sigue andando sin guardar. El esquema completo está en api/migraciones/000_esquema_base.sql.

Para una tabla nueva: una migración (python api/migrar.py --nueva nombre), un módulo db/<tabla>.py con sus funciones usando
consulta/insertar/actualizar/borrar, y una línea `from .<tabla> import *` acá.
"""
import urllib.request, urllib.error   # noqa: F401  (las pruebas reemplazan db.urllib.request.urlopen)
from ._cliente import _cfg, _cabeceras, _req, _rpc, _q, _ahora_iso, disponible, consulta, insertar, actualizar, borrar, filtros_a_params, ping   # noqa: F401
from .conversaciones import *   # noqa: F401,F403
from .publicaciones import *    # noqa: F401,F403
from .clips import *            # noqa: F401,F403
from .config import *           # noqa: F401,F403
from .frases import *           # noqa: F401,F403
from .usuarios import *         # noqa: F401,F403
from .usuarios import _USUARIO_COLS, _COLUMNAS_USUARIO   # noqa: F401
from .uso import *              # noqa: F401,F403
from .servicios import *        # noqa: F401,F403
from .salud import *            # noqa: F401,F403
from .vectores import *         # noqa: F401,F403
from .banco import *            # noqa: F401,F403
from .metricas import *         # noqa: F401,F403   (8/11: métricas de campañas y canales)
from . import proyectos         # noqa: F401
from .presencia import *        # noqa: F401,F403   (5/11: quién está mirando o editando una pieza o un recorte)
