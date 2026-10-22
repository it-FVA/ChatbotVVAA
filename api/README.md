# API HTTP del asistente (fase 0 + recortes de la fase 1)

Es el primer paso del plan de interfaz propia (`fva-transcripcion/analisis/plan-interfaz-propia-2026-10.md`):
una API en FastAPI que llama al **mismo cerebro** que la app de Streamlit (`nucleo.py`, `db.py`), sin tocarlo.
Streamlit sigue en producción tal cual; esta API corre al lado. Por ahora: login, sesión, chat con streaming,
lectura de conversaciones y publicaciones, y (fase 1, 21/10 noche, `recortes.py`) todo lo de «Mis recortes»: editar y regenerar
con el editor visual de la web (`web/`), borrar, estilo por defecto. **No publica ni aprueba** (fases 2 y 3).

## Qué hay

| Archivo | Qué hace |
|---|---|
| `main.py` | la app FastAPI: carga el corpus una vez al arrancar y define los endpoints |
| `chat.py` | el chat con streaming (SSE): réplica paso a paso de `nucleo.responder_con_pieza` con la segunda llamada al modelo en streaming; arma las tarjetas de fuentes (traducción en/de, estado de los recortes, «citada») |
| `auth.py` | cookie de sesión firmada (HttpOnly, SameSite, 30 días), login por usuario/contraseña, login con Google |
| `roles.py` | copia de `publicar_ui.roles` leyendo del entorno (ese módulo importa Streamlit) |
| `config.py` | variables de entorno; en local carga `.streamlit/secrets.toml` |
| `migraciones/autorizados_login_google.sql` | tabla `autorizados` (email, rol, agregado_por, creado) para el login con Google |
| `recortes.py` | router de recortes (fase 1): misma lógica de negocio que `publicar_ui._mis_recortes` / `_editor_recorte`, más `edicion["segmentos"]` |
| `salud.py` | (22/10) `GET /salud` (health check) y la base de la pantalla «Salud» / Dashboard de Administración: `/salud/servicios` (13 chequeos con ok / aviso / error y «qué hacer» + bloque `capacidad`), `/salud/historial`, `/salud/capacidad`. Guarda cada corrida en `salud_historial` |
| `migraciones/salud_historial.sql`, `migraciones/fragmentos_emb_pgvector.sql` | (22/10) tabla del historial de salud; extensión `vector`, tabla `fragmentos_emb`, índice HNSW y funciones `match_fragmentos*`, `match_lexico`, `tamano_base` (todas aplicadas en Supabase el 22/10) |
| `tests/` | pytest + httpx: 70 pruebas sin OpenAI ni Supabase (`test_api.py`, `test_recortes.py`, `test_salud.py`, `test_capacidad.py`, `test_vectores.py`), y 1 real (marcada `real`) |
| `ejemplos.http` | llamadas de ejemplo (REST Client / curl) |
| `Dockerfile`, `requirements.txt` | para desplegar en cualquier hosting que acepte un contenedor |

En `db.py` se agregaron al final (sin cambiar las existentes): `cargar_conversacion_de`, `autorizado`,
`listar_autorizados`, `agregar_autorizado`, `quitar_autorizado`.

## Endpoints

| Método y ruta | Quién | Qué devuelve |
|---|---|---|
| `GET /salud` | nadie | ok, fragmentos cargados, Supabase sí/no, modelo, si está configurado Google y el `google_client_id` (lo usa el botón de la web; no es secreto); (22/10) más `version`, `arranque`, `vectores` |
| `GET /salud/servicios` (`?guardar=0`) | admins, o `?token=SALUD_TOKEN` / cabecera `X-Salud-Token` | (22/10) `{creado, estado, chequeos: [{nombre, estado, detalle, que_hacer, desde, …}], capacidad: [...], ms}`; guarda la corrida en `salud_historial` |
| `GET /salud/capacidad` | ídem | solo el bloque `capacidad` (uso vs. límite del plan por proveedor) |
| `PUT /salud/capacidad/config` `{umbrales_planes?, presupuesto_openai_usd?, vercel_uso_manual_gb?}` | admins | guarda esas claves en `config` |
| `GET /salud/historial` (`?limite=`) | ídem | las últimas corridas guardadas (incluye las filas `arranque`) |
| `POST /login` `{usuario, clave}` | — | pone la cookie; devuelve lo mismo que `/yo` |
| `POST /login/google` `{id_token}` | — | verifica el token con Google; admite si el email termina en `DOMINIO_FVA` o está en `autorizados` |
| `POST /logout` | — | borra la cookie |
| `GET /yo` | con sesión | `{usuario, origen, idioma, rol: {nombre, crea, aprueba, publica}}` |
| `GET /conversaciones` | con sesión | `[{id, titulo, actualizado}]` de la persona (sin papelera) |
| `GET /conversaciones/{id}` | dueño | la conversación con los mensajes normalizados y, en cada respuesta, `tarjetas` |
| `POST /conversaciones/{id}/mensajes` `{texto, stream?}` | dueño (`id` = `nueva` abre una) | la respuesta del bot; con `stream: true` o `Accept: text/event-stream`, SSE |
| `GET /recortes` (`?equipo=1`, `?todos=1`, `?buscar=`) | con sesión (`todos`: aprobadores) | «Mis recortes» / «Del equipo» (listos de otras personas) / Panel admin → Clips, con `propio`, `puede_editar`, `puede_borrar`, `miniatura`, `duracion_ms`, `estado_texto` |
| `GET /recortes/opciones` | con sesión | tipografías, tamaños, colores, fondos, posiciones (`recortar_clip`), límites del tramo, estilo del equipo |
| `GET /recortes/estilo-defecto` · `PUT` | con sesión · aprobadores | config `clips_estilo` |
| `GET /recortes/{id}` | con sesión | el recorte + `lineas` (SRT parseado), `estilo_actual`, `srt_corregido` |
| `POST /recortes/{id}/edicion` | dueño o aprobador | = «🔁 Regenerar»: guarda `clips.edicion` (`inicio_ms`, `fin_ms`, `segmentos`, `lineas`/`srt`, `estilo`, `quitar_pausas`, `descartar_srt`), valida como Streamlit, estado 'pedido' |
| `DELETE /recortes/{id}` · `GET /recortes/{id}/usos` | dueño o aprobador | = «🗑 Borrar» (archivo de WordPress + fila) · piezas que usan el video |
| `POST /recortes/{id}/reintentar` | aprobadores | = «↻ Reintentar» |
| `GET /publicaciones` (`?todos=1`) | con sesión (`todos`: aprobadores) | «Mis publicaciones»: piezas + solapas por estado (o el registro completo) |
| `GET /autorizados` | aprobadores | la lista de emails autorizados (solo lectura por ahora) |

Documentación interactiva en `/docs` (Swagger) cuando la API está corriendo.

### El chat en streaming

`POST /conversaciones/nueva/mensajes` con `Accept: text/event-stream` manda eventos `event: …` / `data: {json}`:

1. `inicio` `{conversacion_id, titulo}` (null si es nueva)
2. `estado` `{texto: "pensando"}` y después `{texto: "buscando", herramienta: "buscar_material"}` por cada herramienta
3. `fuentes` `{tarjetas: [...]}` apenas termina la búsqueda, **antes** de que el bot escriba
4. `pieza` `{canal, titulo, texto, …}` si el bot llamó a `proponer_publicacion`
5. `texto` `{delta: "…"}` muchas veces: la respuesta a medida que llega
6. `fin` `{conversacion_id, titulo, texto, pieza, tarjetas, mensaje}`: la conversación ya quedó guardada en Supabase

Cada tarjeta trae lo que hoy dibuja la app: `tag`, `titulo`, `texto`, `autor`, `fuente`, `ir` (link al segundo o al
párrafo), `citada` (el bot la nombró en la respuesta), `traduccion` (cuentas en/de) y, en los videos, `recortes`
`{horizontal, vertical}` con el estado del clip de ese tramo (null si nadie lo pidió).

Las mismas herramientas que en Streamlit (`nucleo.TOOLS`): `buscar_material`, `proponer_publicacion`, `pedir_recorte`,
`estado_recortes`, `analizar_corpus`. Los recortes que pide el bot quedan firmados por la persona de la sesión.

## Correr en local

Desde la **raíz del repo** (no desde `api/`):

```bash
pip install -r api/requirements.txt
uvicorn api.main:app --reload
```

Lee `.streamlit/secrets.toml` si existe (igual que la app), así que con los mismos secrets anda sin configurar nada
más. Arranca en unos 10 s (carga del corpus). Probar: abrir http://127.0.0.1:8000/docs, o los ejemplos de
`ejemplos.http`. Con otro archivo de secrets: `FVA_SECRETS=/ruta/secrets.toml`.

Pruebas:

```bash
python -m pytest api/tests -q -m "not real"
```

```bash
OPENAI_API_KEY=... python -m pytest api/tests -q -m real -s
```

## Variables de entorno

Los mismos nombres que los secrets de Streamlit. En un servidor se cargan como variables de entorno; en local, del `secrets.toml`.

| Variable | Para qué | Obligatoria |
|---|---|---|
| `OPENAI_API_KEY`, `ASISTENTE_MODELO` | el modelo (como hoy) | sí |
| `SUPABASE_URL`, `SUPABASE_KEY` | conversaciones, clips, publicaciones, autorizados | sí (sin ellas anda el chat pero no guarda) |
| `USUARIOS_JSON` | `{"franco": "clave", …}`: reemplaza la tabla `[usuarios]` de secrets en el servidor | sí (o `[usuarios]` en secrets.toml) |
| `IDIOMAS_JSON` | `{"gratefulness": "en"}`: reemplaza `[idiomas]` (si falta, valen los defaults de la app) | no |
| `APROBADORES`, `ADMINS`, `PUBLICACION_DIRECTA` | roles, como en Streamlit (21/10: creador → aprobador → admin; un admin también aprueba) | no (defaults `julian,franco,beto` / `franco,beto`) |
| `SESION_SECRETO` | firma de la cookie de sesión; una cadena larga al azar | **sí en producción** (si falta se genera una al arrancar y las sesiones mueren al reiniciar) |
| `COOKIE_SEGURA` | `1` detrás de HTTPS (cookie `Secure`) | sí en producción |
| `COOKIE_SAMESITE` | `lax` (default) si interfaz y API comparten dominio; `none` + `COOKIE_SEGURA=1` si están en dominios distintos | no |
| `GOOGLE_CLIENT_ID` | el client id del proyecto de Google Cloud (login con Google). Sin él, `/login/google` responde 503 | no |
| `DOMINIO_FVA` | dominio de la Fundación cuyas cuentas entran solas (ej. `viviragradecidos.org`). Vacío = solo la lista `autorizados` | no |
| `BUSQUEDA_HIBRIDA`, `RERANK_*`, `CONCEPTOS_URL`, `DISTINCIONES_URL`, `EXPANSION_CONSULTA`, `CONTEXTO_CHARS`, `LIMPIEZA_EXTRA`, `DATOS_FIJOS_URL` | interruptores del buscador, como hoy | no |
| `API_CARGAR_CORPUS` | `0` para arrancar sin cargar el corpus (tests) | no |
| `VECTORES` | (22/10) `local` (default: embeddings `.npy` en memoria) o `supabase` (pgvector, tabla `fragmentos_emb`). Ver «Búsqueda en Supabase» | no |
| `LEXICO` | (22/10) `local` (default: BM25 en memoria) o `supabase` (texto de Postgres). Solo cuenta con `BUSQUEDA_HIBRIDA=1` | no |
| `VECTORES_K` | cuántos candidatos pide cada búsqueda a Postgres en modo supabase (300) | no |
| `SALUD_TOKEN` | token para consultar `/salud/servicios` desde un monitor externo sin sesión | no |
| `MEMORIA_LIMITE_MB` | límite de memoria del plan para la fila «memoria» (512) | no |
| `META_IG_TOKEN_VENCE` | `AAAA-MM-DD` en que vence el token de Instagram (Meta no lo informa para tokens de Instagram Login); la fila «instagram» avisa 14 días antes | no |
| `META_IG_TOKEN`, `META_FB_PAGE_TOKEN`, `WP_APP_PASSWORD`, `DRIVE_TOKEN_JSON`, `YOUTUBE_TOKEN_JSON`, `GITHUB_TOKEN` | si están, «Salud» verifica esos servicios (hoy los usa la cola de GitHub Actions, no la API); `GITHUB_TOKEN` solo sube el límite de la API pública de GitHub | no |
| `PORT` | puerto (lo pone el hosting) | no |

## Desplegar en Render (API) + Vercel (web) — plan gratuito para probar (21/10)

Cuentas: Render (workspace «Vivir Agradecidos») y Vercel (equipo «Vivir Agradecidos»), las dos con el GitHub it-fva.

1. `python api/armar_env.py` en la máquina de Franco → genera `api.env` (secretos; ignorado por git).
2. Render → New → **Blueprint** → repo `it-FVA/ChatbotVVAA`, rama `claude/deploy-render-vercel` → lee `render.yaml`
   (servicio `fva-api`, Docker, plan free, health check `/salud`). En **Environment → Add from .env** pegar el contenido
   de `api.env`. Primer deploy: ~5 min (construye la imagen con el corpus).
3. Vercel → **Import Project** → mismo repo y rama → *Root Directory* `web`, framework Vite (build `npm run build`, salida
   `dist`) → variables `VITE_API_URL=https://fva-api.onrender.com` (la URL que dio Render) y
   `VITE_STREAMLIT_URL=https://chatbotvvaa.streamlit.app` → Deploy.
4. Si la URL de Vercel no es `https://fva-web.vercel.app`, corregir `CORS_ORIGENES` en Render con la real.
5. Probar: abrir la web, entrar con un usuario de `[usuarios]`, ver Mis recortes. Si Render se quedó sin memoria
   (log «Out of memory»), pasar el servicio a Standard o mover los embeddings a Supabase.

## Desplegar (notas generales: Railway o Render)

La API es un contenedor: `api/Dockerfile`, construido desde la raíz del repo (necesita `nucleo.py`, `db.py`, el
corpus `fragmentos.jsonl` + `fragmentos_openai.npy` y `datos_fijos.md`). Memoria medida el 19/10: ~200 MB con el
corpus, ~400 MB con la búsqueda híbrida; el plan gratuito de Render (512 MB, se duerme) no alcanza.

- **Railway:** nuevo proyecto → Deploy from GitHub repo → en Settings, *Dockerfile path* = `api/Dockerfile` → pegar las
  variables de entorno de la tabla → genera un dominio. Railway pasa `PORT` solo.
- **Render:** New → Web Service → repo → *Runtime: Docker*, *Dockerfile path* `api/Dockerfile`, *Docker context* `.` →
  variables de entorno → plan Standard (2 GB). Render pasa `PORT` solo.
- En cualquiera: `SESION_SECRETO` y `COOKIE_SEGURA=1`. Si la interfaz web va en otro dominio (Vercel), además
  `COOKIE_SAMESITE=none` y CORS con credenciales (no está configurado: se agrega cuando se decida el dominio).

Probar el contenedor en local:

```bash
docker build -f api/Dockerfile -t fva-api .
```

```bash
docker run -p 8000:8000 --env-file api.env fva-api
```

## Resultado de la prueba en local (21/10/2026)

API levantada con `uvicorn api.main:app` sobre los secrets reales (modelo y switches de producción), usuario `franco`:

| Paso | Resultado |
|---|---|
| `GET /salud` | ok, 26.448 fragmentos, Supabase conectado |
| `GET /yo` sin sesión · login con clave mala | 401 · 401 |
| `POST /login` franco | 200, rol aprobador / admin, idioma es, cookie `fva_sesion` |
| `POST /conversaciones/nueva/mensajes` «¿qué dice Br. David sobre la gratitud?» (SSE) | 1 `inicio`, 2 `estado`, 1 `fuentes`, 291 `texto`, 1 `fin` |
| Tiempos (desde el envío) | herramienta decidida a los 7 s · fuentes a los 26 s · primer texto a los 27 s · fin a los 33 s |
| Fuentes | 6 tarjetas de Br. David (5 artículos, 1 libro con página), 2 marcadas como citadas en la respuesta |
| Conversación | guardada en Supabase con título «David Steindl Rast y gratitud»; apareció primera en `GET /conversaciones`; `GET /conversaciones/{id}` la devolvió con sus 2 mensajes (la fila de prueba se borró después) |
| `GET /recortes` · `GET /publicaciones` | 5 recortes · 6 piezas (1 publicada, 5 pruebas), mismas listas que Streamlit |
| `GET /autorizados` | 503: falta correr la migración (ver abajo) |
| `POST /logout` → `GET /yo` | 200 → 401 |

Lo que tarda es el buscador (de los 7 s a los 26 s: búsqueda, reranker y traducción de la consulta), igual que en
Streamlit; el streaming no lo cambia, solo muestra el texto apenas empieza.


## Salud de los servicios (22/10)

`api/salud.py` es la base de la pantalla «Salud» y del Dashboard de Administración (web, pendiente). `GET /salud/servicios`
corre en paralelo 13 chequeos y devuelve, por cada uno, `estado` (ok / aviso / error), `detalle` (qué midió) y `que_hacer`
(el paso concreto). Nada se inventa: lo que no se puede verificar (sin credenciales, sin red) lo dice.

| Chequeo | Qué mira | Aviso / error |
|---|---|---|
| `supabase` | una consulta mínima a `config` y la latencia | error si no responde; aviso si tarda > 2 s |
| `openai` | `models.retrieve` del modelo de producción (gratis; cacheado 10 min) | error si la clave falla o el modelo no existe |
| `wordpress` | `GET /wp-json/` y, con `WP_USER` + `WP_APP_PASSWORD`, `/wp/v2/users/me` | error si el sitio o las credenciales fallan |
| `instagram` | el token de Instagram Login (`IG…`) contra `graph.instagram.com/me`; el vencimiento sale de `META_IG_TOKEN_VENCE` (Meta no permite `debug_token` con estos tokens, probado 22/10) | aviso 14 días antes de vencer o si falta la fecha; error si venció o no sirve |
| `facebook` | `debug_token` del token de la página: validez, vencimiento, permisos | ídem |
| `drive`, `youtube` | canje del `refresh_token` por un access token en Google (no consume cuota) | error si Google lo rechaza (`invalid_grant` = volver a autorizar) |
| `cola_publicacion` | última corrida de `cola.yml` (API pública de GitHub, cacheada 5 min) + piezas `pendiente` vencidas hace > 30 min | aviso si falló, si tiene > 45 min o si hay piezas sin procesar |
| `recortes` | ídem con `recortar_pendientes.yml` + clips en `pedido` hace > 1 h | ídem |
| `frase_del_dia` | interruptor, foto por defecto, frase de hoy y de mañana | aviso si está prendida y falta algo |
| `api` | versión, desde cuándo corre, corpus cargado, modo de vectores | aviso si el corpus no está cargado |
| `web` | `GET` a `VITE_WEB_URL` o al primer origen de `CORS_ORIGENES` | error si no responde 200 |
| `memoria` | RSS del proceso contra `MEMORIA_LIMITE_MB` | aviso al 80 %, error al 95 % |

Cada corrida se guarda resumida en `salud_historial` (`creado`, `estado` general, `detalle` json) y, con eso, cada chequeo
que no está ok trae `desde`: la fecha de la corrida más vieja de la racha actual con ese estado. Cada arranque de la API
deja también una fila `estado='arranque'` (sirve para contar los despertares del plan free).

**Bloque `capacidad`** (pedido de Franco, 22/10: «¿funciona? ¿por qué? ¿cuánto cuesta? ¿por qué?»). Por proveedor:
`{nombre, plan, costo_mensual_usd, metrica, uso, limite, unidad, porcentaje, umbral, estado, justificacion, fuente_limite,
referencia, desde}`. El plan y el costo salen de la tabla `servicios` (Panel admin → Servicios y costos); el umbral de
`config.umbrales_planes` (un número o `{"default": 70, "supabase": 80}`; default 70 %): al superarlo el estado pasa a
`aviso` con la justificación «conviene pasar a plan pago: métrica, cuánto, desde cuándo».

| Proveedor | Uso medido | Límite y fuente |
|---|---|---|
| Supabase | tamaño de la base (función SQL `tamano_base()`), filas por tabla; si la consulta falla, «pausada» | 500 MB (supabase.com/pricing, 22/10) |
| Render | RSS del proceso; arranques en frío en 24 h y 7 días (aviso con 5 o más por día) | 512 MB (render.com/docs/compute-plans, 22/10); 750 h/mes |
| Vercel | **no se puede leer sin `VERCEL_TOKEN`**: dato manual (`PUT /salud/capacidad/config {vercel_uso_manual_gb}`) | 100 GB/mes de Fast Data Transfer, marcado `referencia: true` (es la guía de uso típico de Hobby, no un derecho del plan; Hobby es solo para uso no comercial) |
| OpenAI | gasto estimado del mes = `uso_openai` × `config.openai_precios` (misma fórmula que el Panel admin), tokens, proyección a 30 días | `config.presupuesto_openai_usd` (lo fija la Fundación; sin él, no hay porcentaje) |

Primera corrida real (22/10, desde la máquina de Franco): todo ok salvo `api` (sin corpus, esperable en la prueba);
Instagram válido para @vivir.agradecidos, Facebook sin vencimiento, Drive y YouTube vigentes, cola y recortes corridos
hace 1-2 min, web en Vercel respondiendo. Capacidad: Supabase 203 MB de 500 (41 %; 190 MB son `fragmentos_emb`),
OpenAI US$ 0,08 en lo que va del mes (57 llamadas).

## Búsqueda en Supabase (pgvector) — medición del 22/10

Todo esto quedó medido antes de existir el interruptor en Render, con la regla del proyecto (cualquier cambio del buscador se
mide con el set dorado antes de prenderse). Informe completo: `informes/medicion-vectores-supabase-validado.md`.

**Qué hay.** Extensión `vector` (pgvector 0.8) en Supabase, tabla `fragmentos_emb` (idx = posición en `fragmentos.jsonl`,
fragmento_id, documento_id, texto, `embedding vector(512)`, `tsv` generado con `to_tsvector('spanish', unaccent(texto))`),
índice HNSW coseno + GIN, funciones SQL `match_fragmentos(query_embedding, k)`, `match_fragmentos_varios(jsonb, k)` (varias
consultas fusionadas por máximo, como hace `nucleo._buscar` con la traducción y la expansión) y `match_lexico(consulta, k)`.
`subir_embeddings.py` subió los 26.448 vectores desde `fragmentos_openai.npy` (lotes de 400, upsert por idx, verificación
de conteo y muestra al final: OK). En `nucleo.py`, `VECTORES=supabase` consulta Postgres en lugar del `.npy` (que ya no se
carga) y `LEXICO=supabase` reemplaza BM25 por el texto de Postgres; BM25 y la fusión RRF siguen iguales en modo local.
El default sigue siendo `local`.

**Medición (22/10, 51 consultas validadas, acierto@6, producción = híbrida + limpieza + reranker 50/400 fusión):**

| Modo | Sin reranker | Con reranker | Latencia media sin / con reranker | RSS del proceso |
|---|---|---|---|---|
| V0 · local (producción) | 39/51 | 41/51 | 0,39 s / 1,96 s | 399 MB |
| V1 · `VECTORES=supabase` | 39/51 (idéntico, consulta por consulta) | 41/51 | 0,76 s / 2,69 s | 347 MB |
| V2 · `VECTORES=supabase` + `LEXICO=supabase` | **33/51** | 41/51 | 0,61 s / 2,20 s | 148 MB |

Memoria por partes: jsonl 72 MB, `.npy` 52 MB, **BM25 245 MB**. `fragmentos_emb` ocupa 190 MB de los 500 MB del plan Free
de Supabase.

**Conclusión.** V1 cumple (misma calidad, +0,4 s) pero ahorra poco (52 MB). V2 ahorra 252 MB pero la recuperación empeora
(6 consultas menos sin reranker; el reranker lo tapa): por la regla del proyecto no se adopta tal como está. La decisión
de prenderlo o pagar plan es de Franco (ver HANDOFF 70).

**Cómo prenderlo en Render** (solo V1, si Franco lo decide): en `render.yaml`, dentro de `envVars`, descomentar
`VECTORES: supabase` (está comentado al lado de `BUSQUEDA_HIBRIDA`) y pushear a main; el Blueprint lo sincroniza. La imagen
sigue llevando el `.npy` (volver a `local` es cambiar la variable). `GET /salud` muestra el modo en `vectores`.

## Lo que falta / decisiones pendientes

- **Correr la migración** `migraciones/autorizados_login_google.sql` en Supabase (SQL Editor). Hasta entonces, el
  login con Google admite solo el dominio y `/autorizados` responde 503.
- **Proyecto de Google Cloud** (con la cuenta de la Fundación) para tener el `GOOGLE_CLIENT_ID`; y definir
  `DOMINIO_FVA` (`viviragradecidos.org` o `vivir-agradecidos.org`, pendiente en el plan). Los usuarios que entren
  con Google quedan identificados por su email: el historial de «franco» no se une al de «franco@…» (mapeo pendiente,
  está en el plan). Los roles sí: `franco@dominio` hereda lo de `franco` en `APROBADORES`.
- **Hosting**: Railway o Render (Franco prefiere Render + Vercel; el plan recomendaba el VPS). La API no depende de eso.
- **CORS y dominio** de la interfaz web (fase 2), alta/baja de autorizados desde el panel, logout de Google.
- **Variable global `nucleo.USUARIO_ACTUAL`**: sigue siendo global; la API ejecuta las herramientas de a una (candado)
  para que cada recorte quede firmado por quien lo pidió. Lo limpio es que pase a ser un parámetro de `nucleo` (plan, §2.3).
- `chat.py` replica `nucleo.responder_con_pieza` (21/10). Si esa función cambia, hay que cambiar la copia; la fase 2
  del plan prevé compararlas con el set dorado y dejar una sola versión con streaming en `nucleo`.
