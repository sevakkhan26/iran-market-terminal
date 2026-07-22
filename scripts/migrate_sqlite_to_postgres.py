#!/usr/bin/env python3
"""One-shot: copy data from old SQLite volume into Postgres.

Usage (on server, with both volumes / DATABASE_URL available):

  docker run --rm --network iran-market-terminal_default \\
    -v docker-projects_iran-market-data:/sqlite:ro \\
    -v $PWD/scripts:/scripts:ro \\
    -e DATABASE_URL=postgresql://terminal:terminal@iran-market-db:5432/terminal \\
    -e SQLITE_PATH=/sqlite/terminal.db \\
    python:3.12-slim bash -c \\
      "pip install -q psycopg[binary] && python /scripts/migrate_sqlite_to_postgres.py"

Or from the running app container if sqlite is mounted at /sqlite.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from typing import Any, Iterable, List, Optional, Sequence, Tuple

import psycopg
from psycopg.rows import dict_row

SQLITE_PATH = os.environ.get("SQLITE_PATH", "/sqlite/terminal.db")
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://terminal:terminal@127.0.0.1:5432/terminal",
)
BATCH = int(os.environ.get("MIGRATE_BATCH", "2000"))
# Set MIGRATE_HISTORY=0 to only copy config tables (pairs, refs, alerts, settings)
MIGRATE_HISTORY = os.environ.get("MIGRATE_HISTORY", "1").lower() not in ("0", "false", "no")


def pg_url() -> str:
    url = DATABASE_URL.strip()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return url


def copy_table(
    sconn: sqlite3.Connection,
    pconn: psycopg.Connection,
    table: str,
    columns: Sequence[str],
    *,
    conflict: Optional[str] = None,
    transform=None,
    where: str = "",
) -> int:
    scol = ", ".join(columns)
    rows = sconn.execute(f"SELECT {scol} FROM {table} {where}").fetchall()
    if not rows:
        print(f"  {table}: 0 rows")
        return 0
    data: List[Tuple[Any, ...]] = []
    for r in rows:
        tup = tuple(r)
        if transform:
            tup = transform(tup)
        data.append(tup)
    placeholders = ", ".join(["%s"] * len(columns))
    sql = f"INSERT INTO {table} ({scol}) VALUES ({placeholders})"
    if conflict:
        sql += f" ON CONFLICT {conflict}"
    total = 0
    with pconn.cursor() as cur:
        for i in range(0, len(data), BATCH):
            chunk = data[i : i + BATCH]
            cur.executemany(sql, chunk)
            total += len(chunk)
        pconn.commit()
    print(f"  {table}: {total} rows")
    return total


def main() -> int:
    if not os.path.exists(SQLITE_PATH):
        print(f"SQLite not found: {SQLITE_PATH}", file=sys.stderr)
        return 1
    print(f"SQLite: {SQLITE_PATH}")
    print(f"Postgres: {pg_url().split('@')[-1]}")

    sconn = sqlite3.connect(SQLITE_PATH)
    sconn.row_factory = sqlite3.Row

    with psycopg.connect(pg_url(), row_factory=dict_row) as pconn:
        print("==> config tables")
        # custom_pairs
        copy_table(
            sconn, pconn, "custom_pairs",
            ["base", "quote", "enabled", "created_ts"],
            conflict="(base, quote) DO UPDATE SET enabled=EXCLUDED.enabled",
        )
        # reference_ids
        copy_table(
            sconn, pconn, "reference_ids",
            ["asset", "cg_id", "created_ts"],
            conflict="(asset) DO UPDATE SET cg_id=EXCLUDED.cg_id",
        )
        # custom_exchanges (spec is JSON text)
        copy_table(
            sconn, pconn, "custom_exchanges",
            ["name", "spec", "enabled", "created_ts"],
            conflict="(name) DO UPDATE SET spec=EXCLUDED.spec, enabled=EXCLUDED.enabled",
        )
        # alert_rules — skip if already seeded with same names
        existing = pconn.execute("SELECT count(*) AS c FROM alert_rules").fetchone()["c"]
        if existing == 0:
            copy_table(
                sconn, pconn, "alert_rules",
                ["name", "rule_type", "base", "exchange", "threshold",
                 "window_sec", "cooldown_sec", "enabled", "created_ts"],
            )
        else:
            print(f"  alert_rules: skip (already {existing} rows)")

        # settings.json → app_settings
        settings_path = os.path.join(os.path.dirname(SQLITE_PATH), "settings.json")
        if os.path.exists(settings_path):
            data = json.loads(open(settings_path, encoding="utf-8").read())
            now = time.time()
            with pconn.cursor() as cur:
                for k, v in data.items():
                    try:
                        fv = float(v)
                    except (TypeError, ValueError):
                        continue
                    cur.execute(
                        "INSERT INTO app_settings (key, value, updated_ts) VALUES (%s,%s,%s)"
                        " ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value,"
                        " updated_ts=EXCLUDED.updated_ts",
                        (k, fv, now),
                    )
                pconn.commit()
            print(f"  app_settings: {len(data)} keys from settings.json")

        if not MIGRATE_HISTORY:
            print("MIGRATE_HISTORY=0 — skipping history tables")
            return 0

        print("==> history tables (may take a while)")
        # price_snapshots — no unique key; only insert if PG is empty-ish
        pg_snaps = pconn.execute("SELECT count(*) AS c FROM price_snapshots").fetchone()["c"]
        if pg_snaps < 100:
            copy_table(
                sconn, pconn, "price_snapshots",
                ["exchange", "base", "quote", "bid", "ask", "mid", "spread_pct",
                 "bid_depth", "ask_depth", "volume_24h_base", "volume_24h_quote", "ts"],
            )
        else:
            print(f"  price_snapshots: skip (pg already has {pg_snaps})")

        pg_comp = pconn.execute("SELECT count(*) AS c FROM composite_snapshots").fetchone()["c"]
        if pg_comp < 50:
            copy_table(
                sconn, pconn, "composite_snapshots",
                ["base", "quote", "mid", "best_bid", "best_ask",
                 "total_volume_quote", "premium_pct", "ts"],
            )
        else:
            print(f"  composite_snapshots: skip (pg already has {pg_comp})")

        pg_candles = pconn.execute("SELECT count(*) AS c FROM candles").fetchone()["c"]
        if pg_candles < 100:
            copy_table(
                sconn, pconn, "candles",
                ["exchange", "base", "quote", "resolution", "ts",
                 "open", "high", "low", "close", "volume"],
                conflict="(exchange, base, quote, resolution, ts) DO NOTHING",
            )
        else:
            print(f"  candles: skip (pg already has {pg_candles})")

        # calendar
        pg_cal = pconn.execute("SELECT count(*) AS c FROM calendar_events").fetchone()["c"]
        if pg_cal < 20:
            copy_table(
                sconn, pconn, "calendar_events",
                ["title", "country", "impact", "forecast", "previous",
                 "actual", "surprise_pct", "ts"],
                conflict="(title, country, ts) DO NOTHING",
            )
        else:
            print(f"  calendar_events: skip (pg already has {pg_cal})")

        # reference prices
        copy_table(
            sconn, pconn, "reference_prices",
            ["asset", "usd", "ts"],
        )

        # tob / trade volumes / arb — best effort
        for table, cols, conf in [
            ("tob_share",
             ["exchange", "base", "side", "hour_ts", "seconds_best", "seconds_total"],
             "(exchange, base, side, hour_ts) DO NOTHING"),
            ("trade_volumes",
             ["exchange", "base", "hour_ts", "base_vol", "quote_vol"],
             "(exchange, base, hour_ts) DO NOTHING"),
        ]:
            try:
                copy_table(sconn, pconn, table, cols, conflict=conf)
            except Exception as exc:
                print(f"  {table}: skip ({exc})")

        try:
            # arb_windows without id identity conflict — insert without id
            n = copy_table(
                sconn, pconn, "arb_windows",
                ["base", "quote", "buy_exchange", "sell_exchange", "opened_ts",
                 "closed_ts", "peak_net_pct", "avg_net_pct", "samples",
                 "max_size_base", "peak_profit_quote", "max_cost_quote"],
            )
        except Exception as exc:
            print(f"  arb_windows: skip ({exc})")

        # alert events
        try:
            pe = pconn.execute("SELECT count(*) AS c FROM alert_events").fetchone()["c"]
            if pe == 0:
                copy_table(
                    sconn, pconn, "alert_events",
                    ["rule_id", "rule_type", "message", "severity", "ts", "acknowledged"],
                )
        except Exception as exc:
            print(f"  alert_events: skip ({exc})")

    print("DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
