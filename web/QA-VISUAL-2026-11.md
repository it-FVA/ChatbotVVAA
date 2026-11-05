# QA visual y de coherencia · noviembre 2026

Auditoría del 5/11/2026 sobre producción (https://chatbot-vvaa.vercel.app, sesión de Franco) y sobre el código de `web/src`.
Una línea por hallazgo: pantalla · qué pasa · decisión (**arreglar** / **dejar** / **preguntar**).

Método: texto de cada pantalla leído del DOM, tamaños y clases por JavaScript, ancho de 375 px emulado con un iframe
del mismo origen (las capturas de pantalla se congelaban en Chrome). Las pantallas de Login y Primera vez se miraron
solo en el código.

## Textos

| # | Pantalla | Hallazgo | Decisión |
|---|---|---|---|
| T1 | Diseñar | Chip «SIMULADO» al lado de cada canal (y «Blogpost · simulado» arriba de la vista previa). Es el modo interno del canal; a quien diseña no le cambia nada. | arreglar: se saca de los canales y de la vista previa |
| T2 | Diseñar | «Blogpost en modo simulado: …» y «(el canal real está en …: lo que mandes a aprobación sale con ese modo)» debajo del canal. | arreglar: se saca; queda una sola línea arriba del formulario, solo cuando el canal no está en real («Este canal está en modo de prueba: la pieza se arma pero no sale de verdad») (decisión del coordinador, 5/11) |
| T3 | Diseñar | Botón «Ver simulado» y el texto «“Ver simulado” solo muestra cómo quedaría». | arreglar: pasa a «Ver cómo quedaría»; el estado de esas piezas pasa de «simulada/simulado» a «prueba» |
| T4 | Diseñar | Toast «Pieza simulada: así quedaría.» y título de resultado «Así quedaría en X». | arreglar: «Así quedaría la pieza.» |
| T5 | Diseñar | «Quedó en la cola.» al enviar. | arreglar: «Quedó programada: sale en su fecha.» |
| T6 | Diseñar | Mensaje «X está en modo Y: no hay a dónde mandarla cuando la aprueben». | arreglar: «X no está habilitado todavía: guardala como borrador.» |
| T6b | Diseñar | El aviso del paso 3 («Blogpost: está en simulado, no sale nada de verdad…») lo arma la API (`aviso_con_fecha`). | dejar: texto de la API, fuera del alcance (anotado para el coordinador) |
| T7 | Diseñar | Al llegar con `?canal=` desde el menú, producción sigue mostrando el selector de los cuatro canales. | dejar: en el código ya está la versión fija (`pub-canal-fijo`, commit 3e5c01b, todavía sin desplegar); se verifica después del deploy |
| T8 | Diseñar | Vista previa muestra «Blogpost · simulado» como chip. | arreglar: solo el nombre del canal (y el tipo de Instagram) |
| T9 | Mis publicaciones | Estados «simulada» y «simulado» para la misma cosa (dos piezas seguidas). Vienen de la API en `estado_texto`. | arreglar en la web: se muestra «prueba» para ambos (la API no se toca) |
| T10 | Mis publicaciones | Subtítulo termina en «… borradores y pruebas.» pero la solapa se llama «Pruebas» y el chip dice «simulada». | arreglar: queda «prueba» en todos lados |
| T11 | Mis publicaciones · Aprobación | «Instagram · Historia · historia»: el tipo y el formato repiten la palabra. | arreglar: no se agrega el formato cuando coincide con el tipo |
| T12 | Aprobación | Subtítulo: «Piezas para aprobar, la cola, el registro, la papelera y los clips del equipo. La Frase del día está en Campañas; el Dashboard, en Administración.» | arreglar: «Lo que el equipo mandó: revisás, aprobás y seguís qué salió.» |
| T13 | Aprobación → En cola | «La cola corre cada 15 minutos (GitHub Actions) y saca cada pieza en su fecha, con el modo que tenga el canal en ese momento.» | arreglar: «Las piezas aprobadas esperan acá y salen solas en su fecha (se revisa cada 15 minutos).» |
| T14 | Aprobación → En cola | Solapa «En cola». | preguntar: propongo «Programadas» (ver decisiones dudosas) |
| T15 | Aprobación → Clips | «Los corta la nube cada 15 minutos desde los originales en Drive.» | arreglar: «Se cortan solos, tardan unos 15 minutos.» |
| T16 | Aprobación → Clips | Chip de estado vacío («estado neutro» sin texto) en dos tarjetas de En cola. | arreglar: si no hay texto no se dibuja el chip |
| T17 | Mis recortes | «sin pausas (38 s → 32 s)» y «3 pedazos conservados» en la fila de datos, además de la nota larga «Pedazos sacados del medio: 52 s → 38 s (3 tramos conservados)…» | arreglar: la fila queda en «editado» (con el detalle en el tooltip) y la nota sigue contando qué se hizo; el Editor sigue hablando de «pedazos», que es la palabra del equipo |
| T18 | Mis recortes | Subtítulo largo repite la ayuda («Cuando están listos aparece el video y los botones “Diseñar”, “Editar” y “Abrir”…»). | arreglar: «Tus pedazos de video, listos para diseñar una pieza. Tardan unos 15 minutos.» |
| T19 | Chat | Aviso «La API está despertando…» y «La API no respondió en dos minutos». | arreglar: «El asistente está arrancando: puede tardar un minuto.» / «El asistente no respondió. Probá de nuevo en un rato.» (en los tres idiomas) |
| T20 | Ayuda → Si algo falla | «la API se despierta sola en un minuto si estuvo dormida». | arreglar: «el asistente tarda un minuto en arrancar» |
| T21 | Newsletter | Subtítulo de cinco frases con paréntesis sobre qué es un blogpost. | arreglar: dos frases; lo del blogpost va a la Ayuda |
| T22 | Newsletter | «Nada con esas palabras (o la API no tiene acceso a WordPress)». | arreglar: «Nada con esas palabras. Probá otras o pegá la URL.» |
| T23 | Newsletter | Textos de «retomar»: «vuelve a la cola», «pasa a la cola». | arreglar: «vuelve a aprobación» |
| T24 | Frase del día | Leyenda del calendario incluye «simulada» con ícono de ojo. | arreglar: «prueba» |
| T25 | Frase del día → mañana | «el canal está apagado en la API», chip con el modo del canal y «simulada (no salió)», «en cola · sale …». | arreglar: «el canal está apagado», se saca el chip de modo, «prueba (no salió)», «programada · sale …» |
| T26 | Frase del día → mail | «simulado (registra, no manda)», «Faltan variables en el servidor: … el modo real no manda nada», «todavía no está en la cola». | arreglar: «prueba (no manda)», «Falta configurar el envío: lo ve quien administra», «todavía no está programada» |
| T27 | Frase del día | «la cola le asigna la siguiente de la rotación», «ya está en la cola o ya salió». | arreglar: «se asigna sola la siguiente de la rotación», «ya está programada o ya salió» |
| T28 | Frase del día | Subtítulo para aprobadores dice «desde el backlog»; la solapa se llama «Sin día». | arreglar: «desde “Sin día”» |
| T29 | Login | «El login con Google se habilita cuando la API tenga el proyecto de Google Cloud.» y tooltip «falta GOOGLE_CLIENT_ID en la API». | arreglar: «Entrar con Google todavía no está habilitado.» |
| T30 | Compartidos | Subtítulo con «para ver» entre comillas y explicación larga. | dejar: es corto y dice lo que hace falta |
| T31 | Proyectos | Pie «Clic derecho (o ⋮) abre el menú. Ctrl+clic selecciona varios. Arrastrá para mover.» | dejar: es la única pista de esos gestos |
| T32 | Barra | Entrada «WhatsApp · pronto» deshabilitada en Canales. | preguntar: ¿sigue siendo una promesa que quieren mostrar? |
| T33 | Mi cuenta | Rol se muestra como «admin» (clave interna). | arreglar: «administra» / «aprueba» / «diseña» según el rol |
| T34 | Mis publicaciones | Chip «borrador en WordPress» en verde (ok) mientras «borrador» va gris. | arreglar: los dos neutros |
| T35 | Varias | «Dashboard» en el menú de Administración y en textos. | dejar: es la pantalla de administración y el equipo ya la llama así |

## Coherencia

| # | Pantalla | Hallazgo | Decisión |
|---|---|---|---|
| C1 | Todas | Cabecera armada a mano en cada pantalla: a veces `<div>` + `<p>`, a veces `<h1>` suelto, Mis recortes con un `style` en línea para poner el botón a la derecha. | arreglar: componente `Cabecera` (título, subtítulo, acciones) usado en todas |
| C2 | Chat · Proyectos | Título a 16 px y 18 px; el resto a 23 px. | preguntar: son pantallas tipo aplicación (lista a la izquierda); propongo dejarlas |
| C3 | Mis publicaciones · Aprobación · Pieza · Frase | Chips de estado con tres estilos: texto verde sin fondo (`listo`), píldora verde (`ok`), píldora gris (`neutro`); el mismo estado «publicada» se ve distinto según la pantalla. | arreglar: componente `ChipEstado` con una sola paleta (pendiente ámbar, programada verde claro, publicada verde, rechazada/error rojo, borrador/prueba/cancelada gris) |
| C4 | Pieza (detalle) | Estado siempre gris (`estado neutro`) aunque esté publicada o rechazada. | arreglar: usa `ChipEstado` |
| C5 | Recorte (detalle) | Estado como texto suave, sin chip. | arreglar: usa `ChipEstado` |
| C6 | Compartidos · Proyectos | Estado vacío propio (`vacio drive-vacio`) en vez de `EstadoVacio`. | arreglar: Compartidos pasa a `EstadoVacio`; Proyectos tiene acciones propias dentro del vacío, se deja con la misma ilustración |
| C7 | Chat | Estado vacío propio con ejemplos clicables. | dejar: es a propósito (los ejemplos son la acción) |
| C8 | Mis publicaciones · Compartidos · Proyectos | Esqueletos de carga armados a mano con `Hueso` y medidas distintas. | arreglar: `TarjetaEsqueleto` acepta la variante «publicación»; Compartidos y Proyectos comparten `FichaEsqueleto` |
| C9 | Mis recortes · Clips | Hasta seis botones primarios por vista (un «Diseñar» por tarjeta) más «Subir un video». | arreglar: «Diseñar» de cada tarjeta pasa a secundario; el primario de la vista es «Subir un video» |
| C10 | Chat | Dos primarios: «Nueva conversación» y «Enviar». | dejar: están en paneles distintos |
| C11 | Newsletter | Dos primarios: «Redactar» y «Enviar a aprobación». | arreglar: «Redactar» pasa a secundario |
| C12 | Administración → Dashboard | Botón primario «28 días» (un filtro de período). | arreglar: filtros como solapas, ninguno primario |
| C13 | Aprobación → Registro | «Editar» primario dentro de una tarjeta de registro. | arreglar: secundario |
| C14 | Aprobación · Administración | Las dos usan `admin-menu` y `pagina admin`: bien. El subtítulo de Aprobación es el único que explica dónde están otras pantallas. | arreglar (ver T12) |
| C15 | Mis publicaciones · Mis recortes | Solapas con el mismo nombre que la pantalla («Mis recortes» dentro de Mis recortes). | arreglar: «Míos» / «Del equipo» / «Todos» en recortes; en publicaciones ya está bien |
| C16 | Varias | Fechas: «creada 2/11 04:08 p. m.» en tarjetas, «sale el jue 24/9 21:40» en la misma tarjeta (12 h y 24 h mezclados). | arreglar: todo con el formato de `fechaLegible` (24 h) |
| C17 | Todas | `LinkAyuda` («? ¿Cómo se usa?») pegado al final del subtítulo con dos espacios. | arreglar: `Cabecera` lo ubica siempre igual |

## Restos

| # | Dónde | Hallazgo | Decisión |
|---|---|---|---|
| R1 | `frases.css` | Clases sin uso: `fd-activa`, `fd-cabecera`, `fd-canal`, `fd-canales`, `fd-lineas`, `fd-mail-resultados`, `fd-manana-botones`, `solo-lectura`. | arreglar: se borran tras grep |
| R2 | `proyectos.css` | `tipo-conversacion`, `tipo-pieza` sin uso. | arreglar |
| R3 | `admin.css` | `e-sin_dato` sin uso. | arreglar |
| R4 | `compartido.css` | `.pub-modo` y variantes (`real`, `simulado`, `borrador`, `privado`) quedan sin uso al sacar los chips de modo fuera de Administración. | arreglar: se mueven a `frases.css`/`admin.css` si alguien los usa, si no se borran |
| R5 | `src/paginas/RecorteVer.tsx` | Importado solo desde Editor (recorte ajeno). | dejar: se usa |
| R6 | `Publicaciones.tsx` | Mapa `CLASE_ESTADO` con claves en mayúscula (`PUBLICADO`) y duplicadas (`simulada`/`simulado`). | arreglar: pasa a `ChipEstado` |
| R7 | Código | No quedan referencias a Streamlit en `web/src`. | nada |
| R8 | `web/capturas/*.mjs` | Scripts de capturas viejas (necesitan API local). | dejar: fuera de `src`, no afectan el build |

## Celular (375 px)

| # | Pantalla | Hallazgo | Decisión |
|---|---|---|---|
| M1 | Editor de recortes | Desborda a 423 px: las migas con el título largo no cortan. | arreglar: migas con elipsis y `min-width: 0` |
| M2 | Editor de recortes | Un `input` de tiempo mide 50 px y su contenido 56. | arreglar: ancho mínimo 60 px |
| M3 | Administración (escritorio) | A 1366 px el documento mide 1415: con el menú plegado a íconos, los gráficos del Dashboard (`.graficos`, grilla de 320 px mínimos) no se achican dentro de su celda. | arreglar: `min-width: 0` en cada gráfico y `max-width: 100%` en el svg |
| M4 | Resto | Chat, Recortes, Proyectos, Compartidos, Diseñar, Publicaciones, Aprobación, Newsletter, Frase, Ayuda, Cuenta, Pieza: sin desborde. | nada |
| M5 | Diseñar | Botones de envío al final del formulario; «Enviar a aprobación» ya es ancho completo en celular. | dejar |

## Conteo

| Decisión | Cantidad |
|---|---|
| Arreglados | 54 |
| Dejados | 12 |
| A preguntar (mandados al coordinador, aplicados según la propuesta) | 5 |

Capas y commits en la rama `claude/elegant-allen-8a6c19`: textos (f6d8709), coherencia (3d20389), restos (c0ed2ec), celular (este commit).
Verificación local: `npx tsc --noEmit -p .`, `npm test -- --run` (47 pruebas, se agregó `ChipEstado.test.tsx`), `npm run build`.

## Decisiones que tomé sola

- La API manda «simulada» o «simulado» como `estado_texto` según la pieza; la web lo muestra como «prueba» desde `ChipEstado` (la API no se tocó).
- Las horas van todas en 24 h (`fechaHora` con `hour12: false`): antes convivían «04:08 p. m.» y «21:40» en la misma tarjeta.
- «Retomar» y «Editar» de las tarjetas de Mis publicaciones y Registro dejan de ser primarios: el primario de la vista es «Diseñar una pieza».
- El chip de modo del canal en la tarjeta «Mañana» de Frase del día queda solo cuando el canal no está en real, como «prueba» o «apagado».
- El rol en Mi cuenta se describe en palabras («Administra la app (y aprueba)», «Aprueba y publica», «Crea contenido») en vez de la clave interna.
- En Newsletter la función interna `Cabecera` (la cabecera del mail) pasa a llamarse `CabeceraMail` para no chocar con el componente común.
- Constantes exportadas pero usadas solo en su archivo (`PASO_MS`, `LARGO_MINIMO_WORD`, `MAX_POR_RENGLON`, `MAX_DOS_RENGLONES`) se dejaron: no molestan y pueden servir a una prueba.

## Decisiones dudosas (mandadas al coordinador el 5/11; respondió que sí a 1, 2, 4 y 5 y dejar la 3; la 2 con la línea discreta de T2)

1. **«En cola» → «Programadas»** (T14). La palabra «cola» aparece en Aprobación, Frase del día, Newsletter y los toasts. Propongo
   «programadas / programada» en toda la web. Riesgo: el equipo ya puede llamarla «la cola».
2. **Sacar el modo del canal de Diseñar** (T1, T2, T8). Si un canal está en prueba, la persona que diseña no se entera hasta que
   la pieza no sale. Propongo que ese aviso viva solo en Administración y en Frase del día (que ya lo muestra a quien aprueba).
3. **Títulos chicos en Chat y Proyectos** (C2). Son pantallas con panel lateral; propongo dejarlas así y no forzar los 23 px.
4. **«Diseñar» deja de ser primario en cada tarjeta de recorte** (C9). Es la acción más usada de la pantalla; con cinco
   tarjetas hay cinco botones amarillos. Propongo un solo primario por vista («Subir un video»).
5. **WhatsApp · pronto en la barra** (T32). Es una promesa visible desde hace semanas. Propongo dejarla pero sin el tooltip largo.

## Para verificar en producción (después del deploy)

- [ ] Diseñar: sin «SIMULADO» en canales ni en la vista previa; una sola línea «Este canal está en modo de prueba…» arriba del formulario mientras el canal no esté en real; con `?canal=blogpost` se ve el canal fijo, no el selector.
- [ ] Diseñar: botón «Ver cómo quedaría» y toast «Así quedaría la pieza.».
- [ ] Mis publicaciones: chips con la paleta nueva; «prueba» en vez de «simulada/simulado»; «Instagram · Historia» sin repetir.
- [ ] Aprobación: subtítulo nuevo, solapa «Programadas», sin chips vacíos en las tarjetas.
- [ ] Pieza (detalle) y Recorte (detalle): chip de estado con color.
- [ ] Mis recortes: «Diseñar» secundario, «Subir un video» primario, solapas «Míos / Del equipo / Todos».
- [ ] Editor de recortes a 375 px: sin scroll horizontal (migas cortadas con «…»).
- [ ] Administración a 1366 px: sin scroll horizontal.
- [ ] Chat: mensaje de «asistente arrancando» sin la palabra API (probar con la API dormida).
- [ ] Frase del día: leyenda sin «simulada»; mail con «prueba (no manda)».
- [ ] Guía interactiva de cada pantalla: los pasos siguen apuntando a sus elementos (los `data-ayuda` no cambiaron).
