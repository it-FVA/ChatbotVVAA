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
- youtube: `pendiente`, nota «Se pide cuando Google responda la auditoría de la API (en curso)».
- mail: `no_hay`, nota «Perfit: los reportes se ven en la plataforma; la API de métricas por campaña está sin confirmar».
- sitio: `no_hay`, nota «WordPress.com pide autorizar una app propia para leer las estadísticas; por ahora, el enlace».
- whatsapp: `no_hay`, nota «WhatsApp no da métricas de grupos».

Enlaces: Instagram y Facebook → `https://business.facebook.com/latest/insights/overview`; YouTube → `https://studio.youtube.com/`
(«Abrir YouTube Studio → Estadísticas»); mail → `https://app.myperfit.com/`; sitio → `https://wordpress.com/stats/day/<WP_SITE>`;
whatsapp → null.

### `POST /admin/metricas/actualizar`

Captura ahora por API (Instagram y Facebook): cuenta (últimos 28 días) + cada pieza `publicada` en modo `real` de los últimos 60 días
que tenga id de la plataforma en `resultado.ultimo.id` (o `resultado.id`). Guarda filas `fuente='api'`. Responde:

```jsonc
{ "capturado": "iso", "instagram": { "ok": true, "piezas": 4, "error": null }, "facebook": { "ok": false, "piezas": 0, "error": "Falta el permiso read_insights" } }
```

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
