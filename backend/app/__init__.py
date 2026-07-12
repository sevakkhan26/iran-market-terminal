"""App package. Loads backend/.env into the environment on first import so the
same AUTH_* / config variables work locally exactly as they do on Vercel.
Real environment variables always win over .env values."""
import logging
import os
from pathlib import Path

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def _load_dotenv() -> None:
    try:
        if not _ENV_PATH.exists():
            return
        for raw in _ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                os.environ.setdefault(key, value)   # env vars take precedence
    except Exception as exc:  # pragma: no cover — never block startup
        logging.getLogger("terminal.env").warning("could not read .env: %s", exc)


_load_dotenv()
