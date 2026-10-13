# Frontend Dockerfile for Reflex App
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_ROOT_USER_ACTION=ignore \
    ENVIRONMENT=production \
    PYTHONPATH="/app/frontend:/app"

# Create dedicated virtual environment so pip never runs directly on system python
ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"


# Install nodejs & curl ONLY for building frontend assets during docker build
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    unzip \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY frontend/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY frontend /app/frontend
COPY shared /app/shared
RUN mkdir -p /app/data/samples /app/frontend/data/samples && \
    if [ -d "/app/frontend/data/samples" ]; then cp -r /app/frontend/data/samples/* /app/data/samples/ 2>/dev/null || true; fi

WORKDIR /app/frontend

# Pre-compile production static frontend bundle at Docker build time
RUN reflex export --frontend-only --no-zip

EXPOSE 3000
EXPOSE 10000

# Start ultra-lightweight Uvicorn server (~45MB RAM, NO Node.js running at runtime!)
CMD ["python", "server.py"]
