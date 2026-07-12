"""Trade-tape volume estimator: dedup, rolling window, persistence."""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.connectors import _normalize_trades
from app.volume_estimator import VolumeEstimator


def test_normalize_trades_shapes():
    now = time.time()
    # dict shape (Tabdeal/Bitpin style), ms timestamps
    dicts = [{"id": 1, "price": "100", "qty": "2", "time": now * 1000},
             {"match_id": 2, "price": 101, "match_amount": 3, "created_at": now}]
    out = _normalize_trades(dicts)
    assert len(out) == 2 and out[0]["amount"] == 2 and abs(out[0]["ts"] - now) < 2
    # array shape (Ramzinex style) with Rial scale
    arrays = [[1_000_000_000, 0.5, 500_000_000, now]]
    out = _normalize_trades(arrays, price_scale=0.1)
    assert out[0]["price"] == 100_000_000 and out[0]["amount"] == 0.5


def test_estimator_dedup_and_sum():
    est = VolumeEstimator()
    est._loaded = True   # skip DB load
    now = time.time()
    trades = [{"id": "a", "ts": now - 10, "price": 100, "amount": 2},
              {"id": "b", "ts": now - 5, "price": 110, "amount": 1}]
    assert est.ingest("X", "BTC", trades) == 2
    assert est.ingest("X", "BTC", trades) == 0        # duplicates ignored
    base, quote, coverage = est.volumes("X", "BTC")
    assert base == 3 and quote == 100 * 2 + 110 * 1
    assert coverage >= 0


def test_estimator_ignores_prestartup_trades():
    est = VolumeEstimator()
    est._loaded = True
    old = est._started - 3600   # before startup: belongs to persisted buckets
    assert est.ingest("X", "ETH", [{"id": "z", "ts": old, "price": 10, "amount": 1}]) == 0


def test_estimator_flush_and_reload_roundtrip():
    est = VolumeEstimator()
    est._loaded = True
    now = time.time()
    est.ingest("FlushEx", "BTC", [{"id": "f1", "ts": now, "price": 50, "amount": 4}])
    est.flush()
    # a fresh instance must recover the persisted buckets from SQLite
    est2 = VolumeEstimator()
    base, quote, _cov = est2.volumes("FlushEx", "BTC")
    assert base == 4 and quote == 200
