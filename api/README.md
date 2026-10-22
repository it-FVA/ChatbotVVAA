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
| `tests/` | pytest + httpx: 37 pruebas sin OpenAI ni Supabase (`test_api.py`, `test_recortes.py`), y 1 real (marcada `real`) |
| `ejemplos.http` | llamadas de ejemplo (REST Client / curl) |
| `Dockerfile`, `requirements.txt` | para desplegar en cualquier hosting que acepte un contenedor |

En `db.py` se agregaron al final (sin cambiar las existentes): `cargar_conversacion_de`, `autorizado`,
`listar_autorizados`, `agregar_autorizado`, `quitar_autorizado`.

## Endpoints

| Método y ruta | Quién | Qué devuelve |
|---|---|---|
| `GET /salud` | nadie | ok, fragmentos cargados, Supabase sí/no, modelo, si está configurado Google |
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
| `APROBADORES`, `PUBLICACION_DIRECTA` | roles, como hoy | no (default `julian,franco,beto`) |
| `SESION_SECRETO` | firma de la cookie de sesión; una cadena larga al azar | **sí en producción** (si falta se genera una al arrancar y las sesiones mueren al reiniciar) |
| `COOKIE_SEGURA` | `1` detrás de HTTPS (cookie `Secure`) | sí en producción |
| `COOKIE_SAMESITE` | `lax` (default) si interfaz y API comparten dominio; `none` + `COOKIE_SEGURA=1` si están en dominios distintos | no |
| `GOOGLE_CLIENT_ID` | el client id del proyecto de Google Cloud (login con Google). Sin él, `/login/google` responde 503 | no |
| `DOMINIO_FVA` | dominio de la Fundación cuyas cuentas entran solas (ej. `viviragradecidos.org`). Vacío = solo la lista `autorizados` | no |
| `BUSQUEDA_HIBRIDA`, `RERANK_*`, `CONCEPTOS_URL`, `DISTINCIONES_URL`, `EXPANSION_CONSULTA`, `CONTEXTO_CHARS`, `LIMPIEZA_EXTRA`, `DATOS_FIJOS_URL` | interruptores del buscador, como hoy | no |
| `API_CARGAR_CORPUS` | `0` para arrancar sin cargar el corpus (tests) | no |
| `PORT` | puerto (lo pone el hosting) | no |

## Desplegar (sin elegir todavía: Railway o Render)

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
