FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HOST=0.0.0.0 \
    PORT=4000 \
    RUN_COLLECTOR=1

WORKDIR /app/backend

COPY backend/requirements.txt ./
COPY backend/wheelhouse /wheelhouse/

RUN set -e; \
    if ls /wheelhouse/*.whl >/dev/null 2>&1; then \
      echo "pip: offline wheelhouse"; \
      pip install --no-index --find-links=/wheelhouse setuptools wheel; \
      pip install --no-index --find-links=/wheelhouse --no-build-isolation -r requirements.txt; \
    else \
      pip install --no-cache-dir -r requirements.txt; \
    fi; \
    rm -rf /wheelhouse

COPY backend/ /app/backend/
COPY frontend/dist /app/frontend/dist

ARG GIT_SHA=unknown
ENV APP_GIT_SHA=$GIT_SHA
RUN date -u +"%Y-%m-%dT%H:%M:%SZ" > /app/backend/.build_time \
    && chmod +x /app/backend/docker-entrypoint.sh \
    && test -f /app/frontend/dist/index.html

RUN useradd --system --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 4000
HEALTHCHECK --interval=30s --timeout=8s --start-period=120s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:4000/api/health', timeout=6).status==200 else 1)"
ENTRYPOINT ["./docker-entrypoint.sh"]
