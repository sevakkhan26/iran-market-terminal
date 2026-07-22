#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p backend/wheelhouse

echo "==> Python wheels (use docker --dns if host pip lacks network inside containers)"
if command -v docker >/dev/null 2>&1; then
  docker run --rm --dns 8.8.8.8 --dns 1.1.1.1 \
    -v "$ROOT/backend/requirements.txt:/req.txt:ro" \
    -v "$ROOT/backend/wheelhouse:/wheels" \
    python:3.12-slim bash -c \
    "pip install -U pip && pip download -r /req.txt -d /wheels && pip download setuptools wheel -d /wheels"
else
  python3 -m pip download -r backend/requirements.txt -d backend/wheelhouse
  python3 -m pip download setuptools wheel -d backend/wheelhouse
fi

echo "==> Frontend build"
cd frontend
npm install --no-audit --no-fund
npm run build
cd "$ROOT"
test -f frontend/dist/index.html
echo "OK — docker compose build && docker compose up -d"
