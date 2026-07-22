# Iran Market Terminal v3

Professional market monitoring platform for Iranian crypto exchanges —
CoinMarketCap-style overview, TradingView-style charting, and dealing-desk
alerting in one product.

**Persistence: PostgreSQL only.** Snapshots, candles, users, sessions, alerts,
settings, and admin config all live in Postgres. There is no SQLite file and no
`settings.json`.

## Always start from latest `main` (humans + AIs)

This project is shared. **Before any work**, sync with GitHub:

```bash
git fetch origin
git checkout main
git pull --ff-only origin main
```

AI agents / coding assistants: read **`AGENTS.md`** first. Rule: **no pull → no code.**

## Quick start (recommended — Docker Compose)

One command starts **Postgres + the app**. Migrations run automatically on boot.

```bash
git clone https://github.com/sevakkhan26/iran-market-terminal.git
cd iran-market-terminal
git pull --ff-only origin main   # if you already cloned
cp .env.example .env             # optional: set AUTH_* / POSTGRES_PASSWORD
docker compose up -d --build
docker compose ps
docker compose logs -f terminal
```

Open **http://127.0.0.1:4000** (or `http://SERVER_IP:4000`).

Default DB credentials (change in `.env` for real use):

| Var | Default |
|-----|---------|
| `POSTGRES_USER` | `terminal` |
| `POSTGRES_PASSWORD` | `terminal` |
| `POSTGRES_DB` | `terminal` |
| `POSTGRES_PORT` | `5432` (host) |

**After every `git pull`:**

```bash
git pull --ff-only origin main
docker compose up -d --build
```

That rebuilds the app image and re-applies any new Alembic migrations.

### What runs

| Service | Role |
|---------|------|
| `db` | PostgreSQL 16 (volume `pgdata`) |
| `terminal` | FastAPI + collector + built React UI |

### Local backend without dockerized app

```bash
# 1. Start only Postgres
docker compose up -d db

# 2. Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # points at 127.0.0.1:5432
alembic upgrade head
# optional frontend
cd ../frontend && npm install && npm run build && cd ../backend
python3 main.py
```

Demo markets (no exchange network): `DEMO_MODE=1 python3 main.py`

## Database & migrations

- Driver: **psycopg3** connection pool (`backend/app/db.py`)
- Schema: **Alembic** under `backend/alembic/versions/`
- On container start: `docker-entrypoint.sh` waits for Postgres → `alembic upgrade head` → `python main.py`
- Runtime settings (poll intervals, timeouts, …) are rows in `app_settings` — not a JSON file

Add a schema change:

```bash
cd backend
# edit models / write a new file under alembic/versions/
alembic upgrade head          # apply locally
# bump APP_VERSION in backend/main.py
```

## Deploy on a server

Same as quick start. **Do not** deploy the serverless entrypoint
(`backend/api/index.py`) as the only process on a server — that mode disables
the collector.

Reliability built in:

- **Always collects.** The image sets `RUN_COLLECTOR=1`.
- **Self-healing loops** with timeouts + watchdog restart.
- **Observable.** `GET /api/health`; Admin diagnostics show Postgres row counts.
- **Persistent.** All data is in the `pgdata` Docker volume.

Generate the auth secrets once the image is built:

```bash
docker compose run --rm terminal python main.py hash-password "your-strong-password"
docker compose run --rm terminal python main.py generate-secret
# paste both into .env, then:  docker compose up -d
```

## Authentication

Users and sessions are stored in **PostgreSQL** (`users`, `auth_sessions`).
Bootstrap the first admin from env (or defaults for local only):

```bash
docker compose run --rm terminal python main.py hash-password "your-strong-password"
docker compose run --rm terminal python main.py generate-secret
# paste into .env → AUTH_PASSWORD_HASH / AUTH_TOKEN_SECRET, then recreate
docker compose up -d
```

| Variable             | Purpose                                              |
|----------------------|------------------------------------------------------|
| `AUTH_USERNAME`      | bootstrap admin username (default `admin`)           |
| `AUTH_PASSWORD_HASH` | PBKDF2 hash for first admin (secret #1)              |
| `AUTH_TOKEN_SECRET`  | session/token material (secret #2)                   |
| `AUTH_PASSWORD`      | dev-only plaintext alternative to the hash           |

Without secrets set, first boot creates `admin`/`admin` (forced password change).
Never commit `.env`.

## Development

```bash
cd backend  && DEMO_MODE=1 python3 main.py     # API on :4000
cd frontend && npm run dev                      # Vite dev server on :5173 (proxies /api and /ws)
cd backend  && python3 -m pytest tests/         # unit tests
```

## Configuration

- **Postgres:** `DATABASE_URL` or `POSTGRES_HOST` / `USER` / `PASSWORD` / `DB`.
- `backend/app_config.json` — optional static defaults (exchange list, fees,
  assets). Runtime Admin changes (pairs, custom exchanges, poll settings) go to
  Postgres tables / `app_settings`.
- Environment: `DEMO_MODE=1`, `ADMIN_TOKEN=…`, `PORT=…`, `HOST=…`, `AUTH_*`.
- Runtime settings (poll intervals, timeouts) are editable in **Admin** and
  stored in the `app_settings` table.

## Adding exchanges & pairs — no rebuild

- **New pair**: Admin → *Add Trading Pair* → enter base symbol (e.g. `DOGE`).
  Effective on the next poll cycle. (Built-in connectors must support the
  symbol; the generic connector uses its `symbol_template`.)
- **New exchange**: Admin → *Add Exchange* → name + declarative JSON spec:

```json
{
  "orderbook_url": "https://api.example.com/depth?symbol={symbol}",
  "symbol_template": "{base}{quote}",
  "quote_name": "IRT",
  "bids_path": "result.bids",
  "asks_path": "result.asks",
  "price_scale": 0.1,
  "stats_url": "https://api.example.com/ticker?symbol={symbol}",
  "last_path": "lastPrice",
  "volume_base_path": "volume",
  "taker_fee_pct": 0.25
}
```

`price_scale: 0.1` converts Rial-quoted venues to Toman. Dot-paths navigate the
JSON response; `{symbol}` is substituted in URLs and paths.

- **Security**: set `admin_token` in config (or `ADMIN_TOKEN` env) to require
  `X-Admin-Token` on all mutating endpoints. Empty = open (local use only).

## Architecture (summary)

```
docker-compose.yml   Postgres (`db`) + app (`terminal`)
backend/
  main.py            FastAPI + collector + static UI; runs migrations on start
  docker-entrypoint.sh  wait for Postgres → alembic upgrade head → main.py
  alembic/           schema migrations (source of truth)
  app/
    config.py        static defaults + optional app_config.json + env
    settings.py      runtime settings → Postgres app_settings
    db.py            PostgreSQL pool (psycopg3) — all persistence
    connectors.py    Iranian exchanges + GenericRest + CoinGecko + demo
    aggregator.py    poll cycle → metrics → composite → snapshots
    …
frontend/            React 18 + Vite, lightweight-charts, EN/FA + RTL
```

See `ARCHITECTURE.md` for the full design review and roadmap.
