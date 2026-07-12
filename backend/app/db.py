"""SQLite storage layer.

Improvements over v1:
- Single long-lived connection guarded by a lock (no connect() churn).
- Batched transactional writes.
- Retention pruning (hourly) so tables never grow unbounded.
- New tables: candles, calendar_events (actually written now), alert rules/events,
  runtime-added pairs and custom exchange specs.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

def _resolve_data_dir() -> Path:
    """Preferred data dir, falling back to a temp dir on read-only hosting
    (Vercel & other serverless platforms) so imports never crash."""
    preferred = Path(os.environ.get("TERMINAL_DATA_DIR")
                     or Path(__file__).resolve().parent.parent / "data")
    try:
        preferred.mkdir(parents=True, exist_ok=True)
        probe = preferred / ".write-probe"
        probe.write_text("ok")           # some platforms allow mkdir but not write
        probe.unlink()
        return preferred
    except OSError:
        import logging
        import tempfile
        fallback = Path(tempfile.gettempdir()) / "terminal-data"
        fallback.mkdir(parents=True, exist_ok=True)
        logging.getLogger("terminal.db").warning(
            "%s is not writable — using %s (ephemeral). History will not "
            "persist; run on a server with a writable disk for full features.",
            preferred, fallback)
        return fallback


DATA_DIR = _resolve_data_dir()
DB_PATH = DATA_DIR / "terminal.db"

_lock = threading.Lock()
_conn: Optional[sqlite3.Connection] = None


def _connect() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA synchronous=NORMAL")
        _conn.row_factory = sqlite3.Row
    return _conn


def init_db() -> None:
    with _lock:
        c = _connect()
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS price_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exchange TEXT NOT NULL,
                base TEXT NOT NULL,
                quote TEXT NOT NULL,
                bid REAL, ask REAL, mid REAL,
                spread_pct REAL,
                bid_depth REAL, ask_depth REAL,
                volume_24h_base REAL, volume_24h_quote REAL,
                ts REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_snap_pair_ts ON price_snapshots(base, quote, ts);
            CREATE INDEX IF NOT EXISTS idx_snap_ex_pair_ts ON price_snapshots(exchange, base, quote, ts);

            CREATE TABLE IF NOT EXISTS composite_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                base TEXT NOT NULL, quote TEXT NOT NULL,
                mid REAL NOT NULL,
                best_bid REAL, best_ask REAL,
                total_volume_quote REAL,
                premium_pct REAL,
                ts REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_comp_pair_ts ON composite_snapshots(base, quote, ts);

            CREATE TABLE IF NOT EXISTS candles (
                exchange TEXT NOT NULL,
                base TEXT NOT NULL, quote TEXT NOT NULL,
                resolution INTEGER NOT NULL,      -- seconds per candle
                ts REAL NOT NULL,
                open REAL, high REAL, low REAL, close REAL, volume REAL,
                PRIMARY KEY (exchange, base, quote, resolution, ts)
            );

            CREATE TABLE IF NOT EXISTS calendar_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                country TEXT,
                impact TEXT,
                forecast TEXT, previous TEXT, actual TEXT,
                surprise_pct REAL,
                ts REAL NOT NULL,
                UNIQUE(title, country, ts)
            );

            CREATE TABLE IF NOT EXISTS alert_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                rule_type TEXT NOT NULL,
                base TEXT, exchange TEXT,
                threshold REAL NOT NULL,
                window_sec REAL DEFAULT 3600,
                cooldown_sec REAL DEFAULT 900,
                enabled INTEGER DEFAULT 1,
                created_ts REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS alert_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_id INTEGER,
                rule_type TEXT,
                message TEXT NOT NULL,
                severity TEXT DEFAULT 'warning',
                ts REAL NOT NULL,
                acknowledged INTEGER DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_alert_events_ts ON alert_events(ts);

            CREATE TABLE IF NOT EXISTS custom_exchanges (
                name TEXT PRIMARY KEY,
                spec TEXT NOT NULL,          -- JSON declarative connector spec
                enabled INTEGER DEFAULT 1,
                created_ts REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS custom_pairs (
                base TEXT NOT NULL,
                quote TEXT NOT NULL,
                enabled INTEGER DEFAULT 1,
                created_ts REAL NOT NULL,
                PRIMARY KEY (base, quote)
            );

            CREATE TABLE IF NOT EXISTS reference_prices (
                asset TEXT NOT NULL,
                usd REAL NOT NULL,
                ts REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_ref_asset_ts ON reference_prices(asset, ts);

            CREATE TABLE IF NOT EXISTS reference_ids (
                asset TEXT PRIMARY KEY,
                cg_id TEXT NOT NULL,           -- CoinGecko coin id (or '' = unresolvable)
                created_ts REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tob_share (
                exchange TEXT NOT NULL,
                base TEXT NOT NULL,
                side TEXT NOT NULL,            -- 'bid' | 'ask'
                hour_ts REAL NOT NULL,         -- hour bucket start
                seconds_best REAL DEFAULT 0,
                seconds_total REAL DEFAULT 0,
                PRIMARY KEY (exchange, base, side, hour_ts)
            );
            CREATE INDEX IF NOT EXISTS idx_tob_base_hour ON tob_share(base, hour_ts);

            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'viewer',            -- 'admin' | 'viewer'
                must_change_password INTEGER DEFAULT 0,
                created_ts REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS auth_sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_ts REAL NOT NULL,
                expires_ts REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_sessions_user ON auth_sessions(user_id);

            CREATE TABLE IF NOT EXISTS trade_volumes (
                exchange TEXT NOT NULL,
                base TEXT NOT NULL,
                hour_ts REAL NOT NULL,
                base_vol REAL DEFAULT 0,
                quote_vol REAL DEFAULT 0,
                PRIMARY KEY (exchange, base, hour_ts)
            );

            CREATE TABLE IF NOT EXISTS arb_windows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                base TEXT NOT NULL, quote TEXT NOT NULL,
                buy_exchange TEXT NOT NULL, sell_exchange TEXT NOT NULL,
                opened_ts REAL NOT NULL,
                closed_ts REAL,                -- NULL while open
                peak_net_pct REAL DEFAULT 0,
                avg_net_pct REAL DEFAULT 0,
                samples INTEGER DEFAULT 0,
                max_size_base REAL DEFAULT 0,
                peak_profit_quote REAL DEFAULT 0,
                max_cost_quote REAL DEFAULT 0  -- TMN needed on buy venue at peak
            );
            CREATE INDEX IF NOT EXISTS idx_arb_windows_open ON arb_windows(opened_ts);
            """
        )
        c.commit()


# Ensure schema exists as soon as the module is imported.
init_db()


# ---------------------------------------------------------------- snapshots

def insert_snapshots(rows: Iterable[tuple]) -> None:
    """rows: (exchange, base, quote, bid, ask, mid, spread_pct,
              bid_depth, ask_depth, vol_base, vol_quote, ts)"""
    with _lock:
        c = _connect()
        c.executemany(
            "INSERT INTO price_snapshots (exchange, base, quote, bid, ask, mid, spread_pct,"
            " bid_depth, ask_depth, volume_24h_base, volume_24h_quote, ts)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            rows,
        )
        c.commit()


def insert_composites(rows: Iterable[tuple]) -> None:
    """rows: (base, quote, mid, best_bid, best_ask, total_volume_quote, premium_pct, ts)"""
    with _lock:
        c = _connect()
        c.executemany(
            "INSERT INTO composite_snapshots (base, quote, mid, best_bid, best_ask,"
            " total_volume_quote, premium_pct, ts) VALUES (?,?,?,?,?,?,?,?)",
            rows,
        )
        c.commit()


def get_composite_history(base: str, quote: str, since_ts: float,
                          limit: int = 20000) -> List[Dict[str, Any]]:
    with _lock:
        cur = _connect().execute(
            "SELECT ts, mid, best_bid, best_ask, premium_pct FROM composite_snapshots"
            " WHERE base=? AND quote=? AND ts>=? ORDER BY ts ASC LIMIT ?",
            (base, quote, since_ts, limit),
        )
        return [dict(r) for r in cur.fetchall()]


def get_exchange_history(exchange: str, base: str, quote: str, since_ts: float,
                         limit: int = 20000) -> List[Dict[str, Any]]:
    with _lock:
        cur = _connect().execute(
            "SELECT ts, bid, ask, mid, spread_pct, bid_depth, ask_depth,"
            " volume_24h_quote FROM price_snapshots"
            " WHERE exchange=? AND base=? AND quote=? AND ts>=? ORDER BY ts ASC LIMIT ?",
            (exchange, base, quote, since_ts, limit),
        )
        return [dict(r) for r in cur.fetchall()]


def get_spread_history(base: str, quote: str, since_ts: float,
                       exchange: Optional[str] = None) -> List[Dict[str, Any]]:
    q = ("SELECT exchange, ts, spread_pct FROM price_snapshots"
         " WHERE base=? AND quote=? AND ts>=?")
    args: list = [base, quote, since_ts]
    if exchange:
        q += " AND exchange=?"
        args.append(exchange)
    q += " ORDER BY ts ASC LIMIT 50000"
    with _lock:
        cur = _connect().execute(q, args)
        return [dict(r) for r in cur.fetchall()]


def get_mid_at(base: str, quote: str, ts: float, tolerance: float = 900.0) -> Optional[float]:
    """Composite mid closest to ts within tolerance seconds (for 7d change etc.)."""
    with _lock:
        cur = _connect().execute(
            "SELECT mid FROM composite_snapshots WHERE base=? AND quote=?"
            " AND ts BETWEEN ? AND ? ORDER BY ABS(ts-?) ASC LIMIT 1",
            (base, quote, ts - tolerance, ts + tolerance, ts),
        )
        row = cur.fetchone()
        return row["mid"] if row else None


def get_pair_snapshots(base: str, quote: str, since_ts: float,
                       limit: int = 100_000) -> List[Dict[str, Any]]:
    """All per-exchange snapshots for one pair — powers premium method series."""
    with _lock:
        cur = _connect().execute(
            "SELECT exchange, ts, bid, ask, mid, volume_24h_quote FROM price_snapshots"
            " WHERE base=? AND quote=? AND ts>=? ORDER BY ts ASC LIMIT ?",
            (base, quote, since_ts, limit),
        )
        return [dict(r) for r in cur.fetchall()]


# --------------------------------------------------------- USD reference ---

def insert_reference_prices(rows: Iterable[tuple]) -> None:
    """rows: (asset, usd, ts)"""
    with _lock:
        c = _connect()
        c.executemany("INSERT INTO reference_prices (asset, usd, ts) VALUES (?,?,?)", rows)
        c.commit()


def get_reference_history(asset: str, since_ts: float,
                          limit: int = 50_000) -> List[Dict[str, Any]]:
    with _lock:
        cur = _connect().execute(
            "SELECT ts, usd FROM reference_prices WHERE asset=? AND ts>=?"
            " ORDER BY ts ASC LIMIT ?", (asset, since_ts, limit))
        return [dict(r) for r in cur.fetchall()]


def upsert_reference_id(asset: str, cg_id: str) -> None:
    with _lock:
        c = _connect()
        c.execute(
            "INSERT INTO reference_ids (asset, cg_id, created_ts) VALUES (?,?,?)"
            " ON CONFLICT(asset) DO UPDATE SET cg_id=excluded.cg_id",
            (asset.upper(), cg_id, time.time()))
        c.commit()


def get_reference_ids() -> Dict[str, str]:
    with _lock:
        rows = _connect().execute("SELECT asset, cg_id FROM reference_ids").fetchall()
        return {r["asset"]: r["cg_id"] for r in rows}


# ------------------------------------------------------------------ candles

def upsert_candles(rows: Iterable[tuple]) -> None:
    """rows: (exchange, base, quote, resolution, ts, o, h, l, c, v)"""
    with _lock:
        c = _connect()
        c.executemany(
            "INSERT INTO candles (exchange, base, quote, resolution, ts,"
            " open, high, low, close, volume) VALUES (?,?,?,?,?,?,?,?,?,?)"
            " ON CONFLICT(exchange, base, quote, resolution, ts) DO UPDATE SET"
            " open=excluded.open, high=excluded.high, low=excluded.low,"
            " close=excluded.close, volume=excluded.volume",
            rows,
        )
        c.commit()


def get_candles(exchange: str, base: str, quote: str, resolution: int,
                since_ts: float, limit: int = 5000) -> List[Dict[str, Any]]:
    with _lock:
        cur = _connect().execute(
            "SELECT ts, open, high, low, close, volume FROM candles"
            " WHERE exchange=? AND base=? AND quote=? AND resolution=? AND ts>=?"
            " ORDER BY ts ASC LIMIT ?",
            (exchange, base, quote, resolution, since_ts, limit),
        )
        return [dict(r) for r in cur.fetchall()]


# ----------------------------------------------------------------- calendar

def upsert_calendar_events(rows: Iterable[tuple]) -> None:
    """rows: (title, country, impact, forecast, previous, actual, surprise_pct, ts)"""
    with _lock:
        c = _connect()
        c.executemany(
            "INSERT INTO calendar_events (title, country, impact, forecast, previous,"
            " actual, surprise_pct, ts) VALUES (?,?,?,?,?,?,?,?)"
            " ON CONFLICT(title, country, ts) DO UPDATE SET"
            " actual=excluded.actual, forecast=excluded.forecast,"
            " previous=excluded.previous, surprise_pct=excluded.surprise_pct,"
            " impact=excluded.impact",
            rows,
        )
        c.commit()


def get_calendar_events(since_ts: float, until_ts: float) -> List[Dict[str, Any]]:
    with _lock:
        cur = _connect().execute(
            "SELECT * FROM calendar_events WHERE ts BETWEEN ? AND ? ORDER BY ts ASC",
            (since_ts, until_ts),
        )
        return [dict(r) for r in cur.fetchall()]


def get_event_surprise_history(title: str, country: str, limit: int = 24) -> List[Dict[str, Any]]:
    """Past releases of the same indicator — powers 'historical surprise' stats."""
    with _lock:
        cur = _connect().execute(
            "SELECT ts, forecast, previous, actual, surprise_pct FROM calendar_events"
            " WHERE title=? AND country=? AND actual IS NOT NULL AND actual != ''"
            " ORDER BY ts DESC LIMIT ?",
            (title, country, limit),
        )
        return [dict(r) for r in cur.fetchall()]


# ------------------------------------------------------------------- alerts

def insert_alert_rule(name: str, rule_type: str, base: Optional[str],
                      exchange: Optional[str], threshold: float,
                      window_sec: float, cooldown_sec: float) -> int:
    with _lock:
        c = _connect()
        cur = c.execute(
            "INSERT INTO alert_rules (name, rule_type, base, exchange, threshold,"
            " window_sec, cooldown_sec, enabled, created_ts) VALUES (?,?,?,?,?,?,?,1,?)",
            (name, rule_type, base, exchange, threshold, window_sec, cooldown_sec, time.time()),
        )
        c.commit()
        return int(cur.lastrowid)


def get_alert_rules(enabled_only: bool = False) -> List[Dict[str, Any]]:
    q = "SELECT * FROM alert_rules"
    if enabled_only:
        q += " WHERE enabled=1"
    with _lock:
        return [dict(r) for r in _connect().execute(q).fetchall()]


def set_alert_rule_enabled(rule_id: int, enabled: bool) -> None:
    with _lock:
        c = _connect()
        c.execute("UPDATE alert_rules SET enabled=? WHERE id=?", (1 if enabled else 0, rule_id))
        c.commit()


def delete_alert_rule(rule_id: int) -> None:
    with _lock:
        c = _connect()
        c.execute("DELETE FROM alert_rules WHERE id=?", (rule_id,))
        c.commit()


def insert_alert_event(rule_id: Optional[int], rule_type: str, message: str,
                       severity: str, ts: float) -> int:
    with _lock:
        c = _connect()
        cur = c.execute(
            "INSERT INTO alert_events (rule_id, rule_type, message, severity, ts)"
            " VALUES (?,?,?,?,?)",
            (rule_id, rule_type, message, severity, ts),
        )
        c.commit()
        return int(cur.lastrowid)


def get_alert_events(since_ts: float, limit: int = 200) -> List[Dict[str, Any]]:
    with _lock:
        cur = _connect().execute(
            "SELECT * FROM alert_events WHERE ts>=? ORDER BY ts DESC LIMIT ?",
            (since_ts, limit),
        )
        return [dict(r) for r in cur.fetchall()]


def ack_alert_event(event_id: int) -> None:
    with _lock:
        c = _connect()
        c.execute("UPDATE alert_events SET acknowledged=1 WHERE id=?", (event_id,))
        c.commit()


# ----------------------------------------------------- runtime config (admin)

def upsert_custom_exchange(name: str, spec: Dict[str, Any], enabled: bool = True) -> None:
    with _lock:
        c = _connect()
        c.execute(
            "INSERT INTO custom_exchanges (name, spec, enabled, created_ts) VALUES (?,?,?,?)"
            " ON CONFLICT(name) DO UPDATE SET spec=excluded.spec, enabled=excluded.enabled",
            (name, json.dumps(spec), 1 if enabled else 0, time.time()),
        )
        c.commit()


def get_custom_exchanges() -> List[Dict[str, Any]]:
    with _lock:
        rows = _connect().execute("SELECT * FROM custom_exchanges").fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["spec"] = json.loads(d["spec"])
            out.append(d)
        return out


def delete_custom_exchange(name: str) -> None:
    with _lock:
        c = _connect()
        c.execute("DELETE FROM custom_exchanges WHERE name=?", (name,))
        c.commit()


def upsert_custom_pair(base: str, quote: str, enabled: bool = True) -> None:
    with _lock:
        c = _connect()
        c.execute(
            "INSERT INTO custom_pairs (base, quote, enabled, created_ts) VALUES (?,?,?,?)"
            " ON CONFLICT(base, quote) DO UPDATE SET enabled=excluded.enabled",
            (base.upper(), quote.upper(), 1 if enabled else 0, time.time()),
        )
        c.commit()


def get_custom_pairs() -> List[Dict[str, Any]]:
    with _lock:
        return [dict(r) for r in _connect().execute("SELECT * FROM custom_pairs").fetchall()]


def delete_custom_pair(base: str, quote: str) -> None:
    with _lock:
        c = _connect()
        c.execute("DELETE FROM custom_pairs WHERE base=? AND quote=?",
                  (base.upper(), quote.upper()))
        c.commit()


# --------------------------------------------------------------------- auth

def create_user(username: str, password_hash: str, role: str,
                must_change: bool = False) -> int:
    with _lock:
        c = _connect()
        cur = c.execute(
            "INSERT INTO users (username, password_hash, role,"
            " must_change_password, created_ts) VALUES (?,?,?,?,?)",
            (username.strip(), password_hash, role, 1 if must_change else 0, time.time()))
        c.commit()
        return int(cur.lastrowid)


def get_user_by_name(username: str) -> Optional[Dict[str, Any]]:
    with _lock:
        row = _connect().execute(
            "SELECT * FROM users WHERE username=?", (username.strip(),)).fetchone()
        return dict(row) if row else None


def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    with _lock:
        row = _connect().execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        return dict(row) if row else None


def list_users() -> List[Dict[str, Any]]:
    with _lock:
        rows = _connect().execute(
            "SELECT id, username, role, must_change_password, created_ts"
            " FROM users ORDER BY id").fetchall()
        return [dict(r) for r in rows]


def count_users() -> int:
    with _lock:
        return _connect().execute("SELECT COUNT(*) c FROM users").fetchone()["c"]


def set_user_password(user_id: int, password_hash: str,
                      must_change: bool = False) -> None:
    with _lock:
        c = _connect()
        c.execute("UPDATE users SET password_hash=?, must_change_password=? WHERE id=?",
                  (password_hash, 1 if must_change else 0, user_id))
        c.commit()


def delete_user(user_id: int) -> None:
    with _lock:
        c = _connect()
        c.execute("DELETE FROM users WHERE id=?", (user_id,))
        c.execute("DELETE FROM auth_sessions WHERE user_id=?", (user_id,))
        c.commit()


def create_session(token: str, user_id: int, ttl_sec: float) -> None:
    now = time.time()
    with _lock:
        c = _connect()
        c.execute("INSERT INTO auth_sessions (token, user_id, created_ts, expires_ts)"
                  " VALUES (?,?,?,?)", (token, user_id, now, now + ttl_sec))
        c.commit()


def get_session(token: str) -> Optional[Dict[str, Any]]:
    with _lock:
        row = _connect().execute(
            "SELECT s.token, s.user_id, s.expires_ts, u.username, u.role,"
            " u.must_change_password FROM auth_sessions s"
            " JOIN users u ON u.id = s.user_id WHERE s.token=?", (token,)).fetchone()
        return dict(row) if row else None


def delete_session(token: str) -> None:
    with _lock:
        c = _connect()
        c.execute("DELETE FROM auth_sessions WHERE token=?", (token,))
        c.commit()


def delete_user_sessions(user_id: int) -> None:
    with _lock:
        c = _connect()
        c.execute("DELETE FROM auth_sessions WHERE user_id=?", (user_id,))
        c.commit()


def prune_sessions() -> None:
    with _lock:
        c = _connect()
        c.execute("DELETE FROM auth_sessions WHERE expires_ts < ?", (time.time(),))
        c.commit()


# ----------------------------------------------------- trade volume buckets

def bump_trade_volumes(rows: Iterable[tuple]) -> None:
    """rows: (exchange, base, hour_ts, base_vol_delta, quote_vol_delta)"""
    with _lock:
        c = _connect()
        c.executemany(
            "INSERT INTO trade_volumes (exchange, base, hour_ts, base_vol, quote_vol)"
            " VALUES (?,?,?,?,?)"
            " ON CONFLICT(exchange, base, hour_ts) DO UPDATE SET"
            " base_vol = base_vol + excluded.base_vol,"
            " quote_vol = quote_vol + excluded.quote_vol",
            rows,
        )
        c.commit()


def get_trade_volumes(since_ts: float) -> List[Dict[str, Any]]:
    with _lock:
        cur = _connect().execute(
            "SELECT exchange, base, hour_ts, base_vol, quote_vol FROM trade_volumes"
            " WHERE hour_ts>=?", (since_ts,))
        return [dict(r) for r in cur.fetchall()]


# ------------------------------------------------------------ intelligence

def bump_tob_hours(rows: Iterable[tuple]) -> None:
    """rows: (exchange, base, side, hour_ts, seconds_best_delta, seconds_total_delta)"""
    with _lock:
        c = _connect()
        c.executemany(
            "INSERT INTO tob_share (exchange, base, side, hour_ts, seconds_best, seconds_total)"
            " VALUES (?,?,?,?,?,?)"
            " ON CONFLICT(exchange, base, side, hour_ts) DO UPDATE SET"
            " seconds_best = seconds_best + excluded.seconds_best,"
            " seconds_total = seconds_total + excluded.seconds_total",
            rows,
        )
        c.commit()


def get_tob_share(base: str, since_ts: float) -> List[Dict[str, Any]]:
    with _lock:
        cur = _connect().execute(
            "SELECT exchange, side, hour_ts, seconds_best, seconds_total FROM tob_share"
            " WHERE base=? AND hour_ts>=? ORDER BY hour_ts ASC", (base, since_ts))
        return [dict(r) for r in cur.fetchall()]


def open_arb_window(base: str, quote: str, buy_ex: str, sell_ex: str,
                    ts: float) -> int:
    with _lock:
        c = _connect()
        cur = c.execute(
            "INSERT INTO arb_windows (base, quote, buy_exchange, sell_exchange,"
            " opened_ts) VALUES (?,?,?,?,?)", (base, quote, buy_ex, sell_ex, ts))
        c.commit()
        return int(cur.lastrowid)


def update_arb_window(window_id: int, net_pct: float, size_base: float,
                      profit_quote: float, cost_quote: float) -> None:
    with _lock:
        c = _connect()
        c.execute(
            "UPDATE arb_windows SET"
            " peak_net_pct = MAX(peak_net_pct, ?),"
            " avg_net_pct = (avg_net_pct * samples + ?) / (samples + 1),"
            " samples = samples + 1,"
            " max_size_base = MAX(max_size_base, ?),"
            " peak_profit_quote = MAX(peak_profit_quote, ?),"
            " max_cost_quote = MAX(max_cost_quote, ?)"
            " WHERE id=?",
            (net_pct, net_pct, size_base, profit_quote, cost_quote, window_id))
        c.commit()


def close_arb_window(window_id: int, ts: float) -> None:
    with _lock:
        c = _connect()
        c.execute("UPDATE arb_windows SET closed_ts=? WHERE id=? AND closed_ts IS NULL",
                  (ts, window_id))
        c.commit()


def get_arb_windows(since_ts: float, limit: int = 2000) -> List[Dict[str, Any]]:
    with _lock:
        cur = _connect().execute(
            "SELECT * FROM arb_windows WHERE opened_ts>=? OR closed_ts IS NULL"
            " ORDER BY (closed_ts IS NULL) DESC, opened_ts DESC LIMIT ?",
            (since_ts, limit))
        return [dict(r) for r in cur.fetchall()]


# ---------------------------------------------------------------- retention

def prune(retention: Dict[str, int]) -> Dict[str, int]:
    """Delete rows older than the configured horizon. Returns rows deleted per table."""
    now = time.time()
    plans = [
        ("price_snapshots", "ts", retention.get("snapshots_days", 90)),
        ("composite_snapshots", "ts", retention.get("snapshots_days", 90)),
        ("reference_prices", "ts", retention.get("snapshots_days", 90)),
        ("candles", "ts", retention.get("candles_days", 365)),
        ("alert_events", "ts", retention.get("alerts_days", 30)),
        ("calendar_events", "ts", retention.get("calendar_days", 365)),
        ("tob_share", "hour_ts", retention.get("ledger_days", 180)),
        ("arb_windows", "opened_ts", retention.get("ledger_days", 180)),
        ("trade_volumes", "hour_ts", 7),   # only needed for the rolling 24h
    ]
    deleted: Dict[str, int] = {}
    with _lock:
        c = _connect()
        for table, col, days in plans:
            cur = c.execute(f"DELETE FROM {table} WHERE {col} < ?", (now - days * 86400,))
            deleted[table] = cur.rowcount
        c.commit()
    return deleted
