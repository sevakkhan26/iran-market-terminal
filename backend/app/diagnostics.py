"""In-app diagnostics: capture logs + explain why a deployment isn't working.

Three tools, all surfaced in the Admin page:
1. RingLogHandler — every log record the backend emits (including tracebacks)
   is kept in a memory ring buffer and served via /api/logs.
2. environment_report() — instant health checks: python/platform, serverless
   flag, data-dir writability, auth env vars present, frontend dist found,
   connector/aggregator state, DB row counts, feed staleness.
3. connectivity_test() — live probes of every exchange endpoint + reference/
   calendar sources with latency, so geo-blocking or DNS/firewall problems
   are visible in one table.

Set LOG_LEVEL=DEBUG (env) to capture per-request connector chatter too.
"""
from __future__ import annotations

import logging
import os
import platform
import sys
import time
import traceback
from collections import deque
from typing import Any, Dict, List, Optional

log = logging.getLogger("terminal.diagnostics")

# --------------------------------------------------------- log ring buffer

class RingLogHandler(logging.Handler):
    """Keeps the last N log records in memory for the /api/logs endpoint."""

    def __init__(self, capacity: int = 2000) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: deque = deque(maxlen=capacity)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = record.getMessage()
            if record.exc_info and record.exc_info[0] is not None:
                message += "\n" + "".join(traceback.format_exception(*record.exc_info))
            self.records.append({
                "ts": record.created,
                "level": record.levelname,
                "logger": record.name,
                "message": message[:4000],
            })
        except Exception:  # never let logging break the app
            pass

    def tail(self, min_level: str = "DEBUG", limit: int = 300,
             search: str = "") -> List[Dict[str, Any]]:
        threshold = logging.getLevelName(min_level.upper())
        if not isinstance(threshold, int):
            threshold = logging.DEBUG
        needle = search.lower()
        out = [r for r in self.records
               if logging.getLevelName(r["level"]) >= threshold
               and (not needle or needle in r["message"].lower()
                    or needle in r["logger"].lower())]
        return out[-limit:]


ring_handler = RingLogHandler()


def install_log_capture() -> None:
    """Attach the ring buffer to the root logger and honor LOG_LEVEL env."""
    root = logging.getLogger()
    if ring_handler not in root.handlers:
        root.addHandler(ring_handler)
    level_name = os.environ.get("LOG_LEVEL", "").upper()
    if level_name in ("DEBUG", "INFO", "WARNING", "ERROR"):
        root.setLevel(level_name)
        for noisy in ("httpx", "httpcore"):   # keep HTTP client chatter sane
            logging.getLogger(noisy).setLevel(
                logging.INFO if level_name == "DEBUG" else logging.WARNING)
        log.info("log level set to %s via LOG_LEVEL env", level_name)


# ------------------------------------------------------------ health report

def environment_report(aggregator, news_service) -> Dict[str, Any]:
    from . import db
    from .config import CONFIG

    now = time.time()

    def check(ok: bool, detail: str) -> Dict[str, Any]:
        return {"ok": bool(ok), "detail": detail}

    # data dir / database
    try:
        row_counts = {}
        for table in ("price_snapshots", "composite_snapshots", "candles",
                      "calendar_events", "arb_windows"):
            with db._lock:
                row_counts[table] = db._connect().execute(
                    f"SELECT COUNT(*) c FROM {table}").fetchone()["c"]
        db_ok = True
        db_detail = f"{db.DB_PATH} · rows: " + ", ".join(
            f"{k}={v}" for k, v in row_counts.items())
    except Exception as exc:
        db_ok, db_detail, row_counts = False, str(exc), {}

    preferred_dir = os.environ.get("TERMINAL_DATA_DIR") or "backend/data"
    using_fallback = "terminal-data" in str(db.DATA_DIR) and "tmp" in str(db.DATA_DIR).lower()

    # market feed freshness — only slots we actually poll (unsupported pairs
    # are never stored, so they no longer inflate the denominator with red chips)
    snaps = list(aggregator.market_state.values())
    live = [s for s in snaps if s.mid > 0 and s.status != "offline"]
    newest = max((s.timestamp for s in live or snaps), default=0)
    feed_age = round(now - newest, 1) if newest else None

    frontend_dist = None
    try:
        from pathlib import Path
        dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
        frontend_dist = dist.exists() and (dist / "index.html").exists()
    except Exception:
        pass

    serverless = bool(os.environ.get("VERCEL") or os.environ.get("SERVERLESS"))

    return {
        "generated_at": now,
        "system": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "serverless": serverless,
            "demo_mode": bool(CONFIG.get("demo_mode")),
            "log_level": logging.getLevelName(logging.getLogger().level),
            "uptime_hint": "background loops DISABLED (serverless)" if serverless
                           else "background loops enabled",
        },
        "checks": {
            "auth_env": check(
                bool(os.environ.get("AUTH_PASSWORD_HASH") or os.environ.get("AUTH_PASSWORD")),
                "AUTH_USERNAME=%s, AUTH_PASSWORD_HASH %s, AUTH_TOKEN_SECRET %s" % (
                    os.environ.get("AUTH_USERNAME", "(unset → admin)"),
                    "set" if os.environ.get("AUTH_PASSWORD_HASH") else "MISSING",
                    "set" if os.environ.get("AUTH_TOKEN_SECRET") else "MISSING (derived)")),
            "data_dir_writable": check(
                not using_fallback,
                f"using {db.DATA_DIR}" + (
                    f" — FALLBACK, '{preferred_dir}' not writable, history is EPHEMERAL"
                    if using_fallback else " (persistent)")),
            "database": check(db_ok, db_detail),
            "history_accumulating": check(
                row_counts.get("composite_snapshots", 0) > 0,
                f"{row_counts.get('composite_snapshots', 0)} composite snapshots stored"),
            "frontend_dist": check(
                bool(frontend_dist),
                "frontend/dist found" if frontend_dist
                else "frontend/dist MISSING — run: cd frontend && npm run build"),
            "market_feed": check(
                len(live) > 0 and feed_age is not None and feed_age < 60,
                f"{len(live)}/{len(snaps)} polled venue-feeds live, newest data {feed_age}s old"
                if snaps else "NO market data at all — run the connectivity test"),
            "connectors_active": check(
                len(aggregator.connectors) > 0,
                ", ".join(c.exchange_name for c in aggregator.connectors) or "none"),
            "usd_reference": check(
                bool(aggregator.usd_reference),
                f"{aggregator.usd_reference}" if aggregator.usd_reference
                else "no global reference — CoinGecko unreachable?"),
            "calendar_feed": check(
                len(news_service.calendar_cache) > 0,
                f"{len(news_service.calendar_cache)} events cached"),
        },
        # Sort live first so Admin chips read green→amber→red
        "venues": sorted(
            [{
                "exchange": s.exchange, "base": s.base, "status": s.status,
                "age_sec": round(now - s.timestamp, 1) if s.timestamp else None,
                "latency_ms": s.latency_ms,
            } for s in snaps],
            key=lambda v: (
                0 if v["status"] == "connected" else
                1 if v["status"] == "delayed" else 2,
                v["exchange"], v["base"],
            ),
        ),
    }


# -------------------------------------------------------- connectivity test

PROBE_TARGETS = [
    ("Nobitex", "https://apiv2.nobitex.ir/v3/orderbook/BTCIRT"),
    ("Wallex", "https://api.wallex.ir/v1/depth?symbol=BTCTMN"),
    ("Bitpin", "https://api.bitpin.org/api/v1/mth/orderbook/BTC_IRT/"),
    ("Exir", "https://api.exir.io/v2/orderbook?symbol=btc-irt"),
    ("Tabdeal", "https://api1.tabdeal.org/r/api/v1/depth?symbol=BTCIRT&limit=1"),
    ("Ramzinex", "https://publicapi.ramzinex.com/exchange/api/v1.0/exchange/orderbooks/2/buys_sells"),
    ("CoinGecko (USD reference)", "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"),
    ("ForexFactory (calendar)", "https://nfs.faireconomy.media/ff_calendar_thisweek.json"),
]


async def connectivity_test() -> List[Dict[str, Any]]:
    """Probe every upstream from THIS server — reveals geo-blocks instantly."""
    import asyncio

    from .connectors import get_client

    async def probe(name: str, url: str) -> Dict[str, Any]:
        started = time.time()
        try:
            r = await asyncio.wait_for(get_client().get(url), timeout=8)
            body = r.text[:120].replace("\n", " ")
            ok = r.status_code == 200 and len(r.content) > 2
            return {"target": name, "ok": ok, "status": r.status_code,
                    "latency_ms": round((time.time() - started) * 1000),
                    "detail": body if not ok else f"{len(r.content)} bytes"}
        except Exception as exc:
            return {"target": name, "ok": False, "status": None,
                    "latency_ms": round((time.time() - started) * 1000),
                    "detail": f"{type(exc).__name__}: {exc}" or type(exc).__name__}

    results = await asyncio.gather(*(probe(n, u) for n, u in PROBE_TARGETS))
    for r in results:
        (log.info if r["ok"] else log.warning)(
            "nettest %s: %s (%sms) %s", r["target"],
            "OK" if r["ok"] else "FAILED", r["latency_ms"], r["detail"])
    return list(results)
