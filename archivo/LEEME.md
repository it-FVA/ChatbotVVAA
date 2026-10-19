# archivo/ — código que ya no usa la app (18/10/2026, housekeeping)

Nada de esta carpeta se importa desde `app.py`, `nucleo.py` ni los workflows. Queda por historia; se puede borrar sin tocar producción.

- `prototipo_hibrida.py`, `prototipo_distinciones.py`, `resultado_distinciones.txt` (sep/2026): experimentos de búsqueda. La híbrida ya está en `nucleo.py` (`BUSQUEDA_HIBRIDA`); las distinciones no se adoptaron.
- `Taxonomia_v02_normalizada.xlsx`: copia de la planilla que usaba el prototipo de distinciones. La versión viva está en `fva-transcripcion/analisis/`.
- `servidor.py` (sep/2026): UI HTML local para demos, anterior a la app de Streamlit.
- `admin.py` (sep/2026): panel local de revisión de conversaciones, reemplazado por «Panel admin» dentro de la app.
