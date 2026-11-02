# Asistente de contenido — Vivir Agradecidos

Plataforma de contenido de la Fundación: chat sobre el material real del Hermano David y los facilitadores,
diseño de piezas por canal (Instagram, Facebook, blogpost, YouTube, email), recortes de video, newsletter,
Frase del día y circuito de aprobación. Desde el 2/11/2026 es **solo la web + la API** (la app de Streamlit se dio de baja).

## Qué hay acá
- `api/` — la API (FastAPI). `api/main.py` arma la app; cada pantalla tiene su módulo de rutas (`chat_rutas.py`,
  `publicar_rutas.py`, `frases_rutas.py`, `recortes.py`, `admin_rutas.py`…). Corre en **Render** (`render.yaml`, Docker:
  `api/Dockerfile`). Pruebas: `python -m pytest api/tests -q`.
- `web/` — la interfaz (Vite + React + TypeScript). Corre en **Vercel** (`chatbot-vvaa.vercel.app`). `npm run build` en `web/`.
- `nucleo.py` — búsqueda sobre el corpus (`fragmentos.jsonl` + `fragmentos_openai.npy`) y el asistente.
- `db.py` — Supabase (REST). `publicar.py` — conectores (WordPress, Instagram, Facebook, YouTube, WhatsApp prototipo).
  `imagen.py` — la foto con la frase encima. `programar_frases.py` + `frase_mail.py` + `perfit.py` — la Frase del día.
  `newsletter.py` — las plantillas del newsletter. `recortar_clip.py` / `procesar_clips.py` — recortes de video.
- `procesar_cola.py` — la cola de publicación: corre en **GitHub Actions** cada 15 minutos (`.github/workflows/cola.yml`).
- `distribucion/` — plantillas que se copian a otros lados (el mail de la frase, el snippet de WordPress de la home).
- `archivo/` — prototipos viejos, no se usan.

## Correr en local
1. `pip install -r requirements.txt` (una sola vez) y en `web/`: `npm install`.
2. Las claves van en `.streamlit/secrets.toml` (nombre histórico; es solo el archivo local de secretos, no se sube) o en
   `../fva-transcripcion/clave.env`. `api/config.py` y `procesar_cola.py` las cargan al entorno.
3. API: `uvicorn api.main:app --reload --port 8000`. Web: `npm run dev` en `web/` (apunta a la API local).

## Deploy
- **Render** (API): despliega solo con cada push a `main`. Las variables no secretas están en `render.yaml` como
  documentación, pero el Blueprint **no las sincroniza**: una variable nueva o cambiada hay que cargarla también a mano en
  Render → fva-api → Environment. Los secretos se pegan desde `api.env` (`python api/armar_env.py`).
- **Vercel** (web): despliega solo con cada push a `main`.
- **GitHub Actions** (cola): los secretos en Settings → Secrets and variables → Actions (`PUBLICAR_*`, claves de los canales).

## Actualizar el corpus
El corpus se genera en el proyecto **fva-transcripcion** (transcripción + embeddings). Cuando cambie, copiar
`corpus/fragmentos.jsonl` y `corpus/fragmentos_openai.npy` a este repo → commit + push (Render reconstruye la imagen).

El diario de trabajo (decisiones, incidentes, qué se probó) está en `../fva-transcripcion/HANDOFF.md`.
