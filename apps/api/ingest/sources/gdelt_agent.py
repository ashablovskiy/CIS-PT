"""GDELT 2.0 Global Knowledge Graph ingestion agent — BigQuery.

Queries gdelt-bq.gdeltv2.gkg for events relevant to power transformer
supply chain: themes (energy, manufacturing, disaster), organizations
(supplier names), and locations (key plants/ports).

BigQuery free tier: 1 TB/month. Each run targets ≤ 5 GB scanned via:
  - _PARTITIONTIME filter (prune to window)
  - Column selection (never SELECT *)
  - SQL-level keyword filtering before any data leaves BQ

Adaptive behavior:
  - If run returns < 5 items → widen theme/entity filter on next run
  - If run returns > 200 items → narrow filter

Cadence: every 1 hour.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any

from google.cloud import bigquery
from tenacity import retry, stop_after_attempt, wait_exponential

from apps.api.ingest.base import RawItem
from apps.api.ingest.runner import BaseIngestionAgent
from apps.api.settings import settings

logger = logging.getLogger(__name__)

# GDELT GKG table in BigQuery — use the partitioned variant for cost control.
# gdelt-bq.gdeltv2.gkg is unpartitioned (1.8B rows, full scan = $0+ per query).
# gkg_partitioned is DAY-partitioned on ingestion time, enabling _PARTITIONTIME pruning.
GDELT_TABLE = "gdelt-bq.gdeltv2.gkg_partitioned"

# Themes that indicate supply-chain-relevant events
GDELT_THEMES = [
    "ENERGY",
    "MANUFACTURING",
    "ECON_TAXATION",
    "NATURAL_DISASTER",
    "INFRASTRUCTURE_DESTRUCTION",
    "ENV_MINING",
    "WB_2411_ENERGY_AND_MINING",
    "ECON_TRADE",
    "CONFLICT",
]

# Supplier + material names to match in V2Organizations and Themes
SUPPLIER_KEYWORDS = [
    "Siemens Energy", "Hitachi Energy", "GE Vernova", "Hyundai Electric",
    "Hyosung", "Mitsubishi Electric", "WEG", "POSCO", "Nippon Steel",
    "JFE Steel", "Cleveland-Cliffs", "Baosteel", "Stalprodukt",
    "transformer", "electrical steel", "GOES",
]

# Location names (countries + port cities)
LOCATION_KEYWORDS = [
    "South Korea", "Japan", "Germany", "Poland",
    "Busan", "Antwerp", "Rotterdam", "Bremerhaven",
    "Nuremberg", "Weiz", "Ulsan", "Changwon",
]


def _build_theme_filter() -> str:
    quoted = ", ".join(f"'{t}'" for t in GDELT_THEMES)
    return f"REGEXP_CONTAINS(V2Themes, r'(?i)({'|'.join(GDELT_THEMES)})')"


def _build_org_filter() -> str:
    parts = " OR ".join(
        f"LOWER(V2Organizations) LIKE '%{kw.lower()}%'"
        for kw in SUPPLIER_KEYWORDS
    )
    return f"({parts})"


def _build_location_filter() -> str:
    parts = " OR ".join(
        f"LOWER(V2Locations) LIKE '%{kw.lower()}%'"
        for kw in LOCATION_KEYWORDS
    )
    return f"({parts})"


class GdeltAgent(BaseIngestionAgent):
    agent_name = "gdelt_agent"

    def __init__(self) -> None:
        super().__init__()
        # Set credentials path before instantiating the BQ client.
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.google_application_credentials
        self._bq = bigquery.Client(project=settings.gcp_project_id)
        self._widen_filter = False  # set True if previous run returned < 5 items

    def default_lookback_hours(self) -> int:
        return 1

    def keyword_rules(self) -> list[str]:
        # GDELT items already go through heavy SQL filtering; rule filter is light.
        _fallback = [
            "transformer", "electrical steel", "goes", "copper", "aluminum",
            "siemens energy", "hitachi energy", "ge vernova", "hyundai",
            "posco", "nippon steel", "busan", "antwerp", "rotterdam",
            "grid", "power", "energy", "manufacturing", "supply chain",
        ]
        try:
            from apps.api.ingest.keyword_registry import registry
            return registry.get("gdelt") or _fallback
        except Exception:
            return _fallback

    def _build_query(self, window_start: datetime, window_end: datetime) -> str:
        # _PARTITIONTIME works on gkg_partitioned (DAY partitioned by ingestion time).
        # DATE column (INTEGER YYYYMMDDHHMMSS) provides sub-day precision within the shard.
        start_ts = window_start.strftime("%Y-%m-%d %H:%M:%S")
        end_ts = window_end.strftime("%Y-%m-%d %H:%M:%S")
        start_int = int(window_start.strftime("%Y%m%d%H%M%S"))
        end_int = int(window_end.strftime("%Y%m%d%H%M%S"))

        # Combine filters: theme OR supplier/org OR location
        # Widen mode drops the location filter to catch more.
        if self._widen_filter:
            where_clause = f"({_build_theme_filter()} OR {_build_org_filter()})"
        else:
            where_clause = (
                f"({_build_theme_filter()} OR {_build_org_filter()} OR {_build_location_filter()})"
            )

        return f"""
        SELECT
            GKGRECORDID,
            DATE,
            SourceCommonName,
            DocumentIdentifier,
            V2Themes,
            V2Locations,
            V2Organizations,
            V2Tone,
            SharingImage
        FROM `{GDELT_TABLE}`
        WHERE
            _PARTITIONTIME >= TIMESTAMP('{start_ts}')
            AND _PARTITIONTIME < TIMESTAMP('{end_ts}')
            AND DATE >= {start_int}
            AND DATE < {end_int}
            AND {where_clause}
            AND DocumentIdentifier IS NOT NULL
            AND LENGTH(DocumentIdentifier) > 10
        LIMIT 200
        """

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=2, min=5, max=30))
    async def _run_query(self, query: str) -> list[dict[str, Any]]:
        """Run a BigQuery job synchronously (BQ client is sync-only)."""
        import asyncio
        loop = asyncio.get_event_loop()

        def _sync_query():
            job_config = bigquery.QueryJobConfig(
                maximum_bytes_billed=settings.bigquery_max_bytes_billed,
                use_query_cache=True,
            )
            job = self._bq.query(query, job_config=job_config)
            return [dict(row) for row in job.result()]

        return await loop.run_in_executor(None, _sync_query)

    async def pull(self, window: tuple[datetime, datetime]) -> list[RawItem]:
        query = self._build_query(window[0], window[1])
        logger.info(
            "[gdelt] Querying %s → %s (widen=%s)",
            window[0].isoformat(), window[1].isoformat(), self._widen_filter,
        )

        try:
            rows = await self._run_query(query)
        except Exception as exc:
            logger.error("[gdelt] BigQuery error: %s", exc)
            return []

        logger.info("[gdelt] Raw rows returned: %d", len(rows))

        # Adaptive filter adjustment for next run
        if len(rows) < 5:
            self._widen_filter = True
            logger.info("[gdelt] < 5 rows — will widen filter on next run")
        elif len(rows) > 150:
            self._widen_filter = False
            logger.info("[gdelt] > 150 rows — filter staying narrow")

        items: list[RawItem] = []
        for row in rows:
            gkg_id = str(row.get("GKGRECORDID", ""))
            doc_url = row.get("DocumentIdentifier", "")
            source_name = row.get("SourceCommonName", "")

            # Parse GDELT DATE (format: YYYYMMDDHHMMSS)
            date_str = str(row.get("DATE", ""))
            try:
                occurred_at = datetime.strptime(date_str[:14], "%Y%m%d%H%M%S").replace(tzinfo=UTC)
            except ValueError:
                occurred_at = datetime.now(UTC)

            # Tone: comma-separated values; first is overall tone
            tone_raw = str(row.get("V2Tone", "") or "")
            tone_parts = tone_raw.split(",")
            overall_tone = float(tone_parts[0]) if tone_parts and tone_parts[0] else 0.0

            payload: dict[str, Any] = {
                "gkg_record_id": gkg_id,
                "source_name": source_name,
                "url": doc_url,
                "themes": (str(row.get("V2Themes", "") or ""))[:500],
                "organizations": (str(row.get("V2Organizations", "") or ""))[:500],
                "locations": (str(row.get("V2Locations", "") or ""))[:500],
                "overall_tone": round(overall_tone, 2),
                "image_url": row.get("SharingImage", ""),
            }

            items.append(
                RawItem(
                    source="gdelt",
                    source_id=f"gdelt:{gkg_id}",
                    url=doc_url,
                    occurred_at=occurred_at,
                    raw_payload=payload,
                )
            )

        return items
