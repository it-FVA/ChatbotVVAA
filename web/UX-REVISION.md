# Revisión UX/UI de la web de recortes (21/10/2026)

Mirada de diseño de producto sobre las pantallas de la fase 1 (`web/capturas/` del 21/10: login, lista, editor en escritorio
y celular), comparando con cómo resuelven el recorte de video y los subtítulos los productos de referencia. La paleta y la
tipografía no se tocan (Franco: «los colores son los adecuados»). Regla «no inventar»: lo que no pude verificar en una fuente
oficial queda marcado como **[no verificado]**.

## Qué hacen los productos de referencia (lo verificado)

| Producto | Patrón | Fuente |
|---|---|---|
| Riverside | Espacio = reproducir/pausar; **S** parte en el cabezal; Supr/Retroceso saca la sección seleccionada; **+ / −** zoom de la línea de tiempo; flechas mueven el cabezal; las secciones sacadas se saltan al reproducir y exportar; se restauran arrastrando las manijas vecinas o con Deshacer | [Editor hotkeys](https://support.riverside.com/hc/en-us/articles/6279202420253-Editor-hotkeys-and-keyboard-shortcuts), [Trim and split](https://support.riverside.com/hc/en-us/articles/6609268330397-Trim-and-split-a-clip-s-timeline) |
| Kapwing | Manijas de trim en los extremos de cada capa (líneas blancas), **S** parte en el «seeker», botón Split arriba de la línea de tiempo, botones de lupa y «Fit to screen» para el zoom, flechas mueven un cuadro | [Timeline tutorial](https://www.kapwing.com/help/timeline-tutorial/), [Keyboard shortcut guide](https://www.kapwing.com/help/keyboard-shortcut-guide-for-kapwing/) |
| OpusClip | Flechas ±1 cuadro, **D** o Cmd+B parte el clip seleccionado, Retroceso lo borra, Home/End al inicio/fin, **+ / −** zoom; presets de subtítulos con nombre (karaoke, etc.) y plantillas propias guardables | [Keyboard precise editing](https://help.opus.pro/docs/article/keyboard-precise-editing), [pricing](https://opus.pro/pricing) |
| YouTube Studio | «Trim & cut»: una caja azul que se arrastra sobre lo que se conserva; «New cut» = caja roja sobre lo que se saca; se pueden tipear los tiempos exactos; Deshacer y tachito por cada corte; Vista previa antes de guardar | [Trim your videos](https://support.google.com/youtube/answer/9057455) |
| YouTube (clips) | Un único deslizador con dos extremos, límite 5–60 s mostrado en la propia herramienta | [Create clips](https://support.google.com/youtube/answer/10332730) |
| Veed | Lista de subtítulos editable; contador de caracteres por línea (CPL) que se pone **rojo** al pasarse y muestra cuánto se pasó; cantidad de renglones configurable | [How to edit subtitles](https://support.veed.io/en/articles/6971680-how-to-edit-subtitles) |
| CapCut | **[no verificado: solo hojas de atajos de terceros]** Ctrl+B parte, Ctrl+± zoom, Shift+Z ajusta la línea de tiempo a la ventana | [fastshortcuts](https://fastshortcuts.com/shortcuts/capcut/), [tutorialtactic](https://tutorialtactic.com/blog/capcut-shortcuts/) |
| Descript | **[no verificado]** No encontré la página oficial de atajos; en su foro hay hilos contradictorios sobre si Espacio o Tab reproduce | [feedback.descript.com](https://feedback.descript.com/feature-requests/p/allow-spacebar-for-play-button) |
| Adobe Express | Manijas de trim que aparecen al pasar el mouse por cada escena; «Split» con clic derecho en el punto exacto | [Edit videos in Express](https://www.adobe.com/learn/express/web/edit-videos-in-express) |

Patrones que se repiten en casi todos: Espacio reproduce, una tecla parte en el cabezal (S en Riverside y Kapwing), ± hace
zoom, flechas mueven, Supr saca lo seleccionado, manijas grandes en los extremos de lo conservado, lo sacado se ve distinto y
se puede restaurar, y los límites de duración se muestran en la herramienta. Miniaturas de cuadros en la línea de tiempo: las
tienen CapCut, Descript y Kapwing en sus editores **[no verificado en docs: lo sé por uso, no por una página oficial]**.

## Hallazgos sobre nuestras pantallas (priorizados)

1. **Manijas de trim chicas y sin «asa»** (`02-editor-inicial-escritorio.png`): 14 px de ancho, sin icono, la etiqueta de
   tiempo pisa la onda. En celular (`03-editor-editado-movil.png`) son difíciles de agarrar. → Manijas de 22 px con icono de
   agarre, zona táctil de 44 px, burbuja con el tiempo mientras se arrastra, foco de teclado (flechas mueven la manija). **Alta.**
2. **La línea de tiempo no muestra el video**: solo onda. Sin cuadros no se sabe «qué» hay en 47:30 sin ir ahí. → Tira de
   miniaturas generada en el navegador con `<canvas>` a partir del mp4 (sin ffmpeg ni endpoint nuevo), con la onda debajo.
   **Alta.**
3. **Sin zoom ni desplazamiento**: un tramo de 3 minutos en 700 px son 4 px por segundo; imposible afinar. → Botones − / + /
   «ajustar», rueda con Ctrl, teclas + y −, y desplazamiento horizontal. **Alta.**
4. **Sin atajos de teclado**: todo es con el mouse. → Espacio, I y O (inicio y fin en el cabezal), S (partir), flechas ±1 s,
   Shift+flechas ±0,1 s, Supr (sacar el pedazo seleccionado), ± zoom, ? (ayuda). Panel de ayuda visible. **Alta.**
5. **Cabezal poco visible y sin tiempo**: una línea roja de 2 px. → Cabezal con cabeza triangular, tiempo encima y tijera
   para partir ahí mismo (patrón Kapwing/Riverside: partir donde está el seeker). **Media.**
6. **Pedazos sacados**: rayado gris con un chip «✕ 22,7 s» en el medio; no hay noción de «seleccionado» ni «restaurar». →
   Clic selecciona (borde amarillo), Supr saca, chip «Restaurar» en los sacados, rayado más claro. **Media.**
7. **Botones sin jerarquía clara**: «Abrir ↗», «✏️ Editar», «🗑 Borrar» con emojis y el mismo peso; «Partir acá» igual que
   «Deshacer los cortes». → Primario amarillo (una sola acción por pantalla), secundario blanco con borde, peligro con borde
   rojo que se rellena al pasar, sutil sin borde; iconos SVG propios; hover, focus-visible y disabled consistentes; 40 px de
   alto mínimo (44 en pantallas táctiles). **Alta.**
8. **Subtítulos**: la línea activa se resalta pero no hay contador de caracteres ni aviso cuando una línea va a ocupar tres
   renglones (en vertical pasa seguido). → Contador por línea, aviso al pasar el umbral, borde izquierdo verde en la activa y
   autoscroll suave. **Media.** El umbral de caracteres por renglón se estima a partir del ancho del video vertical y del
   tamaño base, **[supuesto: ~26 caracteres por renglón en tamaño normal]**: hay que ajustarlo mirando recortes reales.
9. **Estilo**: cinco listas desplegables iguales y sin presets. → Tres presets con nombre («El de la Fundación», «Negrita
   amarilla», «Caja negra») encima de los controles, con el activo marcado; la vista previa ya reacciona al instante.
   **Media.**
10. **Carga**: «Cargando…» en texto. → Skeletons de tarjetas en la lista y del editor. **Baja.**
11. **Estados vacíos**: un párrafo gris (`Recortes.tsx:76`). → Ilustración simple SVG + texto + botón que lleva al chat.
    **Media.**
12. **Confirmaciones y avisos**: el modal de borrado existe (`04-borrar-confirmacion-*.png`) pero no se cierra con Escape ni
    atrapa el foco; los errores son cajas en línea y los éxitos no se avisan. → Modal accesible (role=dialog, Escape, foco) y
    toasts para «borrado», «mandado a regenerar» y errores. **Media.**
13. **Navegación**: «← Recortes» como link suelto. → Breadcrumbs (Recortes › título). **Baja.**
14. **Layout en escritorio**: el video queda fijo a la izquierda (bien) pero la columna derecha tiene mucho texto explicativo
    repetido en cada sección. → Textos de ayuda más cortos, la ayuda larga en el panel de atajos. **Baja.**
15. **Celular**: el botón «Regenerar» queda al final de una página muy larga. → Barra inferior fija con el botón y el estado
    («3 cambios» / «sin cambios»). **Alta.**
16. **Accesibilidad**: foco invisible en botones (solo en inputs), manijas sin rol, contraste del gris `#6b6b6b` sobre crema
    está justo (4,9:1 estimado **[no medido con herramienta]**). → `:focus-visible` en todo, `role="slider"` con
    `aria-valuenow` en las manijas, tamaños mínimos. **Media.**

## Qué se cambia en esta revisión (orden)

Alta: 1, 2, 3, 4, 7, 15. Media: 5, 6, 8, 9, 11, 12, 16. Baja: 10, 13, 14. Todo en `web/`; no hace falta ningún endpoint
nuevo (las miniaturas se sacan del video en el navegador).

## Fuera (para después)

- Deshacer/rehacer general (Ctrl+Z) como Riverside: hoy solo «Deshacer los cortes».
- Editar los tiempos de cada línea de subtítulo (arrastrar en la línea de tiempo), que tienen Veed y Kapwing.
- Guardar presets propios de estilo por usuario (OpusClip): hoy solo los tres fijos + el del equipo.
- Vista previa real con libass (sigue dependiendo de la copia liviana del plan).
