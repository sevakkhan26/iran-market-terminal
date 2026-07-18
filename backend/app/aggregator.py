"""Market aggregator: polls all connectors, computes metrics, persists snapshots.

Cycle (every `market_interval` seconds):
  1. Fan out order-book fetches for every connector x pair (asyncio.gather).
  2. Ticker stats refreshed on a slower cadence (every 60s).
  3. Build MarketSnapshot per exchange x pair; feed the metrics engine.
  4. Compute composite (cross-exchange) mid + Iran premium per pair.
  5. Every `snapshot_interval` (default 5 min): batch-write snapshots to SQLite.
  6. Run anomaly detection + alert rules; broadcast state to WebSocket clients.
"""
from __future__ import annotations

import asyncio
import logging
import statistics
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import db
from .config import CONFIG
from .connectors import (BaseExchangeConnector, DemoConnector, ReferenceConnector,
                         build_connectors, maybe_recycle_client)
from .metrics import metrics_engine
from .models import MarketSnapshot, MarketStatus, OrderBook, TickerStats
from .settings import settings_store
from .volume_estimator import volume_estimator

log = logging.getLogger("terminal.aggregator")

STALE_AFTER_MS = 15_000


class MarketAggregator:
    def __init__(self) -> None:
        self.connectors: List[BaseExchangeConnector] = []
        self.market_state: Dict[Tuple[str, str], MarketSnapshot] = {}
        self.books: Dict[Tuple[str, str], OrderBook] = {}
        self.stats_cache: Dict[Tuple[str, str], TickerStats] = {}
        self.usd_reference: Dict[str, float] = {}
        self.usd_reference_ts: float = 0.0
        self.last_stats_refresh: float = 0.0
        self.last_snapshot_write: float = 0.0
        self.cycle_count: int = 0
        self.listeners: List[Callable[[Dict[str, Any]], None]] = []
        self._reference = ReferenceConnector(
            CONFIG.get("reference", {}).get("coingecko_ids",
                                            {"BTC": "bitcoin", "ETH": "ethereum",
                                             "USDT": "tether"}))
        self._unresolvable: set = set()
        self._vol_warned: set = set()
        self.reload_connectors()

    # ------------------------------------------------------------- config --
    def reload_connectors(self) -> None:
        custom = db.get_custom_exchanges()
        self.connectors = build_connectors(CONFIG, custom)
        log.info("Active connectors: %s", [c.exchange_name for c in self.connectors])

    def pairs(self) -> List[Tuple[str, str]]:
        quote = CONFIG.get("quote_currency", "TMN")
        bases = [a.upper() for a in CONFIG.get("assets", [])]
        for row in db.get_custom_pairs():
            if row.get("enabled") and row["base"] not in bases:
                bases.append(row["base"])
        return [(b, quote) for b in bases]

    # -------------------------------------------------------------- cycle --
    async def update_markets(self) -> None:
        maybe_recycle_client()   # shed any leaked pooled connections between cycles
        settings = settings_store.get()
        pairs = self.pairs()
        refresh_stats = time.time() - self.last_stats_refresh > 60
        tasks = [
            self._process(connector, base, quote, settings.request_timeout, refresh_stats)
            for connector in self.connectors
            for base, quote in pairs
        ]
        if refresh_stats:
            self.last_stats_refresh = time.time()
        tasks.append(self._refresh_reference())
        await asyncio.gather(*tasks, return_exceptions=True)

        self._compute_composites(pairs)
        self.cycle_count += 1

        if time.time() - self.last_snapshot_write >= settings.snapshot_interval:
            await asyncio.to_thread(self._persist_snapshots, pairs)
            self.last_snapshot_write = time.time()

        self._broadcast()

    async def _process(self, connector: BaseExchangeConnector, base: str, quote: str,
                       timeout: float, refresh_stats: bool) -> None:
        key = (connector.exchange_name, base)
        started = time.time()
        try:
            book = await asyncio.wait_for(connector.fetch_order_book(base), timeout=timeout)
            latency_ms = (time.time() - started) * 1000
            if refresh_stats:
                try:
                    stats_result = await asyncio.wait_for(
                        connector.fetch_stats(base), timeout=timeout)
                    self.stats_cache[key] = stats_result
                    if (not stats_result.volume_24h_base
                            and not stats_result.volume_24h_quote
                            and key not in self._vol_warned):
                        self._vol_warned.add(key)
                        if getattr(connector, "supports_trades", False):
                            log.info("%s reports no 24h volume for %s — building"
                                     " an estimate from the public trade tape",
                                     connector.exchange_name, base)
                        else:
                            log.warning("%s reports no 24h volume for %s and has"
                                        " no trades endpoint — share will read 0",
                                        connector.exchange_name, base)
                except Exception:
                    pass
                # trade-tape fallback: accumulate observed trades into the
                # rolling 24h estimator for venues without reported volume
                cached = self.stats_cache.get(key, TickerStats())
                if (getattr(connector, "supports_trades", False)
                        and not cached.volume_24h_base
                        and not cached.volume_24h_quote):
                    try:
                        trades = await asyncio.wait_for(
                            connector.fetch_trades(base), timeout=timeout)
                        volume_estimator.ingest(connector.exchange_name, base, trades)
                    except Exception as exc:
                        log.debug("%s trades fetch failed: %s",
                                  connector.exchange_name, exc)
            stats = self.stats_cache.get(key, TickerStats())
            vol_estimated = False
            if not stats.volume_24h_base and not stats.volume_24h_quote:
                est_base, est_quote, coverage = volume_estimator.volumes(
                    connector.exchange_name, base)
                if est_quote > 0 or est_base > 0:
                    stats = TickerStats(last_price=stats.last_price,
                                        volume_24h_base=est_base,
                                        volume_24h_quote=est_quote,
                                        change_24h_pct=stats.change_24h_pct)
                    vol_estimated = True
            best_bid, best_ask = book.best_bid, book.best_ask
            if best_bid <= 0 or best_ask <= 0 or best_bid > best_ask * 1.5:
                raise ValueError("degenerate order book")
            mid = (best_bid + best_ask) / 2
            spread = best_ask - best_bid
            bid_depth = book.depth_notional("bid")
            ask_depth = book.depth_notional("ask")
            total = bid_depth + ask_depth
            age_ms = (time.time() - book.timestamp) * 1000
            snap = MarketSnapshot(
                exchange=connector.exchange_name, base=base, quote=quote,
                best_bid=best_bid, best_ask=best_ask, mid=mid,
                spread=spread, spread_pct=spread / best_ask * 100 if best_ask else 0.0,
                bid_depth_quote=bid_depth, ask_depth_quote=ask_depth,
                depth_imbalance=(bid_depth - ask_depth) / total if total else 0.0,
                volume_24h_base=stats.volume_24h_base,
                volume_24h_quote=stats.volume_24h_quote or stats.volume_24h_base * mid,
                volume_estimated=vol_estimated,
                last_price=stats.last_price or mid,
                latency_ms=round(latency_ms, 1),
                timestamp=book.timestamp or time.time(),
                status=(MarketStatus.DELAYED.value if age_ms > STALE_AFTER_MS
                        else MarketStatus.CONNECTED.value),
            )
            self.books[key] = book
            self.market_state[key] = snap
            metrics_engine.ingest(snap)
        except Exception as exc:
            log.debug("%s %s fetch failed: %s", connector.exchange_name, base, exc)
            prev = self.market_state.get(key)
            if prev:
                prev.status = MarketStatus.OFFLINE.value
            else:
                self.market_state[key] = MarketSnapshot(
                    exchange=connector.exchange_name, base=base, quote=quote,
                    status=MarketStatus.OFFLINE.value, timestamp=0.0)

    async def _refresh_reference(self) -> None:
        if not CONFIG.get("reference", {}).get("enabled", True):
            return
        if time.time() - self.usd_reference_ts < 120:
            return
        bases = [b for b, _q in self.pairs()]
        try:
            if CONFIG.get("demo_mode"):
                self.usd_reference = DemoConnector.usd_reference(bases)
                self.usd_reference_ts = time.time()
                return
            # merge persisted id overrides / previously-resolved ids
            for asset, cg_id in db.get_reference_ids().items():
                if cg_id:
                    self._reference.set_id(asset, cg_id)
            # auto-resolve one unknown asset per refresh (rate-limit friendly)
            unknown = [b for b in bases
                       if b not in self._reference.id_map and b not in self._unresolvable]
            if unknown:
                asset = unknown[0]
                cg_id = await self._reference.resolve_id(asset)
                if cg_id:
                    self._reference.set_id(asset, cg_id)
                    db.upsert_reference_id(asset, cg_id)
                    log.info("reference: resolved %s -> %s", asset, cg_id)
                else:
                    self._unresolvable.add(asset)
                    log.warning("reference: could not resolve %s (set a manual"
                                " coingecko_id in Admin)", asset)
            self.usd_reference = await self._reference.fetch_usd_prices()
            self.usd_reference_ts = time.time()
        except Exception as exc:
            log.exception("reference fetch failed")

    # --------------------------------------------------------- composites --
    def composite_mid(self, base: str) -> Optional[float]:
        mids = [s.mid for (ex, b), s in self.market_state.items()
                if b == base and s.mid > 0 and s.status != MarketStatus.OFFLINE.value]
        return statistics.fmean(mids) if mids else None

    def _compute_composites(self, pairs: List[Tuple[str, str]]) -> None:
        now = time.time()
        for base, _quote in pairs:
            mid = self.composite_mid(base)
            if mid:
                metrics_engine.ingest_composite(base, now, mid)

    def premium_pct(self, base: str, method: str = "composite",
                    exchange: Optional[str] = None) -> Optional[float]:
        if base == "USDT":
            return None
        from .premium import live_premium
        by_asset = self.snapshots_by_asset()
        return live_premium(by_asset.get(base, []), by_asset.get("USDT", []),
                            self.usd_reference.get(base, 0.0), method, exchange)

    # -------------------------------------------------------- persistence --
    def _persist_snapshots(self, pairs: List[Tuple[str, str]]) -> None:
        now = time.time()
        snap_rows = []
        comp_rows = []
        for (ex, base), s in self.market_state.items():
            if s.mid <= 0 or s.status == MarketStatus.OFFLINE.value:
                continue
            snap_rows.append((ex, base, s.quote, s.best_bid, s.best_ask, s.mid,
                              s.spread_pct, s.bid_depth_quote, s.ask_depth_quote,
                              s.volume_24h_base, s.volume_24h_quote, now))
        for base, quote in pairs:
            mid = self.composite_mid(base)
            if not mid:
                continue
            live = [s for (ex, b), s in self.market_state.items()
                    if b == base and s.mid > 0]
            best_bid = max((s.best_bid for s in live), default=0.0)
            best_ask = min((s.best_ask for s in live if s.best_ask > 0), default=0.0)
            volume = sum(s.volume_24h_quote for s in live)
            comp_rows.append((base, quote, mid, best_bid, best_ask, volume,
                              self.premium_pct(base), now))
        volume_estimator.flush()
        ref_rows = [(asset, usd, now) for asset, usd in self.usd_reference.items()
                    if usd > 0]
        try:
            if snap_rows:
                db.insert_snapshots(snap_rows)
            if comp_rows:
                db.insert_composites(comp_rows)
            if ref_rows:
                db.insert_reference_prices(ref_rows)
        except Exception as exc:
            log.error("snapshot persist failed: %s", exc)

    # ----------------------------------------------------------- fan-out ---
    def add_listener(self, fn: Callable[[Dict[str, Any]], None]) -> None:
        self.listeners.append(fn)

    def _broadcast(self) -> None:
        if not self.listeners:
            return
        payload = {"type": "markets", "ts": time.time(),
                   "data": [s.to_dict() for s in self.market_state.values()]}
        for fn in list(self.listeners):
            try:
                fn(payload)
            except Exception:
                pass

    # -------------------------------------------------------------- views --
    def snapshots_by_asset(self) -> Dict[str, List[MarketSnapshot]]:
        out: Dict[str, List[MarketSnapshot]] = {}
        for (ex, base), s in self.market_state.items():
            out.setdefault(base, []).append(s)
        return out


market_aggregator = MarketAggregator()
