#!/bin/sh
# Wait for Postgres, run migrations, then start the app.
set -e

echo "Waiting for Postgres…"
python - <<'PY'
import os, time, sys
import psycopg

url = os.environ.get("DATABASE_URL", "").strip()
if not url:
    user = os.environ.get("POSTGRES_USER", "terminal")
    password = os.environ.get("POSTGRES_PASSWORD", "terminal")
    host = os.environ.get("POSTGRES_HOST", "db")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ.get("POSTGRES_DB", "terminal")
    url = f"postgresql://{user}:{password}@{host}:{port}/{db}"

deadline = time.time() + 60
last = None
while time.time() < deadline:
    try:
        with psycopg.connect(url, connect_timeout=3) as conn:
            conn.execute("SELECT 1")
        print("Postgres is ready.")
        sys.exit(0)
    except Exception as exc:
        last = exc
        time.sleep(1)
print(f"Postgres not ready: {last}", file=sys.stderr)
sys.exit(1)
PY

echo "Running migrations…"
alembic upgrade head

echo "Starting app…"
exec python main.py
