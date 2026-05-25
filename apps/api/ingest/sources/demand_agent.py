"""Demand ingestion agent — hyperscaler datacenter announcements + grid demand.

Hybrid sources:
  1. Hyperscaler press-room RSS (Microsoft, Google, Amazon, Meta)
  2. SEC 10-Q capex items re-tagged as 'demand' (from sec_agent's pulled CIKs)
  3. GDELT INVEST/datacenter signals (leverages already-pulled GDELT items)

Goal: surface 'new datacenter announcement', 'new grid project funded',
'interconnection queue update' as discrete signals tied to DemandSource nodes.

Cadence: every 4 hours.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from apps.api.ingest.base import RawItem
from apps.api.ingest.runner import BaseIngestionAgent
from apps.api.settings import settings

logger = logging.getLogger(__name__)

# Hyperscaler press-room RSS feeds
HYPERSCALER_FEEDS: list[dict[str, Any]] = [
    {
        "company": "Microsoft",
        "demand_source": "Microsoft Datacenter Buildout",
        "feeds": [
            "https://news.microsoft.com/feed/",
            "https://blogs.microsoft.com/feed/",
        ],
    },
    {
        "company": "Google",
        "demand_source": "Google Datacenter Buildout",
        "feeds": [
            "https://blog.google/rss/",
            "https://cloud.google.com/blog/rss/",
        ],
    },
    {
        "company": "Amazon",
        "demand_source": "Amazon Datacenter Buildout",
        "feeds": [
            "https://aws.amazon.com/blogs/aws/feed/",
            "https://aws.amazon.com/blogs/infrastructure-and-automation/feed/",
        ],
    },
    {
        "company": "Meta",
        "demand_source": "Meta Datacenter Buildout",
        "feeds": [
            "https://engineering.fb.com/feed/",
            "https://about.fb.com/news/feed/",
        ],
    },
]

# Datacenter / grid demand keywords for rule filter
DEMAND_KEYWORDS = [
    "datacenter", "data center", "data centre", "hyperscale",
    "ai infrastructure", "gpu cluster", "compute campus",
    "power purchase", "grid connection", "interconnection",
    "substation", "transformer", "electricity", "megawatt", "gigawatt",
    "capital expenditure", "capex", "infrastructure investment",
    "grid modernization", "ira", "repower", "renewable energy",
    "microsoft", "google", "amazon", "meta", "aws",
]

DEMAND_THRESHOLD_KEYWORDS = [
    "datacenter", "data center", "data centre", "hyperscale",
    "megawatt", "gigawatt", "power purchase", "grid connection",
    "interconnection", "substation", "transformer",
    "capital expenditure", "capex",
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


class DemandAgent(BaseIngestionAgent):
    agent_name = "demand_agent"

    def default_lookback_hours(self) -> int:
        return 4

    def keyword_rules(self) -> list[str]:
        return DEMAND_KEYWORDS

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _fetch_feed(self, client: httpx.AsyncClient, url: str) -> bytes:
        resp = await client.get(url, follow_redirects=True, timeout=15)
        resp.raise_for_status()
        return resp.content

    async def pull(self, window: tuple[datetime, datetime]) -> list[RawItem]:
        cutoff = window[0]
        items: list[RawItem] = []

        headers = {
            "User-Agent": settings.sec_user_agent,
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        }

        async with httpx.AsyncClient(headers=headers, timeout=20) as client:
            for hyperscaler in HYPERSCALER_FEEDS:
                company = hyperscaler["company"]
                demand_source = hyperscaler["demand_source"]

                for feed_url in hyperscaler["feeds"]:
                    try:
                        raw = await self._fetch_feed(client, feed_url)
                        parsed = feedparser.parse(raw)
                        feed_count = 0

                        for entry in parsed.entries:
                            published = _parse_rss_date(entry)
                            if published < cutoff:
                                continue

                            title = getattr(entry, "title", "") or ""
                            summary = getattr(entry, "summary", "") or ""
                            link = getattr(entry, "link", "") or ""
                            text_blob = (title + " " + summary).lower()

                            # Only keep items that match demand threshold keywords
                            if not any(kw in text_blob for kw in DEMAND_THRESHOLD_KEYWORDS):
                                continue

                            # Classify signal type from keywords
                            signal_type = "datacenter_announcement"
                            if any(k in text_blob for k in ["grid", "substation", "interconnection", "megawatt", "gigawatt"]):
                                signal_type = "grid_power_demand"
                            elif any(k in text_blob for k in ["capex", "capital expenditure", "investment"]):
                                signal_type = "capex_disclosure"

                            source_id = f"demand:{company}:{hash(title) & 0xFFFFFFFF:08x}"
                            items.append(
                                RawItem(
                                    source="demand",
                                    source_id=source_id,
                                    url=link,
                                    occurred_at=published,
                                    raw_payload={
                                        "company": company,
                                        "demand_source_node": demand_source,
                                        "feed_url": feed_url,
                                        "title": title,
                                        "summary": summary[:500],
                                        "link": link,
                                        "published": published.isoformat(),
                                        "signal_type": signal_type,
                                    },
                                )
                            )
                            feed_count += 1

                        if feed_count:
                            logger.info("[demand] %s (%s): %d items", company, feed_url.split("/")[2], feed_count)

                    except Exception as exc:
                        logger.warning("[demand] Error fetching %s feed %s: %s", company, feed_url, exc)

        logger.info("[demand] Total demand signals: %d", len(items))
        return items
