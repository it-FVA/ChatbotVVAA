# API del asistente (fase 0). Se construye desde la RAÍZ del repo (necesita nucleo.py, db.py y el corpus):
#   docker build -f api/Dockerfile -t fva-api .
#   docker run -p 8000:8000 --env-file api.env fva-api
# Independiente del hosting: Railway y Render detectan el Dockerfile y pasan $PORT.
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY api/requirements.txt api/requirements.txt
RUN pip install --no-cache-dir -r api/requirements.txt
COPY nucleo.py db.py publicar.py recortar_clip.py imagen.py datos_fijos.md logo.png fragmentos.jsonl fragmentos_openai.npy ./
COPY fuentes ./fuentes
COPY api ./api
EXPOSE 8000
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
