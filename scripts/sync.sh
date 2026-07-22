#!/usr/bin/env bash
# Sync this checkout to latest origin/main. Run before any local work.
set -euo pipefail
cd "$(dirname "$0")/.."
git fetch origin
git checkout main
git pull --ff-only origin main
echo "OK — now on $(git rev-parse --short HEAD) ($(git log -1 --pretty=%s))"
