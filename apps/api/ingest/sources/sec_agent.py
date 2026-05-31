"""SEC EDGAR ingestion agent — 8-K / 10-K / 10-Q filings.

Watched CIKs, grouped by why they matter to power-transformer procurement.
Only US-listed filers appear here; non-US OEMs/suppliers (Siemens Energy,
Hitachi Energy, POSCO, Nippon Steel, Reinhausen) are covered by the ir_agent.

  Grid / power equipment OEMs:
    GE Vernova      1996810   (corrected from 1993009)
    Eaton           31277
    Hubbell         48898
    nVent Electric  1720635
    Vertiv          1674101   (DC power & thermal)
    Quanta Services 1050915   (grid construction / interconnection)
  Raw material — GOES:
    Cleveland-Cliffs 764065   (the only US grain-oriented electrical-steel mill)
  Hyperscalers / AI demand:
    Microsoft       789019
    Alphabet/Google 1652044
    Amazon          1018724
    Meta            1326801
    Oracle          1341439   (OCI / Stargate)
    CoreWeave       1769628   (AI datacenter)

Uses the EDGAR submissions API (no auth required, 10 req/s limit).
Cadence: daily.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from apps.api.ingest.base import RawItem
from apps.api.ingest.runner import BaseIngestionAgent
from apps.api.settings import settings

logger = logging.getLogger(__name__)

EDGAR_BASE = "https://data.sec.gov"
EDGAR_SEARCH = "https://efts.sec.gov/LATEST/search-index"

# CIK zero-padded to 10 digits → company name
WATCHED_CIKS: dict[str, str] = {
    # Grid / power-equipment OEMs
    "0001996810": "GE Vernova",
    "0000031277": "Eaton",
    "0000048898": "Hubbell",
    "0001720635": "nVent Electric",
    "0001674101": "Vertiv",
    "0001050915": "Quanta Services",
    # Raw material — GOES (only US producer)
    "0000764065": "Cleveland-Cliffs",
    # Hyperscalers / AI demand
    "0000789019": "Microsoft",
    "0001652044": "Alphabet",
    "0001018724": "Amazon",
    "0001326801": "Meta",
    "0001341439": "Oracle",
    "0001769628": "CoreWeave",
}

# Filing types to capture
TARGET_FORM_TYPES = {"8-K", "10-K", "10-Q"}

# Keywords that elevate relevance in rule filter
POWER_KEYWORDS = [
    "transformer", "goes", "grain-oriented", "electrical steel",
    "datacenter", "data center", "capex", "capital expenditure",
    "backlog", "supply chain", "grid", "power equipment",
    "transmission", "substation", "copper", "aluminum",
]


class SecAgent(BaseIngestionAgent):
    agent_name = "sec_agent"

    def default_lookback_hours(self) -> int:
        return 4

    def keyword_rules(self) -> list[str]:
        try:
            from apps.api.ingest.keyword_registry import registry
            return registry.get("sec") or POWER_KEYWORDS
        except Exception:
            return POWER_KEYWORDS

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30))
    async def _fetch_submissions(self, client: httpx.AsyncClient, cik: str) -> dict:
        url = f"{EDGAR_BASE}/submissions/CIK{cik}.json"
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()

    async def pull(self, window: tuple[datetime, datetime]) -> list[RawItem]:
        cutoff = window[0]
        items: list[RawItem] = []

        headers = {
            "User-Agent": settings.sec_user_agent,
            "Accept-Encoding": "gzip, deflate",
        }

        async with httpx.AsyncClient(headers=headers, timeout=30) as client:
            for cik, company_name in WATCHED_CIKS.items():
                try:
                    data = await self._fetch_submissions(client, cik)
                    recent = data.get("filings", {}).get("recent", {})

                    accession_numbers = recent.get("accessionNumber", [])
                    form_types = recent.get("form", [])
                    filing_dates = recent.get("filingDate", [])
                    primary_docs = recent.get("primaryDocument", [])
                    descriptions = recent.get("primaryDocDescription", [])

                    for acc, form, date_str, primary_doc, desc in zip(
                        accession_numbers, form_types, filing_dates, primary_docs, descriptions
                    ):
                        if form not in TARGET_FORM_TYPES:
                            continue

                        try:
                            filed_at = datetime.fromisoformat(date_str).replace(tzinfo=UTC)
                        except ValueError:
                            continue

                        if filed_at < cutoff:
                            break  # EDGAR returns newest-first; stop once past window.

                        acc_path = acc.replace("-", "")
                        doc_url = (
                            f"https://www.sec.gov/Archives/edgar/full-index/"
                            f"{filed_at.year}/{filed_at.strftime('%m')}/company.idx"
                        )
                        viewer_url = (
                            f"https://www.sec.gov/Archives/edgar/data/"
                            f"{int(cik)}/{acc_path}/{primary_doc}"
                        )

                        source_id = f"{cik}:{acc}"
                        items.append(
                            RawItem(
                                source="sec",
                                source_id=source_id,
                                url=viewer_url,
                                occurred_at=filed_at,
                                raw_payload={
                                    "cik": cik,
                                    "company": company_name,
                                    "form_type": form,
                                    "accession_number": acc,
                                    "filed_at": date_str,
                                    "primary_doc": primary_doc,
                                    "description": desc,
                                    "viewer_url": viewer_url,
                                },
                            )
                        )
                        logger.debug("[sec] %s %s filed %s: %s", company_name, form, date_str, acc)

                    logger.info("[sec] %s: found %d relevant filings in window", company_name,
                                sum(1 for i in items if i.raw_payload.get("company") == company_name))

                except Exception as exc:
                    logger.error("[sec] Error fetching %s (%s): %s", company_name, cik, exc)

        return items
