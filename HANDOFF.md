
### 8/11 (18:10) · Bug en la búsqueda del chat desde el 5/11, corregido
Beto vio «module 'db' has no attribute '_cabeceras'» en el chat. Causa: el commit e54fb1b (5/11 01:55, clave acotada de la cola) cambió `db/_cliente._rpc` para armar las cabeceras con `_db._cabeceras`, y el paquete `db` no reexportaba esa función privada: cada búsqueda en el corpus con `VECTORES=supabase` (match_lexico / match_fragmentos_varios) y el chequeo `tamano_base` de Salud fallaban. El chat seguía respondiendo mientras no buscara, por eso tardó 3 días en verse. Arreglo: `_rpc` usa la función local y `db` la reexporta; prueba de regresión `test_rpc_arma_la_llamada` en `api/tests/test_vectores.py`. Verificado en producción con una búsqueda real (citas con fuente). Lección: las pruebas no ejercitan `_rpc` contra nada; cualquier cambio en `db/_cliente.py` debe verificarse con una pregunta al chat en producción.

### 8/11 · Métricas (API)
Pedido de Beto, decisión de Franco: la app como centro de métricas de campañas. Contrato en `web/maquetas/metricas-contrato.md`; la pantalla web la construye otra sesión contra el mismo contrato.

**Quedó hecho (rama `claude/metricas-api-e073a1`):** migración `api/migraciones/20261108_1200_metricas.sql` (tabla `metricas`, índice, RLS, política `cola_todo`), `db/metricas.py`, `metricas.py` (campañas, canales, captura, carga a mano), `metricas_meta.py` (HTTP contra Meta), `metricas_asesor.py` (asesor de campañas con IA: conversa, apertura diaria y resumen por campaña), `api/metricas_rutas.py` (`/admin/metricas/*`, solo admins), captura cada hora desde `procesar_cola.py` (no corre con `--simular`), 27 pruebas nuevas en `api/tests/test_metricas.py`, OpenAPI y `tiposApi.d.ts` regenerados.

**Visto en producción (8/11, 17:40 ART):** tabla creada y migración registrada; la pestaña anda por URL con el menú oculto; el asesor recibe con el resumen del día y responde preguntas con fuentes. Instagram lee la cuenta (alcance, vistas, interacciones, seguidores) y la historia del día: los permisos ALCANZAN. Facebook lee la página (interacciones, seguidores, altas) pero Meta rechazó `page_impressions` (retirada): se cambió a `page_media_view` / `page_total_media_view_unique` (post: `post_media_view` / `post_total_media_view_unique`), SIN CONFIRMAR hasta la próxima lectura. Una pieza vieja de Instagram (8/10) que Meta rechaza frenaba la lectura de las demás: ya no frena, y el error guarda el motivo de Meta.

**Falta (en este orden):**
1. ~~Correr la migración a mano~~ hecho el 8/11. Pendiente original: **Correr la migración a mano** en el SQL Editor de Supabase y registrarla con `python api/migrar.py --registrar 20261108_1200_metricas`. Sin ella, `/campanas`, `/canales` y `/resumen` dan 503 con un texto que lo dice.
2. **Verificar los permisos de Meta en vivo** (no se pudo probar acá): Instagram necesita `instagram_manage_insights` y la página de Facebook `read_insights`. Si faltan, la pantalla muestra «Falta el permiso…» (`api: "sin_permiso"`).
3. **Confirmar los nombres de las métricas contra Meta:** cambian cada pocos meses (listas en constantes arriba de `metricas_meta.py`). Sin confirmar: `follows_and_unfollows` (solo se toman las altas si Meta abre el desglose), `page_impressions` y `page_views_total` de Facebook (Meta retiró varias `page_*`), las de historias y `ig_reels_avg_watch_time` (queda en el crudo).
4. Destapar el ítem del menú (`MOSTRAR_METRICAS`) cuando Franco lo pida.

### 5/11 (03:30) · Cierre de la noche: auditoría de YouTube avanzada, housekeeping de repos y Drive, qué queda para mañana
Franco se fue a dormir y pidió avanzar todo lo posible, dejar por escrito hasta dónde se llegó y apagar la computadora. Esto es el estado.

**Auditoría de YouTube (`analisis/auditoria-youtube-api.md`, con checklist al final):**
- Datos legales encontrados en internet y confirmados por Franco: razón social actual **Fundación Juan y María** (CUIT 33-71604174-9; el nombre largo «Fundación Vivir Agradecidos para la Difusión de la Gratitud…» es el anterior), domicilio legal Ciudad de la Paz 1234, Piso 7, Dpto. B, CABA, CP 1426 (el de los Términos del sitio y del Registro Nacional de Sociedades; el fiscal es Arenales 605, Vicente López, y no va). Fuentes en la hoja. No hace falta el mail a Jesi.
- El formulario, leído de nuevo el 5/11: no pide CUIT ni firmante; sí pide cuenta demo, capturas (política, home, términos, consentimiento OAuth, pantalla de subida) y **screencast de punta a punta o script de subida completo** para herramientas que suben video.
- Publicado por la API de WordPress (producción): página hija **https://viviragradecidos.org/politica-de-privacidad/politica-de-privacidad-youtube/** con la sección «Uso de los servicios de la API de YouTube» (III.A.2: uso de la API, link a la Política de Google, cómo revocar, contacto), y una línea al final de Términos y condiciones (página 30829) que remite a los Términos de YouTube y a esa página. La política general (27883) es de Elementor y no se toca por API: **falta un link desde ahí a la página hija** (Julián o Franco en Elementor). **Staging/testing de WordPress:** no encontré la URL en el diario; Franco la pasa o lo pega él.
- App: links legales en el login y en Diseñar → YouTube (commit `9566de5`, en producción).
- Capturas listas en `analisis/auditoria-youtube/` (01 política con la sección, 02 Diseñar → YouTube con los links, 03 términos).
- **Queda (ver checklist):** link en Elementor, staging, captura del consentimiento OAuth, usuario demo `google-audit` (lo crea Franco: cuenta con contraseña en producción), screencast de 2 min o adjuntar `publicar.py`, y completar/enviar el formulario con franco@ (la sesión lo completa, Franco toca Enviar).

**Housekeeping (informe `analisis/housekeeping-2026-11.md`; Franco aprobó las cuatro listas y la decisión de dos repos con roles: ChatbotVVAA = plataforma, fva-transcripcion = corpus y archivo):**
- Hecho por la sesión de ejecución: `archivo/` en fva-transcripcion con README (conectores viejos, `distribucion/`, scripts superados, `facebook-historial-*.csv`, 109 capturas de la web en `archivo/capturas-web/`), `ChatbotVVAA/herramientas/` (`exportar_palabras.py` con la carpeta de crudos por argumento / `FVA_CRUDOS`, `set-dorado.csv`, README), rutas ajustadas (`comparar_busqueda.py`, `medir_set_dorado.py`, `recortar_clip.py`, `nucleo.py`, `web/README.md`), skills de Streamlit borradas, carpetas vacías y cachés borradas, README de fva-transcripcion reescrito. 289 pruebas API, 41 web. Commits: ChatbotVVAA `8aa50aa` (subido); en fva-transcripcion el trabajo quedó dentro de `f1bf3f6` (la sesión coordinadora hizo `git add -A` mientras los `git mv` estaban en el índice: el mensaje no lo describe, el contenido está completo).
- **Bloqueado por el clasificador (dos sesiones):** los borrados grandes de archivos no versionados (≈ 290 MB) y la limpieza de los 9 worktrees de `ChatbotVVAA/.claude/worktrees/` (≈ 950 MB, todos con su trabajo ya en main). **Franco mañana, en PowerShell:**
  ```
  cd C:\Users\Franco\Documents\GitHub\fva-transcripcion
  Remove-Item corpus\*.backup-*, corpus\fragmentos_vectores.npy, corpus\fragmentos_con_taxonomia.jsonl, corpus\fragmentos_con_temas.jsonl, conectores\bin -Recurse -Force
  cd C:\Users\Franco\Documents\GitHub\ChatbotVVAA
  git worktree list --porcelain | Select-String '^worktree .*worktrees' | ForEach-Object { git worktree remove --force $_.Line.Substring(9) }
  git worktree prune
  ```
  (si `git worktree remove` falla por atributos de solo lectura, borrar las carpetas de `.claude\worktrees` con `Remove-Item -Recurse -Force` y después `git worktree prune`).
- Drive: las carpetas «fva-transcripcion» y «ChatbotVVAA» de Mi unidad son el espejo en vivo de las carpetas de trabajo (respaldo de `youtube/crudos`), no se tocan; **ojo que ese espejo sube `clave.env`**. Mandada a la papelera «VIVIR AGRADECIDOS / chatbot / fva-transcripcion (12.50)» (foto del 21/9). «Nuclear Nomads Trash Can» movida a la raíz de Mi unidad de Franco, como pidió. «Videos originales» queda.

**Para retomar mañana, en orden:** (1) los dos comandos de arriba; (2) usuario demo + captura del consentimiento + link en Elementor + staging; (3) completar el formulario de YouTube; (4) Julián: primera tanda del banco → prender «solo banco»; (5) plan de Render; (6) hueco del pipeline del corpus: escribir el script que suma un video nuevo desde `youtube/transcripts/`.
