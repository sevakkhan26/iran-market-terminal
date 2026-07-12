# Iran Market Terminal v2

Professional market monitoring platform for Iranian crypto exchanges —
CoinMarketCap-style overview, TradingView-style charting, and dealing-desk
alerting in one product.

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
