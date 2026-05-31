"""Node 5 — Synthesizer: Claude Opus + DSPy impact assessment.

Combines triage classification, Neo4j graph context, similar past signals,
and contract clause matches into a structured impact assessment.

Uses DSPy Predict with a typed Signature compiled by MIPROv2 (Week 5).
At startup, loads the latest compiled program from dspy_lab/compiled/ if
available, falling back to the baseline predictor.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import dspy

from apps.api.agents.state import AssessmentState, ReasoningStep
from apps.api.settings import settings

logger = logging.getLogger(__name__)

# ── DSPy setup ────────────────────────────────────────────────────────────────

os.environ.setdefault("ANTHROPIC_API_KEY", settings.anthropic_api_key)

_OPUS = "claude-opus-4-5-20251101"

# Configure DSPy to use Claude Opus via LiteLLM
dspy.configure(
    lm=dspy.LM(
        model=f"anthropic/{_OPUS}",
        api_key=settings.anthropic_api_key,
        max_tokens=2048,
        temperature=0.1,
    )
)


class ImpactAssessment(dspy.Signature):
    """
    You are a senior power transformer procurement analyst.

    Given a supply-chain signal, related Neo4j graph context (affected suppliers,
    plants, shipping routes), similar past events, and relevant contract clauses,
    produce a structured impact assessment.

    Your assessment must:
    - Identify specifically which suppliers, plants, ports, and shipping lanes are affected
    - For each affected contract clause, state whether a trigger threshold is met
      (use parsed_params like trigger_threshold_pct, force_majeure_events list)
    - Quantify impact across dimensions: price, availability, lead_time, logistics, regulatory, demand
    - Provide a 3-5 step reasoning chain, each step citing its source
    - Be calibrated: high confidence only when evidence is specific and direct
    """

    signal_summary: str = dspy.InputField(desc="Signal source, type, and key facts")
    graph_context: str = dspy.InputField(desc="JSON: affected suppliers, plants, ports, lanes from Neo4j")
    similar_past: str = dspy.InputField(desc="JSON: similar past signals and their assessed impacts")
    contract_clauses: str = dspy.InputField(desc="JSON: relevant contract clauses with parsed parameters")
    event_class: str = dspy.InputField(desc="Classified event type")
    impact_dimensions: str = dspy.InputField(desc="Comma-separated impact dimensions from triage")

    summary: str = dspy.OutputField(desc="2-4 sentence executive summary of the impact")
    affected_entities_json: str = dspy.OutputField(
        desc="JSON object: {suppliers: [...], plants: [...], ports: [...], commodities: [...]}"
    )
    affected_clauses_json: str = dspy.OutputField(
        desc="JSON array of {contract_id, clause_type, triggered: bool, detail: str}"
    )
    impact_json: str = dspy.OutputField(
        desc="JSON object: {price: {direction, magnitude_pct, confidence}, availability: {...}, lead_time: {...}, ...}"
    )
    reasoning_chain_json: str = dspy.OutputField(
        desc="JSON array of {step, claim, grounded_in: {source}, inference}"
    )
    confidence: float = dspy.OutputField(desc="Overall confidence 0.0-1.0")


def _load_predictor() -> dspy.Predict:
    """Load compiled program if available, else return baseline predictor."""
    try:
        from apps.api.dspy_lab.optimizer import load_compiled_program
        compiled = load_compiled_program()
        if compiled is not None:
            return compiled
    except Exception as exc:
        logger.debug("[synthesizer] Could not load compiled program: %s", exc)
    return dspy.Predict(ImpactAssessment)

_predictor = _load_predictor()


def _triage_data(state: AssessmentState) -> dict[str, Any]:
    for item in state.graph_context:
        if "_triage" in item:
            return item["_triage"]
    return {}


def _build_signal_summary(state: AssessmentState) -> str:
    p = state.signal_payload
    parts = [f"source={p.get('source', 'unknown')}"]
    for key in ("title", "label", "alert_type", "signal_type", "ticker"):
        if p.get(key):
            parts.append(f"{key}={p[key]}")
    moves = p.get("moves_pct")
    if moves:
        parts.append(f"price_moves={json.dumps(moves)}")
    summary = p.get("summary", "")
    if summary:
        parts.append(f"summary={summary[:300]}")
    return " | ".join(parts)


async def synthesizer_node(state: AssessmentState) -> AssessmentState:
    """Generate the full structured impact assessment using DSPy + Claude Opus."""
    if not state.triage_passed:
        return state

    triage = _triage_data(state)

    # Build inputs
    graph_ctx = [c for c in state.graph_context if "_triage" not in c]
    signal_summary = _build_signal_summary(state)

    # ── Network-state context: frame this signal by the ecosystem condition ──
    # An identical signal means something different in a fragile vs. resilient
    # network. We append a compact state line so the synthesizer can calibrate.
    try:
        from apps.api.network.state import compute_network_state
        ns = await compute_network_state(window_hours=720, top_n=5)
        top_actors = ", ".join(a["actor"] for a in ns["top_actors"][:4])
        hotspots = ", ".join(h["actor"] for h in ns["hotspots"][:3]) or "none"
        signal_summary += (
            f" | NETWORK_STATE: {ns['health_label']} (fragility {ns['health_index']:.2f}); "
            f"most-influential: {top_actors}; pressure hotspots: {hotspots}"
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("[synthesizer] network state unavailable: %s", exc)

    graph_context_str = json.dumps(graph_ctx, default=str)[:3000]
    similar_past_str = json.dumps(state.similar_past, default=str)[:1500]
    contract_str = json.dumps(state.contract_matches, default=str)[:2000]
    event_class = triage.get("event_class", "other")
    impact_dims = ", ".join(triage.get("impact_dimensions", ["price", "availability"]))

    logger.info(
        "[synthesizer] Running Opus assessment | event=%s graph_entries=%d clauses=%d",
        event_class, len(graph_ctx), len(state.contract_matches),
    )

    try:
        result = _predictor(
            signal_summary=signal_summary,
            graph_context=graph_context_str,
            similar_past=similar_past_str,
            contract_clauses=contract_str,
            event_class=event_class,
            impact_dimensions=impact_dims,
        )

        # Parse JSON outputs with fallbacks
        affected_entities = _safe_json(result.affected_entities_json, {
            "suppliers": [], "plants": [], "ports": [], "commodities": []
        })
        affected_clauses = _safe_json(result.affected_clauses_json, [])
        impact = _safe_json(result.impact_json, {})
        reasoning_raw = _safe_json(result.reasoning_chain_json, [])

        # Build typed ReasoningStep list
        reasoning_chain = []
        for i, step in enumerate(reasoning_raw if isinstance(reasoning_raw, list) else []):
            try:
                reasoning_chain.append(ReasoningStep(
                    step=step.get("step", i + 1),
                    claim=step.get("claim", ""),
                    grounded_in=step.get("grounded_in", {}),
                    inference=step.get("inference", ""),
                ))
            except Exception:
                pass

        confidence = float(result.confidence) if result.confidence else 0.5
        confidence = max(0.0, min(1.0, confidence))

        # ── XGBoost price impact enrichment ────────────────────────────────
        # Augment the LLM's price dimension with a data-driven magnitude estimate.
        # This runs even when the model falls back to rule-based estimation.
        try:
            from apps.api.ml.price_impact import price_impact_estimator
            commodities = triage.get("commodities", [])
            ml_estimate = price_impact_estimator.predict(
                signal_payload=state.signal_payload,
                event_class=event_class,
                commodities=commodities or None,
            )
            # Merge ML estimate into the price dimension (only enrich, don't overwrite)
            if "price" not in impact:
                impact["price"] = {}
            price_dim = impact["price"]
            # Prefer LLM direction/magnitude if present; add ML as secondary signal
            if not price_dim.get("direction"):
                price_dim["direction"] = ml_estimate.direction
            if not price_dim.get("magnitude_pct"):
                price_dim["magnitude_pct"] = ml_estimate.magnitude_pct
            price_dim["ml_magnitude_pct"] = ml_estimate.magnitude_pct
            price_dim["ml_direction"] = ml_estimate.direction
            price_dim["ml_confidence"] = ml_estimate.confidence
            price_dim["ml_model"] = ml_estimate.model_version
            price_dim["ml_used"] = ml_estimate.used_ml
            logger.info(
                "[synthesizer] ML price estimate: direction=%s magnitude=%.1f%% model=%s",
                ml_estimate.direction, ml_estimate.magnitude_pct, ml_estimate.model_version,
            )
        except Exception as ml_exc:
            logger.debug("[synthesizer] ML enrichment skipped: %s", ml_exc)

        state.summary = result.summary or ""
        state.affected_entities = affected_entities
        state.affected_clauses = affected_clauses if isinstance(affected_clauses, list) else []
        state.impact_by_dimension = impact
        state.reasoning_chain = reasoning_chain
        state.confidence = confidence

        logger.info(
            "[synthesizer] Assessment complete | confidence=%.2f entities=%s",
            confidence,
            {k: len(v) for k, v in affected_entities.items() if isinstance(v, list)},
        )

    except Exception as exc:
        logger.exception("[synthesizer] DSPy call failed: %s", exc)
        state.errors.append(f"synthesizer_error: {exc}")
        # Minimal fallback so pipeline can still persist something
        state.summary = f"Assessment generation failed: {exc}"
        state.confidence = 0.0

    return state


def _safe_json(raw: Any, default: Any) -> Any:
    if isinstance(raw, (dict, list)):
        return raw
    if not isinstance(raw, str):
        return default
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        return json.loads(raw.strip())
    except Exception:
        return default
