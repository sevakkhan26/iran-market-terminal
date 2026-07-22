# Iran Market Terminal v2

Professional market monitoring platform for Iranian crypto exchanges —
CoinMarketCap-style overview, TradingView-style charting, and dealing-desk
alerting in one product.

## Always start from latest `main` (humans + AIs)

This project is shared. **Before any work**, sync with GitHub:

```bash
git fetch origin
git checkout main
git pull --ff-only origin main
```

AI agents / coding assistants: read **`AGENTS.md`** first. Rule: **no pull → no code.**

## Quick start

```bash
# 1. Backend
cd backend
pip install -r requirements.txt

# 2. Frontend (one-time build; all dependencies bundled locally, no CDN)
cd ../frontend
npm install
npm run build

# 3. Run (serves API + UI on http://127.0.0.1:4000)
cd ../backend
python3 main.py

# Or try it immediately with synthetic markets (no internet needed):
DEMO_MODE=1 python3 main.py
```

Open **http://127.0.0.1:4000**.

## Deploy on a server (Docker) — recommended

This is the supported way to run it on a server. One image builds the frontend
and runs the API **plus the continuous background collector** in one long-lived
process. **Do not deploy the serverless entrypoint (`backend/api/index.py`) on a
server** — that mode disables the collector on purpose, which looks like "the UI
loads but data never updates."

```bash
git clone https://github.com/sevakkhan26/iran-market-terminal.git
cd iran-market-terminal
cp .env.example .env            # optional: set AUTH_* now, or run with defaults first
docker compose up -d --build    # build + start
docker compose ps               # STATUS should become "healthy"
docker compose logs -f          # you should see a "heartbeat" line every ~60s
```

Open **http://SERVER_IP:4000**.

**After every `git pull`, rebuild** — otherwise Docker keeps running the old
image (the #1 cause of "my fix didn't take effect"):

```bash
git pull && docker compose up -d --build
```

Reliability built in:

- **Always collects.** The image sets `RUN_COLLECTOR=1`; polling can't be
  silently disabled.
- **Self-healing.** Each loop is timeout-bounded and auto-restarts; a stuck
  network/DB call aborts its cycle instead of freezing collection.
- **Self-restarting.** If market data goes stale for >5 min (process wedged), a
  watchdog exits and `restart: unless-stopped` brings up a clean container — **no
  more manual `docker restart`.** Tune with `WATCHDOG_STALE_EXIT_SEC`.
- **Observable.** `GET /api/health` returns `200` while data is fresh, `503`
  when stale (drives the Docker health check); logs print a per-loop heartbeat.
- **Persistent.** The SQLite database lives in the `terminal-data` volume and
  survives rebuilds/restarts.

Generate the auth secrets once the image is built:

```bash
docker compose run --rm terminal python main.py hash-password "your-strong-password"
docker compose run --rm terminal python main.py generate-secret
# paste both into .env, then:  docker compose up -d
```

## Authentication (environment-driven, two secrets)

Single account, configured entirely through environment variables — no
credentials in code or in the database, no disk writes on login (works on
read-only/serverless hosting).

```bash
cd backend
cp .env.example .env
python3 main.py hash-password "your-strong-password"   # → AUTH_PASSWORD_HASH=…
python3 main.py generate-secret                        # → AUTH_TOKEN_SECRET=…
# paste both lines into .env, set AUTH_USERNAME, start the server
```

| Variable             | Purpose                                              |
|----------------------|------------------------------------------------------|
| `AUTH_USERNAME`      | login username (default `admin`)                     |
| `AUTH_PASSWORD_HASH` | PBKDF2 hash of the password (secret #1)              |
| `AUTH_TOKEN_SECRET`  | random token-signing secret (secret #2)              |
| `AUTH_PASSWORD`      | dev-only plaintext alternative to the hash           |

On **Vercel/hosting**: add the same variables in Settings → Environment
Variables. Session tokens are HMAC-signed with a key derived from *both*
secrets, so rotating either one (change the env var + redeploy) instantly
invalidates all sessions. Without any variables set, the app falls back to
`admin`/`admin` with a loud startup warning — local development only.
Never commit `.env` (already in .gitignore).

## Development

```bash
cd backend  && DEMO_MODE=1 python3 main.py     # API on :4000
cd frontend && npm run dev                      # Vite dev server on :5173 (proxies /api and /ws)
cd backend  && python3 -m pytest tests/         # unit tests
```

## Configuration

- `backend/app_config.json` — enabled exchanges, taker fees, assets, retention,
  reference-price source, server host/port, admin token.
- Environment: `DEMO_MODE=1`, `ADMIN_TOKEN=…`, `PORT=…`, `HOST=…`,
  `TERMINAL_DATA_DIR=…` (SQLite + settings location).
- Runtime settings (poll intervals, timeouts) are editable in the **Admin** page
  and persist across restarts.

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
backend/
  main.py            FastAPI app, REST + WebSocket, background loops, serves frontend/dist
  app/
    config.py        app_config.json + env overrides
    settings.py      runtime-tunable settings (persisted)
    models.py        dataclasses (snapshots, order books, events, alerts)
    connectors.py    6 Iranian exchanges (full depth + 24h stats + candles),
                     GenericRestConnector (JSON-spec), CoinGecko reference, demo generator
    aggregator.py    poll cycle → metrics → composite index → 5-min snapshots
    metrics.py       1H/24H/7D change, spread stats, liquidity score, Iran premium,
                     depth+fee-aware arbitrage, anomaly detection
    alerts.py        rule engine (8 rule types), cooldowns, persisted events
    candles.py       native klines + ring-built 60s candles, resampling for 1H–1M
    news.py          RSS news + ForexFactory calendar, surprise %, DB persistence
    db.py            SQLite WAL, batched writes, hourly retention pruning
frontend/            React 18 + Vite, lightweight-charts, EN/FA + RTL, zero runtime CDN
```

See `ARCHITECTURE.md` for the full design review and roadmap.
