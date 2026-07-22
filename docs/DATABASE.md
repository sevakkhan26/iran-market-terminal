# Database guide (PostgreSQL)

## Why Postgres

v3+ stores **all** runtime state in PostgreSQL (stable production path):

| Data | Table(s) |
|------|----------|
| Price / composite history | `price_snapshots`, `composite_snapshots` |
| Candles | `candles` |
| Calendar / news cache rows | `calendar_events` |
| Alerts | `alert_rules`, `alert_events` |
| Admin pairs / custom exchanges | `custom_pairs`, `custom_exchanges` |
| USD reference | `reference_prices`, `reference_ids` |
| Intelligence | `tob_share`, `arb_windows`, `trade_volumes` |
| Auth | `users`, `auth_sessions` |
| Runtime settings | `app_settings` |

There is **no** SQLite file and **no** `settings.json`.

## Connection

Set either:

```bash
DATABASE_URL=postgresql://terminal:terminal@127.0.0.1:5432/terminal
```

or discrete vars (`POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`,
`POSTGRES_PASSWORD`, `POSTGRES_DB`). Compose wires these for you.

## Migrations (Alembic)

```bash
cd backend
alembic upgrade head          # apply
alembic current               # show revision
alembic history               # list
```

New migration: add a file under `alembic/versions/` (or
`alembic revision -m "…"` then edit). **Never** change applied revisions in
place on shared branches — add a new revision.

Docker entrypoint always runs `alembic upgrade head` before starting the app,
so a teammate who only does:

```bash
git pull
docker compose up -d --build
```

gets a fully migrated database automatically.

## After git pull (for collaborators)

```bash
git fetch origin && git checkout main && git pull --ff-only origin main
docker compose up -d --build
docker compose logs -f terminal   # look for "Database schema is up to date" / "Postgres is ready"
```

Wipe DB and start clean (dev only):

```bash
docker compose down -v
docker compose up -d --build
```
