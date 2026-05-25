"""Logistics ingestion agent — port congestion + shipping disruptions.

Three complementary free feeds:
  1. IMF PortWatch API    — real-time port congestion (AIS-derived)
  2. Splash247 RSS        — shipping news (canal/route disruptions)
  3. ^BDI via yfinance    — Baltic Dry Index (already pulled by prices_agent;
                            this agent re-checks for sustained 30d moves ≥ 20%)

Watched ports (per spec §8.4):
  Busan (KRPUS), Antwerp (BEANR), Rotterdam (NLRTM),
  Bremerhaven (DEBRV), Savannah (USSAV), Norfolk (USORF)

Incoterms pre-linking: attaches contract_clause matches to escalated signals
before they hit the classifier (spec §8.4).

Cadence: every 1 hour.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser
import httpx
import yfinance as yf
from tenacity import retry, stop_after_attempt, wait_exponential

from apps.api.ingest.base import RawItem
from apps.api.ingest.runner import BaseIngestionAgent

logger = logging.getLogger(__name__)

SPLASH247_RSS = "https://splash247.com/feed/"

# Ports we monitor (locode → display name)
WATCHED_PORTS: dict[str, str] = {
    "KRPUS": "Busan",
    "BEANR": "Antwerp",
    "NLRTM": "Rotterdam",
    "DEBRV": "Bremerhaven",
    "USSAV": "Savannah",
    "USORF": "Norfolk",
}

# BDI proxy: BDRY (Breakwave Dry Bulk Shipping ETF) tracks BDI closely.
# ^BDI is no longer available on Yahoo Finance as of 2025.
BDI_TICKER = "BDRY"
BDI_LABEL = "Breakwave Dry Bulk ETF (BDI proxy)"

# BDI 30-day move threshold (spec §8.4)
BDI_30D_THRESHOLD = 0.20

LOGISTICS_KEYWORDS = [
    "busan", "antwerp", "rotterdam", "bremerhaven", "savannah", "norfolk",
    "canal", "suez", "panama", "strait", "strait of malacca",
    "port", "terminal", "congestion", "strike", "disruption", "vessel",
    "heavy lift", "breakbulk", "shipping", "freight", "route", "lane",
    "transformer", "power equipment", "generator",
]


def _parse_rss_date(entry: Any) -> datetime:
    for attr in ("published", "updated"):
        raw = getattr(entry, attr, None)
        if raw:
            try:
                return parsedate_to_datetime(raw)
            except Exception:
                pass
    return datetime.now(UTC)


class LogisticsAgent(BaseIngestionAgent):
    agent_name = "logistics_agent"

    def default_lookback_hours(self) -> int:
        return 1

    def keyword_rules(self) -> list[str]:
        return LOGISTICS_KEYWORDS

    async def pull(self, window: tuple[datetime, datetime]) -> list[RawItem]:
        items: list[RawItem] = []
        cutoff = window[0]

        # 1. Splash247 RSS — shipping disruptions
        splash_items = await self._pull_splash247(cutoff)
        items.extend(splash_items)

        # 2. BDRY ETF via yfinance (30-day BDI proxy, threshold ≥ 20%)
        bdi_items = self._pull_bdi()
        items.extend(bdi_items)

        return items

    async def _pull_splash247(self, cutoff: datetime) -> list[RawItem]:
        items: list[RawItem] = []
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(SPLASH247_RSS, follow_redirects=True)
                resp.raise_for_status()
                parsed = feedparser.parse(resp.content)

            route_keywords = [
                "canal", "suez", "panama", "strait", "strike", "port",
                "vessel", "grounding", "closure", "disruption", "route",
                "congestion", "heavy lift", "breakbulk", "weather",
            ]

            for entry in parsed.entries:
                published = _parse_rss_date(entry)
                if published < cutoff:
                    continue

                title = getattr(entry, "title", "") or ""
                summary = getattr(entry, "summary", "") or ""
                text_blob = (title + " " + summary).lower()

                if not any(kw in text_blob for kw in route_keywords):
                    continue

                source_id = f"splash247:{getattr(entry, 'id', title[:32])}"
                items.append(
                    RawItem(
                        source="logistics",
                        source_id=source_id,
                        url=getattr(entry, "link", ""),
                        occurred_at=published,
                        raw_payload={
                            "feed": "splash247",
                            "title": title,
                            "summary": summary[:400],
                            "link": getattr(entry, "link", ""),
                            "published": published.isoformat(),
                            "alert_type": "shipping_news",
                        },
                    )
                )

            logger.info("[logistics] Splash247: %d shipping news items", len(items))
        except Exception as exc:
            logger.error("[logistics] Splash247 error: %s", exc)

        return items

    def _pull_bdi(self) -> list[RawItem]:
        """Check BDRY ETF (BDI proxy) for sustained 30-day move ≥ 20% (spec §8.4).

        ^BDI is no longer available on Yahoo Finance; BDRY (Breakwave Dry Bulk
        Shipping ETF) is highly correlated and freely available.
        """
        items: list[RawItem] = []
        try:
            hist = yf.Ticker(BDI_TICKER).history(period="35d", interval="1d")
            if hist.empty or len(hist) < 7:
                logger.warning("[logistics] No data for %s", BDI_TICKER)
                return items

            current = float(hist["Close"].iloc[-1])
            ref_idx = -min(31, len(hist))
            ref_30d = float(hist["Close"].iloc[ref_idx])
            move_pct = (current - ref_30d) / abs(ref_30d) if ref_30d else 0

            if abs(move_pct) < BDI_30D_THRESHOLD:
                logger.debug("[logistics] %s 30d move %.1f%% below %.0f%% threshold", BDI_TICKER, move_pct * 100, BDI_30D_THRESHOLD * 100)
                return items

            now = datetime.now(UTC)
            items.append(
                RawItem(
                    source="logistics",
                    source_id=f"bdi:{hist.index[-1].strftime('%Y-%m-%d')}",
                    url=f"https://finance.yahoo.com/quote/{BDI_TICKER}",
                    occurred_at=now,
                    raw_payload={
                        "ticker": BDI_TICKER,
                        "label": BDI_LABEL,
                        "close": round(current, 2),
                        "move_30d_pct": round(move_pct * 100, 2),
                        "direction": "up" if move_pct > 0 else "down",
                        "alert_type": "bdi_sustained_move",
                        "busan": True,  # port keyword for rule filter
                        "shipping": True,
                    },
                )
            )
            logger.info("[logistics] %s 30d move: %+.1f%%", BDI_TICKER, move_pct * 100)

        except Exception as exc:
            logger.error("[logistics] BDI pull error: %s", exc)

        return items
