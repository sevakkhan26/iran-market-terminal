"""Unit tests for core math: metrics, arbitrage, surprise parsing, resampling."""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["DEMO_MODE"] = "1"

from app.candles import CandleService
from app.metrics import MetricsEngine
from app.models import MarketSnapshot, OrderBook
from app.news import compute_surprise, parse_numeric


def test_parse_numeric():
    assert parse_numeric("1.1%") == 1.1
    assert parse_numeric("-3.8%") == -3.8
    assert parse_numeric("250K") == 250_000
    assert parse_numeric("1.2M") == 1_200_000
    assert parse_numeric("") is None
    assert parse_numeric(None) is None


def test_compute_surprise():
    assert compute_surprise("2.4%", "1.1%") == 1.3
    assert compute_surprise("", "1.1%") is None


def test_iran_premium():
    # BTC at 11.55B TMN, USDT at 110k TMN -> implied $105k vs global $100k = +5%
    p = MetricsEngine.iran_premium_pct(11_550_000_000, 110_000, 100_000)
    assert abs(p - 5.0) < 0.01


def test_arbitrage_depth_and_fees():
    books = {
        "Cheap": OrderBook(bids=[[99, 1]], asks=[[100, 2], [101, 3]], timestamp=time.time()),
        "Rich": OrderBook(bids=[[103, 1], [102.5, 5]], asks=[[104, 1]], timestamp=time.time()),
    }
    ops = MetricsEngine.arbitrage("BTC", "TMN", books)
    assert ops, "expected at least one opportunity"
    best = ops[0]
    assert best.buy_exchange == "Cheap" and best.sell_exchange == "Rich"
    assert best.gross_pct > best.net_pct > 0
    assert best.max_size_base > 0


def test_no_arbitrage_when_fees_exceed_edge():
    books = {
        "A": OrderBook(bids=[[99.9, 1]], asks=[[100, 1]], timestamp=time.time()),
        "B": OrderBook(bids=[[100.05, 1]], asks=[[100.2, 1]], timestamp=time.time()),
    }
    ops = MetricsEngine.arbitrage("BTC", "TMN", books)
    # 0.05% edge < two taker fees -> filtered out
    assert all(o.net_pct <= 0 or o.max_size_base == 0 for o in ops) or not ops


def test_liquidity_scores_relative():
    now = time.time()
    deep = MarketSnapshot(exchange="Deep", base="BTC", quote="TMN", mid=100,
                          spread_pct=0.1, bid_depth_quote=1e9, ask_depth_quote=1e9,
                          timestamp=now, status="connected")
    thin = MarketSnapshot(exchange="Thin", base="BTC", quote="TMN", mid=100,
                          spread_pct=0.8, bid_depth_quote=1e6, ask_depth_quote=1e6,
                          timestamp=now, status="connected")
    scores = MetricsEngine.liquidity_scores([deep, thin])
    assert scores["Deep"] > scores["Thin"]
    assert 0 <= scores["Thin"] <= 100


def test_change_pct_from_ring():
    eng = MetricsEngine()
    now = time.time()
    for i in range(120):
        eng.ingest_composite("BTC", now - 3600 + i * 30, 100 + i * 0.1)
    chg = eng.change_pct("BTC", "TMN", 3600)
    assert chg is not None and chg > 0


def test_candle_resample():
    candles = [{"ts": t, "open": t, "high": t + 1, "low": t - 1,
                "close": t + 0.5, "volume": 1} for t in range(0, 600, 60)]
    out = CandleService._resample(candles, 300)
    assert len(out) == 2
    assert out[0]["open"] == 0 and out[0]["close"] == 240.5
    assert out[0]["volume"] == 5
