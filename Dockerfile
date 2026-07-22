# syntax=docker/dockerfile:1
#
# Iran Market Terminal — single self-contained image:
#   1. builds the React/Vite frontend,
#   2. serves it + the FastAPI API + the continuous background collector
#      from ONE long-lived process on one port.
#
# This image ALWAYS runs the collector (RUN_COLLECTOR=1). It is deliberately not
# the serverless entrypoint (backend/api/index.py) — that one disables polling.

# ---------- Stage 1: build the frontend ----------
FROM node:20-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build                       # -> /build/frontend/dist

# ---------- Stage 2: python runtime (API + collector + static UI) ----------
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HOST=0.0.0.0 \
    PORT=4000 \
    RUN_COLLECTOR=1 \
    TERMINAL_DATA_DIR=/data

WORKDIR /app/backend

# Python deps first for better layer caching
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Backend source + the frontend built in stage 1
COPY backend/ /app/backend/
COPY --from=frontend /build/frontend/dist /app/frontend/dist

# Build stamp — so /api/meta and the Admin page show exactly what's deployed.
# Placed after the source COPY so it refreshes whenever the code changes.
# Pass a commit with:  docker compose build --build-arg GIT_SHA=$(git rev-parse --short HEAD)
ARG GIT_SHA=unknown
ENV APP_GIT_SHA=$GIT_SHA
RUN date -u +"%Y-%m-%dT%H:%M:%SZ" > /app/backend/.build_time

# Run as a non-root user; a named volume mounted at /data inherits its ownership
RUN useradd --system --create-home --uid 10001 appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /app /data
USER appuser

EXPOSE 4000
VOLUME ["/data"]

# The container is "healthy" only while the collector is producing fresh data.
# /api/health returns 503 when market data is stale.
HEALTHCHECK --interval=30s --timeout=8s --start-period=90s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:4000/api/health', timeout=6).status==200 else 1)"

# Long-lived server + supervised background loops + self-restart watchdog.
CMD ["python", "main.py"]
