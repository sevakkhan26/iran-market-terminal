# syntax=docker/dockerfile:1
#
# Iran Market Terminal — single self-contained image:
#   1. builds the React/Vite frontend,
#   2. serves it + the FastAPI API + the continuous background collector
#      from ONE long-lived process on one port.
#
# Postgres is a *separate* compose service. This image waits for it, runs
# Alembic migrations, then starts the app.

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
    POSTGRES_HOST=db \
    POSTGRES_PORT=5432 \
    POSTGRES_USER=terminal \
    POSTGRES_PASSWORD=terminal \
    POSTGRES_DB=terminal

WORKDIR /app/backend

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ /app/backend/
COPY --from=frontend /build/frontend/dist /app/frontend/dist

ARG GIT_SHA=unknown
ENV APP_GIT_SHA=$GIT_SHA
RUN date -u +"%Y-%m-%dT%H:%M:%SZ" > /app/backend/.build_time \
    && chmod +x /app/backend/docker-entrypoint.sh

RUN useradd --system --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 4000

HEALTHCHECK --interval=30s --timeout=8s --start-period=120s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:4000/api/health', timeout=6).status==200 else 1)"

# Wait for Postgres → alembic upgrade head → python main.py
ENTRYPOINT ["./docker-entrypoint.sh"]
