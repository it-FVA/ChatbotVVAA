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
5. Su ayuda: `definirAyuda("<pantalla>", { … })` arriba del componente y `data-ayuda="<pantalla>.<id>"` en cada botón o zona que se explica (`web/src/ayuda/registro.ts`). La página `/ayuda` y la guía interactiva («¿Cómo se usa?» → «Guía en pantalla») salen de ahí. La prueba `web/src/ayuda/registro.test.tsx` (agregá un escenario de la pantalla) y `web/scripts/verificar-ayuda.mjs` (corre con `npm test` y antes de `npm run build`) fallan si no coinciden. Sumá `import "../paginas/<Pantalla>"` en `web/src/ayuda/index.ts` para fijar su lugar en la página.

**Una persona con cualquier permiso**: Administración → Usuarios (rol creador / aprobador / admin en la tabla `usuarios`). Ya no hay contraseñas
ni listas de roles en secrets ni en el entorno.

## Banco de imágenes (5/11)
- Julián carga las fotos en Drive, en «FBA Automatización de Contenidos» → «Banco de Imágenes», con subcarpetas libres (por formato o por tema) y nombres `etiqueta_etiqueta_1080x1920.jpg`. Las medidas dan el formato (iguales = `cuadrado`, más alta = `vertical`, más ancha = `horizontal`; sin medidas, lo da una subcarpeta con ese nombre). Las demás palabras del nombre y de las subcarpetas son etiquetas.
- La cola (`procesar_cola.py`, cada 15 minutos) llama a `banco.sincronizar_desde_config`: recorre la carpeta, sube a WordPress lo que no está en la tabla `banco_imagenes` (o cambió en Drive), con título = etiquetas y la marca `banco-fva` en la descripción. Hasta 30 por pasada; el resto en la siguiente. Nunca rompe la cola: si falla, lo dice en el log.
- Administración → Configuración → «Banco de imágenes»: la carpeta de Drive (se puede pegar el link entero), el interruptor `banco_solo` (las pantallas que buscan fotos miran solo el banco; si no hay nada para la búsqueda muestran las últimas del banco, no la biblioteca entera), cuántas hay por formato y «Sincronizar ahora» (`POST /admin/banco/sincronizar`; `GET /admin/banco` da los números).
- Agregar otra carpeta: hoy hay una sola (`banco_drive_carpeta`). Para sumar otra, cambiar la clave a una lista o correr `banco.sincronizar_banco(cfg, svc, carpeta_id, registro)` con su id desde `procesar_cola.py`; el registro es por id de archivo de Drive, así que no se pisan.
- La cola necesita `DRIVE_TOKEN_JSON` como secret del repo (el mismo de `recortar-pendientes`) y el rol acotado `cola` con permisos sobre `banco_imagenes` (`api/migraciones/manual_cola_rol.sql`, idempotente: volver a correrlo después de aplicar la migración).

## Proyectos compartidos: presencia y aviso de conflicto (5/11)
- Presencia: Diseñar, Newsletter, el editor de recortes y las vistas de pieza/recorte muestran quién más está ahí («Julián está editando», «Pato está mirando»). La web late a `POST /presencia/{pieza|recorte}/{id}` cada 20 s (`web/src/util/usePresencia.ts`; no late con la pestaña oculta y avisa con `DELETE` al salir) y la API devuelve a los demás con latido en el último minuto. Tabla `presencia` (migración `20261105_1500_presencia`); la cola borra los latidos de más de 10 minutos. Sin Realtime ni websockets, y no es edición simultánea.
- Aviso de conflicto: cada pantalla manda al guardar la `version` que cargó (`resultado.guardado_en` de la pieza, `edicion.guardado_en` del recorte). Si otra persona guardó después, la API contesta 409 con `{detail, version_actual, editada_por}` y la web ofrece «Recargar y ver sus cambios» o «Guardar igual, pisando» (reintenta sin `version`). Sin `version` se guarda como siempre.
- Para sumar otra pantalla: `usePresencia(tipo, id, modo)` + `<Presencia presentes={…} />` en la cabecera; si guarda, mandar la `version` y mostrar `<ConflictoGuardado />` ante `esConflictoDeVersion(e)`.

## Token de Instagram (se renueva solo, 5/11)
- El token de Instagram Login dura 60 días. Vive en la tabla `config`, clave `meta_ig_token` (`{"token", "vence", "renovado"}`); la API y la cola leen ese mismo, sin redeploy (`meta_token.py`, usado por `publicar.Config`).
- `META_IG_TOKEN` del entorno es solo la **semilla**: se usa si no hay nada guardado o Supabase no está.
- La cola (`procesar_cola.py`) llama a `renovar_token_ig()` al empezar cada corrida: si faltan menos de 30 días (o no se conoce el vencimiento) pide el refresh a Meta y guarda el nuevo. Si falla, deja el viejo y lo dice en el log.
- Forzarlo a mano: `POST /admin/instagram/renovar-token` (solo admins). Salud → «instagram» muestra de dónde sale y cuándo vence (rojo a menos de 7 días).
- Si algún día venciera igual: generar un token nuevo en Meta for Developers, pegarlo en `META_IG_TOKEN` y borrar la clave `meta_ig_token` de `config` (o forzar la renovación).

## Actualizar el corpus
El corpus se genera en el proyecto **fva-transcripcion** (transcripción + embeddings). Cuando cambie, copiar
`corpus/fragmentos.jsonl` y `corpus/fragmentos_openai.npy` a este repo → commit + push (Render reconstruye la imagen).

El diario de trabajo (decisiones, incidentes, qué se probó) está en `../fva-transcripcion/HANDOFF.md`.
