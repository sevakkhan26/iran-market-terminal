"""In-memory metrics engine.

Keeps ring buffers of recent observations (per exchange x asset, plus a
composite per asset) and computes:
- 1H/24H change from memory, 7D change from persisted snapshots
- spread statistics (mean / min / max / volatility)
- relative liquidity scores (0-100)
- Iran premium vs global USD reference
- depth-aware, fee-aware arbitrage opportunities
- anomaly detection (price deviation, liquidity drops, stale feeds)
"""
from __future__ import annotations

import math
import statistics
import time
from collections import deque
from typing import Deque, Dict, List, Optional, Tuple

from . import db
from .config import taker_fee_pct
from .models import Anomaly, ArbitrageOpportunity, MarketSnapshot, OrderBook

RING_MAXLEN = 40_000  # ~33h at a 3s cycle

Point = Tuple[float, float]                      # (ts, value)
ExKey = Tuple[str, str]                          # (exchange, base)


class MetricsEngine:
    def __init__(self) -> None:
        self.mid_rings: Dict[ExKey, Deque[Point]] = {}
        self.spread_rings: Dict[ExKey, Deque[Point]] = {}
        self.depth_rings: Dict[ExKey, Deque[Point]] = {}       # total depth notional
        self.composite_rings: Dict[str, Deque[Point]] = {}     # per asset

    # ------------------------------------------------------------- ingest --
    def ingest(self, snap: MarketSnapshot) -> None:
        key = (snap.exchange, snap.base)
        if snap.mid > 0:
            self.mid_rings.setdefault(key, deque(maxlen=RING_MAXLEN)).append(
                (snap.timestamp, snap.mid))
            self.spread_rings.setdefault(key, deque(maxlen=RING_MAXLEN)).append(
                (snap.timestamp, snap.spread_pct))
            self.depth_rings.setdefault(key, deque(maxlen=RING_MAXLEN)).append(
                (snap.timestamp, snap.bid_depth_quote + snap.ask_depth_quote))

    def ingest_composite(self, base: str, ts: float, mid: float) -> None:
        if mid > 0:
            self.composite_rings.setdefault(base, deque(maxlen=RING_MAXLEN)).append((ts, mid))

    # ------------------------------------------------------------ changes --
    @staticmethod
    def _value_at(ring: Deque[Point], target_ts: float) -> Optional[float]:
        """Earliest value at/after target_ts (rings are append-ordered)."""
        if not ring:
            return None
        if ring[0][0] > target_ts + 900:  # ring doesn't reach back far enough
            return None
        # binary search over the deque snapshot
        arr = list(ring)
        lo, hi = 0, len(arr) - 1
        best = None
        while lo <= hi:
            mid_i = (lo + hi) // 2
            if arr[mid_i][0] >= target_ts:
                best = arr[mid_i][1]
                hi = mid_i - 1
            else:
                lo = mid_i + 1
        return best

    def change_pct(self, base: str, quote: str, window_sec: float) -> Optional[float]:
        ring = self.composite_rings.get(base)
        now = time.time()
        current = ring[-1][1] if ring else None
        if current is None:
            return None
        past: Optional[float] = None
        if ring:
            past = self._value_at(ring, now - window_sec)
        if past is None:  # fall back to persisted snapshots (7D etc.)
            past = db.get_mid_at(base, quote, now - window_sec, tolerance=window_sec * 0.1)
        if not past:
            return None
        return (current - past) / past * 100.0

    def sparkline(self, base: str, points: int = 40,
                  window_sec: float = 86400.0) -> List[float]:
        ring = self.composite_rings.get(base)
        if not ring:
            return []
        now = time.time()
        arr = [p for p in ring if p[0] >= now - window_sec]
        if len(arr) < 2:
            arr = list(ring)[-points:]
        if len(arr) <= points:
            return [round(v, 2) for _, v in arr]
        step = len(arr) / points
        return [round(arr[int(i * step)][1], 2) for i in range(points)]

    # ------------------------------------------------------- spread stats --
    def spread_stats(self, exchange: str, base: str,
                     window_sec: float = 3600.0) -> Dict[str, Optional[float]]:
        ring = self.spread_rings.get((exchange, base))
        now = time.time()
        values = [v for ts, v in (ring or []) if ts >= now - window_sec and v >= 0]
        if not values:
            return {"current": None, "avg": None, "min": None, "max": None, "stdev": None}
        return {
            "current": round(values[-1], 4),
            "avg": round(statistics.fmean(values), 4),
            "min": round(min(values), 4),
            "max": round(max(values), 4),
            "stdev": round(statistics.pstdev(values), 4) if len(values) > 1 else 0.0,
        }

    # ---------------------------------------------------- liquidity score --
    @staticmethod
    def liquidity_scores(snaps: List[MarketSnapshot]) -> Dict[str, float]:
        """Relative 0-100 score per exchange for one asset.

        50% depth (log-scaled vs best venue), 35% spread tightness, 15% freshness.
        """
        live = [s for s in snaps if s.mid > 0]
        if not live:
            return {}
        max_depth = max((s.bid_depth_quote + s.ask_depth_quote) for s in live) or 1.0
        min_spread = min((s.spread_pct for s in live if s.spread_pct > 0), default=0.01)
        now = time.time()
        scores: Dict[str, float] = {}
        for s in live:
            depth = s.bid_depth_quote + s.ask_depth_quote
            depth_score = math.log1p(depth) / math.log1p(max_depth) if depth > 0 else 0.0
            spread_score = min(1.0, min_spread / s.spread_pct) if s.spread_pct > 0 else 0.0
            age = now - s.timestamp
            fresh_score = max(0.0, 1.0 - age / 60.0)
            scores[s.exchange] = round(
                100 * (0.5 * depth_score + 0.35 * spread_score + 0.15 * fresh_score), 1)
        return scores

    def depth_drop_pct(self, exchange: str, base: str,
                       window_sec: float = 3600.0) -> Optional[float]:
        """How far current total depth sits below its window average (positive = drop)."""
        ring = self.depth_rings.get((exchange, base))
        if not ring or len(ring) < 10:
            return None
        now = time.time()
        values = [v for ts, v in ring if ts >= now - window_sec]
        if len(values) < 10:
            return None
        avg = statistics.fmean(values)
        if avg <= 0:
            return None
        return round((avg - values[-1]) / avg * 100.0, 2)

    # ------------------------------------------------------------ premium --
    @staticmethod
    def iran_premium_pct(asset_mid_tmn: float, usdt_mid_tmn: float,
                         asset_usd: float) -> Optional[float]:
        if asset_mid_tmn <= 0 or usdt_mid_tmn <= 0 or asset_usd <= 0:
            return None
        implied_usd = asset_mid_tmn / usdt_mid_tmn
        return round((implied_usd - asset_usd) / asset_usd * 100.0, 3)

    # ---------------------------------------------------------- arbitrage --
    @staticmethod
    def arbitrage(base: str, quote: str,
                  books: Dict[str, OrderBook]) -> List[ArbitrageOpportunity]:
        """Depth-aware, fee-aware cross-exchange opportunities."""
        now = time.time()
        out: List[ArbitrageOpportunity] = []
        names = [n for n, b in books.items() if b.bids and b.asks]
        for buy_ex in names:
            for sell_ex in names:
                if buy_ex == sell_ex:
                    continue
                fb = taker_fee_pct(buy_ex) / 100.0
                fs = taker_fee_pct(sell_ex) / 100.0
                asks = list(books[buy_ex].asks)
                bids = list(books[sell_ex].bids)
                size = 0.0
                profit = 0.0
                cost = 0.0
                ai = bi = 0
                a_qty = asks[0][1] if asks else 0.0
                b_qty = bids[0][1] if bids else 0.0
                while ai < len(asks) and bi < len(bids):
                    ap, bp = asks[ai][0], bids[bi][0]
                    eff_buy = ap * (1 + fb)
                    eff_sell = bp * (1 - fs)
                    if eff_buy >= eff_sell:
                        break
                    qty = min(a_qty, b_qty)
                    size += qty
                    profit += qty * (eff_sell - eff_buy)
                    cost += qty * eff_buy
                    a_qty -= qty
                    b_qty -= qty
                    if a_qty <= 1e-12:
                        ai += 1
                        a_qty = asks[ai][1] if ai < len(asks) else 0.0
                    if b_qty <= 1e-12:
                        bi += 1
                        b_qty = bids[bi][1] if bi < len(bids) else 0.0
                if size <= 0:
                    continue
                buy_p = books[buy_ex].best_ask
                sell_p = books[sell_ex].best_bid
                gross = (sell_p - buy_p) / buy_p * 100.0
                net = profit / cost * 100.0 if cost > 0 else 0.0
                out.append(ArbitrageOpportunity(
                    base=base, quote=quote,
                    buy_exchange=buy_ex, sell_exchange=sell_ex,
                    buy_price=round(buy_p, 2), sell_price=round(sell_p, 2),
                    gross_pct=round(gross, 4), net_pct=round(net, 4),
                    max_size_base=round(size, 6),
                    est_profit_quote=round(profit, 0),
                    timestamp=now,
                ))
        out.sort(key=lambda o: o.net_pct, reverse=True)
        return out

    # ------------------------------------------------------ order impact ---
    @staticmethod
    def order_impact_pct(book: OrderBook, notional_quote: float,
                         side: str = "buy") -> Optional[float]:
        """Slippage of a market order of `notional_quote` TMN vs the mid price.

        Walks the book level-by-level. Returns None if the book can't absorb
        the full size (itself a liquidity red flag)."""
        levels = book.asks if side == "buy" else book.bids
        if not levels or not book.bids or not book.asks:
            return None
        mid = (book.best_bid + book.best_ask) / 2
        remaining = notional_quote
        cost = 0.0
        qty = 0.0
        for price, amount in levels:
            level_notional = price * amount
            take = min(remaining, level_notional)
            cost += take
            qty += take / price
            remaining -= take
            if remaining <= 0:
                break
        if remaining > 0 or qty <= 0:
            return None  # book too thin for this size
        avg_price = cost / qty
        impact = (avg_price - mid) / mid * 100.0 if side == "buy" \
            else (mid - avg_price) / mid * 100.0
        return round(impact, 4)

    def composite_move_pct(self, base: str, window_sec: float = 300.0) -> Optional[float]:
        """Composite change over a short window (price-spike detector)."""
        ring = self.composite_rings.get(base)
        if not ring or len(ring) < 3:
            return None
        now = time.time()
        past = self._value_at(ring, now - window_sec)
        if not past:
            return None
        return (ring[-1][1] - past) / past * 100.0

    # ---------------------------------------------------------- anomalies --
    def detect_anomalies(self, snaps_by_asset: Dict[str, List[MarketSnapshot]],
                         stale_after_sec: float = 30.0) -> List[Anomaly]:
        now = time.time()
        anomalies: List[Anomaly] = []
        for base, snaps in snaps_by_asset.items():
            live = [s for s in snaps if s.mid > 0 and s.status != "offline"]

            # 1. sudden composite price spike (5-minute window)
            move = self.composite_move_pct(base, 300)
            if move is not None and abs(move) >= 1.0:
                anomalies.append(Anomaly(
                    kind="price_spike", exchange="composite", base=base,
                    message=f"{base} moved {move:+.2f}% in the last 5 minutes",
                    severity="critical" if abs(move) >= 2.5 else "warning",
                    value=round(move, 3), timestamp=now))

            # 2. cross-exchange price deviation vs median
            if len(live) >= 3:
                med = statistics.median(s.mid for s in live)
                for s in live:
                    dev = (s.mid - med) / med * 100.0
                    if abs(dev) >= 2.0:
                        sev = "critical"
                    elif abs(dev) >= 0.75:
                        sev = "warning"
                    else:
                        continue
                    anomalies.append(Anomaly(
                        kind="price_deviation", exchange=s.exchange, base=base,
                        message=(f"{s.exchange} {base} deviates {dev:+.2f}% "
                                 f"from cross-exchange median"),
                        severity=sev, value=round(dev, 3), timestamp=now))

            for s in snaps:
                # 3. exchange / API issues
                if s.status == "offline":
                    anomalies.append(Anomaly(
                        kind="api_issue", exchange=s.exchange, base=base,
                        message=f"{s.exchange} {base}: API unreachable — feed offline",
                        severity="critical", value=0.0, timestamp=now))
                    continue
                age = now - s.timestamp if s.timestamp else 1e9
                if age > stale_after_sec:
                    anomalies.append(Anomaly(
                        kind="stale_feed", exchange=s.exchange, base=base,
                        message=f"{s.exchange} {base} feed stale for {int(age)}s",
                        severity="warning", value=round(age, 1), timestamp=now))

                # 4. spread abnormally wide vs its own 1h average
                st = self.spread_stats(s.exchange, base, 3600)
                if (st["avg"] and st["current"] is not None and st["avg"] > 0
                        and st["current"] >= max(0.3, 2.5 * st["avg"])):
                    anomalies.append(Anomaly(
                        kind="spread_widening", exchange=s.exchange, base=base,
                        message=(f"{s.exchange} {base} spread {st['current']:.2f}% is "
                                 f"{st['current'] / st['avg']:.1f}x its 1h average"),
                        severity="warning", value=st["current"], timestamp=now))

                # 5. order-book depth collapse vs 1h average
                drop = self.depth_drop_pct(s.exchange, base)
                if drop is not None and drop >= 40.0:
                    anomalies.append(Anomaly(
                        kind="liquidity_drop", exchange=s.exchange, base=base,
                        message=(f"{s.exchange} {base} order-book depth down "
                                 f"{drop:.0f}% vs 1h average"),
                        severity="critical" if drop >= 70 else "warning",
                        value=drop, timestamp=now))
        return anomalies


metrics_engine = MetricsEngine()
