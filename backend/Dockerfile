# Financial AI Agent backend
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

# Persistent memory lives here; mount a volume in production.
ENV CHROMA_DB_PATH=/data/chroma_db
RUN mkdir -p /data/chroma_db

EXPOSE 8000

# $PORT is provided by Railway/Render; default to 8000 locally.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
