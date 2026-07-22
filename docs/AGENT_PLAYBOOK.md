# Agent playbook — Iran Market Terminal

**Read this file completely before doing anything else.**  
This is the single source of truth for AI agents (Claude, Cursor, Copilot, Grok, …).

If instructions conflict, prefer: **this file > `AGENTS.md` > `README.md`**.

---

## 0. Absolute rules

1. **No pull → no code.** Always sync `origin/main` first.
2. **Postgres only.** Never reintroduce SQLite, `settings.json`, or file-based runtime state.
3. **Bump version** on every product change (`backend/main.py` → `APP_VERSION` + `frontend/package.json`).
4. **After pull:** rebuild/restart so the friend (or you) is not on a stale image.
5. **Do not invent deploy paths.** Use Docker Compose from the repo root unless the user forbids Docker.

---

## 1. First actions every session (copy-paste)

```bash
cd /path/to/iran-market-terminal
git fetch origin
git checkout main
git pull --ff-only origin main
git log -3 --oneline
git status
```

If pull fails (local commits / dirty tree):

- Show `git status` and recent log to the user.
- Do **not** keep coding on an outdated base.
- With user approval: stash/commit, then `git pull --rebase origin main` or reset as they prefer.

---

## 2. Bring the project up (local / friend machine)

### 2.1 Happy path

```bash
cp -n .env.example .env
# optional: edit AUTH_*, POSTGRES_PASSWORD, POSTGRES_PORT

docker compose up -d --build
docker compose ps
docker compose logs -f terminal
```

Open **http://127.0.0.1:4000**

What this does:

| Step | Automatic? |
|------|------------|
| Start PostgreSQL (`db`) | Yes |
| Start app + collector (`terminal`) | Yes |
| `alembic upgrade head` (schema) | Yes (entrypoint) |
| Auth bootstrap (admin user) | Yes |
| Load 18 default assets from `app_config.json` | Yes |

Default login if secrets empty: often **admin / admin** (forced password change may apply).  
Prefer setting `AUTH_*` in `.env` for real use.

### 2.2 If Docker build fails (pip/npm DNS errors)

Very common on some hosts (Docker cannot resolve pypi.org / registry.npmjs.org).

```bash
./scripts/prepare-offline-build.sh
# or manually:
# docker run --rm --dns 8.8.8.8 --dns 1.1.1.1 \
#   -v "$PWD/backend/requirements.txt:/req.txt:ro" \
#   -v "$PWD/backend/wheelhouse:/wheels" \
#   python:3.12-slim bash -c \
#   "pip install -U pip && pip download -r /req.txt -d /wheels && pip download setuptools wheel -d /wheels"
# cd frontend && npm install && npm run build && cd ..

docker compose up -d --build
```

Image install uses local `backend/wheelhouse` + `frontend/dist` when present (see `Dockerfile`).

### 2.3 Port clashes

| Host port | Default | If busy |
|-----------|---------|---------|
| App | `4000` (`PORT`) | change `PORT` in `.env` |
| Postgres | `5433` (`POSTGRES_PORT`) | e.g. `5435` in `.env` |

Inside Compose, app always talks to `db:5432`.

### 2.4 Verify stack is healthy

```bash
docker compose ps
curl -s http://127.0.0.1:4000/api/health
docker compose logs --tail 50 terminal
```

Expect:

- `db` = healthy  
- `terminal` = healthy / up  
- health JSON: `"status":"ok"`, `"collector_enabled":true`  
- logs: Postgres ready, migrations OK, market cycle / heartbeat  

Admin UI → System Diagnostics should show **database: postgres://…** and market feed live.

---

## 3. Architecture agents must not break

```
docker-compose.yml
  db          → PostgreSQL 16 (volume pgdata)
  terminal    → FastAPI + background collector + static React

backend/
  docker-entrypoint.sh   wait PG → alembic upgrade head → python main.py
  alembic/               schema migrations (source of truth)
  app/db.py              all persistence (psycopg3 pool)
  app/settings.py        runtime settings → table app_settings
  app/aggregator.py      poll cycle (semaphores + circuit breakers)
  app/connectors.py      exchange APIs
  app_config.json        default assets / exchange toggles / coingecko ids
  main.py                APP_VERSION + API + loops

frontend/                React + Vite (built into dist, served by backend)
```

### Persistence map (all Postgres)

| Data | Where |
|------|--------|
| Prices / composites | `price_snapshots`, `composite_snapshots` |
| Candles | `candles` |
| Calendar | `calendar_events` |
| Alerts | `alert_rules`, `alert_events` |
| Custom pairs / exchanges | `custom_pairs`, `custom_exchanges` |
| USD refs | `reference_prices`, `reference_ids` |
| Intelligence | `tob_share`, `arb_windows`, `trade_volumes` |
| Auth | `users`, `auth_sessions` |
| Runtime settings | `app_settings` |

**Forbidden regressions:** SQLite files, `settings.json` for runtime, writing market history to disk JSON/XML.

---

## 4. Schema changes

```bash
cd backend
# add file under alembic/versions/  (never rewrite applied revisions)
alembic upgrade head
# bump APP_VERSION
```

Docker entrypoint always runs `alembic upgrade head` on start.

Details: `docs/DATABASE.md`.

---

## 5. Migrating old SQLite data (optional)

Only needed when recovering from a pre-v3 volume (`terminal.db`).

```bash
# Example: old data volume + running compose network
docker run --rm --network iran-market-terminal_default \
  -v docker-projects_iran-market-data:/data:ro \
  -v "$PWD/scripts:/scripts:ro" \
  -e DATABASE_URL=postgresql://terminal:terminal@iran-market-db:5432/terminal \
  -e SQLITE_PATH=/data/terminal.db \
  -e MIGRATE_HISTORY=1 \
  python:3.12-slim bash -c \
    "pip install -q 'psycopg[binary]' && python /scripts/migrate_sqlite_to_postgres.py"
```

If Docker cannot open the SQLite file (WAL), copy `terminal.db` (+ wal/shm) into a project-local folder first, then mount that folder.

Script: `scripts/migrate_sqlite_to_postgres.py`  
- Default assets also live in `backend/app_config.json` (18 pairs) so a **fresh** install is usable without SQLite migrate.

---

## 6. Exchange / feed notes agents must know

- Polling is **bounded** (`MAX_INFLIGHT`, per-exchange semaphores, circuit breakers). Do not fan out unlimited concurrent order-book requests.
- **Exir** rate-limits hard → majors only + cooldown (see connectors).
- **Ramzinex** public CDN often **TCP-times out** on some networks.  
  - Disable: `RAMZINEX_DISABLE=1` in `.env`  
  - Force on: `RAMZINEX_FORCE=1`  
  - Custom base: `RAMZINEX_API_BASE=https://…`  
- Unsupported venue×pair slots must **not** create permanent red Admin chips (skip storing them).

---

## 7. After every code change (agent checklist)

```text
[ ] git pull --ff-only origin main (start of work)
[ ] implement change
[ ] bump APP_VERSION (+ frontend package.json version)
[ ] if schema change → new Alembic revision
[ ] if Docker/deploy docs change → update this playbook / README
[ ] git pull again before commit (catch concurrent pushes)
[ ] commit with clear message
[ ] push if user asked
[ ] docker compose up -d --build  (when verifying locally)
[ ] curl /api/health + check Admin diagnostics / overview assets
```

---

## 8. Common failures and fixes

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| UI loads, prices all `-`, venues 0/N | Collector off / DNS / old image | `RUN_COLLECTOR=1`, rebuild, check logs, Admin connectivity test |
| `pip` / `npm` fail inside `docker build` | Docker DNS | `./scripts/prepare-offline-build.sh` then rebuild |
| Port 5432/5433 in use | Another Postgres | set `POSTGRES_PORT=5435` in `.env` |
| Only BTC/ETH/USDT after DB wipe | Fresh Postgres | expected; defaults now 18 assets in `app_config.json`, or re-run migrator |
| Red Ramzinex only | API blocked on host | `RAMZINEX_DISABLE=1` |
| Agent works on stale code | Skipped pull | re-read §1 |

---

## 9. What “friend after git pull” should look like

If their agent follows this playbook:

1. Pull latest `main`  
2. `docker compose up -d --build` (or offline prepare first)  
3. App + Postgres + migrations run  
4. Markets show **18 assets** (from config) and live feeds from reachable exchanges  
5. No SQLite dependency  

They will **not** automatically get another machine’s production history unless someone runs the migrator or shares a DB dump.

---

## 10. Files to open in order (agents)

1. **`docs/AGENT_PLAYBOOK.md`** ← you are here  
2. `AGENTS.md`  
3. `docs/DATABASE.md`  
4. `README.md`  
5. `docker-compose.yml`, `Dockerfile`, `backend/docker-entrypoint.sh`  
6. Then source under `backend/app/`

---

## 11. One-line summary for the agent

**Pull `main`, bring up Compose (Postgres + app), never reintroduce file DBs, bump version on changes, verify `/api/health` and Admin diagnostics before claiming success.**
