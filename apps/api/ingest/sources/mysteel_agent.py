"""Mysteel.net ingestion agent — Chinese steel/commodities intelligence.

Mysteel has no RSS feed. This agent:
  1. Fetches configurable listing pages (latest news, AD/CVD, analysis)
  2. Extracts article URLs from the server-side rendered HTML
  3. Fetches each article page (with rate-limiting) and extracts content
  4. Deduplicates by URL so re-runs don't re-ingest the same articles

Why Mysteel matters for transformer procurement:
  - Primary source for grain-oriented electrical steel (GOES) prices/supply
  - Chinese steel mill output, inventory, and export duty changes
  - Anti-dumping / countervailing duty news (AD/CVD tab) affecting POSCO, NLMK, etc.
  - Energy-transition steel demand analysis
  - Copper and aluminium supply (transformer windings)
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from datetime import UTC, datetime, timedelta

import httpx
from bs4 import BeautifulSoup

from apps.api.ingest.base import RawItem
from apps.api.ingest.runner import BaseIngestionAgent

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

_BASE = "https://www.mysteel.net"

# Listing pages to scrape (ordered by priority).
# Each yields article URLs which are then de-duped before fetching.
_LISTING_PAGES = [
    f"{_BASE}/market-insights/news/latest/",          # all latest
    f"{_BASE}/market-insights/news/ad-and-cvd/",      # AD/CVD — very relevant for GOES/steel imports
    f"{_BASE}/market-insights/analysis/energy-transition/",  # energy transition analysis
]

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

# Max articles to fetch per agent run (listing pages show ~20-40 each)
_MAX_ARTICLES = 25
# Delay between article fetches (be respectful)
_FETCH_DELAY = 0.8   # seconds


# ── Helpers ───────────────────────────────────────────────────────────────────

_ARTICLE_URL_RE = re.compile(r"/(?:news|market-insights/[^/]+/[^/]+)/(\d+)-([a-z0-9-]+)")
_DATE_RE        = re.compile(r"(\d{4}-\d{2}-\d{2})")
_SLUG_DATE_RE   = re.compile(r"(\d{8})$")   # slugs ending in YYYYMMDD like …-20260605


def _article_id_from_url(url: str) -> str | None:
    m = _ARTICLE_URL_RE.search(url)
    return m.group(1) if m else None


def _date_from_slug(slug: str) -> datetime | None:
    """Articles like flash-…-20260605 embed their date in the slug."""
    m = _SLUG_DATE_RE.search(slug)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y%m%d").replace(tzinfo=UTC)
        except ValueError:
            pass
    return None


async def _fetch(client: httpx.AsyncClient, url: str) -> str | None:
    try:
        r = await client.get(url, timeout=20)
        if r.status_code == 200:
            return r.text
        logger.debug("[mysteel] %s → HTTP %d", url, r.status_code)
    except Exception as exc:
        logger.debug("[mysteel] fetch %s failed: %s", url, exc)
    return None


def _extract_listing_urls(html: str) -> list[str]:
    """Return de-duped article URLs from a Mysteel listing page."""
    urls: list[str] = []
    seen: set[str] = set()
    for m in _ARTICLE_URL_RE.finditer(html):
        article_id = m.group(1)
        full_url = _BASE + m.group(0)
        if article_id not in seen:
            seen.add(article_id)
            urls.append(full_url)
    return urls


def _extract_article(html: str, url: str) -> tuple[str, str, datetime | None]:
    """Return (title, body_text, published_at) from an article page."""
    soup = BeautifulSoup(html, "html.parser")

    # Title
    h1 = soup.find("h1")
    title = h1.get_text(strip=True) if h1 else ""
    if not title:
        title = soup.title.string.strip() if soup.title and soup.title.string else url

    # Remove nav, script, style clutter
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    # Article body — Mysteel uses .article-content or .news-content
    body_el = (
        soup.find(class_=re.compile(r"article[-_]content|news[-_]content|article[-_]body"))
        or soup.find("article")
        or soup.find("main")
    )
    body = re.sub(r"\s+", " ", (body_el or soup).get_text(separator=" ")).strip()

    # Date — look for ISO date pattern in the HTML
    published_at: datetime | None = None
    # 1. Try slug
    slug_m = _ARTICLE_URL_RE.search(url)
    if slug_m:
        published_at = _date_from_slug(slug_m.group(2))
    # 2. Try date in HTML
    if published_at is None:
        for m in _DATE_RE.finditer(html):
            try:
                candidate = datetime.strptime(m.group(1), "%Y-%m-%d").replace(tzinfo=UTC)
                # Sanity check: must be within last 2 years
                if datetime.now(UTC) - timedelta(days=730) < candidate <= datetime.now(UTC):
                    published_at = candidate
                    break
            except ValueError:
                pass

    return title, body[:6000], published_at


# ── Agent ─────────────────────────────────────────────────────────────────────

class MysteelAgent(BaseIngestionAgent):
    agent_name = "mysteel"

    def default_lookback_hours(self) -> int:
        return 24   # check daily; Mysteel publishes throughout the day

    def keyword_rules(self) -> list[str]:
        return [
            # Materials directly used in transformers
            "electrical steel", "grain oriented", "goes", "silicon steel",
            "non-grain", "core steel", "transformer steel",
            "copper", "alumin",
            # Key GOES / steel mills
            "posco", "nippon steel", "jfe steel", "baosteel", "wuhan iron",
            "cleveland-cliffs", "novolipetsk", "nlmk",
            # OEM / industry actors
            "transformer", "siemens energy", "hitachi energy", "ge vernova",
            "hyundai electric", "hyosung", "mitsubishi electric", "weg",
            # Trade policy (directly affects import prices)
            "anti-dumping", "countervailing", "ad/cvd", "tariff", "duty",
            "safeguard", "section 232", "section 201",
            # Supply chain
            "iron ore", "scrap", "pig iron", "billet", "slab",
            "coking coal", "met coal",
            # Energy / grid demand
            "power grid", "substation", "transmission", "grid",
            "data center", "datacenter", "hyperscaler", "energy transition",
        ]

    async def pull(
        self, window: tuple[datetime, datetime]
    ) -> list[RawItem]:
        start, end = window
        items: list[RawItem] = []
        seen_ids: set[str] = set()

        async with httpx.AsyncClient(headers=_HEADERS, follow_redirects=True) as client:

            # ── Step 1: collect article URLs from listing pages ────────────
            candidate_urls: list[str] = []
            for listing_url in _LISTING_PAGES:
                html = await _fetch(client, listing_url)
                if html:
                    urls = _extract_listing_urls(html)
                    for u in urls:
                        aid = _article_id_from_url(u)
                        if aid and aid not in seen_ids:
                            seen_ids.add(aid)
                            candidate_urls.append(u)
                    logger.info("[mysteel] %s → %d article URLs", listing_url, len(urls))
                await asyncio.sleep(_FETCH_DELAY)

            # Limit total articles to avoid hammering the server
            candidate_urls = candidate_urls[:_MAX_ARTICLES]
            logger.info("[mysteel] fetching %d article pages…", len(candidate_urls))

            # ── Step 2: fetch and extract each article ─────────────────────
            for url in candidate_urls:
                html = await _fetch(client, url)
                if not html:
                    continue

                title, body, published_at = _extract_article(html, url)

                # Skip if too little content
                if len(body) < 80:
                    logger.debug("[mysteel] skipping %s — too little content", url)
                    await asyncio.sleep(_FETCH_DELAY)
                    continue

                # Window filter — skip articles outside the lookback
                if published_at is not None:
                    if published_at < start or published_at > end:
                        logger.debug("[mysteel] skipping %s — outside window (%s)", url, published_at.date())
                        await asyncio.sleep(_FETCH_DELAY)
                        continue
                else:
                    # No date found — include if from listing (assume recent)
                    published_at = datetime.now(UTC)

                article_id = _article_id_from_url(url) or hashlib.sha256(url.encode()).hexdigest()[:12]
                items.append(RawItem(
                    source="mysteel",
                    source_id=f"mysteel:{article_id}",
                    url=url,
                    occurred_at=published_at,
                    raw_payload={
                        "title":   title,
                        "summary": body[:500],   # keep payload lean — body alone was hitting token limits
                        "source_name": "Mysteel",
                        "domain":  "mysteel.net",
                    },
                    content_hash=hashlib.sha256(body[:1000].encode()).hexdigest()[:32],
                ))

                logger.info("[mysteel] ✓ %s | %s | %s", published_at.date() if published_at else "?", url.split("/")[-1][:60], title[:60])
                await asyncio.sleep(_FETCH_DELAY)

        logger.info("[mysteel] pulled %d articles in window", len(items))
        return items
