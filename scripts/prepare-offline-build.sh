#!/usr/bin/env bash
# Prepare wheelhouse + frontend/dist on the HOST (where DNS works), so
# `docker compose build` can install without PyPI/npm network access.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Downloading Python wheels → backend/wheelhouse"
mkdir -p backend/wheelhouse
python3 -m pip download -r backend/requirements.txt -d backend/wheelhouse

echo "==> Building frontend → frontend/dist"
cd frontend
if [ -f package-lock.json ]; then
  npm install --no-audit --no-fund
else
  npm install --no-audit --no-fund
fi
npm run build
cd "$ROOT"

echo "==> Ready. Build with:"
echo "    docker compose build && docker compose up -d"
echo "    # or: docker build --build-arg GIT_SHA=\$(git rev-parse --short HEAD) -t iran-market-terminal:latest ."
