"""Point tests at a disposable Postgres (or skip DB-heavy paths).

Set TEST_DATABASE_URL to a throwaway database, e.g.:
  postgresql://terminal:terminal@127.0.0.1:5432/terminal_test

If unset, we use the default local compose DB and rely on transactions / unique
usernames. Prefer a dedicated test DB for CI.
"""
import os

os.environ.setdefault("DEMO_MODE", "1")
os.environ.setdefault("POSTGRES_HOST", os.environ.get("POSTGRES_HOST", "127.0.0.1"))
os.environ.setdefault("POSTGRES_PORT", os.environ.get("POSTGRES_PORT", "5432"))
os.environ.setdefault("POSTGRES_USER", os.environ.get("POSTGRES_USER", "terminal"))
os.environ.setdefault("POSTGRES_PASSWORD", os.environ.get("POSTGRES_PASSWORD", "terminal"))
os.environ.setdefault("POSTGRES_DB", os.environ.get("POSTGRES_DB", "terminal"))
if os.environ.get("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]

# Run migrations once for the test process
try:
    from app.db import ensure_schema
    ensure_schema()
except Exception as exc:  # pragma: no cover
    import warnings
    warnings.warn(f"Could not migrate test database: {exc}")
