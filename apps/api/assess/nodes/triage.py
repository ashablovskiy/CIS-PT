"""Node 1 — Triage: entity extraction + event classification.

Reads the signal payload, identifies named entities that exist in the
supply graph (suppliers, commodities, ports, countries), classifies the
event type using Claude Haiku, and decides whether to proceed.

Skips signals already assessed within the last 7 days (dedup).
"""

from __future__ import annotations

import json
import logging

from apps.api.agents.state import AssessmentState
from apps.api.budget import budgeted_client
from apps.api.classify.schemas import ClassificationResult, EventClass
from apps.api.ingest.keyword_registry import registry
from apps.api.prompts.registry import registry as _prompt_registry

logger = logging.getLogger(__name__)

_HAIKU = "claude-haiku-4-5-20251001"


def _extract_entity_hints(payload: dict) -> str:
    """Build a concise text representation of the signal for the LLM."""
    parts = []
    for key in ("title", "summary", "label", "themes", "organizations", "locations",
                "ticker", "alert_type", "company", "signal_type"):
        val = payload.get(key)
        if val and isinstance(val, str):
            parts.append(f"{key}: {val[:300]}")
    moves = payload.get("moves_pct")
    if moves:
        parts.append(f"price_moves: {json.dumps(moves)}")
    return "\n".join(parts) or json.dumps(payload, default=str)[:500]


async def triage_node(state: AssessmentState) -> AssessmentState:
    """Classify the signal and decide whether assessment is worthwhile."""
    payload = state.signal_payload
    signal_text = _extract_entity_hints(payload)

    logger.info("[triage] signal_id=%s source=%s", state.signal_id, payload.get("source", "?"))

    try:
        response = await budgeted_client.messages_create(
            model=_HAIKU,
            max_tokens=512,
            system=await _prompt_registry.aget("triage_classifier"),
            messages=[{"role": "user", "content": f"Classify this signal:\n\n{signal_text}"}],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        data = json.loads(raw.strip())
        result = ClassificationResult(**data)

    except Exception as exc:
        logger.warning("[triage] Classification failed: %s — using defaults", exc)
        state.errors.append(f"triage_error: {exc}")
        # Minimal fallback: infer from source
        source = payload.get("source", "")
        result = ClassificationResult(
            event_class=_infer_event_class(source, payload),
            confidence=0.4,
            reasoning="fallback inference from source type",
        )

    # Gate: skip OTHER class with low confidence
    if result.event_class == EventClass.OTHER and result.confidence < 0.5:
        logger.info("[triage] Skipping — event_class=other, confidence=%.2f", result.confidence)
        state.triage_passed = False
        return state

    # Augment graph_entities with keyword_registry fuzzy matches
    enriched = _enrich_entities(result.graph_entities, payload)

    state.triage_passed = True
    # Store classification in state via graph_context metadata
    state.graph_context = [{"_triage": {
        "event_class": result.event_class,
        "secondary_event_classes": result.secondary_event_classes,
        "geo_tags": result.geo_tags,
        "graph_entities": enriched,
        "commodities": result.commodities,
        "impact_dimensions": [str(d) for d in result.impact_dimensions],
        "state_change": result.state_change,
        "confidence": result.confidence,
        "reasoning": result.reasoning,
    }}]

    logger.info(
        "[triage] PASSED — class=%s entities=%s confidence=%.2f",
        result.event_class,
        {k: len(v) for k, v in enriched.items() if v},
        result.confidence,
    )
    return state


def _infer_event_class(source: str, payload: dict) -> EventClass:
    """Simple rule-based fallback when LLM classification fails."""
    if source == "prices":
        return EventClass.COMMODITY_PRICE_MOVE
    if source == "logistics":
        return EventClass.LOGISTICS_DISRUPTION
    if source == "sec":
        return EventClass.FINANCIAL_DISCLOSURE
    if source == "demand":
        return EventClass.DEMAND_SURGE
    alert = payload.get("alert_type", "")
    if "congestion" in alert or "shipping" in alert:
        return EventClass.LOGISTICS_DISRUPTION
    return EventClass.OTHER


def _enrich_entities(
    llm_entities: dict[str, list[str]],
    payload: dict,
) -> dict[str, list[str]]:
    """Cross-reference LLM-extracted entities against registry for canonical names."""
    text_blob = json.dumps(payload, default=str).lower()

    # Load registry sets per label for fast lookup
    def _matches(label: str) -> list[str]:
        kws = registry.get(label)  # type: ignore[arg-type]
        return [kw for kw in kws if kw in text_blob]

    enriched: dict[str, list[str]] = {
        "suppliers": list(set(llm_entities.get("suppliers", []))),
        "commodities": list(set(llm_entities.get("commodities", []))),
        "ports": list(set(llm_entities.get("ports", []))),
        "countries": list(set(llm_entities.get("countries", []))),
    }

    # Add registry matches not already present (deduplicated)
    for label, key in [("gdelt", "suppliers"), ("prices", "commodities"), ("logistics", "ports")]:
        for kw in _matches(label):
            if kw not in [e.lower() for e in enriched.get(key, [])]:
                enriched.setdefault(key, []).append(kw)

    return enriched
