"""Trade-tape 24h volume estimator.

For venues that don't report 24h volume, we build our own: poll the public
recent-trades endpoint, dedupe, and accumulate base/quote turnover into hourly
buckets persisted in SQLite. The rolling 24h sum becomes the volume estimate.

Properties:
- Coverage grows from 0h to a full 24h as the collector runs; the API exposes
  coverage so the UI can say "estimate based on Xh of observed trades".
- Buckets persist across restarts (only trades observed after startup are
  counted again, so there is no double counting — at worst a small gap).
- Dedup inside a run uses trade ids when available, otherwise the
  (ts, price, amount) triple.
"""
from __future__ import annotations

import logging
import time
from collections import deque
from typing import Any, Dict, List, Optional, Tuple

from . import db

log = logging.getLogger("terminal.volume")

WINDOW = 24 * 3600
Key = Tuple[str, str]   # (exchange, base)


class VolumeEstimator:
    def __init__(self) -> None:
        self._buckets: Dict[Key, Dict[float, List[float]]] = {}   # persisted view
        self._pending: Dict[Key, Dict[float, List[float]]] = {}   # not yet flushed
        self._seen: Dict[Key, deque] = {}
        self._seen_sets: Dict[Key, set] = {}
        self._started = time.time()
        self._first_trade: Dict[Key, float] = {}
        self._loaded = False

    def _load(self) -> None:
        """Restore last-24h buckets persisted by a previous run."""
        try:
            for r in db.get_trade_volumes(time.time() - WINDOW):
                key = (r["exchange"], r["base"])
                self._buckets.setdefault(key, {})[r["hour_ts"]] = \
                    [r["base_vol"], r["quote_vol"]]
                self._first_trade.setdefault(key, r["hour_ts"])
        except Exception as exc:
            log.error("trade volume load failed: %s", exc)
        self._loaded = True

    # ---------------------------------------------------------------- ingest
    def ingest(self, exchange: str, base: str,
               trades: List[Dict[str, Any]]) -> int:
        """trades: [{id?, ts, price, amount}] → returns newly counted trades."""
        if not self._loaded:
            self._load()
        key = (exchange, base.upper())
        seen_q = self._seen.setdefault(key, deque(maxlen=4000))
        seen = self._seen_sets.setdefault(key, set())
        added = 0
        now = time.time()
        for tr in trades:
            ts = float(tr.get("ts") or now)
            price = float(tr.get("price") or 0)
            amount = float(tr.get("amount") or 0)
            if price <= 0 or amount <= 0:
                continue
            if ts < self._started - 60:     # pre-startup trades: covered by persisted buckets
                continue
            tid = tr.get("id") or (round(ts, 3), price, amount)
            if tid in seen:
                continue
            if len(seen_q) == seen_q.maxlen:
                seen.discard(seen_q[0])
            seen_q.append(tid)
            seen.add(tid)
            hour = ts - ts % 3600
            bucket = self._pending.setdefault(key, {}).setdefault(hour, [0.0, 0.0])
            bucket[0] += amount
            bucket[1] += amount * price
            self._first_trade.setdefault(key, ts)
            added += 1
        return added

    # ----------------------------------------------------------------- flush
    def flush(self) -> None:
        """Persist pending deltas and merge them into the local view."""
        rows = []
        for key, hours in self._pending.items():
            for hour, (b, q) in hours.items():
                rows.append((key[0], key[1], hour, b, q))
                merged = self._buckets.setdefault(key, {}).setdefault(hour, [0.0, 0.0])
                merged[0] += b
                merged[1] += q
        if rows:
            try:
                db.bump_trade_volumes(rows)
                self._pending.clear()
            except Exception as exc:
                log.error("trade volume flush failed: %s", exc)

    # ---------------------------------------------------------------- output
    def volumes(self, exchange: str, base: str) -> Tuple[float, float, float]:
        """(base_vol_24h, quote_vol_24h, coverage_hours)"""
        if not self._loaded:
            self._load()
        key = (exchange, base.upper())
        cutoff = time.time() - WINDOW
        base_sum = quote_sum = 0.0
        for source in (self._buckets.get(key, {}), self._pending.get(key, {})):
            for hour, (b, q) in source.items():
                if hour >= cutoff - 3600:   # include the partially-expired hour
                    base_sum += b
                    quote_sum += q
        first = self._first_trade.get(key)
        coverage = min(WINDOW, time.time() - first) / 3600 if first else 0.0
        return base_sum, quote_sum, round(coverage, 1)


volume_estimator = VolumeEstimator()
