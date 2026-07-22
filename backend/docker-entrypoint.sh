#!/bin/sh
# Wait for Postgres, run migrations, then start the app.
set -e

echo "==> Waiting for Postgres…"
python - <<'PY'
from app.db import wait_for_db
wait_for_db(timeout_sec=90.0)
print("Postgres is ready.")
PY

echo "==> Running migrations…"
python - <<'PY'
from app.db import ensure_schema
ensure_schema(retries=8)
print("Migrations OK.")
PY

echo "==> Starting app…"
exec python main.py
