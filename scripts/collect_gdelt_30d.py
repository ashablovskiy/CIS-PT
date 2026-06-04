#!/usr/bin/env python3
"""Standalone GDELT 30-day historical data collector.

Collection strategy (tried in order):
  1. DOC API  — pre-filtered artlist, up to 250 results per 7-day slice,
                no auth, no download. Rate-limited to 1 req/5s.
  2. GKG CSV  — direct 15-min GDELT v2 file downloads, filtered locally,
                sampled at 4 files/day (00, 06, 12, 18 UTC).
                No rate limit; ~5 MB per file.

Output: newline-delimited JSON to --output path (default: data/gdelt_30d.jsonl)
        or stdout (--output -)

Usage:
    uv run python scripts/collect_gdelt_30d.py
    uv run python scripts/collect_gdelt_30d.py --days 30 --output data/gdelt_30d.jsonl
    uv run python scripts/collect_gdelt_30d.py --gkg-only   # skip DOC API
    uv run python scripts/collect_gdelt_30d.py --doc-only   # skip GKG CSV
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import io
import json
import logging
import re
import sys
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

# Ensure project root importable when run as scripts/collect_gdelt_30d.py
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("gdelt_collect")

# ── Search configuration ──────────────────────────────────────────────────────

# DOC API full-text search query. GDELT requires OR'd terms wrapped in outer
# parentheses — without them the API returns a plain-text error:
#   "Queries containing OR'd terms must be surrounded by ()."
# Query kept short to avoid URL-length limits.
_DOC_QUERY = (
    '("power transformer" OR "electrical steel" OR "grain oriented steel" '
    'OR "tap changer" OR "transformer backlog" OR "transformer capacity" '
    'OR "Siemens Energy" OR "Hitachi Energy" OR "GE Vernova" '
    'OR "Hyundai Electric" OR "POSCO" OR "Nippon Steel")'
)

# GKG V2Themes to match (any one is sufficient).
_GKG_THEMES = {
    "ENERGY", "MANUFACTURING", "ECON_TAXATION", "NATURAL_DISASTER",
    "INFRASTRUCTURE_DESTRUCTION", "ENV_MINING", "WB_2411_ENERGY_AND_MINING",
    "ECON_TRADE", "CONFLICT",
}

# GKG V2Organizations / DocumentIdentifier keywords (lowercase, any one matches).
_GKG_ORG_KEYWORDS = [
    "siemens energy", "hitachi energy", "ge vernova", "hyundai electric",
    "hyosung", "mitsubishi electric", "weg", "posco", "nippon steel",
    "jfe steel", "cleveland-cliffs", "baosteel",
]

# Also match these in title/URL for topic coverage.
_GKG_TOPIC_KEYWORDS = [
    "transformer", "electrical steel", "grain oriented", "tap changer",
    "oltc", "substation", "power grid", "high voltage",
]

_ALL_KEYWORDS = _GKG_ORG_KEYWORDS + _GKG_TOPIC_KEYWORDS

# Pre-compiled word-boundary patterns for each keyword (avoids substring false
# positives like "weg" matching "owego" or "sowegalive").
_ORG_PATTERNS = [re.compile(r"\b" + re.escape(k) + r"\b") for k in _GKG_ORG_KEYWORDS]
_ALL_PATTERNS = [re.compile(r"\b" + re.escape(k) + r"\b") for k in _ALL_KEYWORDS]

# Languages kept from DOC API results (empty = GDELT couldn't detect → keep).
_KEEP_LANGUAGES = {"English", ""}

# ── API constants ─────────────────────────────────────────────────────────────

_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"
_DOC_MAX_RECORDS = 250
_DOC_DATE_FMT = "%Y%m%d%H%M%S"
_DOC_SLICE_DAYS = 7       # chunk wide windows into 7-day slices
_DOC_SLICE_DELAY = 9.0    # seconds between DOC API requests (rate limit is 1/5s)
_DOC_INITIAL_PAUSE = 7.0  # pause before first request in a batch

_GKG_BASE = "http://data.gdeltproject.org/gdeltv2"
_GKG_SAMPLE_HOURS = [0, 6, 12, 18]   # UTC hours sampled per day
_GKG_DL_CONCURRENCY = 2              # parallel GKG downloads
_GKG_DL_DELAY = 1.0                  # seconds between concurrent batches

# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_seendate(raw: str) -> datetime:
    clean = raw.replace("T", "").replace("Z", "").replace("-", "").replace(":", "")
    try:
        return datetime.strptime(clean[:14], "%Y%m%d%H%M%S").replace(tzinfo=UTC)
    except Exception:
        return datetime.now(UTC)


def _matches_gkg_row(themes_col: str, orgs_col: str, url: str) -> bool:
    """Return True if a GKG row is topically relevant."""
    # Theme match: V2Themes format is "THEME,score;THEME,score;..."
    row_themes = {t.split(",")[0].upper() for t in themes_col.split(";") if t}
    if row_themes & _GKG_THEMES:
        # Theme matched — also need a word-boundary keyword hit in org or URL
        text = (orgs_col + " " + url).lower()
        if any(p.search(text) for p in _ALL_PATTERNS):
            return True

    # Org keyword exact word match (no theme requirement)
    text = (orgs_col + " " + url).lower()
    return any(p.search(text) for p in _ORG_PATTERNS)


# ── DOC API collector ─────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, min=12, max=90))
async def _fetch_doc_slice(
    client: httpx.AsyncClient, start: datetime, end: datetime
) -> list[dict]:
    params = {
        "query": _DOC_QUERY,
        "mode": "artlist",
        "format": "json",
        "maxrecords": str(_DOC_MAX_RECORDS),
        "sort": "datedesc",
        "startdatetime": start.strftime(_DOC_DATE_FMT),
        "enddatetime": end.strftime(_DOC_DATE_FMT),
    }
    resp = await client.get(_DOC_API, params=params, timeout=45)
    body = resp.text.strip()

    if resp.status_code == 429 or (resp.status_code == 200 and body and not body.startswith("{")):
        logger.warning("[docapi] rate-limited (%d): %s", resp.status_code, body[:80])
        raise httpx.HTTPStatusError(
            f"rate-limited ({resp.status_code})", request=resp.request, response=resp
        )

    resp.raise_for_status()
    if not body:
        return []
    try:
        return resp.json().get("articles") or []
    except Exception:
        logger.warning("[docapi] non-JSON response: %s", body[:120])
        return []


async def collect_via_docapi(
    start: datetime, end: datetime
) -> tuple[list[dict], set[str]]:
    """Pull via GDELT DOC API, 7-day slices. Returns (articles, seen_urls)."""
    results: list[dict] = []
    seen_urls: set[str] = set()

    headers = {"User-Agent": "cis-research/0.1 a.shablovskiy@gmail.com"}
    async with httpx.AsyncClient(headers=headers) as client:
        await asyncio.sleep(_DOC_INITIAL_PAUSE)
        slice_start = start
        first = True
        while slice_start < end:
            slice_end = min(slice_start + timedelta(days=_DOC_SLICE_DAYS), end)
            if not first:
                await asyncio.sleep(_DOC_SLICE_DELAY)
            first = False

            try:
                articles = await _fetch_doc_slice(client, slice_start, slice_end)
            except Exception as exc:
                logger.warning("[docapi] slice %s–%s failed after retries: %s",
                               slice_start.date(), slice_end.date(), exc)
                articles = []

            kept = 0
            for art in articles:
                lang = art.get("language", "")
                if lang and lang not in _KEEP_LANGUAGES:
                    continue
                url = art.get("url") or art.get("socialimage") or ""
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                results.append({
                    "source": "gdelt_docapi",
                    "url": url,
                    "title": art.get("title", ""),
                    "domain": art.get("domain", ""),
                    "language": lang,
                    "sourcecountry": art.get("sourcecountry", ""),
                    "occurred_at": _parse_seendate(art.get("seendate", "")).isoformat(),
                    "seendate": art.get("seendate", ""),
                    "pull_method": "docapi",
                })
                kept += 1

            logger.info("[docapi] slice %s–%s → %d articles (%d new, %d total so far)",
                        slice_start.date(), slice_end.date(), len(articles), kept, len(results))
            slice_start = slice_end

    return results, seen_urls


# ── GKG CSV collector ─────────────────────────────────────────────────────────

def _gkg_ts_for(day: datetime, hour: int) -> str:
    """Return GDELT timestamp string for a given day + hour (rounds to last 15-min)."""
    minute = (datetime.now(UTC).minute // 15 * 15) if (
        day.date() == datetime.now(UTC).date() and hour == datetime.now(UTC).hour
    ) else 0
    dt = day.replace(hour=hour, minute=minute, second=0, microsecond=0)
    # Snap to 15-minute boundary
    dt = dt.replace(minute=(dt.minute // 15) * 15)
    return dt.strftime("%Y%m%d%H%M%S")


def _filter_gkg_stream(data: bytes, seen_urls: set[str]) -> list[dict]:
    """Parse a GKG CSV zip in memory, return matching rows as dicts."""
    items: list[dict] = []
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            fname = next((n for n in zf.namelist() if n.endswith(".csv")), None)
            if not fname:
                return items
            with zf.open(fname) as f:
                # GKG CSV uses tab delimiter, no header row
                reader = csv.reader(io.TextIOWrapper(f, encoding="utf-8", errors="replace"),
                                    delimiter="\t")
                for row in reader:
                    if len(row) < 19:
                        continue
                    gkg_id   = row[0]
                    date_str = row[1]
                    source   = row[3]
                    url      = row[4]
                    themes   = row[8]    # V2Themes
                    locs     = row[10]   # V2Locations
                    orgs     = row[14]   # V2Organizations
                    tone_raw = row[15]   # V2Tone
                    img      = row[18]   # SharingImage

                    if not url or url in seen_urls:
                        continue
                    if not _matches_gkg_row(themes, orgs, url):
                        continue

                    seen_urls.add(url)
                    try:
                        occurred_at = datetime.strptime(date_str[:14], "%Y%m%d%H%M%S").replace(tzinfo=UTC)
                    except Exception:
                        occurred_at = datetime.now(UTC)

                    tone_parts = tone_raw.split(",")
                    overall_tone = float(tone_parts[0]) if tone_parts and tone_parts[0] else 0.0

                    items.append({
                        "source": "gdelt_gkg",
                        "gkg_record_id": gkg_id,
                        "url": url,
                        "source_name": source,
                        "themes": themes[:500],
                        "organizations": orgs[:500],
                        "locations": locs[:500],
                        "overall_tone": round(overall_tone, 2),
                        "occurred_at": occurred_at.isoformat(),
                        "pull_method": "gkg_csv",
                        "sharing_image": img,
                    })
    except Exception as exc:
        logger.debug("[gkg] parse error: %s", exc)
    return items


async def _download_gkg_file(
    client: httpx.AsyncClient, ts: str
) -> tuple[str, bytes | None]:
    url = f"{_GKG_BASE}/{ts}.gkg.csv.zip"
    try:
        resp = await client.get(url, timeout=60)
        if resp.status_code == 404:
            return ts, None
        resp.raise_for_status()
        return ts, resp.content
    except Exception as exc:
        logger.debug("[gkg] download %s failed: %s", ts, exc)
        return ts, None


async def collect_via_gkg(
    start: datetime, end: datetime, seen_urls: set[str]
) -> list[dict]:
    """Download sampled GKG CSV files and filter locally."""
    # Build list of (ts, day) tuples to download
    timestamps: list[str] = []
    day = start.replace(hour=0, minute=0, second=0, microsecond=0)
    while day <= end:
        for hour in _GKG_SAMPLE_HOURS:
            ts_dt = day.replace(hour=hour)
            if start <= ts_dt <= end:
                # Snap to nearest 15-min (GKG files every 15 min)
                snapped = ts_dt.replace(minute=(ts_dt.minute // 15) * 15)
                timestamps.append(snapped.strftime("%Y%m%d%H%M%S"))
        day += timedelta(days=1)

    logger.info("[gkg] downloading %d files (%d days × %d samples)",
                len(timestamps), (end - start).days + 1, len(_GKG_SAMPLE_HOURS))

    results: list[dict] = []
    headers = {"User-Agent": "cis-research/0.1 a.shablovskiy@gmail.com"}

    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        # Process in small batches to limit concurrency
        for i in range(0, len(timestamps), _GKG_DL_CONCURRENCY):
            batch = timestamps[i : i + _GKG_DL_CONCURRENCY]
            tasks = [_download_gkg_file(client, ts) for ts in batch]
            batch_results = await asyncio.gather(*tasks)

            for ts, data in batch_results:
                if data is None:
                    continue
                items = _filter_gkg_stream(data, seen_urls)
                if items:
                    logger.info("[gkg] %s → %d matching rows", ts, len(items))
                    results.extend(items)

            if i + _GKG_DL_CONCURRENCY < len(timestamps):
                await asyncio.sleep(_GKG_DL_DELAY)

    logger.info("[gkg] total: %d matching articles from %d files",
                len(results), len(timestamps))
    return results


# ── Main ──────────────────────────────────────────────────────────────────────

async def main(args: argparse.Namespace) -> None:
    now = datetime.now(UTC)
    start = now - timedelta(days=args.days)
    end = now

    logger.info("Collecting GDELT %d-day history: %s → %s",
                args.days, start.date(), end.date())

    all_items: list[dict] = []
    seen_urls: set[str] = set()

    # ── Step 1: DOC API ───────────────────────────────────────────────────────
    if not args.gkg_only:
        logger.info("=== Step 1: GDELT DOC API ===")
        doc_items, seen_urls = await collect_via_docapi(start, end)
        all_items.extend(doc_items)
        logger.info("DOC API yielded %d articles", len(doc_items))
    else:
        logger.info("Skipping DOC API (--gkg-only)")

    # ── Step 2: GKG CSV fallback ──────────────────────────────────────────────
    doc_count = len(all_items)
    if not args.doc_only and (args.gkg_only or doc_count < args.gkg_fallback_threshold):
        if not args.gkg_only:
            logger.info("DOC API returned %d articles (< threshold %d) — running GKG CSV fallback",
                        doc_count, args.gkg_fallback_threshold)
        logger.info("=== Step 2: GKG CSV direct download ===")
        gkg_items = await collect_via_gkg(start, end, seen_urls)
        all_items.extend(gkg_items)
        logger.info("GKG CSV yielded %d additional articles", len(gkg_items))
    else:
        if not args.gkg_only:
            logger.info("DOC API sufficient (%d articles) — skipping GKG CSV", doc_count)

    # ── Output ────────────────────────────────────────────────────────────────
    logger.info("Total: %d unique articles", len(all_items))

    out_path = args.output
    if out_path == "-":
        fh = sys.stdout
        close_fh = False
    else:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        fh = open(out_path, "w", encoding="utf-8")
        close_fh = True

    try:
        for item in all_items:
            fh.write(json.dumps(item, default=str) + "\n")
    finally:
        if close_fh:
            fh.close()

    if out_path != "-":
        logger.info("Wrote %d records to %s", len(all_items), out_path)

    # Summary breakdown by source
    by_source: dict[str, int] = {}
    for item in all_items:
        by_source[item["source"]] = by_source.get(item["source"], 0) + 1
    for src, count in sorted(by_source.items(), key=lambda x: -x[1]):
        logger.info("  %-20s %d articles", src, count)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Collect GDELT 30-day historical data")
    ap.add_argument("--days", type=int, default=30, help="lookback window in days (default 30)")
    ap.add_argument(
        "--output", default="data/gdelt_30d.jsonl",
        help="output path (JSONL), use - for stdout",
    )
    ap.add_argument(
        "--gkg-fallback-threshold", type=int, default=50,
        help="trigger GKG CSV fallback when DOC API returns fewer than this many articles (default 50)",
    )
    ap.add_argument("--gkg-only", action="store_true", help="skip DOC API, use GKG CSV only")
    ap.add_argument("--doc-only", action="store_true", help="skip GKG CSV fallback")
    args = ap.parse_args()

    asyncio.run(main(args))
