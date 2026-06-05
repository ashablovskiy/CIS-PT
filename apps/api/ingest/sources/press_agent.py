"""Industry trade press ingestion agent — RSS feeds via feedparser.

Feed list managed in press_feeds.yml (add/remove without touching Python).
Cross-feed deduplication via title-based hash (Voyage embeddings when key available).
Cadence: every 2 hours.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

import feedparser
import httpx
import yaml
from tenacity import retry, stop_after_attempt, wait_exponential

from apps.api.ingest.base import RawItem
from apps.api.ingest.runner import BaseIngestionAgent
from apps.api.settings import settings

logger = logging.getLogger(__name__)

FEEDS_YML = Path(__file__).resolve().parent / "press_feeds.yml"

POWER_KEYWORDS = [
    # ── Transformer / T&D ────────────────────────────────────────────────────
    "transformer", "goes", "grain-oriented", "electrical steel", "silicon steel",
    "core steel", "transformer steel", "non-grain", "oltc", "tap changer",
    "power grid", "transmission", "substation", "switchgear", "bushing",
    # ── Materials ────────────────────────────────────────────────────────────
    "copper", "aluminum", "aluminium", "scrap", "iron ore", "coking coal",
    "pig iron", "billet", "slab", "hot-rolled", "cold-rolled",
    # ── OEM / supply chain actors ────────────────────────────────────────────
    "siemens energy", "hitachi energy", "ge vernova",
    "hyundai electric", "hyosung", "mitsubishi electric", "weg",
    "posco", "nippon steel", "cleveland-cliffs", "jfe steel",
    "baosteel", "wuhan iron", "novolipetsk", "nlmk",
    # ── Trade policy & regulatory ────────────────────────────────────────────
    "anti-dumping", "countervailing", "cbam", "carbon border",
    "section 232", "section 201", "safeguard", "tariff", "trade defense",
    "trade remedy", "dumping margin", "eurofer", "eurometal",
    # ── Grid demand / infrastructure ─────────────────────────────────────────
    "datacenter", "data center", "hyperscaler", "grid modernization",
    "energy transition", "green steel", "decarbonization",
    "ira", "repower", "backlog", "lead time", "supply chain",
    # ── Logistics ────────────────────────────────────────────────────────────
    "shipping", "heavy lift", "freight", "port congestion",
    "baltic dry", "container rate",
]


def _title_hash(title: str) -> str:
    """Stable 16-char hash of a normalized title for cross-feed dedup."""
    normalized = " ".join(title.lower().split())
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def _parse_published(entry: feedparser.FeedParserDict) -> datetime:
    """Best-effort datetime from feedparser entry, falls back to now()."""
    for attr in ("published_parsed", "updated_parsed"):
        ts = getattr(entry, attr, None)
        if ts:
            import time
            return datetime.fromtimestamp(time.mktime(ts), tz=UTC)
    # Try raw string
    for attr in ("published", "updated"):
        raw = getattr(entry, attr, None)
        if raw:
            try:
                return parsedate_to_datetime(raw)
            except Exception:
                pass
    return datetime.now(UTC)


class PressAgent(BaseIngestionAgent):
    agent_name = "press_agent"

    def __init__(self) -> None:
        super().__init__()
        with open(FEEDS_YML) as f:
            config = yaml.safe_load(f)
        self._feeds: list[dict] = config.get("feeds", [])
        logger.info("[press] Loaded %d feeds from %s", len(self._feeds), FEEDS_YML.name)

    def default_lookback_hours(self) -> int:
        return 2

    def keyword_rules(self) -> list[str]:
        try:
            from apps.api.ingest.keyword_registry import registry
            return registry.get("press") or POWER_KEYWORDS
        except Exception:
            return POWER_KEYWORDS

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=5))
    async def _fetch_feed(self, client: httpx.AsyncClient, feed_url: str) -> bytes:
        resp = await client.get(feed_url, follow_redirects=True)
        resp.raise_for_status()
        return resp.content

    async def pull(self, window: tuple[datetime, datetime]) -> list[RawItem]:
        cutoff = window[0]
        items: list[RawItem] = []
        seen_hashes: set[str] = set()  # cross-feed title dedup

        headers = {
            "User-Agent": settings.sec_user_agent,  # generic UA
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        }

        async with httpx.AsyncClient(headers=headers, timeout=15) as client:
            for feed_cfg in self._feeds:
                feed_name = feed_cfg["name"]
                feed_url = feed_cfg["url"]
                feed_tags = feed_cfg.get("tags", [])

                try:
                    raw_bytes = await self._fetch_feed(client, feed_url)
                    parsed = feedparser.parse(raw_bytes)

                    feed_items = 0
                    for entry in parsed.entries:
                        published = _parse_published(entry)
                        if published < cutoff:
                            continue

                        title = getattr(entry, "title", "") or ""
                        summary = getattr(entry, "summary", "") or ""
                        link = getattr(entry, "link", "") or ""

                        title_h = _title_hash(title)
                        if title_h in seen_hashes:
                            logger.debug("[press] Dedup skip: %s", title[:60])
                            continue
                        seen_hashes.add(title_h)

                        source_id = f"{feed_name}:{title_h}"
                        items.append(
                            RawItem(
                                source="press",
                                source_id=source_id,
                                url=link,
                                occurred_at=published,
                                raw_payload={
                                    "feed_name": feed_name,
                                    "feed_tags": feed_tags,
                                    "title": title,
                                    "summary": summary[:500],
                                    "link": link,
                                    "published": published.isoformat(),
                                },
                            )
                        )
                        feed_items += 1

                    logger.info("[press] %s: %d new items", feed_name, feed_items)

                except Exception as exc:
                    logger.error("[press] Error fetching %s: %s", feed_name, exc)

        return items
