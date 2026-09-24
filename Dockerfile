# LaTablée — ONE container: FastAPI serves both the API and the built web UI.
ARG NEXT_PUBLIC_BASE_PATH=""
ARG BUILD_FROM=python:3.12-slim

FROM node:20-alpine AS webui
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci || npm install
COPY frontend ./
ARG NEXT_PUBLIC_BASE_PATH
ENV NEXT_PUBLIC_BASE_PATH=$NEXT_PUBLIC_BASE_PATH
RUN npm run build

FROM ${BUILD_FROM}
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    LATABLEE_STATIC_DIR=/srv/latablee/static

WORKDIR /srv/latablee
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential libxml2-dev libxslt1-dev curl ffmpeg libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY backend ./backend
RUN pip install --no-cache-dir .

# Web UI build output → served by the API itself (mounted at /static + SPA fallback)
COPY --from=webui /build/out /srv/latablee/static

RUN useradd -m -u 1000 latablee && mkdir -p /srv/latablee/data && chown -R latablee /srv/latablee
USER latablee

EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
  CMD curl -fsS http://localhost:3000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3000", "--app-dir", "backend"]