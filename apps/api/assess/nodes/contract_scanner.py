"""Node 4 — Contract Scanner: find relevant clauses for this signal.

Matches contract clauses by:
  1. Commodity overlap (clause.references_commodities ∩ triage.commodities)
  2. Clause type relevance to the event_class (e.g. force_majeure for disasters,
     indexation for price moves, incoterms/ld for logistics disruptions)
  3. Supplier name match on the parent contract

Returns parsed_params for each matching clause so the synthesizer can
reason about specific thresholds (trigger %, review cadence, etc.).
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text

from apps.api.agents.state import AssessmentState
from apps.api.db.session import async_session_factory

logger = logging.getLogger(__name__)

# Map event_class → preferred clause types (ordered by relevance)
_EVENT_CLAUSE_MAP: dict[str, list[str]] = {
    "commodity_price_move":    ["indexation", "escalation", "force_majeure"],
    "logistics_disruption":    ["incoterms", "force_majeure", "ld", "slot", "heavy_lift"],
    "supplier_capacity":       ["slot", "ld", "delivery_obligation", "force_majeure"],
    "geopolitical_disruption": ["force_majeure", "incoterms", "indexation"],
    "regulatory_trade":        ["force_majeure", "incoterms", "indexation"],
    "demand_surge":            ["slot", "delivery_obligation", "ld"],
    "financial_disclosure":    ["indexation", "escalation"],
    "natural_disaster":        ["force_majeure", "ld", "delivery_obligation"],
    "other":                   ["force_majeure", "indexation"],
}


def _triage_data(state: AssessmentState) -> dict[str, Any]:
    for item in state.graph_context:
        if "_triage" in item:
            return item["_triage"]
    return {}


async def contract_scanner_node(state: AssessmentState) -> AssessmentState:
    """Match contract clauses relevant to this signal's event class and commodities."""
    if not state.triage_passed:
        return state

    triage = _triage_data(state)
    event_class = triage.get("event_class", "other")
    commodities = triage.get("commodities", [])
    supplier_names = triage.get("graph_entities", {}).get("suppliers", [])

    preferred_types = _EVENT_CLAUSE_MAP.get(event_class, ["force_majeure", "indexation"])

    try:
        async with async_session_factory() as session:
            matches: list[dict[str, Any]] = []

            _clause_select = """
                SELECT
                    c.external_id  AS contract_id,
                    c.supplier_name,
                    c.category,
                    cl.id          AS clause_id,
                    cl.clause_type,
                    cl.text,
                    cl.references_commodities,
                    cl.parsed_params
                FROM contract_clauses cl
                JOIN contracts c ON c.id = cl.contract_id
            """

            # ── Pass 1: commodity-matched clauses ────────────────────────────
            if commodities:
                # Build parameterised ANY() via Python-side comma list
                placeholders = ", ".join(f":c{i}" for i in range(len(commodities)))
                params = {f"c{i}": v for i, v in enumerate(commodities)}
                rows = await session.execute(text(
                    f"{_clause_select} WHERE cl.references_commodities::text[] && "
                    f"ARRAY[{placeholders}]::text[] "
                    f"ORDER BY c.supplier_name, cl.clause_type LIMIT 20"
                ), params)
                for row in rows.mappings():
                    matches.append(_row_to_match(row, relevance="commodity_match"))

            # ── Pass 2: supplier-matched clauses ─────────────────────────────
            if supplier_names:
                sup_lower = [s.lower() for s in supplier_names]
                placeholders = ", ".join(f":s{i}" for i in range(len(sup_lower)))
                params = {f"s{i}": v for i, v in enumerate(sup_lower)}
                rows = await session.execute(text(
                    f"{_clause_select} WHERE LOWER(c.supplier_name) = ANY(ARRAY[{placeholders}]::text[]) "
                    f"ORDER BY cl.clause_type LIMIT 20"
                ), params)
                seen_ids = {m["clause_id"] for m in matches}
                for row in rows.mappings():
                    if str(row["clause_id"]) not in seen_ids:
                        matches.append(_row_to_match(row, relevance="supplier_match"))

            # ── Pass 3: if no matches, fetch by event class clause types ─────
            if not matches:
                types = preferred_types[:3]
                placeholders = ", ".join(f":t{i}" for i in range(len(types)))
                params = {f"t{i}": v for i, v in enumerate(types)}
                rows = await session.execute(text(
                    f"{_clause_select} WHERE cl.clause_type = ANY(ARRAY[{placeholders}]::text[]) "
                    f"ORDER BY cl.clause_type LIMIT 15"
                ), params)

                for row in rows.mappings():
                    matches.append(_row_to_match(row, relevance="event_class_match"))

            # Sort by preferred clause type order
            type_rank = {t: i for i, t in enumerate(preferred_types)}
            matches.sort(key=lambda m: type_rank.get(m["clause_type"], 99))

            state.contract_matches = matches[:12]  # cap context size

        logger.info(
            "[contract_scanner] Found %d clause matches for event_class=%s commodities=%s",
            len(state.contract_matches), event_class, commodities,
        )

    except Exception as exc:
        logger.warning("[contract_scanner] Query failed: %s", exc)
        state.errors.append(f"contract_scanner_error: {exc}")

    return state


def _row_to_match(row: Any, relevance: str) -> dict[str, Any]:
    return {
        "contract_id": row["contract_id"],
        "supplier_name": row["supplier_name"],
        "category": row["category"],
        "clause_id": str(row["clause_id"]),
        "clause_type": row["clause_type"],
        "text": (row["text"] or "")[:400],
        "references_commodities": row["references_commodities"] or [],
        "parsed_params": row["parsed_params"] or {},
        "relevance": relevance,
    }
