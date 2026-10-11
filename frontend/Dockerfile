# Frontend Dockerfile for Reflex App
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install nodejs & curl for Reflex's frontend compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    unzip \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY frontend/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY frontend /app/frontend
COPY shared /app/shared

WORKDIR /app/frontend

# Pre-compile production frontend bundle at build time so runtime container boots instantly
RUN reflex export --frontend-only --no-zip

EXPOSE 3000
EXPOSE 10000

CMD ["sh", "-c", "reflex run --env prod --backend-host 0.0.0.0 --backend-port ${PORT:-3000} --frontend-port ${PORT:-3000}"]
