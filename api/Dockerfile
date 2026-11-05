# API del asistente (fase 0). Se construye desde la RAÍZ del repo (necesita nucleo.py, el paquete db/ y el corpus):
#   docker build -f api/Dockerfile -t fva-api .
#   docker run -p 8000:8000 --env-file api.env fva-api
# Independiente del hosting: Railway y Render detectan el Dockerfile y pasan $PORT.
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
# Los módulos de la raíz se copian por patrón: un módulo nuevo no exige tocar este archivo.
COPY *.py datos_fijos.md logo.png fragmentos.jsonl fragmentos_openai.npy ./
# (5/11) VECTORES=supabase en Render: los embeddings se consultan en pgvector y fragmentos_openai.npy no se carga en memoria.
# El archivo sigue en la imagen solo como respaldo para volver a VECTORES=local sin redeploy de código.
COPY fuentes ./fuentes
COPY distribucion ./distribucion
COPY db ./db
COPY api ./api
EXPOSE 8000
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
