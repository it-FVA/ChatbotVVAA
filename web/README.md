# Interfaz web propia (fase 1: «Mis recortes» · fase 2: el chat · fase 3: Publicar, Mis publicaciones y Aprobación, 22/10)

## Publicar, Mis publicaciones y Aprobación (fase 3, 22/10)

Las tres pantallas que vivían en Streamlit (`publicar_ui.py`), con la misma lógica de negocio en la API (`api/publicar_rutas.py`) y mejor UX.
Capturas `capturas/30`–`34` (escritorio y celular).

- **Publicar** (`/publicar`, `src/paginas/Publicar.tsx`): los tres pasos de Streamlit pero **un paso visible a la vez** con el resumen de los
  anteriores y «Editar». 1 · Qué se publica: canal (Instagram, Facebook, Blogpost, YouTube) con su modo a la vista, título, texto con contador.
  2 · Foto y diseño: frase sobre la imagen, banco de WordPress (busca sola con la sugerencia del bot o el formato del canal), «Otra imagen» (URL
  o subir un archivo, que va al banco), formato, logo y posición, firma, tipografía, peso, posición y alineación, «Publicar así»; con un
  recorte: reel/historia. 3 · Cuándo y enviar: «Cuanto antes» o «Programar» con día, hora (Argentina) y atajos, el aviso de qué va a pasar
  (`util/publicar.aviso`, = `publicar_ui._aviso`), y **un botón principal según el rol**: «Enviar a aprobación» (creadores) o «Publicar en
  <canal>» (quien publica directo, con «Entiendo que esto publica de verdad» en modo real); secundarios «Ver simulado» y «Guardar borrador».
  A la derecha (abajo en celular) la **vista previa en vivo** (`componentes/VistaPrevia.tsx`): Instagram feed cuadrado/vertical, historia 9:16,
  reel; Facebook (texto arriba, foto abajo); Blogpost (foto destacada, título, cuerpo con markdown/HTML); YouTube (reproductor, título,
  descripción). La foto con la frase la compone la API (`POST /publicar/componer`) con un retardo de medio segundo al cambiar cualquier
  control. Al terminar, un panel de resultado con el aviso, los links (posteo, entrada o borrador de WordPress) y «Así quedaría».
  Entradas: «Publicar» en la barra (pieza nueva), desde el chat (la pieza propuesta llega en `location.state`), desde un recorte listo
  (`?recorte=<id>`: video precargado, Instagram si es vertical) y desde un borrador (`?borrador=<id>`).
- **Mis publicaciones** (`/publicaciones`, `src/paginas/Publicaciones.tsx`): solapas Todas / Pendientes / Aprobadas / Publicadas / Borradores /
  Rechazadas / Pruebas con conteos; tarjetas con miniatura (foto o video), estado, canal y formato, fecha de creación, «sale el», quién aprobó o
  rechazó y la nota, error; acciones Retomar (borradores; los de newsletter abren Streamlit), Ver el posteo / la entrada, Abrir en WordPress,
  Descargar HTML (newsletter) y Eliminar con confirmación (solo lo eliminable).
- **Aprobación** (`/aprobacion`, aprobadores, `src/paginas/Aprobacion.tsx`), con menú propio como Administración: **Para aprobar** (vista previa
  completa del canal, texto, fecha y hora editables sugeridas en hora Argentina, nota, «Aprobar y programar» / «Rechazar»; newsletter en un
  iframe con «Aprobar (queda listo para Perfit)» y «Descargar HTML»), **En cola** (cancelar), **Registro** con buscador, **Papelera** de
  conversaciones (restaurar) y **Clips** (la pantalla de recortes embebida con «Todos» fijo; los admins fijan ahí el **estilo por defecto** de
  los subtítulos). El contador de pendientes aparece en el menú. Frase del día y Dashboard siguen en Streamlit (link para admins).
- **Chat**: el recuadro de la pieza propuesta ahora muestra el resumen (canal, título, frase para la imagen, foto sugerida, cuándo, texto) y
  **«Abrir en Publicar»** (precargado) más «Guardar borrador» como atajo. **Recortes**: cada recorte listo tiene **«Publicar»**.
- **Barra**: Chat, Publicar, Mis publicaciones, Mis recortes, Newsletter (Streamlit), Aprobación (aprobadores), Administración y Frase del día
  (Streamlit) para admins.
- Fuera de esta fase: subir un archivo de video para YouTube (solo recortes), Newsletter y Frase del día en la web, Proyectos, Dashboard.
# Interfaz web propia (fase 1: «Mis recortes» con editor visual · revisión UX del 21/10 · usuarios y administración del 22/10)

Es la interfaz que reemplaza a Streamlit (decisión de Franco del 22/10: la web es la aplicación definitiva; Streamlit queda de
respaldo hasta el traspaso; plan en `fva-transcripcion/analisis/plan-interfaz-propia-2026-10.md`). Habla con la API de `api/` y
no toca el cerebro (`nucleo.py`, `db.py`). Las capturas de cómo se ve están en `capturas/` (escritorio 1366 px y celular 375 px):
`00`–`11` la fase 1 (login, lista, editor de recortes), `20`–`24` el chat (vacío, respuesta con fuentes, tarjeta de video con el
recorte en proceso, pieza propuesta, cajón de conversaciones en celular). La revisión de UX/UI de los recortes está en `UX-REVISION.md`.

## El chat (fase 2, 22/10)

`/chat` y `/chat/<id>` (`src/paginas/Chat.tsx`, estilos en `src/chat.css`). Paridad con el chat de Streamlit (`app.py`) y lo que
Streamlit no podía hacer:

- **Conversaciones** (`componentes/ListaConversaciones.tsx`): lista de la persona agrupada por Hoy / Ayer / Últimos 7 días /
  Anteriores con fecha relativa, buscador, «Nueva conversación», renombrar en el lugar (lápiz, Enter guarda, Esc cancela) y borrar
  con confirmación; el borrado va a la papelera de `db.py` (30 días) y durante 12 s hay «Deshacer» (`POST …/restaurar`). Es un
  componente aparte y cada ítem lleva `data-id`: la próxima etapa (carpetas / proyectos con arrastrar y soltar) agrupa la lista sin
  rehacer el chat. En celular es un cajón (botón «Conversaciones», Esc o el velo lo cierran).
- **Mensajes** (`componentes/Mensaje.tsx`): markdown con `marked` + `DOMPurify` (títulos, listas, citas, tablas, links que abren
  aparte); la respuesta llega en **streaming** (SSE por `fetch`, `src/apiChat.ts`) con el estado «Pensando… / Buscando en el
  material… / Escribiendo…» y un cursor; «Detener» corta la respuesta (ese intercambio no queda guardado, la pantalla lo avisa).
  Enter envía, Shift+Enter hace una línea nueva; el cuadro crece con el texto. Autoscroll solo si la persona está abajo; si subió,
  aparece un botón para ir al final. Al abrir una conversación se carga el historial completo con sus fuentes y piezas.
- **Fuentes** (`componentes/Fuentes.tsx`): plegable «Fuentes (n) · k citadas en la respuesta» (abierto salvo que haya pieza, como
  Streamlit), tarjetas compactas (tag, autor, título, cita de dos líneas que se despliega al pasar el mouse o tocarla, «Ver fuente»),
  las citadas resaltadas en verde; en los videos la miniatura de YouTube con el tramo y los botones «Pedir el recorte» / «Pedir en
  vertical» (`POST /recortes`) → «recorte en proceso» → «Ver el recorte» + «Editar» (abre el editor de `/recortes/<id>`). Mientras
  haya alguno en proceso, cada minuto consulta `GET /conversaciones/<id>/recortes` y actualiza las tarjetas.
- **Pieza propuesta** (`componentes/PiezaPropuesta.tsx`): cuando el bot llama a `proponer_publicacion`, debajo de la respuesta el
  recuadro con canal (chips), modo del canal (`GET /publicaciones/modos`), título, texto, texto sobre la imagen, fotos del banco de
  WordPress (`GET /banco`, busca sola con la sugerencia del bot), fecha y hora opcionales, y los botones **Enviar a aprobación**
  (`POST /publicaciones/a-aprobar`; deshabilitado con el motivo si el canal no lo permite) y **Guardar borrador**
  (`POST /publicaciones/borrador`), más el link a «Mis publicaciones» (por ahora Streamlit). Una pieza `newsletter` manda al editor
  de Newsletter de Streamlit.
- **Descargas**: «Word» en las respuestas de 600 caracteres o más y «Excel» si tienen tablas (`GET …/mensajes/{n}/docx|xlsx`),
  con el nombre de la conversación.
- **Idioma de la cuenta** (`GET /yo` → `idioma`): los textos de la pantalla en es/en/de (`src/textos.ts`) y las etiquetas de las
  tarjetas traducidas (ARTICLE/BOOK, ARTIKEL/BUCH) con la traducción de título y cita que manda la API. Los botones de recorte y
  el recuadro de la pieza se muestran solo en español, como en Streamlit.
- **Si la API duerme** (Render plan free): antes de mandar, si hace más de 10 min que no hablamos con ella, pega a `/salud`; si no
  contesta avisa «La API está despertando: puede tardar un minuto» y reintenta cada 5 s hasta 2 min; recién entonces manda el mensaje.
- **Atajos**: `/` enfoca el cuadro, Esc cierra el cajón y los modales. Accesibilidad básica: `role=log` con `aria-live`, botones
  con nombre, foco visible, tamaños táctiles.

Capturas del chat: `node capturas/capturas-chat.mjs <token> <id-conversacion> [escritorio|movil]` (mismo mecanismo que
`capturas.mjs`; solo mira, no manda mensajes ni pide recortes).
# Interfaz web propia (fase 1: «Mis recortes» con editor visual · revisión UX del 21/10 · pedazos como piezas, 22/10)

Es la primera pantalla de la interfaz que va a reemplazar a Streamlit (plan en
`fva-transcripcion/analisis/plan-interfaz-propia-2026-10.md`). Habla con la API de `api/` (fase 0 + los endpoints de
recortes de esta fase) y no toca Streamlit, que sigue en producción. Las capturas de cómo se ve están en `capturas/`
(escritorio 1366 px y celular 375 px): login, lista (cargando, vacía, normal), editor antes y después de editar, zoom de la
línea de tiempo, atajos de teclado, confirmación de borrado, pantalla de «regenerando», barra inferior en celular y (22/10) la
secuencia de salida con tres pedazos (12), un bloque arrastrándose con la marca de inserción (13) y «Ver secuencia» andando (14).
La revisión de UX/UI que motivó la segunda vuelta (hallazgos, referencias con links, qué se cambió y qué quedó) está en
`UX-REVISION.md`; la sección «Pedazos como piezas» de ese documento cuenta el diseño de los dos carriles.

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
- **Barra lateral**: «Chat» (fase 2), «Publicar», «Mis publicaciones» (fase 3), «Mis recortes» y «Newsletter» (abre Streamlit, URL en
  `VITE_STREAMLIT_URL`). En celular se vuelve una barra arriba. La página de inicio es el chat.
- **Recortes**: solapas «Mis recortes», «👥 Del equipo» (los listos de otras personas: abrir, sin editar ni borrar) y
  «Todos» para aprobadores; buscador por título, video o quién lo pidió; cada tarjeta con el video (o la miniatura de
  YouTube si todavía no está), formato, tramo, duración, estado (listo · en proceso · regenerando con los cambios · error), nota,
  quién lo pidió, «Abrir», «✏️ Editar» y «🗑 Borrar» con confirmación (avisa si una publicación usa el video). Mientras haya
  alguno en proceso, la lista se refresca sola cada minuto.
- **Editor** (`/recortes/<id>`, solo en un recorte listo y propio, o cualquiera si sos aprobador):
  - reproductor del mp4 del recorte, con la **vista previa del estilo** de subtítulos dibujada encima (tipografía, tamaño, color,
    fondo o borde, negrita, posición: la misma traducción a CSS que usaba Streamlit, pero sobre el video real; se puede apagar);
  - **línea de tiempo en dos carriles** (`componentes/LineaTiempo.tsx`; las operaciones sobre los pedazos, en `util/piezas.ts`):
    - arriba, el **original**, en el eje del video original: la **tira de miniaturas** (cuadros sacados del mp4 en el navegador
      con un `<video>` oculto + `<canvas>`, sin ffmpeg ni endpoint), la **forma de onda** (el navegador decodifica el audio; si
      no puede, marcas cada segundo) y la regla de tiempos; **zoom** (botones − / + / ajustar, teclas ± y 0, Ctrl + rueda) con
      desplazamiento horizontal y la vista siguiendo al cabezal; dos **manijas grandes** del tramo (zona de agarre de 44 px,
      burbuja con el tiempo, `role=slider`, flechas cuando tienen el foco), campos de minutos y segundos y botones ±1 s
      sincronizados; **cabezal** con el tiempo y una tijera para partir ahí mismo; lo rayado = fuera del video actual; cada
      pedazo conservado lleva el **número** que ocupa en la secuencia, los sacados quedan rayados con un chip «Restaurar»;
    - abajo, la **secuencia de salida** (22/10, pedido de Franco: «cada vez que hacemos Split tenemos que tratarlo como un canvas
      para poder mover las piezas»): un **bloque por pedazo conservado**, contiguos, en el orden en que salen en el video final,
      cada uno con su miniatura, su duración, **dos manijas amarillas** en los bordes que recortan ESE pedazo sobre el original
      (pueden comerse lo sacado de al lado, nunca pisar a otro pedazo conservado; mínimo 0,5 s), un **agarre para arrastrarlo** a
      otro lugar (se suelta entre dos bloques, con una marca roja de inserción; con mouse se arrastra desde cualquier parte del
      bloque, en touch desde el agarre para no bloquear el desplazamiento) y botones **◀ ▶ ×** (un lugar antes / después, sacar);
      un cabezal rojo muestra dónde está el reproductor dentro de la secuencia;
  - **partir** el pedazo bajo el cabezal (botón, tijera del cabezal o tecla S), clic en un pedazo o en su bloque lo selecciona
    (borde amarillo), Supr lo saca, «Restaurar» lo vuelve a agregar en su lugar natural de la secuencia; «Deshacer los cortes»
    vuelve a un solo pedazo; **«Ver secuencia»** (o tecla P) reproduce los pedazos en el orden elegido saltando lo sacado (el
    reproductor sigue mostrando el video actual: lo que quedó fuera de él se saltea); «Sale 48,0 s» cuenta lo que va a durar;
  - **atajos de teclado** (panel «Atajos» o tecla ?): Espacio, P (ver secuencia), ←/→ ±1 s, Shift ±0,1 s, I/O marcan inicio y
    fin, S parte, Supr saca, [ y ] mueven el pedazo seleccionado en la secuencia, +/−/0 zoom, Inicio/Fin; no actúan mientras se
    escribe en un campo;
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
clave nueva, `segmentos` = `[[a_ms, b_ms], …]` absolutos del original con los pedazos que se conservan, **en el orden en que
salen** (22/10): si el orden es el del original, la cola (`procesar_clips.py` → `recortar_clip.cortar(segmentos=)`) los pega
como antes (select/aselect); si no, recorta cada pedazo y los concatena en ese orden (`recortar_clip.concatenar_tramos`,
trim + concat con re-encode, audio incluido) y rearma los subtítulos desde las palabras pedazo por pedazo con los tiempos
corridos al orden nuevo; un SRT corregido se descarta con aviso (misma regla que al cambiar el tramo). Dos pedazos consecutivos
en la lista y contiguos en el original se unen (partir sin sacar ni mover no cambia nada). Las validaciones (fin > inicio, de
2 s a 3 min, pedazos sin solaparse, cada uno de al menos 0,5 s, el total entre 2 s y 3 min, aviso si el SRT corregido era de
otro video) viven en la API (`api/recortes.py`); la web las repite solo para deshabilitar el botón a tiempo.

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
Capturas de pantalla reproducibles (24, las tres últimas del 22/10): `node capturas/capturas.mjs <token> <id-recorte> [escritorio|movil]` (necesita
`playwright-core`, que no está en `package.json`: `npm install --no-save playwright-core`; usa el Edge o Chrome instalado; el
token es el valor de la cookie `fva_sesion` que devuelve `POST /login`). El id tiene que ser una **fila de prueba** (el modo
escritorio manda a regenerar al final; después hay que volverla a `listo` o borrarla).

## Variables (`.env`, ver `.env.example`)

| Variable | Para qué | Default |
|---|---|---|
| `VITE_API_URL` | a dónde van las llamadas a la API. Vacío = `/api` (proxy de Vite en desarrollo, o la API servida bajo `/api` en el mismo dominio) | vacío |
| `VITE_API_PROXY` | solo desarrollo: dónde corre la API local | `http://127.0.0.1:8000` |
| `VITE_STREAMLIT_URL` | la app de Streamlit en producción (link «Mis publicaciones», editor de Newsletter) | `https://chatbotvvaa.streamlit.app` |

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
- **Publicar** desde la tarjeta o desde el chat en real: no está (fase 3). Desde el chat la pieza se guarda como borrador o se manda a
  aprobación; la foto con la frase encima, el logo, el diseño y subir archivos siguen en Publicar de Streamlit. «Mis publicaciones»,
  el panel de aprobación y el newsletter abren Streamlit.
- **Chat**: «📣 Publicar el recorte» desde la tarjeta de video (fase 3); el bot puede pedir recortes solo (`pedir_recorte`) y la
  tarjeta lo refleja al recargar o en el próximo refresco; las carpetas / proyectos de conversaciones son la próxima etapa.
- **Estilo por defecto del equipo**: la API lo expone (`GET/PUT /recortes/estilo-defecto`), la web todavía no tiene la pantalla
  de admin (sigue en Panel admin → Clips de Streamlit).
- **Login con Google**: funciona contra la API local (sin probar con una cuenta real); falta el mapeo usuario ↔ email del historial
  y agregar el dominio de producción a los orígenes autorizados.
- **Hosting y dominio**: Vercel + Railway/Render o el VPS; CORS y `COOKIE_SAMESITE` dependen de eso.
- **Idiomas**: el chat está en es/en/de; la pantalla de recortes y el login, solo en español.
