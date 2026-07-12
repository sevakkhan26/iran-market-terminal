"""Seed 30 days of plausible history when running in demo mode.

Gives charts, 7D change and spread analytics real data to work with on first
boot, without waiting for live collection.
"""
from __future__ import annotations

import logging
import random
import time

from . import db
from .config import CONFIG
from .connectors import DemoConnector, DEMO_PROFILES

log = logging.getLogger("terminal.demo_seed")

SNAP_RES = 300      # 5-minute composite snapshots + candles
EX_RES = 3600       # hourly per-exchange snapshots
DAYS = 30


def seed_if_needed() -> None:
    if not CONFIG.get("demo_mode"):
        return
    quote = CONFIG.get("quote_currency", "TMN")
    assets = [a.upper() for a in CONFIG.get("assets", [])]
    if not assets:
        return
    existing = db.get_composite_history(assets[0], quote, time.time() - 86400 * DAYS, limit=5)
    if len(existing) >= 5:
        return
    log.info("Demo mode: seeding %dd of synthetic history...", DAYS)
    now = time.time()
    start = now - DAYS * 86400
    rng = random.Random(7)
    comp_rows, candle_rows, ex_rows, ref_rows = [], [], [], []

    for asset in assets:
        usd = DemoConnector.BASE_USD.get(asset, 100.0)
        target = usd * DemoConnector.USDT_TMN * 1.025
        # random walk that ends near the live demo starting price
        n = int(DAYS * 86400 / SNAP_RES)
        vol = 0.0035 if asset != "USDT" else 0.0008
        walk = [0.0]
        for _ in range(n - 1):
            walk.append(walk[-1] + rng.gauss(0, vol))
        drift = walk[-1]
        prices = [target * (1 + w - drift * i / (n - 1)) *
                  (1 - 0.02 * (1 - i / n))  # gentle 30d uptrend
                  for i, w in enumerate(walk)]

        prev = prices[0]
        for i, price in enumerate(prices):
            ts = start + i * SNAP_RES
            premium = 2.5 + rng.gauss(0, 0.6) if asset != "USDT" else None
            comp_rows.append((asset, quote, price, price * 0.9995, price * 1.0005,
                              price * rng.uniform(500, 900), premium, ts))
            # consistent USD reference so historical premium ≈ stored premium
            if asset != "USDT":
                usdt_tmn = DemoConnector.USDT_TMN * 1.025
                ref_rows.append((asset, price / usdt_tmn / (1 + (premium or 0) / 100), ts))
            else:
                ref_rows.append((asset, 1.0 + rng.gauss(0, 0.0005), ts))
            hi = max(prev, price) * (1 + abs(rng.gauss(0, 0.0012)))
            lo = min(prev, price) * (1 - abs(rng.gauss(0, 0.0012)))
            candle_rows.append(("composite", asset, quote, SNAP_RES, ts,
                                prev, hi, lo, price, rng.uniform(0.5, 4.0)))
            prev = price

        # hourly per-exchange snapshots for spread/liquidity analytics
        for name, bias, spread_bps in DEMO_PROFILES:
            for h in range(DAYS * 24):
                ts = start + h * EX_RES
                idx = min(int(h * EX_RES / SNAP_RES), n - 1)
                mid = prices[idx] * (1 + bias / 100 + rng.gauss(0, 0.001))
                sp_pct = spread_bps / 100 * rng.uniform(0.6, 1.8)
                half = mid * sp_pct / 200
                depth = mid * rng.uniform(20, 120)
                ex_rows.append((name, asset, quote, mid - half, mid + half, mid,
                                sp_pct, depth, depth * rng.uniform(0.7, 1.3),
                                rng.uniform(50, 400), mid * rng.uniform(50, 400), ts))

    db.insert_composites(comp_rows)
    db.upsert_candles(candle_rows)
    db.insert_snapshots(ex_rows)
    db.insert_reference_prices(ref_rows)
    log.info("Seeded %d composite, %d candle, %d exchange, %d reference rows",
             len(comp_rows), len(candle_rows), len(ex_rows), len(ref_rows))
