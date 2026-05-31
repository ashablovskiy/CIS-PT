"""IR / corporate-news ingestion agent — non-US OEMs + key suppliers.

Covers the companies the sec_agent can't (no EDGAR obligation) and that mostly
lack clean native RSS: Siemens Energy, Hitachi Energy, Hyundai Electric, the
GOES mills (POSCO, Nippon Steel, JFE, TKES, Baowu), and the critical component /
material suppliers (Reinhausen, Trench, Weidmann, DuPont Nomex, Nynas).

Mechanism: scoped Google News RSS queries (one per company), with optional
native RSS. Google News aggregates capacity announcements, earnings/guidance,
shareholder updates, supply disruptions and capex into a parseable feed without
per-site scraping.

Feed list managed in ir_feeds.yml — add/remove companies without touching code.
Cadence: every 6 hours.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote_plus

import feedparser
import httpx
import yaml
from tenacity import retry, stop_after_attempt, wait_exponential

from apps.api.ingest.base import RawItem
from apps.api.ingest.runner import BaseIngestionAgent
from apps.api.settings import settings

logger = logging.getLogger(__name__)

FEEDS_YML = Path(__file__).resolve().parent / "ir_feeds.yml"

# Rule-filter fallback keywords (used only if the Neo4j keyword registry fails).
IR_KEYWORDS = [
    "transformer", "goes", "grain-oriented", "electrical steel", "tap changer",
    "oltc", "bushing", "pressboard", "nomex", "transformer oil", "naphthenic",
    "capacity", "backlog", "lead time", "earnings", "guidance", "investment",
    "siemens energy", "hitachi energy", "hyundai electric", "hyosung",
    "mitsubishi electric", "toshiba", "tbea", "weg", "sgb-smit", "cg power",
    "posco", "nippon steel", "jfe", "thyssenkrupp", "baowu", "baosteel",
    "reinhausen", "trench", "weidmann", "dupont", "nynas",
]


def _gnews(query: str) -> str:
    """Build a Google News RSS search URL for a scoped query."""
    return (
        "https://news.google.com/rss/search?q="
        + quote_plus(query)
        + "&hl=en-US&gl=US&ceid=US:en"
    )


def _title_hash(title: str) -> str:
    return hashlib.sha256(" ".join(title.lower().split()).encode()).hexdigest()[:16]


def _parse_published(entry) -> datetime:
    for attr in ("published_parsed", "updated_parsed"):
        ts = getattr(entry, attr, None)
        if ts:
            import time
            return datetime.fromtimestamp(time.mktime(ts), tz=UTC)
    for attr in ("published", "updated"):
        raw = getattr(entry, attr, None)
        if raw:
            try:
                return parsedate_to_datetime(raw)
            except Exception:
                pass
    return datetime.now(UTC)


class IrAgent(BaseIngestionAgent):
    agent_name = "ir_agent"

    def __init__(self) -> None:
        super().__init__()
        with open(FEEDS_YML) as f:
            config = yaml.safe_load(f)
        self._entries: list[dict] = config.get("entries", [])
        logger.info("[ir] Loaded %d IR entries from %s", len(self._entries), FEEDS_YML.name)

    def default_lookback_hours(self) -> int:
        return 8

    def keyword_rules(self) -> list[str]:
        try:
            from apps.api.ingest.keyword_registry import registry
            return registry.get("ir") or IR_KEYWORDS
        except Exception:
            return IR_KEYWORDS

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=5))
    async def _fetch(self, client: httpx.AsyncClient, url: str) -> bytes:
        resp = await client.get(url, follow_redirects=True)
        resp.raise_for_status()
        return resp.content

    async def _pull_one(
        self, client: httpx.AsyncClient, url: str, company: str,
        entity_type: str, feed_kind: str, cutoff: datetime, seen: set[str],
    ) -> list[RawItem]:
        items: list[RawItem] = []
        try:
            raw = await self._fetch(client, url)
            parsed = feedparser.parse(raw)
        except Exception as exc:
            logger.warning("[ir] %s fetch failed (%s): %s", company, url[:60], exc)
            return items

        for entry in parsed.entries:
            published = _parse_published(entry)
            if published < cutoff:
                continue
            title = getattr(entry, "title", "") or ""
            if not title:
                continue
            th = _title_hash(title)
            if th in seen:
                continue
            seen.add(th)

            summary = getattr(entry, "summary", "") or ""
            link = getattr(entry, "link", "") or ""
            items.append(
                RawItem(
                    source="ir",
                    source_id=f"ir:{company}:{th}",
                    url=link,
                    occurred_at=published,
                    raw_payload={
                        "company": company,
                        "entity_type": entity_type,
                        "feed_kind": feed_kind,
                        "title": title,
                        "summary": summary[:500],
                        "link": link,
                        "published": published.isoformat(),
                    },
                )
            )
        return items

    async def pull(self, window: tuple[datetime, datetime]) -> list[RawItem]:
        cutoff = window[0]
        items: list[RawItem] = []
        seen: set[str] = set()  # cross-entry title dedup within a run

        headers = {
            "User-Agent": settings.sec_user_agent,
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        }

        async with httpx.AsyncClient(headers=headers, timeout=15) as client:
            for e in self._entries:
                company = e["company"]
                entity_type = e.get("entity_type", "oem")
                count = 0

                for rss in e.get("native_rss", []) or []:
                    pulled = await self._pull_one(
                        client, rss, company, entity_type, "native_rss", cutoff, seen
                    )
                    items.extend(pulled)
                    count += len(pulled)

                if e.get("news_query"):
                    pulled = await self._pull_one(
                        client, _gnews(e["news_query"]), company, entity_type,
                        "google_news", cutoff, seen,
                    )
                    items.extend(pulled)
                    count += len(pulled)

                if count:
                    logger.info("[ir] %s (%s): %d items", company, entity_type, count)

        logger.info("[ir] Total IR signals: %d", len(items))
        return items
