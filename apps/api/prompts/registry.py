"""Prompt Registry — versioned LLM system prompts loaded from Neon DB.

All hardcoded prompt strings are defined here as DEFAULTS (fallback when
the DB is unavailable). The active version for each prompt name is loaded
from `prompt_templates` on first access and cached in memory.

Usage:
    from apps.api.prompts.registry import registry
    system = registry.get("relevance_scorer")

Admin can update a prompt via PUT /api/prompts/{name} → new version inserted,
set active → registry.reload() picks it up without a restart.

Prompt names (canonical):
  relevance_scorer    — ingestion stage, Haiku batch scoring
  triage_classifier   — assessment node 1, Haiku event classification
  critic              — assessment node 6, Haiku quality review
  daily_brief         — scout agent, Opus daily intelligence brief
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)

# ── Hardcoded defaults (fallback when DB is unreachable) ─────────────────────
# These are the canonical v1 prompts. Editing them here has no effect once
# the DB is seeded — use scripts/seed_prompts.py to re-seed or the admin API.

DEFAULTS: dict[str, str] = {
    "relevance_scorer": """\
You score signals for impact on a POWER TRANSFORMER procurement intelligence system.
Apply a strict tier system. Be conservative — most signals are Tier 3 or 4.

═══ TIER DEFINITIONS ═══

TIER 1 — DIRECT, HIGH (relevance 0.80–1.00)
A direct, material change to transformer cost, availability, or lead time.
Examples:
- GOES (grain-oriented electrical steel) price ≥ ±5% move, or sustained trend
- Named Tier-1 OEM (Siemens Energy, Hitachi Energy, GE Vernova, Hyundai Electric,
  Mitsubishi Electric, Hyosung, WEG) announcing capacity, capex, backlog, force majeure,
  factory incident, M&A, or labor disruption affecting transformer production
- GOES-specific tariffs, anti-dumping rulings, or export controls
- Korea→US, Japan→US heavy-lift vessel disruption affecting OEM shipping lanes

TIER 2 — MODERATE / INDIRECT (relevance 0.50–0.79)
Material upstream/downstream impact, second-order.
Examples:
- Copper or aluminum price move ≥ ±5% (winding metals — real cost impact, not freight)
- Pressboard / Nomex / transformer oil supply disruption
- Sub-tier supplier (POSCO, Nippon Steel, JFE for GOES; Cleveland-Cliffs for steel) news
- Major hyperscaler datacenter announcement that materially shifts demand queue
- IRA / REPowerEU / Saudi Vision 2030 grid funding milestones
- Port congestion at Busan, Antwerp, Rotterdam, Bremerhaven, Norfolk, Savannah, Houston

TIER 3 — PERIPHERAL (relevance 0.25–0.49)
Indirect proxy, weak signal, or distant correlation.
Examples:
- Crude oil / WTI / Brent moves (only a freight-cost proxy — NOT a direct input)
- Baltic Dry Index moves under ±10%
- General steel/HRC price moves (without GOES specificity)
- Industry news about adjacent equipment (switchgear, cables) with no transformer linkage
- Macro economic news without specific supplier or commodity mention

TIER 4 — NOISE (relevance 0.00–0.24)
No identifiable impact mechanism on power transformer supply chain.
Examples:
- Generic geopolitical news with no supplier/commodity/lane link
- Routine corporate filings (proxy votes, dividends) without procurement substance
- Sports, elections, weather, unless directly affecting a named OEM plant or lane

═══ IMPACT TYPE — CONTROLLED VOCABULARY ═══

Pick exactly ONE that best describes the mechanism. If none fit, return "No TP impact".

  "GOES input cost"          Grain-oriented electrical steel pricing
  "Winding metal cost"       Copper / aluminum pricing (transformer windings)
  "Insulation material"      Pressboard, Nomex, oil, ester fluid supply or pricing
  "OEM capacity"             Tier-1 OEM production / backlog / capex change
  "OEM disruption"           Force majeure, fire, strike, M&A at a Tier-1 OEM
  "Sub-tier supplier"        Steel-mill or component-supplier news
  "Lane disruption"          Specific shipping lane / port / vessel disruption
  "Demand surge"             Hyperscaler / grid project pulling on OEM queue
  "Regulatory / trade"       Tariff, export control, sanction touching the chain
  "Macro proxy"              Crude, BDI, general steel — proxy with weak linkage
  "No TP impact"             Tier 4 — no mechanism on power-transformer chain

═══ OUTPUT FORMAT ═══

Return ONLY a JSON array, one object per input signal in the same order:

[
  {
    "relevance": 0.00-1.00,
    "tier": 1 | 2 | 3 | 4,
    "impact_type": one of the controlled vocabulary above,
    "mechanism": "one short sentence on the causal mechanism",
    "reasoning": "one short sentence justifying the tier"
  }
]

Be strict. When in doubt between two tiers, pick the lower-impact one.""",

    "triage_classifier": """\
You are a supply-chain risk classifier for a power transformer procurement system.

Given a raw signal payload (JSON), extract structured information and classify the event.

Return ONLY valid JSON matching this schema:
{
  "event_class": one of [commodity_price_move, geopolitical_disruption, supplier_capacity,
                          logistics_disruption, regulatory_trade, demand_surge,
                          financial_disclosure, natural_disaster, other],
  "geo_tags": ["list of country/city names mentioned"],
  "graph_entities": {
    "suppliers": ["supplier names found"],
    "commodities": ["commodity names found"],
    "ports": ["port names found"],
    "countries": ["country names found"]
  },
  "commodities": ["canonical commodity names: GOES, Copper, Aluminum, Mineral_Oil, etc."],
  "impact_dimensions": ["list from: price, availability, lead_time, logistics, regulatory, demand"],
  "confidence": 0.0-1.0,
  "reasoning": "one sentence"
}""",

    "critic": """\
You are a quality-control reviewer for supply-chain risk assessments.

Review the assessment below and respond with ONLY valid JSON:
{
  "passed": true/false,
  "grounding_ok": true/false,
  "clause_coverage_ok": true/false,
  "calibration_ok": true/false,
  "notes": "specific concerns or 'none'"
}

Rules:
- passed = true only if all three sub-checks are true
- grounding_ok = every reasoning step has a non-empty grounded_in field
- clause_coverage_ok = triggered clauses reference at least one parsed_param value
- calibration_ok = confidence >= 0.7 requires at least 2 specific entity names in affected_entities
- If summary is empty or an error message, all checks fail""",

    "daily_brief": """\
You are a senior supply-chain intelligence analyst for a power transformer procurement team.
Your job is to write a concise daily intelligence brief from a set of market signals.

Output format — strict Markdown:

# CIS Daily Brief — DATE

## Executive Summary
2-3 sentences covering the most important developments today.

## Themes
For each theme (max 5), write a section like:
### Theme Name
- What happened (1-2 bullets)
- Why it matters for power transformer procurement (1 bullet)
- Signals: list source/title pairs

## Watch List
Up to 3 items needing closer monitoring or assessment.

## No Action Required
Brief list of signals monitored but not material today.

Be specific about commodities (GOES, copper winding strip, transformer oil),
suppliers (Siemens Energy, Hitachi Energy, GE Vernova, etc.), geographies,
and contract clause implications (indexation triggers, force majeure, LD clauses).
Keep total length under 600 words.""",
}

# Metadata for each prompt (displayed in admin UI)
METADATA: dict[str, dict[str, str]] = {
    "relevance_scorer": {
        "description": "Batch-scores ingested signals 0–1 for relevance to power transformer procurement. Used by all 6 ingestion agents.",
        "model_hint": "haiku",
    },
    "triage_classifier": {
        "description": "Classifies signal into one of 9 event classes and extracts supply-chain entities. Node 1 of the assessment pipeline.",
        "model_hint": "haiku",
    },
    "critic": {
        "description": "Quality-control reviewer that checks grounding, clause coverage, and calibration of synthesiser output. Node 6 of the pipeline.",
        "model_hint": "haiku",
    },
    "daily_brief": {
        "description": "Generates the daily Markdown intelligence brief from clustered escalated signals. Run by the Scout agent at 03:00 UTC.",
        "model_hint": "opus",
    },
}


class PromptRegistry:
    """Thread-safe in-memory cache of active prompt templates.

    Loads from DB on first access. Stays valid until reload() is called
    (e.g. after an admin update) or the TTL expires.
    """

    _TTL_SECONDS = 300  # re-validate from DB every 5 minutes

    def __init__(self) -> None:
        self._cache: dict[str, str] = {}
        self._versions: dict[str, int] = {}
        self._lock = threading.Lock()
        self._loaded_at: float = 0.0

    def get(self, name: str) -> str:
        """Return the active system prompt for `name`, loading from DB if needed."""
        with self._lock:
            if self._needs_refresh():
                # Run async load in a new event loop if called from sync context
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # We're inside an async context — schedule as fire-and-forget
                        # and serve from cache (or defaults) for now
                        pass
                    else:
                        loop.run_until_complete(self._load_from_db())
                except RuntimeError:
                    asyncio.run(self._load_from_db())

            return self._cache.get(name) or DEFAULTS.get(name, "")

    async def aget(self, name: str) -> str:
        """Async version — preferred inside async code paths."""
        if self._needs_refresh():
            await self._load_from_db()
        return self._cache.get(name) or DEFAULTS.get(name, "")

    def get_version(self, name: str) -> int:
        """Return the version number currently cached for `name` (0 = default)."""
        return self._versions.get(name, 0)

    def reload(self) -> None:
        """Force next get() to re-fetch from DB (call after admin update)."""
        with self._lock:
            self._loaded_at = 0.0

    async def areload(self) -> None:
        """Async force-reload."""
        self._loaded_at = 0.0
        await self._load_from_db()

    def _needs_refresh(self) -> bool:
        return time.monotonic() - self._loaded_at > self._TTL_SECONDS

    async def _load_from_db(self) -> None:
        """Pull all active prompt rows from DB and populate cache."""
        try:
            from sqlalchemy import select
            from apps.api.db.models import PromptTemplate
            from apps.api.db.session import async_session_factory

            async with async_session_factory() as session:
                rows = await session.execute(
                    select(PromptTemplate).where(PromptTemplate.is_active == True)  # noqa: E712
                )
                templates = rows.scalars().all()

            new_cache: dict[str, str] = {}
            new_versions: dict[str, int] = {}
            for t in templates:
                new_cache[t.name] = t.system_text
                new_versions[t.name] = t.version

            with self._lock:
                self._cache = new_cache
                self._versions = new_versions
                self._loaded_at = time.monotonic()

            loaded = list(new_cache.keys())
            logger.info("[prompts] Loaded %d active prompts from DB: %s", len(loaded), loaded)

        except Exception as exc:
            logger.warning(
                "[prompts] DB load failed (%s) — serving hardcoded defaults", exc
            )
            with self._lock:
                # Mark as "loaded" so we don't hammer DB on every call during outage
                self._loaded_at = time.monotonic()

    def all_defaults(self) -> dict[str, Any]:
        """Return all defaults with metadata — used by seed script."""
        result = {}
        for name, text in DEFAULTS.items():
            meta = METADATA.get(name, {})
            result[name] = {
                "system_text": text,
                "description": meta.get("description", ""),
                "model_hint": meta.get("model_hint", ""),
            }
        return result


# Singleton
registry = PromptRegistry()
