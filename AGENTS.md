# Agent / AI instructions (MANDATORY)

**Full setup + ops playbook:** [`docs/AGENT_PLAYBOOK.md`](docs/AGENT_PLAYBOOK.md)

Read **`docs/AGENT_PLAYBOOK.md` first** on every session. That file has the complete
checklist: pull, Docker Compose, Postgres, offline builds, migrations, exchange
quirks, version bumps, and verification.

This file is only a short gate.

---

## Before ANY work

```bash
git fetch origin
git checkout main
git pull --ff-only origin main
```

**No pull → no code.**

## Bring the stack up (after pull)

```bash
cp -n .env.example .env
# if docker build fails DNS:
#   ./scripts/prepare-offline-build.sh
docker compose up -d --build
curl -s http://127.0.0.1:4000/api/health
```

Postgres + Alembic migrations run automatically on container start.

## Always

- **PostgreSQL only** (no SQLite / settings.json for runtime data)
- **Bump `APP_VERSION`** in `backend/main.py` (+ `frontend/package.json`) on product changes
- Do not unbounded-fanout exchange polls (`MAX_INFLIGHT` + circuit breakers)

## Rule of thumb

Pull → Compose up → Verify health → Then code.
