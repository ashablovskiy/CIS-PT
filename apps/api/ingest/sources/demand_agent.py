"""Demand ingestion agent — datacenter / AI / grid demand signals.

Two pull mechanisms per demand source:
  1. native RSS  — hyperscaler press rooms that publish a usable feed
                   (Microsoft, Google, Amazon, Meta)
  2. Google News RSS query — for orgs with no datacenter-buildout feed
                   (OpenAI, Anthropic, Oracle/Stargate, CoreWeave) and the
                   major datacenter builders / colos (Vantage, QTS, Switch,
                   Crusoe, Digital Realty, Equinix). Google News gives us
                   coverage of their capacity / capex / power-deal news
                   without scraping each site.

Goal: surface 'new datacenter announcement', 'new grid project funded',
'gigawatt power deal', 'interconnection queue update' as discrete signals
tied to DemandSource nodes.

Cadence: every 4 hours.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote_plus

import feedparser
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from apps.api.ingest.base import RawItem
from apps.api.ingest.runner import BaseIngestionAgent
from apps.api.settings import settings

logger = logging.getLogger(__name__)


def _gnews(query: str) -> str:
    """Build a Google News RSS search URL for a scoped query."""
    return (
        "https://news.google.com/rss/search?q="
        + quote_plus(query)
        + "&hl=en-US&gl=US&ceid=US:en"
    )


# ── Demand sources ──────────────────────────────────────────────────────────
# Each source has a `demand_source` (maps to a DemandSource graph node) and
# EITHER `feeds` (native RSS) OR `news_query` (Google News query string).

DEMAND_SOURCES: list[dict[str, Any]] = [
    # ---- Hyperscalers: native press-room RSS ----
    {
        "company": "Microsoft", "demand_source": "Microsoft Datacenter Buildout",
        "feeds": ["https://news.microsoft.com/feed/", "https://blogs.microsoft.com/feed/"],
    },
    {
        "company": "Google", "demand_source": "Google Datacenter Buildout",
        "feeds": ["https://blog.google/rss/", "https://cloud.google.com/blog/rss/"],
    },
    {
        "company": "Amazon", "demand_source": "Amazon Datacenter Buildout",
        "feeds": ["https://aws.amazon.com/blogs/aws/feed/"],
    },
    {
        "company": "Meta", "demand_source": "Meta Datacenter Buildout",
        "feeds": ["https://engineering.fb.com/feed/", "https://about.fb.com/news/feed/"],
    },
    # ---- AI labs: Google News (no datacenter-buildout RSS) ----
    {
        "company": "OpenAI", "demand_source": "OpenAI / Stargate Buildout",
        "news_query": 'OpenAI (datacenter OR "data center" OR Stargate OR gigawatt OR "compute")',
    },
    {
        "company": "Anthropic", "demand_source": "Anthropic Compute Buildout",
        "news_query": 'Anthropic (datacenter OR "data center" OR compute OR "power")',
    },
    # ---- Cloud / AI infra with heavy buildout ----
    {
        "company": "Oracle", "demand_source": "Oracle / OCI Buildout",
        "news_query": 'Oracle (datacenter OR "data center" OR Stargate OR gigawatt OR OCI)',
    },
    {
        "company": "CoreWeave", "demand_source": "CoreWeave Buildout",
        "news_query": 'CoreWeave (datacenter OR "data center" OR capacity OR power)',
    },
    # ---- Major datacenter builders / colos ----
    {
        "company": "Vantage", "demand_source": "Vantage Data Centers Buildout",
        "news_query": '"Vantage Data Centers" (campus OR megawatt OR gigawatt OR expansion)',
    },
    {
        "company": "QTS", "demand_source": "QTS / Blackstone Buildout",
        "news_query": '"QTS Data Centers" OR "QTS Realty" (campus OR megawatt OR expansion)',
    },
    {
        "company": "Switch", "demand_source": "Switch Buildout",
        "news_query": '"Switch" datacenter (campus OR megawatt OR expansion)',
    },
    {
        "company": "Crusoe", "demand_source": "Crusoe Energy Buildout",
        "news_query": '"Crusoe" (datacenter OR "data center" OR Stargate OR megawatt)',
    },
    {
        "company": "Digital Realty", "demand_source": "Digital Realty Buildout",
        "news_query": '"Digital Realty" (megawatt OR gigawatt OR campus OR power)',
    },
    {
        "company": "Equinix", "demand_source": "Equinix Buildout",
        "news_query": '"Equinix" (megawatt OR campus OR expansion OR power)',
    },
]

# Datacenter / grid demand keywords for rule filter (fallback / boost)
DEMAND_KEYWORDS = [
    "datacenter", "data center", "data centre", "hyperscale",
    "ai infrastructure", "gpu cluster", "compute campus", "stargate",
    "power purchase", "grid connection", "interconnection",
    "substation", "transformer", "electricity", "megawatt", "gigawatt",
    "capital expenditure", "capex", "infrastructure investment",
    "grid modernization", "ira", "repower", "renewable energy",
    "microsoft", "google", "amazon", "meta", "aws", "openai", "anthropic",
    "oracle", "coreweave", "vantage", "equinix", "digital realty", "crusoe",
]

# Items must hit at least one of these to be kept (native-feed filter).
DEMAND_THRESHOLD_KEYWORDS = [
    "datacenter", "data center", "data centre", "hyperscale", "stargate",
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


def _classify(text_blob: str) -> str:
    if any(k in text_blob for k in ["grid", "substation", "interconnection", "megawatt", "gigawatt", "power purchase"]):
        return "grid_power_demand"
    if any(k in text_blob for k in ["capex", "capital expenditure", "investment"]):
        return "capex_disclosure"
    return "datacenter_announcement"


class DemandAgent(BaseIngestionAgent):
    agent_name = "demand_agent"

    def default_lookback_hours(self) -> int:
        return 4

    def keyword_rules(self) -> list[str]:
        try:
            from apps.api.ingest.keyword_registry import registry
            return registry.get("demand") or DEMAND_KEYWORDS
        except Exception:
            return DEMAND_KEYWORDS

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _fetch(self, client: httpx.AsyncClient, url: str) -> bytes:
        resp = await client.get(url, follow_redirects=True, timeout=20)
        resp.raise_for_status()
        return resp.content

    async def _pull_feed(
        self, client: httpx.AsyncClient, url: str, company: str,
        demand_source: str, cutoff: datetime, is_gnews: bool,
    ) -> list[RawItem]:
        items: list[RawItem] = []
        try:
            raw = await self._fetch(client, url)
            parsed = feedparser.parse(raw)
        except Exception as exc:
            logger.warning("[demand] %s fetch failed (%s): %s", company, url[:60], exc)
            return items

        for entry in parsed.entries:
            published = _parse_rss_date(entry)
            if published < cutoff:
                continue
            title = getattr(entry, "title", "") or ""
            summary = getattr(entry, "summary", "") or ""
            link = getattr(entry, "link", "") or ""
            text_blob = (title + " " + summary).lower()

            # Google News results are already query-scoped; native feeds are broad,
            # so apply the threshold-keyword gate only to native feeds.
            if not is_gnews and not any(kw in text_blob for kw in DEMAND_THRESHOLD_KEYWORDS):
                continue

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
                        "feed_kind": "google_news" if is_gnews else "native_rss",
                        "title": title,
                        "summary": summary[:500],
                        "link": link,
                        "published": published.isoformat(),
                        "signal_type": _classify(text_blob),
                    },
                )
            )
        return items

    async def pull(self, window: tuple[datetime, datetime]) -> list[RawItem]:
        cutoff = window[0]
        items: list[RawItem] = []
        seen_titles: set[str] = set()  # cross-source dedup within a run

        headers = {
            "User-Agent": settings.sec_user_agent,
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        }

        async with httpx.AsyncClient(headers=headers, timeout=20) as client:
            for src in DEMAND_SOURCES:
                company = src["company"]
                demand_source = src["demand_source"]

                urls: list[tuple[str, bool]] = []
                for f in src.get("feeds", []):
                    urls.append((f, False))
                if src.get("news_query"):
                    urls.append((_gnews(src["news_query"]), True))

                src_count = 0
                for url, is_gnews in urls:
                    pulled = await self._pull_feed(
                        client, url, company, demand_source, cutoff, is_gnews
                    )
                    for it in pulled:
                        t = it.raw_payload.get("title", "").lower().strip()
                        if t and t in seen_titles:
                            continue
                        seen_titles.add(t)
                        items.append(it)
                        src_count += 1

                if src_count:
                    logger.info("[demand] %s: %d items", company, src_count)

        logger.info("[demand] Total demand signals: %d", len(items))
        return items
