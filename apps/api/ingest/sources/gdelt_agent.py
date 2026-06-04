"""GDELT ingestion agent — three-path based on window size.

BigQuery path (windows ≤ 6 h):
  Queries gdelt-bq.gdeltv2.gkg_partitioned. Cost per hourly run ≈ 0.47 GB,
  well within the 5 GB maximum_bytes_billed guard. This is the live-cron path.

DOC API path (windows > 6 h, e.g. backfill):
  Queries the free GDELT 2.0 DOC API (api.gdeltproject.org/api/v2/doc/doc).
  No auth, no bytes billed. Up to 250 articles per request.
  Wide windows are chunked into 7-day slices (5 requests for a 30-day window).
  English-only post-filter on the `language` field.

GKG CSV fallback (per-slice, triggered when DOC API slice yields 0 articles):
  Downloads raw GDELT v2 GKG 15-minute CSV files from data.gdeltproject.org.
  No rate limit (plain HTTP). Each file ≈ 5 MB compressed; sampled at 4 files/day
  (00, 06, 12, 18 UTC) → 28 files per 7-day slice ≈ 140 MB/slice download.
  Filtered locally by V2Themes + V2Organizations keywords.

Why three paths:
  A 30-day BQ query scans ≈ 16.9 GB — 3× our 5 GB limit.
  The DOC API is rate-limited (1 req/5s); exhausted retries leave empty slices.
  The GKG CSV path provides a reliable floor — no auth, no rate limits, complete
  GDELT coverage — at the cost of more bandwidth.

Cadence: every 1 hour (cron uses BQ; backtest_30d uses DOC API automatically,
         with GKG CSV kicking in for any slice the DOC API can't fill).
"""

from __future__ import annotations

import asyncio
import csv
import io
import logging
import os
import re
import zipfile
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote_plus

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from apps.api.ingest.base import RawItem
from apps.api.ingest.runner import BaseIngestionAgent
from apps.api.settings import settings

logger = logging.getLogger(__name__)

# ── BigQuery constants ────────────────────────────────────────────────────────

GDELT_TABLE = "gdelt-bq.gdeltv2.gkg_partitioned"

# Windows ≤ this use BigQuery; wider windows use the DOC API.
_BQ_MAX_HOURS = 6

GDELT_THEMES = [
    "ENERGY", "MANUFACTURING", "ECON_TAXATION", "NATURAL_DISASTER",
    "INFRASTRUCTURE_DESTRUCTION", "ENV_MINING", "WB_2411_ENERGY_AND_MINING",
    "ECON_TRADE", "CONFLICT",
]

SUPPLIER_KEYWORDS = [
    "Siemens Energy", "Hitachi Energy", "GE Vernova", "Hyundai Electric",
    "Hyosung", "Mitsubishi Electric", "WEG", "POSCO", "Nippon Steel",
    "JFE Steel", "Cleveland-Cliffs", "Baosteel", "transformer", "electrical steel",
]

LOCATION_KEYWORDS = [
    "South Korea", "Japan", "Germany", "Poland",
    "Busan", "Antwerp", "Rotterdam", "Bremerhaven",
]

# ── DOC API constants ─────────────────────────────────────────────────────────

GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"
_DOC_SLICE_DAYS = 7       # chunk size for wide windows
_DOC_MAX_RECORDS = 250    # DOC API hard cap
_DOC_DATE_FMT = "%Y%m%d%H%M%S"

# GDELT DOC API query — GDELT requires OR'd terms to be wrapped in outer
# parentheses; without them the API returns a plain-text error:
#   "Queries containing OR'd terms must be surrounded by ()."
# Query kept short to avoid URL-length limits (GDELT silently returns empty
# results on very long queries). English filtering done post-fetch on the
# `language` field. keyword_rules() catches additional terms at rule-filter.
_DOC_QUERY = (
    '("power transformer" OR "electrical steel" OR "grain oriented steel" '
    'OR "tap changer" OR "transformer backlog" OR "transformer capacity" '
    'OR "Siemens Energy" OR "Hitachi Energy" OR "GE Vernova" '
    'OR "Hyundai Electric" OR "POSCO" OR "Nippon Steel")'
)

# Languages to keep from DOC API responses (post-filter).
# Empty string = GDELT couldn't detect language → keep it (likely English domain).
_KEEP_LANGUAGES = {"English", ""}

# ── GKG CSV fallback constants ────────────────────────────────────────────────

_GKG_BASE_URL = "http://data.gdeltproject.org/gdeltv2"
# UTC hours sampled per day when falling back to raw GKG files.
_GKG_SAMPLE_HOURS = (0, 6, 12, 18)
# Max parallel GKG file downloads (each ~5 MB).
_GKG_DL_CONCURRENCY = 2

# Topic keywords searched in V2Organizations + DocumentIdentifier (lowercase).
_GKG_TOPIC_KEYWORDS = [
    "transformer", "electrical steel", "grain oriented", "tap changer",
    "oltc", "substation", "power grid", "high voltage",
]

# Pre-compiled word-boundary patterns — avoids substring false positives
# (e.g. "weg" matching "owego" or "sowegalive").
_GKG_ORG_KW_LOWER = [k.lower() for k in SUPPLIER_KEYWORDS]
_GKG_ALL_KW_LOWER = _GKG_ORG_KW_LOWER + _GKG_TOPIC_KEYWORDS
_GKG_ORG_PATTERNS = [re.compile(r"\b" + re.escape(k) + r"\b") for k in _GKG_ORG_KW_LOWER]
_GKG_ALL_PATTERNS = [re.compile(r"\b" + re.escape(k) + r"\b") for k in _GKG_ALL_KW_LOWER]


# ── BQ helpers ────────────────────────────────────────────────────────────────

def _bq_theme_filter() -> str:
    return "REGEXP_CONTAINS(V2Themes, r'(?i)(" + "|".join(GDELT_THEMES) + ")')"

def _bq_org_filter() -> str:
    parts = " OR ".join(f"LOWER(V2Organizations) LIKE '%{kw.lower()}%'" for kw in SUPPLIER_KEYWORDS)
    return f"({parts})"

def _bq_loc_filter() -> str:
    parts = " OR ".join(f"LOWER(V2Locations) LIKE '%{kw.lower()}%'" for kw in LOCATION_KEYWORDS)
    return f"({parts})"


class GdeltAgent(BaseIngestionAgent):
    agent_name = "gdelt_agent"

    def __init__(self) -> None:
        super().__init__()
        self._bq_client: Any = None  # lazy-initialised
        self._widen_filter = False

    def _get_bq(self) -> Any:
        """Lazy-init BigQuery client — avoids import cost when DOC API path is taken."""
        if self._bq_client is None:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.google_application_credentials
            from google.cloud import bigquery  # type: ignore[import]
            self._bq_client = bigquery.Client(project=settings.gcp_project_id)
        return self._bq_client

    def default_lookback_hours(self) -> int:
        return 1

    def keyword_rules(self) -> list[str]:
        _fallback = [
            "transformer", "electrical steel", "goes", "siemens energy",
            "hitachi energy", "ge vernova", "hyundai", "posco", "nippon steel",
            "tap changer", "oltc", "bushing", "grid", "power", "substation",
        ]
        try:
            from apps.api.ingest.keyword_registry import registry
            return registry.get("gdelt") or _fallback
        except Exception:
            return _fallback

    # ── BigQuery path ─────────────────────────────────────────────────────────

    def _build_bq_query(self, start: datetime, end: datetime) -> str:
        start_ts = start.strftime("%Y-%m-%d %H:%M:%S")
        end_ts = end.strftime("%Y-%m-%d %H:%M:%S")
        start_int = int(start.strftime("%Y%m%d%H%M%S"))
        end_int = int(end.strftime("%Y%m%d%H%M%S"))
        where = (
            f"({_bq_theme_filter()} OR {_bq_org_filter()} OR {_bq_loc_filter()})"
            if not self._widen_filter
            else f"({_bq_theme_filter()} OR {_bq_org_filter()})"
        )
        return f"""
        SELECT GKGRECORDID, DATE, SourceCommonName, DocumentIdentifier,
               V2Themes, V2Locations, V2Organizations, V2Tone, SharingImage
        FROM `{GDELT_TABLE}`
        WHERE _PARTITIONTIME >= TIMESTAMP('{start_ts}')
          AND _PARTITIONTIME <  TIMESTAMP('{end_ts}')
          AND DATE >= {start_int}
          AND DATE <  {end_int}
          AND {where}
          AND DocumentIdentifier IS NOT NULL
          AND LENGTH(DocumentIdentifier) > 10
        LIMIT 200
        """

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=2, min=5, max=30))
    async def _run_bq_query(self, query: str) -> list[dict]:
        from google.cloud import bigquery  # type: ignore[import]
        loop = asyncio.get_event_loop()

        def _sync():
            cfg = bigquery.QueryJobConfig(
                maximum_bytes_billed=settings.bigquery_max_bytes_billed,
                use_query_cache=True,
            )
            job = self._get_bq().query(query, job_config=cfg)
            return [dict(row) for row in job.result()]

        return await loop.run_in_executor(None, _sync)

    async def _pull_via_bq(self, start: datetime, end: datetime) -> list[RawItem]:
        query = self._build_bq_query(start, end)
        logger.info("[gdelt/bq] Querying %s → %s (widen=%s)",
                    start.date(), end.date(), self._widen_filter)
        try:
            rows = await self._run_bq_query(query)
        except Exception as exc:
            logger.error("[gdelt/bq] Query failed: %s", exc)
            return []

        logger.info("[gdelt/bq] Rows returned: %d", len(rows))
        if len(rows) < 5:
            self._widen_filter = True
        elif len(rows) > 150:
            self._widen_filter = False

        items: list[RawItem] = []
        for row in rows:
            gkg_id = str(row.get("GKGRECORDID", ""))
            doc_url = row.get("DocumentIdentifier", "")
            date_str = str(row.get("DATE", ""))
            try:
                occurred_at = datetime.strptime(date_str[:14], "%Y%m%d%H%M%S").replace(tzinfo=UTC)
            except ValueError:
                occurred_at = datetime.now(UTC)
            tone_raw = str(row.get("V2Tone", "") or "")
            tone_parts = tone_raw.split(",")
            overall_tone = float(tone_parts[0]) if tone_parts and tone_parts[0] else 0.0
            items.append(RawItem(
                source="gdelt",
                source_id=f"gdelt:{gkg_id}",
                url=doc_url,
                occurred_at=occurred_at,
                raw_payload={
                    "gkg_record_id": gkg_id,
                    "source_name": row.get("SourceCommonName", ""),
                    "url": doc_url,
                    "themes": (str(row.get("V2Themes", "") or ""))[:500],
                    "organizations": (str(row.get("V2Organizations", "") or ""))[:500],
                    "locations": (str(row.get("V2Locations", "") or ""))[:500],
                    "overall_tone": round(overall_tone, 2),
                    "pull_method": "bigquery",
                },
            ))
        return items

    # ── GKG CSV fallback helpers ──────────────────────────────────────────────

    def _matches_gkg_row(self, themes_col: str, orgs_col: str, url: str) -> bool:
        themes = {t.split(",")[0].upper() for t in themes_col.split(";") if t}
        text = (orgs_col + " " + url).lower()
        if themes & set(GDELT_THEMES):
            if any(p.search(text) for p in _GKG_ALL_PATTERNS):
                return True
        return any(p.search(text) for p in _GKG_ORG_PATTERNS)

    def _parse_gkg_zip(self, data: bytes, seen_urls: set[str]) -> list[RawItem]:
        items: list[RawItem] = []
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                fname = next((n for n in zf.namelist() if n.endswith(".csv")), None)
                if not fname:
                    return items
                with zf.open(fname) as f:
                    reader = csv.reader(
                        io.TextIOWrapper(f, encoding="utf-8", errors="replace"),
                        delimiter="\t",
                    )
                    for row in reader:
                        if len(row) < 19:
                            continue
                        gkg_id, date_str = row[0], row[1]
                        source_name, url = row[3], row[4]
                        themes, locs = row[8], row[10]
                        orgs, tone_raw = row[14], row[15]
                        if not url or url in seen_urls:
                            continue
                        if not self._matches_gkg_row(themes, orgs, url):
                            continue
                        seen_urls.add(url)
                        try:
                            occurred_at = datetime.strptime(
                                date_str[:14], "%Y%m%d%H%M%S"
                            ).replace(tzinfo=UTC)
                        except Exception:
                            occurred_at = datetime.now(UTC)
                        tone_parts = tone_raw.split(",")
                        overall_tone = float(tone_parts[0]) if tone_parts and tone_parts[0] else 0.0
                        items.append(RawItem(
                            source="gdelt",
                            source_id=f"gdelt:gkg:{abs(hash(url)) & 0xFFFFFFFFFFFF:012x}",
                            url=url,
                            occurred_at=occurred_at,
                            raw_payload={
                                "gkg_record_id": gkg_id,
                                "source_name": source_name,
                                "url": url,
                                "themes": themes[:500],
                                "organizations": orgs[:500],
                                "locations": locs[:500],
                                "overall_tone": round(overall_tone, 2),
                                "pull_method": "gkg_csv",
                            },
                        ))
        except Exception as exc:
            logger.debug("[gdelt/gkg] parse error: %s", exc)
        return items

    async def _pull_gkg_slice(
        self, client: httpx.AsyncClient, start: datetime, end: datetime,
        seen_urls: set[str],
    ) -> list[RawItem]:
        """Download sampled GKG CSV files for a date window and filter locally."""
        timestamps: list[str] = []
        day = start.replace(hour=0, minute=0, second=0, microsecond=0)
        while day <= end:
            for hour in _GKG_SAMPLE_HOURS:
                ts_dt = day.replace(hour=hour)
                if start <= ts_dt <= end:
                    snapped = ts_dt.replace(minute=(ts_dt.minute // 15) * 15)
                    timestamps.append(snapped.strftime("%Y%m%d%H%M%S"))
            day += timedelta(days=1)

        logger.info("[gdelt/gkg] slice %s–%s: fetching %d sampled files",
                    start.date(), end.date(), len(timestamps))

        items: list[RawItem] = []
        for i in range(0, len(timestamps), _GKG_DL_CONCURRENCY):
            batch = timestamps[i : i + _GKG_DL_CONCURRENCY]

            async def _dl(ts: str) -> tuple[str, bytes | None]:
                url = f"{_GKG_BASE_URL}/{ts}.gkg.csv.zip"
                try:
                    r = await client.get(url, timeout=60)
                    if r.status_code == 404:
                        return ts, None
                    r.raise_for_status()
                    return ts, r.content
                except Exception as exc:
                    logger.debug("[gdelt/gkg] download %s: %s", ts, exc)
                    return ts, None

            results = await asyncio.gather(*[_dl(ts) for ts in batch])
            for ts, data in results:
                if data is None:
                    continue
                new_items = self._parse_gkg_zip(data, seen_urls)
                if new_items:
                    logger.info("[gdelt/gkg] %s → %d matching rows", ts, len(new_items))
                    items.extend(new_items)
            if i + _GKG_DL_CONCURRENCY < len(timestamps):
                await asyncio.sleep(1.0)

        return items

    # ── DOC API path ─────────────────────────────────────────────────────────

    @retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, min=12, max=60))
    async def _fetch_doc_slice(
        self, client: httpx.AsyncClient, start: datetime, end: datetime
    ) -> list[dict]:
        params = {
            "query": _DOC_QUERY,
            "mode": "artlist",
            "format": "json",
            "maxrecords": str(_DOC_MAX_RECORDS),
            "sort": "datedesc",
            "startdatetime": start.strftime(_DOC_DATE_FMT),
            "enddatetime":   end.strftime(_DOC_DATE_FMT),
        }
        resp = await client.get(GDELT_DOC_API, params=params, timeout=30)
        body = resp.text.strip()

        # GDELT rate-limit responses:
        #   - 429 with plain-text body (hard limit)
        #   - 200 with plain-text body (soft limit — "Please limit requests…")
        # Both need to trigger a retry; raise HTTPStatusError so tenacity catches it.
        if resp.status_code == 429 or (
            resp.status_code == 200 and body and not body.startswith("{")
        ):
            logger.warning("[gdelt/docapi] Rate limited (%d): %s", resp.status_code, body[:80])
            raise httpx.HTTPStatusError(
                f"GDELT rate-limited ({resp.status_code})",
                request=resp.request, response=resp,
            )

        resp.raise_for_status()
        if not body:
            return []
        try:
            return resp.json().get("articles") or []
        except Exception:
            logger.warning("[gdelt/docapi] Non-JSON response: %s", body[:120])
            return []

    def _parse_seendate(self, raw: str) -> datetime:
        """Parse GDELT seendate e.g. '20260515T120000Z' or '20260515120000'."""
        clean = raw.replace("T", "").replace("Z", "").replace("-", "").replace(":", "")
        try:
            return datetime.strptime(clean[:14], "%Y%m%d%H%M%S").replace(tzinfo=UTC)
        except Exception:
            return datetime.now(UTC)

    async def _pull_via_docapi(self, start: datetime, end: datetime) -> list[RawItem]:
        """Pull via GDELT DOC API, 7-day slices. Falls back to GKG CSV for empty slices."""
        items: list[RawItem] = []
        seen_urls: set[str] = set()
        total_slices = 0
        gkg_slices = 0

        headers = {"User-Agent": settings.sec_user_agent}
        async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
            # Brief initial pause — avoids rate-limit if the agent was already
            # making requests in the same process (e.g. back-to-back runs).
            await asyncio.sleep(6.0)
            slice_start = start
            while slice_start < end:
                slice_end = min(slice_start + timedelta(days=_DOC_SLICE_DAYS), end)
                try:
                    articles = await self._fetch_doc_slice(client, slice_start, slice_end)
                except Exception as exc:
                    logger.warning("[gdelt/docapi] slice %s–%s failed after retries: %s — "
                                   "trying GKG CSV fallback",
                                   slice_start.date(), slice_end.date(), exc)
                    articles = []

                kept = 0
                for art in articles:
                    # Post-filter: skip non-English articles
                    lang = art.get("language", "")
                    if lang and lang not in _KEEP_LANGUAGES:
                        continue
                    url = art.get("url", "") or art.get("socialimage", "")
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    title = art.get("title", "")
                    occurred_at = self._parse_seendate(art.get("seendate", ""))
                    items.append(RawItem(
                        source="gdelt",
                        source_id=f"gdelt:doc:{abs(hash(url)) & 0xFFFFFFFFFFFF:012x}",
                        url=url,
                        occurred_at=occurred_at,
                        raw_payload={
                            "title": title,
                            "url": url,
                            "domain": art.get("domain", ""),
                            "language": art.get("language", ""),
                            "sourcecountry": art.get("sourcecountry", ""),
                            "seendate": art.get("seendate", ""),
                            "pull_method": "docapi",
                        },
                    ))
                    kept += 1

                logger.info("[gdelt/docapi] slice %s–%s: %d articles (%d new)",
                            slice_start.date(), slice_end.date(), len(articles), kept)

                # GKG CSV fallback: kick in when DOC API returned nothing for this slice
                if kept == 0:
                    logger.info("[gdelt/gkg] DOC API empty for %s–%s — trying GKG CSV",
                                slice_start.date(), slice_end.date())
                    try:
                        gkg_items = await self._pull_gkg_slice(
                            client, slice_start, slice_end, seen_urls
                        )
                        items.extend(gkg_items)
                        gkg_slices += 1
                        logger.info("[gdelt/gkg] slice %s–%s: %d articles via GKG CSV",
                                    slice_start.date(), slice_end.date(), len(gkg_items))
                    except Exception as exc:
                        logger.warning("[gdelt/gkg] slice %s–%s failed: %s",
                                       slice_start.date(), slice_end.date(), exc)

                total_slices += 1
                slice_start = slice_end
                if slice_start < end:
                    await asyncio.sleep(8.0)  # GDELT states 1 req/5s — 8s is safe margin

        logger.info("[gdelt/docapi] Total: %d unique articles across %d slice(s) "
                    "(%d used GKG CSV fallback)",
                    len(items), total_slices, gkg_slices)
        return items

    # ── Main entry ────────────────────────────────────────────────────────────

    async def pull(self, window: tuple[datetime, datetime]) -> list[RawItem]:
        start, end = window
        hours = (end - start).total_seconds() / 3600

        if hours <= _BQ_MAX_HOURS:
            logger.info("[gdelt] Using BigQuery path (window=%.1fh ≤ %dh threshold)",
                        hours, _BQ_MAX_HOURS)
            return await self._pull_via_bq(start, end)
        else:
            logger.info("[gdelt] Using DOC API path (window=%.1fh > %dh threshold — "
                        "BQ would scan %.1f GB, limit is %.1f GB)",
                        hours, _BQ_MAX_HOURS,
                        hours / 24 * 0.47,           # rough estimate
                        settings.bigquery_max_bytes_billed / 1e9)
            return await self._pull_via_docapi(start, end)
