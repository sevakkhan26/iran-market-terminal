"""News + economic calendar service.

Fixes vs v1:
- min_impact / coin filters actually work.
- Calendar events persist to SQLite → historical surprise stats per indicator.
- Surprise % computed when actual & forecast are numeric.
- Staleness timestamps exposed so the UI can flag old data.
- Demo mode generates synthetic feeds for offline development.
"""
from __future__ import annotations

import asyncio
import logging
import random
import re
import time
from typing import Any, Dict, List, Optional

from . import db
from .config import CONFIG
from .connectors import get_client
from .models import EconomicEvent, ImpactLevel, NewsItem

log = logging.getLogger("terminal.news")

RSS_FEEDS = [
    ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("CoinTelegraph", "https://cointelegraph.com/rss"),
    ("Bitcoin Magazine", "https://bitcoinmagazine.com/.rss/full/"),
    ("Decrypt", "https://decrypt.co/feed"),
    ("CryptoSlate", "https://cryptoslate.com/feed/"),
    ("NewsBTC", "https://www.newsbtc.com/feed/"),
    ("U.Today", "https://u.today/rss"),
    ("Investing.com", "https://www.investing.com/rss/news.rss"),
    ("Yahoo Finance", "https://finance.yahoo.com/news/rssindex"),
]

FOREX_FACTORY_URLS = [
    "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
    "https://nfs.faireconomy.media/ff_calendar_nextweek.json",
]

BTC_KEYWORDS = ["bitcoin", "btc", "satoshi", "halving", "miner", "mining"]
ETH_KEYWORDS = ["ethereum", "eth", "vitalik", "staking", "l2", "layer 2", "defi"]
MARKET_KEYWORDS = ["crypto", "market", "fed", "rate", "inflation", "sec",
                   "regulation", "etf", "stablecoin", "tether", "usdt",
                   "sanction", "dollar", "treasury", "liquidation"]
HIGH_IMPACT_KEYWORDS = ["crash", "hack", "exploit", "sec sues", "ban", "etf approved",
                        "etf rejected", "bankrupt", "liquidation", "emergency",
                        "sanction", "halving", "all-time high", "plunge", "surge"]

_NUM_RE = re.compile(r"^\s*([-+]?\d*\.?\d+)\s*([%kmbt]?)", re.IGNORECASE)
_MULT = {"": 1.0, "%": 1.0, "k": 1e3, "m": 1e6, "b": 1e9, "t": 1e12}


def parse_numeric(value: Any) -> Optional[float]:
    if value is None:
        return None
    m = _NUM_RE.match(str(value))
    if not m:
        return None
    return float(m.group(1)) * _MULT.get(m.group(2).lower(), 1.0)


def compute_surprise(actual: Any, forecast: Any) -> Optional[float]:
    a, f = parse_numeric(actual), parse_numeric(forecast)
    if a is None or f is None:
        return None
    return round(a - f, 4)


def classify_relevance(text: str) -> Optional[str]:
    t = text.lower()
    if any(k in t for k in ETH_KEYWORDS):
        return "ETH"
    if any(k in t for k in BTC_KEYWORDS):
        return "BTC"
    if any(k in t for k in MARKET_KEYWORDS):
        return "MARKET"
    return None


def detect_impact(text: str) -> ImpactLevel:
    t = text.lower()
    if any(k in t for k in HIGH_IMPACT_KEYWORDS):
        return ImpactLevel.HIGH
    return ImpactLevel.MEDIUM


class NewsService:
    def __init__(self) -> None:
        self.news_cache: List[NewsItem] = []
        self.calendar_cache: List[EconomicEvent] = []
        self.news_refreshed_at: float = 0.0
        self.calendar_refreshed_at: float = 0.0

    # ---------------------------------------------------------------- news --
    async def refresh_news(self) -> None:
        if CONFIG.get("demo_mode"):
            self.news_cache = _demo_news()
            self.news_refreshed_at = time.time()
            return
        try:
            import feedparser  # lazy: heavy import
        except ImportError:
            log.error("feedparser not installed; news disabled")
            return
        items: List[NewsItem] = []

        async def fetch(source: str, url: str) -> None:
            try:
                parsed = await asyncio.to_thread(feedparser.parse, url)
                for entry in parsed.entries[:15]:
                    title = getattr(entry, "title", "") or ""
                    coin = classify_relevance(title)
                    if not coin:
                        continue
                    ts = time.time()
                    if getattr(entry, "published_parsed", None):
                        import calendar as _cal
                        ts = _cal.timegm(entry.published_parsed)
                    items.append(NewsItem(
                        title=title.strip(), source=source,
                        impact=detect_impact(title),
                        related_coins=[coin], timestamp=ts,
                        url=getattr(entry, "link", "") or "", category=coin))
            except Exception as exc:
                log.debug("RSS %s failed: %s", source, exc)

        await asyncio.gather(*(fetch(s, u) for s, u in RSS_FEEDS))
        if items:
            items.sort(key=lambda n: n.timestamp, reverse=True)
            self.news_cache = items[:120]
            self.news_refreshed_at = time.time()

    def get_news(self, coin: str = "ALL",
                 min_impact: int = 1) -> List[Dict[str, Any]]:
        out = []
        for item in self.news_cache:
            if int(item.impact) < min_impact:
                continue
            if coin not in ("ALL", "") and coin.upper() not in item.related_coins \
                    and item.category != coin.upper():
                continue
            out.append({
                "title": item.title, "source": item.source,
                "impact": item.impact.name, "category": item.category,
                "url": item.url, "timestamp": item.timestamp,
            })
        return out

    # ------------------------------------------------------------ calendar --
    async def refresh_calendar(self) -> None:
        if CONFIG.get("demo_mode"):
            events = _demo_calendar()
        else:
            events = await self._fetch_forexfactory()
        if not events:
            # Live feed unreachable: fall back to events persisted in SQLite
            # (last successful fetch) so the calendar is never blank.
            if not self.calendar_cache:
                self._load_calendar_from_db()
            return
        self.calendar_cache = events
        self.calendar_refreshed_at = time.time()
        try:
            db.upsert_calendar_events([
                (e.title, e.country, e.impact, e.forecast, e.previous,
                 e.actual, e.surprise_pct, e.timestamp) for e in events
            ])
        except Exception as exc:
            log.error("calendar persist failed: %s", exc)

    def _load_calendar_from_db(self) -> None:
        try:
            rows = db.get_calendar_events(time.time() - 3 * 86400,
                                          time.time() + 8 * 86400)
        except Exception as exc:
            log.error("calendar DB fallback failed: %s", exc)
            return
        if rows:
            self.calendar_cache = [
                EconomicEvent(
                    title=r["title"], country=r["country"] or "",
                    impact=r["impact"] or "Low", forecast=r["forecast"] or "",
                    previous=r["previous"] or "", actual=r["actual"] or "",
                    timestamp=r["ts"], surprise_pct=r["surprise_pct"])
                for r in rows
            ]
            log.info("calendar: serving %d events from DB fallback", len(rows))

    async def _fetch_forexfactory(self) -> List[EconomicEvent]:
        raw: List[Any] = []
        for url in FOREX_FACTORY_URLS:
            try:
                r = await get_client().get(url)
                r.raise_for_status()
                chunk = r.json()
                if isinstance(chunk, list):
                    raw.extend(chunk)
            except Exception as exc:
                log.warning("calendar fetch failed (%s): %s", url, exc)
        events: List[EconomicEvent] = []
        from datetime import datetime
        seen = set()
        for item in raw if isinstance(raw, list) else []:
            dedupe = (item.get("title"), item.get("country"), item.get("date"))
            if dedupe in seen:
                continue
            seen.add(dedupe)
            try:
                ts = datetime.fromisoformat(
                    str(item.get("date", "")).replace("Z", "+00:00")).timestamp()
            except ValueError:
                continue
            actual = str(item.get("actual", "") or "")
            forecast = str(item.get("forecast", "") or "")
            events.append(EconomicEvent(
                title=str(item.get("title", "")).strip(),
                country=str(item.get("country", "")).strip().upper(),
                impact=str(item.get("impact", "Low")).strip(),
                forecast=forecast, previous=str(item.get("previous", "") or ""),
                actual=actual, timestamp=ts,
                surprise_pct=compute_surprise(actual, forecast),
                revised=str(item.get("revised", "") or "")))
        return events

    def get_calendar(self, impact: str = "ALL",
                     country: str = "ALL") -> List[Dict[str, Any]]:
        out = []
        for e in sorted(self.calendar_cache, key=lambda x: x.timestamp):
            if impact not in ("ALL", "") and e.impact.upper() != impact.upper():
                continue
            if country not in ("ALL", "") and e.country.upper() != country.upper():
                continue
            d = e.to_dict()
            d["history"] = None  # filled on demand via /api/calendar/history
            out.append(d)
        return out


# ------------------------------------------------------------------- demo ---

_DEMO_HEADLINES = [
    ("Bitcoin breaks above key resistance as ETF inflows accelerate", "BTC", ImpactLevel.HIGH),
    ("Ethereum staking yields tighten as validator queue grows", "ETH", ImpactLevel.MEDIUM),
    ("Tether prints $1B USDT on Tron — stablecoin supply at record", "MARKET", ImpactLevel.MEDIUM),
    ("Fed officials signal patience on rate cuts; risk assets steady", "MARKET", ImpactLevel.MEDIUM),
    ("Major exchange reports withdrawal delays amid volume spike", "MARKET", ImpactLevel.HIGH),
    ("Bitcoin miners' reserve hits 6-month low after price rally", "BTC", ImpactLevel.MEDIUM),
    ("Layer-2 activity on Ethereum reaches new all-time high", "ETH", ImpactLevel.MEDIUM),
    ("Rial volatility drives record Iranian stablecoin demand", "MARKET", ImpactLevel.HIGH),
]


def _demo_news() -> List[NewsItem]:
    now = time.time()
    rng = random.Random(int(now / 600))
    items = []
    for i, (title, cat, impact) in enumerate(_DEMO_HEADLINES):
        items.append(NewsItem(
            title=title, source=rng.choice(["CoinDesk", "CoinTelegraph", "Decrypt"]),
            impact=impact, related_coins=[cat], timestamp=now - i * 1800 - rng.uniform(0, 900),
            url="https://example.com/demo", category=cat))
    return items


_DEMO_EVENTS = [
    ("Core CPI m/m", "USD", "High", "0.3%", "0.2%"),
    ("Federal Funds Rate", "USD", "High", "4.25%", "4.50%"),
    ("Non-Farm Employment Change", "USD", "High", "185K", "210K"),
    ("German Factory Orders m/m", "EUR", "Low", "1.1%", "-3.8%"),
    ("ECB Press Conference", "EUR", "High", "", ""),
    ("BOJ Policy Rate", "JPY", "Medium", "0.50%", "0.50%"),
    ("Unemployment Claims", "USD", "Medium", "224K", "231K"),
    ("Crude Oil Inventories", "USD", "Low", "-1.2M", "3.9M"),
    ("GDP q/q", "GBP", "Medium", "0.2%", "0.1%"),
    ("Retail Sales m/m", "USD", "Medium", "0.4%", "0.1%"),
]


def _demo_calendar() -> List[EconomicEvent]:
    now = time.time()
    rng = random.Random(42)
    events = []
    for i, (title, country, impact, forecast, previous) in enumerate(_DEMO_EVENTS):
        # spread events over the week: some past (with actuals), some upcoming
        offset = (i - 4) * 21600 + rng.uniform(-3600, 3600)
        ts = now + offset
        actual = ""
        if ts < now and forecast:
            f = parse_numeric(forecast) or 0
            actual_val = f + rng.uniform(-0.4, 0.4) * max(abs(f), 0.2)
            unit = "%" if "%" in forecast else ("K" if "K" in forecast else "")
            scale = 1e3 if unit == "K" else 1.0
            actual = f"{actual_val / scale:.1f}{unit}"
        revised = "0.3%" if title == "Retail Sales m/m" else ""
        events.append(EconomicEvent(
            title=title, country=country, impact=impact,
            forecast=forecast, previous=previous, actual=actual,
            timestamp=ts, surprise_pct=compute_surprise(actual, forecast),
            revised=revised))
    return events


news_service = NewsService()
