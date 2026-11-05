
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
