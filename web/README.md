# Interfaz web propia (fase 1: «Mis recortes» con editor visual · revisión UX del 21/10 · usuarios y administración del 22/10)

Es la primera pantalla de la interfaz que va a reemplazar a Streamlit (plan en
`fva-transcripcion/analisis/plan-interfaz-propia-2026-10.md`). Habla con la API de `api/` (fase 0 + los endpoints de
recortes de esta fase) y no toca Streamlit, que sigue en producción. Las capturas de cómo se ve están en `capturas/`
(escritorio 1366 px y celular 375 px): login, lista (cargando, vacía, normal), editor antes y después de editar, zoom de la
línea de tiempo, atajos de teclado, confirmación de borrado, pantalla de «regenerando» y barra inferior en celular. La revisión
de UX/UI que motivó la segunda vuelta (hallazgos, referencias con links, qué se cambió y qué quedó) está en `UX-REVISION.md`.

## Qué hay

- **Login** con usuario y contraseña (los mismos de siempre, `POST /login`) y **con Google** (Google Identity Services: el botón
  oficial devuelve un `id_token` que va a `POST /login/google`; la API lo verifica con `GOOGLE_CLIENT_ID` y admite las cuentas
  `@viviragradecidos.org` (`DOMINIO_FVA`) o las de la tabla `autorizados`). El client id lo publica `GET /salud`; si la API no lo
  tiene, el botón queda deshabilitado. Orígenes autorizados en Google Cloud: `http://localhost:5173`, `http://localhost:8000`,
  `http://127.0.0.1:8000` (hay que agregar el dominio de producción cuando exista). No se probó con una cuenta real: el botón
  carga y abre el selector de Google; el rechazo de un token inválido sí se probó (401).
- **Cuentas** (22/10): en el login, «¿Primera vez? Creá tu cuenta» (`/primera-vez`): paso 1 el email (`POST /cuentas/verificar`: puede si
  es del dominio de la Fundación o está en la lista blanca; si un admin ya le armó la cuenta sin clave, el usuario viene fijado), paso 2
  usuario y contraseña con las reglas a la vista (`POST /cuentas/primera-vez`) y entra. «Mi cuenta» (`/cuenta`, clic en el nombre abajo
  de la barra): datos y **cambiar mi contraseña**; si la contraseña es temporal (la puso un admin), la app manda ahí hasta cambiarla.
- **Administración** (22/10, solo admins, `/administracion`, separada de «Aprobación»): menú propio con **Usuarios** (tabla: usuario,
  nombre, email, rol, activo, último ingreso; cambiar rol desde la fila, activar/desactivar, renombrar actualizando el historial, resetear
  la contraseña con clave temporal mostrada una sola vez o «sin clave», borrar con confirmación, crear; aviso con los usuarios que siguen
  solo en secrets; «Últimos cambios» plegado), **Lista blanca** (emails de fuera del dominio con rol y nota: agregar, editar, quitar) y
  los lugares de Dashboard, Salud, Servicios y costos y Configuración marcados «pronto». **Aprobación** (`/aprobacion`, aprobadores) es por
  ahora un marcador que lleva al Panel admin de Streamlit. En celular, las tablas se vuelven tarjetas.
- **Roles** (21/10, los mismos que Streamlit, los devuelve `GET /yo` en `rol`): «creador de contenido» (todos: chat, piezas a
  aprobación, sus recortes), «aprobador» (`APROBADORES`: además la solapa «Todos» de recortes, editar y borrar los ajenos, cola,
  registro, papelera) y «admin» (`ADMINS`, default `franco,beto`; un admin también aprueba: además Frase del día, Dashboard y la
  configuración, p. ej. `PUT /recortes/estilo-defecto`). En la web hoy se usa `rol.aprueba` (solapa «Todos», permisos de las
  tarjetas) y el nombre del rol en la barra; `rol.admin` queda para la pantalla de configuración cuando exista.
- **Barra lateral**: «Mis recortes» (esta pantalla) y dos links que por ahora abren la app de Streamlit en producción
  («Chat» y «Mis publicaciones», URL en `VITE_STREAMLIT_URL`). En celular se vuelve una barra arriba.
- **Recortes**: solapas «Mis recortes», «👥 Del equipo» (los listos de otras personas: abrir, sin editar ni borrar) y
  «Todos» para aprobadores; buscador por título, video o quién lo pidió; cada tarjeta con el video (o la miniatura de
  YouTube si todavía no está), formato, tramo, duración, estado (listo · en proceso · regenerando con los cambios · error), nota,
  quién lo pidió, «Abrir», «✏️ Editar» y «🗑 Borrar» con confirmación (avisa si una publicación usa el video). Mientras haya
  alguno en proceso, la lista se refresca sola cada minuto.
- **Editor** (`/recortes/<id>`, solo en un recorte listo y propio, o cualquiera si sos aprobador):
  - reproductor del mp4 del recorte, con la **vista previa del estilo** de subtítulos dibujada encima (tipografía, tamaño, color,
    fondo o borde, negrita, posición: la misma traducción a CSS que usaba Streamlit, pero sobre el video real; se puede apagar);
  - **línea de tiempo** en el eje del video original, con la **tira de miniaturas** (cuadros sacados del mp4 en el navegador con
    un `<video>` oculto + `<canvas>`, sin ffmpeg ni endpoint), la **forma de onda** (el navegador decodifica el audio; si no
    puede, marcas cada segundo) y la regla de tiempos; **zoom** (botones − / + / ajustar, teclas ± y 0, Ctrl + rueda) con
    desplazamiento horizontal y la vista siguiendo al cabezal; dos **manijas grandes** arrastrables (zona de agarre de 44 px,
    burbuja con el tiempo, `role=slider`, flechas cuando tienen el foco), campos de minutos y segundos y botones ±1 s
    sincronizados; **cabezal** con el tiempo y una tijera para partir ahí mismo; lo rayado = fuera del video actual;
  - **partir** en el cabezal (botón, tijera del cabezal o tecla S), clic en un pedazo lo selecciona (borde amarillo), Supr lo
    saca, el chip de cada pedazo lo saca o lo **restaura**; «Deshacer los cortes» vuelve a un solo pedazo;
  - **atajos de teclado** (panel «Atajos» o tecla ?): Espacio, ←/→ ±1 s, Shift ±0,1 s, I/O marcan inicio y fin, S parte, Supr,
    +/−/0 zoom, Inicio/Fin; no actúan mientras se escribe en un campo;
  - **Quitar pausas largas** (casilla, igual que en Streamlit);
  - **subtítulos por línea** (solo vertical): la que suena se resalta y la lista la sigue, clic en el tiempo salta a ese momento,
    se corrige el texto, una línea vacía se saca; contador de caracteres por línea y aviso cuando puede ocupar tres renglones
    (umbral supuesto: 26 por renglón, `Subtitulos.tsx`; ajustar mirando videos reales);
  - **estilo** con tres presets («El de la Fundación» = el del equipo o el por defecto, «Negrita amarilla», «Caja negra»; solo
    se ofrecen si sus valores existen en `GET /recortes/opciones`) y los mismos controles de Streamlit;
  - un único **«Regenerar el recorte»** que manda `POST /recortes/{id}/edicion`, cuenta los cambios («3 cambios: tramo,
    pedazos, estilo»), muestra un toast y la pantalla «regenerando, ~15 min»; en celular va en una barra inferior fija.
- **Sistema**: botones con jerarquía (primario amarillo, secundario, sutil, peligro), iconos SVG propios (`componentes/Iconos.tsx`,
  sin librería), foco visible, alto mínimo 40 px (44 en pantallas táctiles), skeletons de carga, estados vacíos con ilustración y
  llamada a la acción, toasts (`componentes/Toasts.tsx`), modal accesible (Escape, foco atrapado, `componentes/Modal.tsx`),
  migas de pan.

Lo que guarda en `clips.edicion` es lo mismo que Streamlit (`inicio_ms`, `fin_ms`, `srt`, `estilo`, `quitar_pausas`) más una
clave nueva, `segmentos` = `[[a_ms, b_ms], …]` absolutos del original con los pedazos que se conservan; la cola
(`procesar_clips.py` → `recortar_clip.cortar(segmentos=)`) los pega y corre los subtítulos. Las validaciones (fin > inicio, de
2 s a 3 min, aviso si el SRT corregido era del tramo anterior) viven en la API (`api/recortes.py`); la web las repite solo para
deshabilitar el botón a tiempo.

## Correr en local

Hace falta Node 18+ y la API corriendo al lado.

1. La API, desde la raíz del repo (lee `.streamlit/secrets.toml`):

```bash
uvicorn api.main:app --port 8000
```

2. La web:

```bash
cd web && npm install && npm run dev
```

Abre http://localhost:5173. En desarrollo, Vite reenvía `/api/...` a la API (`VITE_API_PROXY`, por defecto
http://127.0.0.1:8000), así la cookie de sesión es del mismo origen y no hace falta CORS.

Otros comandos: `npm run build` (compila a `dist/`, archivos estáticos), `npm run typecheck`, `npm run preview`.

Capturas de las pantallas de cuentas (22/10): `node capturas/capturas-usuarios.mjs [escritorio|movil]` con la API simulada
(`python api/tests/servidor_simulado.py`, tabla en memoria, sin Supabase) y `npm run dev` levantados: `20-primera-vez-*`,
`21-primera-vez-paso2-*`, `22-cuenta-*`, `23-admin-usuarios-*`, `24-admin-reset-clave-*`, `25-admin-lista-blanca-*`, `26-aprobacion-*`.

Capturas de pantalla reproducibles: `node capturas/capturas.mjs <token> <id-recorte> [escritorio|movil]` (necesita
`playwright-core`, que no está en `package.json`: `npm install --no-save playwright-core`; usa el Edge o Chrome instalado; el
token es el valor de la cookie `fva_sesion` que devuelve `POST /login`). El id tiene que ser una **fila de prueba** (el modo
escritorio manda a regenerar al final; después hay que volverla a `listo` o borrarla).

## Variables (`.env`, ver `.env.example`)

| Variable | Para qué | Default |
|---|---|---|
| `VITE_API_URL` | a dónde van las llamadas a la API. Vacío = `/api` (proxy de Vite en desarrollo, o la API servida bajo `/api` en el mismo dominio) | vacío |
| `VITE_API_PROXY` | solo desarrollo: dónde corre la API local | `http://127.0.0.1:8000` |
| `VITE_STREAMLIT_URL` | la app de Streamlit en producción (links «Chat» y «Mis publicaciones») | `https://chatbotvvaa.streamlit.app` |

Las `VITE_*` se fijan al compilar (no se leen en tiempo de ejecución).

## Cómo se desplegaría (sin elegir todavía)

La web son archivos estáticos (`npm run build` → `dist/`). La API es un contenedor (`api/Dockerfile`). Dos opciones, las dos
compatibles con el plan:

- **Vercel (web) + Railway o Render (API)**: en Vercel, *Import project* → carpeta raíz `web`, framework Vite, build
  `npm run build`, salida `dist`; variables `VITE_API_URL=https://<dominio-de-la-api>` y `VITE_STREAMLIT_URL`. Como la web y la
  API quedan en dominios distintos, la API necesita `COOKIE_SAMESITE=none`, `COOKIE_SEGURA=1` y **CORS con credenciales** para
  el dominio de Vercel (no está configurado en la API: se agrega cuando se decida el dominio; son unas líneas con
  `CORSMiddleware`). Alternativa sin CORS: una *rewrite* en Vercel que sirva `/api/*` desde la API (misma mecánica que el
  proxy de Vite). Para el `BrowserRouter` hace falta la rewrite habitual de SPA (`/* → /index.html`).
- **Un solo servidor (VPS de Hostinger, recomendación del plan)**: nginx sirve `dist/` y pasa `/api/` a uvicorn; un solo
  dominio, cookie `lax`, sin CORS.

La API se despliega como dice `api/README.md` (Railway o Render, Dockerfile desde la raíz). Nada de esto está hecho: hoy solo
corre en local.

## Lo que quedó fuera / decisiones pendientes

- **Vista previa «real»** (un cuadro del video con los subtítulos quemados por libass, `GET /recortes/{id}/cuadro` del plan):
  no está; la vista previa es CSS sobre el video, que además ya tiene sus subtítulos quemados (se ven los dos). Para una previa
  limpia hace falta la copia liviana sin subtítulos que el plan prevé subir desde la cola (decisión: espacio en WordPress).
- **Mover las manijas fuera del tramo actual** se puede (se guarda y la cola corta del original), pero no se ve en el
  reproductor hasta regenerar: misma limitación del plan (hace falta la copia con margen).
- **Tiempos de los subtítulos**: se edita el texto, no el momento en que entra y sale (como en Streamlit).
- **Publicar** desde la tarjeta: no está (fase 3); «Mis publicaciones» y el chat abren Streamlit.
- **Estilo por defecto del equipo**: la API lo expone (`GET/PUT /recortes/estilo-defecto`), la web todavía no tiene la pantalla
  de admin (sigue en Panel admin → Clips de Streamlit).
- **Login con Google**: funciona contra la API local (sin probar con una cuenta real); falta el mapeo usuario ↔ email del historial
  y agregar el dominio de producción a los orígenes autorizados.
- **Hosting y dominio**: Vercel + Railway/Render o el VPS; CORS y `COOKIE_SAMESITE` dependen de eso.
- **Idiomas**: la pantalla está solo en español (las cuentas en/de del plan quedan para la fase 2).
