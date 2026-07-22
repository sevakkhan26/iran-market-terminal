"""Initial PostgreSQL schema for Iran Market Terminal.

Revision ID: 001_initial
Revises:
Create Date: 2026-07-22

All runtime state lives in Postgres — no SQLite / settings.json.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS price_snapshots (
            id BIGSERIAL PRIMARY KEY,
            exchange TEXT NOT NULL,
            base TEXT NOT NULL,
            quote TEXT NOT NULL,
            bid DOUBLE PRECISION,
            ask DOUBLE PRECISION,
            mid DOUBLE PRECISION,
            spread_pct DOUBLE PRECISION,
            bid_depth DOUBLE PRECISION,
            ask_depth DOUBLE PRECISION,
            volume_24h_base DOUBLE PRECISION,
            volume_24h_quote DOUBLE PRECISION,
            ts DOUBLE PRECISION NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_snap_pair_ts
            ON price_snapshots(base, quote, ts);
        CREATE INDEX IF NOT EXISTS idx_snap_ex_pair_ts
            ON price_snapshots(exchange, base, quote, ts);

        CREATE TABLE IF NOT EXISTS composite_snapshots (
            id BIGSERIAL PRIMARY KEY,
            base TEXT NOT NULL,
            quote TEXT NOT NULL,
            mid DOUBLE PRECISION NOT NULL,
            best_bid DOUBLE PRECISION,
            best_ask DOUBLE PRECISION,
            total_volume_quote DOUBLE PRECISION,
            premium_pct DOUBLE PRECISION,
            ts DOUBLE PRECISION NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_comp_pair_ts
            ON composite_snapshots(base, quote, ts);

        CREATE TABLE IF NOT EXISTS candles (
            exchange TEXT NOT NULL,
            base TEXT NOT NULL,
            quote TEXT NOT NULL,
            resolution INTEGER NOT NULL,
            ts DOUBLE PRECISION NOT NULL,
            open DOUBLE PRECISION,
            high DOUBLE PRECISION,
            low DOUBLE PRECISION,
            close DOUBLE PRECISION,
            volume DOUBLE PRECISION,
            PRIMARY KEY (exchange, base, quote, resolution, ts)
        );

        CREATE TABLE IF NOT EXISTS calendar_events (
            id BIGSERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            country TEXT,
            impact TEXT,
            forecast TEXT,
            previous TEXT,
            actual TEXT,
            surprise_pct DOUBLE PRECISION,
            ts DOUBLE PRECISION NOT NULL,
            UNIQUE (title, country, ts)
        );

        CREATE TABLE IF NOT EXISTS alert_rules (
            id BIGSERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            rule_type TEXT NOT NULL,
            base TEXT,
            exchange TEXT,
            threshold DOUBLE PRECISION NOT NULL,
            window_sec DOUBLE PRECISION DEFAULT 3600,
            cooldown_sec DOUBLE PRECISION DEFAULT 900,
            enabled INTEGER DEFAULT 1,
            created_ts DOUBLE PRECISION NOT NULL
        );

        CREATE TABLE IF NOT EXISTS alert_events (
            id BIGSERIAL PRIMARY KEY,
            rule_id BIGINT,
            rule_type TEXT,
            message TEXT NOT NULL,
            severity TEXT DEFAULT 'warning',
            ts DOUBLE PRECISION NOT NULL,
            acknowledged INTEGER DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_alert_events_ts ON alert_events(ts);

        CREATE TABLE IF NOT EXISTS custom_exchanges (
            name TEXT PRIMARY KEY,
            spec TEXT NOT NULL,
            enabled INTEGER DEFAULT 1,
            created_ts DOUBLE PRECISION NOT NULL
        );

        CREATE TABLE IF NOT EXISTS custom_pairs (
            base TEXT NOT NULL,
            quote TEXT NOT NULL,
            enabled INTEGER DEFAULT 1,
            created_ts DOUBLE PRECISION NOT NULL,
            PRIMARY KEY (base, quote)
        );

        CREATE TABLE IF NOT EXISTS reference_prices (
            asset TEXT NOT NULL,
            usd DOUBLE PRECISION NOT NULL,
            ts DOUBLE PRECISION NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_ref_asset_ts ON reference_prices(asset, ts);

        CREATE TABLE IF NOT EXISTS reference_ids (
            asset TEXT PRIMARY KEY,
            cg_id TEXT NOT NULL,
            created_ts DOUBLE PRECISION NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tob_share (
            exchange TEXT NOT NULL,
            base TEXT NOT NULL,
            side TEXT NOT NULL,
            hour_ts DOUBLE PRECISION NOT NULL,
            seconds_best DOUBLE PRECISION DEFAULT 0,
            seconds_total DOUBLE PRECISION DEFAULT 0,
            PRIMARY KEY (exchange, base, side, hour_ts)
        );
        CREATE INDEX IF NOT EXISTS idx_tob_base_hour ON tob_share(base, hour_ts);

        CREATE TABLE IF NOT EXISTS users (
            id BIGSERIAL PRIMARY KEY,
            username TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'viewer',
            must_change_password INTEGER DEFAULT 0,
            created_ts DOUBLE PRECISION NOT NULL,
            CONSTRAINT users_username_unique UNIQUE (username)
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username_ci
            ON users (LOWER(username));

        CREATE TABLE IF NOT EXISTS auth_sessions (
            token TEXT PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_ts DOUBLE PRECISION NOT NULL,
            expires_ts DOUBLE PRECISION NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_sessions_user ON auth_sessions(user_id);

        CREATE TABLE IF NOT EXISTS trade_volumes (
            exchange TEXT NOT NULL,
            base TEXT NOT NULL,
            hour_ts DOUBLE PRECISION NOT NULL,
            base_vol DOUBLE PRECISION DEFAULT 0,
            quote_vol DOUBLE PRECISION DEFAULT 0,
            PRIMARY KEY (exchange, base, hour_ts)
        );

        CREATE TABLE IF NOT EXISTS arb_windows (
            id BIGSERIAL PRIMARY KEY,
            base TEXT NOT NULL,
            quote TEXT NOT NULL,
            buy_exchange TEXT NOT NULL,
            sell_exchange TEXT NOT NULL,
            opened_ts DOUBLE PRECISION NOT NULL,
            closed_ts DOUBLE PRECISION,
            peak_net_pct DOUBLE PRECISION DEFAULT 0,
            avg_net_pct DOUBLE PRECISION DEFAULT 0,
            samples INTEGER DEFAULT 0,
            max_size_base DOUBLE PRECISION DEFAULT 0,
            peak_profit_quote DOUBLE PRECISION DEFAULT 0,
            max_cost_quote DOUBLE PRECISION DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_arb_windows_open ON arb_windows(opened_ts);

        -- Runtime app settings (replaces settings.json)
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value DOUBLE PRECISION NOT NULL,
            updated_ts DOUBLE PRECISION NOT NULL
        );
        """
    )


def downgrade() -> None:
    for table in (
        "app_settings", "arb_windows", "trade_volumes", "auth_sessions", "users",
        "tob_share", "reference_ids", "reference_prices", "custom_pairs",
        "custom_exchanges", "alert_events", "alert_rules", "calendar_events",
        "candles", "composite_snapshots", "price_snapshots",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
