# Asistente de contenido — Vivir Agradecidos

Plataforma de contenido de la Fundación: chat sobre el material real del Hermano David y los facilitadores,
diseño de piezas por canal (Instagram, Facebook, blogpost, YouTube, email), recortes de video, newsletter,
Frase del día y circuito de aprobación. Desde el 2/11/2026 es **solo la web + la API** (la app de Streamlit se dio de baja).

## Qué hay acá
- `api/` — la API (FastAPI). `api/main.py` arma la app; cada pantalla tiene su módulo de rutas (`chat_rutas.py`,
  `publicar_rutas.py`, el paquete `frases/`, `recortes.py`, `admin_rutas.py`…). `pieza.py` es el modelo único de una pieza. Corre en **Render** (`render.yaml`, Docker:
  `api/Dockerfile`). Pruebas: `python -m pytest api/tests -q`.
- `web/` — la interfaz (Vite + React + TypeScript). Corre en **Vercel** (`chatbot-vvaa.vercel.app`). `npm run build` en `web/`.
- `canales.py` — el registro único de canales de publicación (ver «Cómo agregar X»).
- `nucleo.py` — búsqueda sobre el corpus (`fragmentos.jsonl` + `fragmentos_openai.npy`) y el asistente.
- `db/` — Supabase (REST), un módulo por tabla; el esquema completo en `api/migraciones/000_esquema_base.sql` (`python api/migrar.py`). `publicar.py` — conectores (WordPress, Instagram, Facebook, YouTube, WhatsApp prototipo).
  `imagen.py` — la foto con la frase encima. `programar_frases.py` + `frase_mail.py` + `perfit.py` — la Frase del día.
  `newsletter.py` — las plantillas del newsletter. `recortar_clip.py` / `procesar_clips.py` — recortes de video.
  **Videos subidos** (5/11): en Mis recortes, «Subir un video» (o «o subí un video» en Diseñar → YouTube) sube un mp4/mov propio, hasta 200 MB, editado afuera. `POST /recortes/subir` lo manda a WordPress y crea una fila de `clips` ya `listo` con `video_id = "subido:<uuid>"` (sin migración): desde ahí se diseña, publica, comparte y borra como cualquier recorte, pero no se edita (tramo y subtítulos son de YouTube).
- `procesar_cola.py` — la cola de publicación: corre en **GitHub Actions** cada 15 minutos (`.github/workflows/cola.yml`).
- `distribucion/` — plantillas que se copian a otros lados (el mail de la frase, el snippet de WordPress de la home).

## Correr en local
1. `pip install -r requirements.txt` (una sola vez) y en `web/`: `npm install`.
2. Las claves van en `.streamlit/secrets.toml` (nombre histórico; es solo el archivo local de secretos, no se sube) o en
   `../fva-transcripcion/clave.env`. `api/config.py` y `procesar_cola.py` las cargan al entorno.
3. API: `uvicorn api.main:app --reload --port 8000`. Web: `npm run dev` en `web/` (apunta a la API local).
4. Pruebas (las mismas que corre el CI en cada push): `python -m pytest api/tests -q` desde la raíz; en `web/`: `npx tsc --noEmit -p .`,
   `npm test` (Vitest + Testing Library, la API simulada está en `web/src/pruebas/apiSimulada.ts`) y `npm run build`.

## Deploy
- **Render** (API): despliega solo con cada push a `main`. Las variables no secretas están en `render.yaml` como
  documentación, pero el Blueprint **no las sincroniza**: una variable nueva o cambiada hay que cargarla también a mano en
  Render → fva-api → Environment. Los secretos se pegan desde `api.env` (`python api/armar_env.py`).
- **Vercel** (web): despliega solo con cada push a `main`.
- **GitHub Actions** (cola): los secretos en Settings → Secrets and variables → Actions (`PUBLICAR_*`, claves de los canales).
  La cola puede correr con una clave de Supabase acotada (`SUPABASE_KEY_COLA`, sin acceso a usuarios ni conversaciones): los pasos para
  crearla están en el encabezado de `api/migraciones/manual_cola_rol.sql`; mientras no exista el secret usa `SUPABASE_KEY`.

## Cómo agregar X (después de la reestructuración del 3/11)

**Un canal de publicación** (p. ej. WhatsApp real, Telegram):
1. `canales.py`: una entrada en `CANALES` (clave, nombres, modos válidos, variable `PUBLICAR_*`, claves, si va a la cola, si pasa por
   aprobación, icono, y las funciones `foto` / `video` que lo publican). Si la Frase del día sale por ahí, una entrada en `SALIDAS_FRASE`.
2. El conector en `publicar.py` (o un módulo propio): recibe `(cfg, pieza, quien, fecha)` y devuelve `{"ok", "modo", "aviso", …}`.
3. La variable en `api/variables_entorno.py` y `python api/generar_config.py` (regenera `render.yaml` y `cola.yml`); cargarla a mano en Render.
4. Una prueba en `api/tests/test_canales.py` pasa sola por el canal nuevo (`enviar_pieza` en simulado); `--simular` también lo cubre.
No se toca la cola, ni las rutas, ni la web: `publicar.enviar_pieza` despacha con el registro y la web recibe el canal por `GET /yo`,
`GET /publicar/opciones` y `GET /publicaciones/modos` (nombres, formato, avisos).

**Un campo nuevo en la pieza** (p. ej. hashtags):
1. `api/pieza.py`: el campo en `Pieza` (y en `CLAVES_CORTAS` si se guarda con clave corta). `a_borrador()` y `desde_fila()` lo recorren solos.
2. `python api/generar_openapi.py` y `npm run tipos` en `web/` (los tipos TS salen del OpenAPI; `apiPublicar.cuerpo()` deja de compilar
   hasta que el formulario lo mande).
3. El control en `web/src/paginas/Publicar.tsx` (y `PiezaForm` en `tiposPublicar.ts`) y, si se ve, `componentes/VistaPrevia.tsx`.

**Una solapa en el detalle del día de Frase del día**:
1. `web/src/paginas/frase/solapas/<Nombre>.tsx`: un componente con `PropsSolapa` (la frase, el día, `correr`, `ocupado`).
2. Una línea en `SOLAPAS` de `web/src/paginas/frase/solapas/index.ts`.
3. Si necesita API: una ruta en el router que corresponda de `api/frases/` (calendario, manana, mail, solicitudes, previas) y, si guarda
   algo, la función en `db/frases.py` y una migración (abajo). La prueba, al lado de la ruta.

**Una tabla nueva en Supabase**:
1. `python api/migrar.py --nueva nombre` crea `api/migraciones/AAAAMMDD_HHMM_nombre.sql`; escribir el DDL (idempotente).
2. Aplicarla: `python api/migrar.py --aplicar` (con `SUPABASE_DB_URL` y `psycopg`) o pegarla en el SQL Editor / `apply_migration` del
   MCP y anotarla con `python api/migrar.py --registrar nombre`. `python api/migrar.py` dice qué falta.
3. `db/<tabla>.py` con sus funciones sobre `db.consulta / insertar / actualizar / borrar` (escapan siempre) y una línea
   `from .<tabla> import *` en `db/__init__.py`. Las rutas solo importan `db`; las pruebas reemplazan esas funciones con `monkeypatch`.

**Una variable de entorno**: una entrada en `api/variables_entorno.py`, `python api/generar_config.py`, y cargarla a mano en Render.

**Una pantalla nueva en la web** (3/11, después del nivel 3):
1. `web/src/paginas/<Pantalla>.tsx` y su ruta en `App.tsx`. Sus estilos, en `web/src/<pantalla>.css` importado SOLO desde esa pantalla
   (`estilos.css` queda para lo que usan todas: variables, layout, botones, modal; `compartido.css` para lo que comparten Publicar y el chat).
2. Las llamadas a la API, de una línea cada una sobre el cliente único: `pedir<Tipo>("/ruta")` de `web/src/api.ts` en un `api<Nombre>.ts`
   (`pedirCrudo` para blobs, multipart o streaming). No hay otro `fetch`.
3. Fechas y horas: solo `web/src/util/fechas.ts` (`fechaHora`, `fechaLegible`, `horaArgentina`, `hace`…); no se formatean fechas a mano.
4. Una prueba al lado (`<Pantalla>.test.tsx`) con `instalarApi({ "GET /ruta": respuesta })` de `web/src/pruebas/apiSimulada.ts`.

**Una persona con cualquier permiso**: Administración → Usuarios (rol creador / aprobador / admin en la tabla `usuarios`). Ya no hay contraseñas
ni listas de roles en secrets ni en el entorno.

## Actualizar el corpus
El corpus se genera en el proyecto **fva-transcripcion** (transcripción + embeddings). Cuando cambie, copiar
`corpus/fragmentos.jsonl` y `corpus/fragmentos_openai.npy` a este repo → commit + push (Render reconstruye la imagen).

El diario de trabajo (decisiones, incidentes, qué se probó) está en `../fva-transcripcion/HANDOFF.md`.
