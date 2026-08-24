# Asistente de contenido — Vivir Agradecidos

App de búsqueda y armado de contenido sobre el material real del Hermano David y los
facilitadores de la Fundación. Es **una sola app** que corre igual **en local** y **en
Streamlit Cloud** (sin divergencia).

## Correr en LOCAL
1. Instalar dependencias (una sola vez):

       pip install -r requirements.txt

2. Poné tus claves en `.streamlit/secrets.toml` (tu `OPENAI_API_KEY` nueva + una `APP_PASSWORD`).
   Ese archivo **no se sube** (está en `.gitignore`).
3. Levantar la app:

       streamlit run app.py

4. Se abre en el navegador y pide la contraseña (`APP_PASSWORD`).

## Deploy en Streamlit Cloud
- La app publicada toma este mismo repo (branch `main`, archivo `app.py`).
- Los secrets se cargan en **Streamlit Cloud → Advanced settings → Secrets** (no van en el repo).
- Para actualizar: **Commit + Push** en GitHub Desktop → Streamlit redeploya solo.

## Qué hay acá
- `app.py` — la app: búsqueda semántica + copiloto (tool-calling) + armado de borradores.
- `fragmentos.jsonl` — el corpus (videos + web + libros); los libros incluyen la página.
- `fragmentos_openai.npy` — embeddings del corpus (OpenAI, 512 dim).
- `.streamlit/config.toml` — tema de marca (claro/oscuro).
- `requirements.txt` — dependencias.

## Actualizar el corpus
El corpus se genera en el proyecto **fva-transcripcion** (pipeline de transcripción +
embeddings). Cuando cambie, copiar `corpus/fragmentos.jsonl` y `corpus/fragmentos_openai.npy`
a este repo → Commit + Push.
