# Métricas (Administración → pestaña «Métricas»): contrato API ↔ web

Pedido de Beto (8/11): «que la app sea el centro de métricas de evolución de campañas». Decisión de Franco (8/11): alternativa E del
análisis `fva-transcripcion/analisis/analiticas-por-api-2026-11.md`: un panel único con una tarjeta por canal (números por API donde
hay, enlace directo y carga a mano donde no) y un botón «¿Cómo le fue a esta campaña?» que resume con IA. Vive en
`/administracion/metricas`. **El ítem del menú queda OCULTO** (constante `MOSTRAR_METRICAS = false` en `Administracion.tsx`) hasta que
Franco pida destaparlo; la ruta directa funciona igual.

Dos preguntas, dos mitades de la pantalla:

1. **Cuánto hicimos** (sale de nuestra base, sin APIs): campañas = Proyectos (`proyectos` + `proyecto_items` tipo `pieza` →
   `publicaciones`), piezas por canal y por estado, línea de tiempo. Las piezas que no están en ningún proyecto van en «Sin campaña».
2. **Cuánto llegó** (depende de cada plataforma): Instagram y Facebook por API (ya tenemos tokens; Instagram puede necesitar el
   permiso `instagram_manage_insights`: si Meta lo rechaza, se informa); YouTube, Perfit, sitio y WhatsApp: enlace a la plataforma +
   campo para anotar a mano.

## Tabla nueva: `metricas` (migración `api/migraciones/20261108_1200_metricas.sql`, la corre Franco a mano)

```sql
create table if not exists metricas (
  id uuid primary key default gen_random_uuid(),
  creado timestamptz not null default now(),
  ambito text not null check (ambito in ('pieza', 'canal', 'resumen')),
  ref text not null,                 -- pieza: publicaciones.id · canal: clave del canal (instagram, facebook…) · resumen: proyecto_id o 'sueltas'
  canal text,                        -- en pieza y canal, siempre; en resumen, null
  fuente text not null check (fuente in ('api', 'manual', 'ia')),
  periodo_desde date,                -- canal: qué período cubren los números (manual: lo que cargó la persona; api: la ventana pedida)
  periodo_hasta date,
  datos jsonb not null default '{}', -- ver «datos normalizados»
  nota text,
  por text,                          -- quién cargó (usuario) o 'cola' / 'api' / 'ia'
  capturado timestamptz not null default now()
);
create index if not exists metricas_ref_idx on metricas (ambito, ref, fuente, capturado desc);
alter table metricas enable row level security;
-- + política cola_todo para el rol cola, igual que banco_imagenes (20261105_1900_banco_imagenes_rls.sql)
```

Se guarda **cada captura** (historia); «la última» de cada (ambito, ref, fuente) es la que se muestra.

### Datos normalizados (`datos` de pieza y canal)

Claves comunes a todos los canales, todas opcionales, números enteros. Lo que la plataforma no da, no está (nunca 0 inventado).

| clave | qué es |
|---|---|
| `alcance` | cuentas/personas distintas alcanzadas |
| `vistas` | vistas o impresiones |
| `me_gusta` | likes / reacciones totales |
| `comentarios` | |
| `guardados` | |
| `compartidos` | |
| `clics` | clics en el link / en el posteo |
| `interacciones` | total de interacciones si la plataforma lo da |
| `seguidores` | seguidores totales (ámbito canal) |
| `seguidores_nuevos` | altas en el período (ámbito canal) |
| `visitas` / `visitantes` | sitio web |
| `enviados` / `aperturas` | mail |
| `respuestas` | historias |

Además: `crudo` (dict con lo que devolvió la plataforma, tal cual, para no perder nada), `errores` (lista de textos: qué métrica no
se pudo traer y por qué, p. ej. «Meta rechazó `saved`: (#100) …»). En `resumen` (fuente `ia`): `{texto, fuentes: [str], falto: [str],
comparado_con: str|null, modelo: str}`.

## Rutas (`api/metricas_rutas.py`, prefijo `/admin/metricas`, todas con `Depends(auth.admin)`)

### `GET /admin/metricas/campanas?dias=90` | `?mes=AAAA-MM`

Período como en `admin_rutas.periodo()` (por defecto 90 días). Una pieza «cae» en el período por su fecha efectiva: `procesado_en`,
si no `fecha_programada`, si no `creado`.

```jsonc
{
  "periodo": { "tipo": "dias", "dias": 90, "desde": "...", "hasta": null, "texto": "últimos 90 días" },
  "campanas": [
    {
      "id": "uuid", "nombre": "Lo común nos convoca", "emoji": "🤝", "color": "#…", "dueno": "pato", "creado": "iso",
      "piezas_total": 3,
      "por_canal": { "instagram": { "publicada": 1, "programada": 1, "en_aprobacion": 1, "borrador": 0, "prueba": 0, "no_salio": 0 } },
      "por_estado": { "publicada": 1, "programada": 1, "en_aprobacion": 1, "borrador": 0, "prueba": 0, "no_salio": 0 },
      "primera": "iso|null", "ultima": "iso|null",
      "piezas": [
        { "id": "uuid", "canal": "instagram", "canal_texto": "Instagram", "titulo": "…", "estado": "publicada", "estado_grupo": "publicada",
          "fecha": "iso", "ver_url": "https://…|null", "formato": "historia|cuadrado|reel|carrusel|null", "usuario": "pato", "modo": "real|simulado|…",
          "metricas": { "alcance": 120, "me_gusta": 14, "fuente": "api", "capturado": "iso" } }
      ]
    }
  ],
  "sueltas": { "id": "sueltas", "nombre": "Sin campaña", "emoji": null, "color": null, "dueno": null, "creado": null, "piezas_total": 0, "por_canal": {}, "por_estado": {}, "primera": null, "ultima": null, "piezas": [] },
  "totales": { "piezas": 12, "publicada": 5, "programada": 2, "en_aprobacion": 3, "borrador": 1, "prueba": 1, "no_salio": 0, "por_canal": { "instagram": 7, "facebook": 5 } }
}
```

`estado_grupo` (único lugar donde se define: `metricas.GRUPO_ESTADO`):
`publicada` ← publicada · `programada` ← pendiente, lista, procesando, enviando · `en_aprobacion` ← a_aprobar · `borrador` ← borrador ·
`prueba` ← simulada, prueba, registrada · `no_salio` ← rechazada, cancelada, error. Cualquier otro estado → `prueba`.
Las campañas van ordenadas por `ultima` descendente; adentro, las piezas por `fecha` descendente. Campañas sin piezas en el período
igual aparecen (con `piezas: []`) si tienen piezas en total; subproyectos cuentan dentro del padre (`padre_id`) y además aparecen
como propios: NO. Simplificación del 8/11: cada proyecto es una campaña, sin anidar; las piezas de un subproyecto cuentan para el
subproyecto y no para el padre.

### `GET /admin/metricas/canales`

```jsonc
{
  "actualizado": "iso|null",          // última captura por API de cualquier canal
  "canales": [
    {
      "clave": "instagram", "texto": "Instagram", "icono": "instagram", "modo": "real", "configurado": true,
      "api": "disponible" | "sin_permiso" | "no_hay" | "pendiente" | "error",
      "nota_api": "texto corto: por qué no hay API o qué falta (p. ej. «Falta el permiso instagram_manage_insights en el token»)",
      "enlace": "https://business.facebook.com/latest/insights/overview", "enlace_texto": "Ver en Meta Business Suite",
      "conectado": false, "conectar_url": null,   // (8/11) solo el sitio los usa: ¿hay token de WordPress.com? y la ruta de la API que lleva a conectarlo («/admin/metricas/wordpress/autorizar»; la web le antepone la base de la API); null si no hay app registrada
      "ultima": { "datos": { "alcance": 1200, "seguidores": 3400, "crudo": {…}, "errores": [] }, "periodo_desde": "2026-10-10", "periodo_hasta": "2026-11-08", "capturado": "iso", "fuente": "api" } | null,
      "manual": { "datos": { "alcance": 1500 }, "periodo_desde": "…", "periodo_hasta": "…", "capturado": "iso", "nota": "…", "por": "franco" } | null
    }
  ]
}
```

Canales listados (en este orden, todos siempre): instagram, facebook, youtube, mail (Newsletter / Frase por mail), home + wordpress
juntos como `sitio` (texto «Sitio web»), whatsapp. `api`:
- instagram, facebook: `disponible` si hay token; `sin_permiso` si Meta devolvió error de permiso en la última captura; `error` si otro
  error; `pendiente` si nunca se capturó.
- youtube (8/11, Franco): ya no es `pendiente` por defecto. `disponible` si hay token y la última captura trajo números; `sin_permiso` si
  el token no tiene el permiso de YouTube Analytics (nota: «Falta autorizar la lectura de estadísticas de YouTube…»; igual vienen las
  vistas, suscriptores, me gusta y comentarios de la Data API); `error` otro; `pendiente` si nunca se capturó. `POST /actualizar` suma la
  clave `youtube` con la misma forma `{ok, piezas, error}`. Módulo: `metricas_youtube.py`.
- mail: `no_hay`, nota «Perfit: los reportes se ven en la plataforma; la API de métricas por campaña está sin confirmar».
- sitio (8/11, Franco: WordPress.com): `disponible` si hay token guardado y la última captura trajo números; `pendiente` si hay app registrada
  (`WPCOM_CLIENT_ID` y `WPCOM_CLIENT_SECRET`) pero falta conectar (nota «Falta conectar con WordPress.com (un clic)») o si está conectado y
  nunca se capturó; `error` si WordPress.com ya no acepta el token (nota «WordPress.com ya no acepta la conexión: hay que volver a conectar (un
  clic)») u otro; `no_hay` sin app registrada, con la nota de antes («WordPress.com pide autorizar una app propia para leer las estadísticas;
  por ahora, el enlace»). Módulo: `metricas_wordpress.py`.
- whatsapp: `no_hay`, nota «WhatsApp no da métricas de grupos».

Enlaces: Instagram y Facebook → `https://business.facebook.com/latest/insights/overview`; YouTube → `https://studio.youtube.com/`
(«Abrir YouTube Studio»; 8/11 v2: los textos de enlace son «Ver en Perfit», «Ver en WordPress.com» y «Abrir YouTube Studio»); mail → `https://app.myperfit.com/`; sitio → `https://wordpress.com/stats/day/<WP_SITE>`;
whatsapp → null.

### `POST /admin/metricas/actualizar`

Captura ahora por API (Instagram, Facebook, YouTube y —8/11— el sitio): cuenta (últimos 28 días) + cada pieza `publicada` en modo `real` de los últimos 60 días
que tenga id de la plataforma en `resultado.ultimo.id` (o `resultado.id`). Guarda filas `fuente='api'`. Responde:

```jsonc
{ "capturado": "iso", "instagram": { "ok": true, "piezas": 4, "error": null }, "facebook": { "ok": false, "piezas": 0, "error": "Falta el permiso read_insights" },
  "youtube": { "ok": true, "piezas": 2, "error": null }, "sitio": { "ok": false, "piezas": 0, "error": "Falta conectar con WordPress.com (un clic)" } }
```

`sitio` (8/11): cuenta de 28 días en una fila `ambito: "canal", ref: "sitio"` con `visitas`, `visitantes`, `me_gusta`, `comentarios` y en el `crudo` el
top de 5 entradas, 5 referentes y 5 clics; y cada entrada de WordPress `publicada` en modo `real` de los últimos 60 días en una fila `ambito: "pieza"`
con `visitas` (OJO: es el total desde que se publicó, no el de un período; el `crudo` lo dice). Solo necesita el token guardado, así que también corre desde la cola.

Nunca lanza 500 por un error de Meta: lo devuelve en `error`. La cola (`procesar_cola.py`) llama a `metricas.capturar_si_toca(cfg)`
al final de cada pasada: captura si pasó más de 1 hora desde la última (config `metricas_ultima_captura`), para no perder las
historias, cuyas métricas Instagram borra a las 24 h.

### `PUT /admin/metricas/manual`

Body: `{ "ambito": "canal" | "pieza", "ref": "instagram" | "<publicacion id>", "canal": "instagram", "periodo_desde": "AAAA-MM-DD|null",
"periodo_hasta": "AAAA-MM-DD|null", "datos": { "alcance": 1500, "clics": 30 }, "nota": "texto|null" }`.
Valida: ambito y claves de `datos` dentro de las normalizadas, números enteros ≥ 0, al menos una clave. Guarda `fuente='manual'`,
`por=usuario`. Devuelve la fila guardada (`{id, ambito, ref, canal, datos, periodo_desde, periodo_hasta, nota, por, capturado}`).
Registra en `usuarios_cambios` como el resto de Administración (clave `metricas_manual:<ref>`).

### `GET /admin/metricas/resumen/{ref}` y `POST /admin/metricas/resumen`

`ref` = id de proyecto o `sueltas`. GET devuelve el último resumen guardado (fuente `ia`) o `null`. POST body `{ "ref": "...",
"dias": 90 }` genera uno nuevo con OpenAI (modelo auxiliar, el mismo que `newsletter.redactar`), lo guarda como `ambito='resumen'` y
devuelve:

```jsonc
{ "ref": "uuid", "nombre": "Lo común nos convoca", "texto": "markdown corto (≤ 250 palabras)", "fuentes": ["Instagram (API, 8/11)", "Facebook (cargado a mano por Franco, 1/11)"],
  "falto": ["YouTube: sin datos", "2 piezas publicadas sin métricas"], "comparado_con": "Polarizaciones|null", "modelo": "gpt-…", "capturado": "iso" }
```

El prompt lleva: las piezas de la campaña (canal, formato, fecha, título, estado) con sus métricas y la fuente de cada número; la
campaña anterior del mismo dueño (la de `ultima` inmediatamente anterior) con sus totales, si hay; y la guía de canales
(`fuentes/guia_canales.md`, texto de Beto) como criterio de qué se espera de cada formato. Reglas del texto: rioplatense, sin jerga,
decir siempre de dónde sale cada número y qué faltó; no inventar nada que no esté en los datos; terminar con una o dos sugerencias
para la próxima campaña apoyadas en la guía. Si no hay ninguna métrica (ni API ni manual), igual responde: resume lo hecho y dice
qué habría que cargar. Registra el uso en `uso_openai` con `que='auxiliar'` y `usuario` = quien pidió.

## Web (`web/src/paginas/admin/Metricas.tsx`, ruta `/administracion/metricas`)

- Cabecera de sección: «Métricas» con el selector de período de Dashboard (7 / 28 / 90 días o un mes) que alimenta `campanas`.
- **Cuánto llegó**: grilla de tarjetas por canal (`canales`). Cada tarjeta: ícono y nombre, chip de estado (`api`), números grandes
  de `ultima.datos` (hasta 4: alcance, vistas, interacciones o me_gusta, seguidores) con «capturado hace…», los de `manual` abajo
  («anotado por X el …») si hay, botón/enlace externo (`enlace`), botón «Anotar números» que abre un formulario (período, campos
  normalizados, nota → `PUT manual`). Botón arriba a la derecha «Actualizar desde Instagram y Facebook» (`POST actualizar`), con
  «última actualización hace…». Errores de Meta se muestran en la tarjeta con el texto de `nota_api`, nunca un 500 pelado.
- **Cuánto hicimos**: una tarjeta por campaña (`campanas` + `sueltas` al final si tiene piezas): nombre con emoji/color, totales por
  estado como chips (ChipEstado ya existente), mini tabla por canal, lista de piezas plegable (título, canal, estado, fecha, link
  «ver», métricas en una línea si hay), y el botón **«¿Cómo le fue?»** que llama a `POST resumen` y muestra el texto (markdown con
  `marked` + DOMPurify como en el chat), las fuentes y lo que faltó. Si ya había un resumen guardado (`GET resumen/{ref}`), se
  muestra con su fecha y el botón dice «Volver a resumir».
- Estados vacíos con `EstadoVacio`; cargando con `Cargando`; errores con `AvisoError`.
- Ayuda: `definirAyuda("metricas", …)` (≤ 6 pasos, ≤ 120 palabras) con `data-ayuda="metricas.<id>"` en los elementos.
- Menú: entrada `{ a: "/administracion/metricas", texto: "Métricas", icono: "grafico" }` en `MENU`, filtrada por `MOSTRAR_METRICAS`
  (false). Comentario: «(8/11, Franco) oculto hasta que lo pida; la URL directa funciona».
- Tipos: en `adminApi.ts` a mano según este contrato, con comentario «provisional: se reemplaza por tiposApi.d.ts tras `npm run tipos`».
- Vocabulario de usuario: «campaña» (no proyecto), «alcance», «vistas», «anotado a mano», «desde la plataforma». Nada de «API»,
  «endpoint», «token» en pantalla: en su lugar «la conexión con Instagram», «falta un permiso en la conexión».

## Agregado del 8/11 (Franco, 12:30): el asesor de campañas

El botón «¿Cómo le fue?» pasa a ser un caso particular de un **asesor de campañas con el que se conversa**. Conoce todo lo que esta
pestaña muestra (campañas, piezas, métricas por API y anotadas a mano, la guía de canales) y responde preguntas libres: «¿cómo nos
fue?», «¿esta campaña rindió mejor que la anterior?», «¿qué canal conviene para la próxima?». Es el asesor de marketing del equipo.

### API

- `GET /admin/metricas/asesor/apertura?dias=90` → el mensaje proactivo con que recibe al abrir la pestaña: resumen del momento
  (qué pasó en los últimos 7 días, qué campaña se mueve, qué números faltan cargar, una sugerencia). Se genera **una vez por día**
  (se guarda como `ambito='resumen'`, `ref='apertura'`, fuente `ia`; si la última es de hoy, hora Argentina, se devuelve esa sin
  llamar al modelo). Respuesta: `{ "texto": "markdown corto", "fuentes": [...], "falto": [...], "capturado": "iso", "nuevo": true|false }`.
- `POST /admin/metricas/asesor` body `{ "mensajes": [{ "rol": "usuario" | "asesor", "texto": "..." }], "dias": 90 }` (los últimos
  hasta 12 mensajes de la conversación, el último es del usuario) → `{ "texto": "markdown", "fuentes": [...], "falto": [...] }`.
  Contexto que recibe el modelo en el system prompt: la salida completa de `campanas(periodo)` compactada (por campaña: nombre,
  dueño, fechas, totales por canal y estado, y por pieza: canal, formato, fecha, estado, métricas con fuente), la de `canales_estado`
  (números de cuenta por canal con fuente y período), y la guía de canales. Reglas: las mismas del resumen (rioplatense, sin jerga,
  cada número con su fuente, decir qué falta, no inventar, comparar contra algo cuando se pueda, sugerencias apoyadas en la guía).
  Registra el uso con `que='auxiliar'`. No se guarda la conversación (vive en la pantalla). Si falta `OPENAI_API_KEY` → 503 como el resumen.
- `POST /admin/metricas/resumen` se mantiene (el botón por campaña): internamente es una pregunta fija al mismo asesor
  («¿Cómo le fue a la campaña X?») con el mismo contexto. `metricas_resumen.py` → renombrar a `metricas_asesor.py` con una función
  `responder(mensajes, periodo, usuario)` y las dos envolturas (`apertura`, `resumen_campana`).

### Web

- Panel «Tu asesor de campañas» arriba de todo en Métricas (debajo de la cabecera), ancho completo: al abrir muestra el mensaje de
  `apertura` (con «hoy» o la fecha), debajo la conversación y una entrada de texto con botón «Preguntar» (Enter envía). Tres
  sugerencias clicables como chips la primera vez: «¿Cómo nos fue esta semana?», «¿Qué campaña rindió mejor?», «¿Qué canal conviene
  para la próxima campaña?». Cada respuesta se renderiza como markdown saneado, con «De dónde salen los números» y «Lo que faltó»
  plegados si vienen. Mientras responde: «Mirando las campañas y sus números…». La conversación vive en el estado de la pantalla
  (se pierde al salir; está bien).
- El botón «¿Cómo le fue?» de cada campaña sigue, y además su respuesta se agrega a la conversación del asesor como si la hubiera
  preguntado el usuario.
- Ayuda: el panel del asesor es el primer paso de la guía («Preguntale al asesor cómo vienen las campañas: te responde con los
  números y de dónde salen»). Sigue valiendo el límite de 6 pasos / 120 palabras.

## Agregado del 8/11 (Franco, tarde): Métricas v2

Cinco mejoras que pidió Franco al ver la pestaña en producción. Rama `claude/metricas-v2`.

### Asesor más profundo (`metricas_asesor.py`)

- El bloque de cada campaña que ve el modelo suma listas **nombradas**: «Programadas» y «En aprobación» con título, canal, fecha/hora
  relativa en hora Argentina («mañana 10:00 (9/11)») y quién (`de pato`); «Publicadas en los últimos 7 días» con título, canal y fecha.
  Hasta 15 por lista. Después, el detalle de piezas con sus números (ahora con «de <usuario>»).
- Los **borradores** no se nombran ni cuentan como hechos: solo un conteo «aparte: N borradores».
- La apertura nombra las cosas por campaña («quedan programadas X (Instagram, mañana 10:00, de Pato)…», «esta semana salieron…»), después
  los números con su fuente y lo que falta cargar. Límite: **350 palabras** (`LIMITE_APERTURA`); las preguntas libres siguen en 250
  (`LIMITE_PALABRAS`) pero ven las mismas listas. `responder(..., limite=…)`.

### Campaña virtual «Frase del día (automática)»

`metricas.campanas` agrupa las piezas cuyo `usuario` está en `admin_rutas.SERVICIO` (frase_del_dia, bot, cola, prueba) y que no están en
ningún Proyecto en una campaña `{id: "frase_del_dia", nombre: "Frase del día (automática)", emoji: "📅", dueno: null, color: null, creado: null,
piezas_total, por_canal, por_estado, primera, ultima, piezas}` con la misma forma que las demás. Va **después de las campañas reales y antes de
«Sin campaña»** (dentro de `campanas`), y solo aparece si tiene piezas en el período. Una pieza de esos usuarios que sí está en un Proyecto se
queda en el Proyecto. El asesor la trata como una campaña más (puede comparar sus historias con las de una campaña hecha por personas).
`GET /admin/metricas/resumen/frase_del_dia` y `POST /admin/metricas/resumen` con `ref: "frase_del_dia"` funcionan (`comparado_con` siempre null).

### Configuración: `metricas_excluir_usuarios`

Clave de `admin_rutas.CLAVES_CONFIG` (tabla `config`), lista de usuarios; **vacía por defecto, nadie en el código**. `PUT /admin/config` acepta
una lista o texto separado por líneas/comas, y valida que cada usuario exista en la tabla `usuarios` (400 «No existe el usuario «x».»).
`metricas.campanas` (y por lo tanto el asesor) ignora las piezas de esos usuarios, en campañas y en totales; `canales_estado` no cambia.
Pantalla: Configuración → bloque «Métricas» (un usuario por línea).

### `totales` y borradores

`totales.piezas` = publicada + programada + en_aprobacion («piezas hechas»). `borrador`, `prueba` y `no_salio` siguen viniendo como conteos y la
web los muestra aparte («Aparte: N en prueba, M borradores.»). `totales.por_canal` cuenta solo las piezas hechas. En cada tarjeta de campaña los
borradores van en un plegable propio («3 borradores») y no entran en los chips ni en la tabla por canal. `Campana.piezas_total` sigue incluyéndolos.

### Mover a campaña desde Métricas

En «Sin campaña» y en «Frase del día (automática)», cada pieza tiene «Mover a campaña»: un selector con los Proyectos que la persona puede editar
(`GET /proyectos`, permiso distinto de «ver») y «Nueva campaña…» (pide un nombre y hace `POST /proyectos`). Al elegir llama
`POST /proyectos/{id}/items` con `{tipo: "pieza", item_id}` y recarga las campañas. Si `agregar_item` lo rechaza (un admin puede no ser dueño
del Proyecto, o la pieza ser ajena y no compartida), se muestra el texto del error tal como viene, en castellano. **No se agregó
`proyectos_disponibles` a `/admin/metricas/campanas`**: `GET /proyectos` ya da lo necesario. No se reutilizó `MoverA.tsx` (modal con árbol de carpetas que
depende del contexto `ProyectosProvider`); se hizo un selector chico dentro de la pantalla.

### Canales: enlaces y carga a mano

- Donde la API no hay (`api: "no_hay"`) y el canal tiene enlace, el chip «se mira en la plataforma» es el enlace mismo (texto = `enlace_texto`), además del botón de siempre.
- El botón pasa a «Cargar números a mano» con la línea gris «Para lo que la plataforma no nos deja leer solo: copiá acá lo que ves en sus estadísticas, con el período.».
  En los canales con `api: "disponible"` queda escondido dentro de un «¿Preferís cargarlos a mano?».
- La ayuda (`definirAyuda("metricas")`) se actualizó sin pasar los límites.

## Agregado del 8/11 (Franco, noche): el sitio con WordPress.com

La tarjeta «Sitio web» lee las estadísticas de WordPress.com con una autorización que se hace con dos clics desde la pantalla (flujo OAuth2
«authorization code», https://developer.wordpress.com/docs/oauth2/). El paso único de Franco es registrar la app (ver HANDOFF).

### Rutas (admin; las dos primeras no están en el OpenAPI porque las abre el navegador, no `pedir`)
- `GET /admin/metricas/wordpress/autorizar` → 302 a `https://public-api.wordpress.com/oauth2/authorize?client_id&redirect_uri&response_type=code&scope=global&blog=<WP_SITE>&state=<firmado>`.
  `redirect_uri` = `<API_URL_PUBLICA o la base del pedido>/admin/metricas/wordpress/callback` (tiene que ser idéntica a la registrada en la app).
  Sin app registrada vuelve a la web con `?wordpress=error&motivo=…` (no deja un JSON en pantalla).
- `GET /admin/metricas/wordpress/callback?code&state` → valida el `state`, canjea el código (`POST /oauth2/token`), guarda `config.wpcom_token`
  = `{access_token, blog_id, blog_url, autorizado_en, por}`, registra el cambio en `usuarios_cambios` (clave `wpcom_token`, sin el token) y redirige (302) a
  `<WEB_URL>/administracion/metricas?wordpress=ok`. Con error: `?wordpress=error&motivo=<texto corto>`. `state` inválido o vencido → 400.
  **No exige cookie de admin**: llega desde otro sitio y la cookie puede no viajar. Lo autoriza el `state`: firmado con el secreto de sesión
  (otra «sal», `auth.firmar_estado`), lleva el usuario admin que lo pidió y vence a los 10 minutos; se vuelve a comprobar que siga siendo admin y activo.
- `DELETE /admin/metricas/wordpress` → `{ok: true}`; borra el token (queda la clave vacía). Registra el cambio.
- `GET /canales` suma `conectado` y `conectar_url` a cada canal (solo el sitio los llena).

### Web
- Tarjeta «Sitio web»: con `conectar_url` y sin `conectado`, botón «Conectar con WordPress.com» (link normal a `BASE + conectar_url`, no fetch);
  conectado y con error, «Volver a conectar con WordPress.com»; conectado, un enlace chico «Desconectar» (pide confirmación, `DELETE`).
- Al volver con `?wordpress=ok` avisa «WordPress.com conectado: tocá Actualizar.»; con `?wordpress=error` muestra el `motivo`. Limpia la query.
- El botón de arriba dice «Actualizar desde las plataformas» y el resumen muestra las cuatro líneas (Instagram, Facebook, YouTube y Sitio web).

### Sin confirmar contra WordPress.com (no hay app registrada todavía)
Ver el docstring de `metricas_wordpress.py`: que el token del flujo «code» no expire, si `scope=global` hace falta, la forma exacta de las respuestas
de `stats/summary`, `top-posts`, `referrers`, `clicks` y que `stats/post/{id}` acepte `fields=views`.
