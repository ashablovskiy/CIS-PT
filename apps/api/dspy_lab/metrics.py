"""DSPy metric functions for MIPROv2 optimization.

The quality metric scores synthesizer outputs on structural + semantic criteria
without requiring a gold-standard label — useful when feedback is sparse.

Scoring dimensions (each 0.0–1.0, weighted):
  1. entity_specificity  (0.25) — names specific suppliers/plants, not empty arrays
  2. clause_coverage     (0.25) — affected_clauses populated with triggered analysis
  3. reasoning_quality   (0.25) — 4+ steps, each with non-empty grounded_in + inference
  4. calibration         (0.15) — confidence not stuck at 0.5; correlates with entity count
  5. summary_quality     (0.10) — length > 100 chars, domain terms present

When gold-standard outputs are available (feedback-accepted examples),
an additional semantic similarity check boosts the score.
"""

from __future__ import annotations

import json
import re
from typing import Any

import dspy

# Domain terms that indicate high-quality, specific assessments
_DOMAIN_TERMS = {
    "indexation", "force_majeure", "incoterm", "liquidated damage", "ld clause",
    "slot", "delivery obligation", "goes", "winding strip", "transformer", "mva",
    "clause", "parsed_params", "trigger", "allocation", "curtailment", "congestion",
    "siemens", "hitachi", "ge vernova", "eaton", "abb",
}

_SUPPLIER_NAMES = {
    "siemens energy", "hitachi energy", "ge vernova", "eaton", "abb",
    "hyundai", "ls electric", "cogent power", "nippon steel", "jfe steel", "posco",
    "transformers & rectifiers",
}


def _safe_json(raw: Any, default: Any) -> Any:
    if isinstance(raw, (dict, list)):
        return raw
    if not isinstance(raw, str):
        return default
    try:
        return json.loads(raw.strip().lstrip("```json").rstrip("```"))
    except Exception:
        return default


def assessment_quality_metric(example: dspy.Example, prediction: Any, trace=None) -> float:
    """Score a synthesizer prediction on 5 quality dimensions.

    Returns a float in [0, 1]. Used by MIPROv2 as the optimization objective.
    """
    score = 0.0

    # ── 1. Entity specificity (0.25) ─────────────────────────────────────────
    entities = _safe_json(getattr(prediction, "affected_entities_json", "{}"), {})
    suppliers = entities.get("suppliers", [])
    plants = entities.get("plants", [])
    commodities = entities.get("commodities", [])

    named_suppliers = [s for s in suppliers if isinstance(s, str) and len(s) > 2]
    named_plants = [p for p in plants if isinstance(p, str) and len(p) > 2]

    entity_score = min(1.0, (
        min(len(named_suppliers), 3) / 3 * 0.5 +   # up to 3 suppliers → 0.5
        min(len(named_plants), 3) / 3 * 0.3 +       # up to 3 plants → 0.3
        min(len(commodities), 2) / 2 * 0.2          # up to 2 commodities → 0.2
    ))
    score += entity_score * 0.25

    # ── 2. Clause coverage (0.25) ─────────────────────────────────────────────
    clauses = _safe_json(getattr(prediction, "affected_clauses_json", "[]"), [])
    if isinstance(clauses, list) and len(clauses) > 0:
        # Check quality of clause entries
        good_clauses = 0
        for c in clauses:
            if not isinstance(c, dict):
                continue
            has_type = bool(c.get("clause_type"))
            has_detail = len(c.get("detail", "")) > 20
            has_triggered = "triggered" in c
            if has_type and has_detail and has_triggered:
                good_clauses += 1
        clause_score = min(1.0, good_clauses / max(len(clauses), 1))
    else:
        clause_score = 0.0
    score += clause_score * 0.25

    # ── 3. Reasoning quality (0.25) ───────────────────────────────────────────
    chain = _safe_json(getattr(prediction, "reasoning_chain_json", "[]"), [])
    if isinstance(chain, list):
        steps_with_grounding = 0
        steps_with_inference = 0
        for step in chain:
            if not isinstance(step, dict):
                continue
            grounded = step.get("grounded_in", {})
            if isinstance(grounded, dict):
                source = grounded.get("source", "")
            else:
                source = str(grounded)
            if source and len(source) > 10:
                steps_with_grounding += 1
            if step.get("inference") and len(step.get("inference", "")) > 20:
                steps_with_inference += 1

        step_count = len(chain)
        reasoning_score = (
            min(step_count, 4) / 4 * 0.4 +                              # 4+ steps → 0.4
            min(steps_with_grounding, 4) / 4 * 0.4 +                    # grounded → 0.4
            min(steps_with_inference, 4) / 4 * 0.2                      # inference → 0.2
        )
    else:
        reasoning_score = 0.0
    score += reasoning_score * 0.25

    # ── 4. Confidence calibration (0.15) ──────────────────────────────────────
    try:
        confidence = float(getattr(prediction, "confidence", 0.5))
    except (TypeError, ValueError):
        confidence = 0.5

    # Penalise exactly 0.5 (default/lazy), reward calibrated values
    if confidence == 0.5:
        calibration_score = 0.3
    elif 0.3 <= confidence <= 0.95:
        # Higher confidence valid only if entities are specific
        if confidence > 0.75 and len(named_suppliers) >= 2:
            calibration_score = 1.0
        elif confidence > 0.75 and len(named_suppliers) == 0:
            calibration_score = 0.4  # overconfident with no entities
        else:
            calibration_score = 0.8
    else:
        calibration_score = 0.2  # extreme values (0, 1.0) are suspicious
    score += calibration_score * 0.15

    # ── 5. Summary quality (0.10) ─────────────────────────────────────────────
    summary = getattr(prediction, "summary", "") or ""
    summary_lower = summary.lower()

    length_ok = len(summary) >= 100
    has_domain_terms = sum(1 for t in _DOMAIN_TERMS if t in summary_lower) >= 2
    has_supplier_name = any(s in summary_lower for s in _SUPPLIER_NAMES)

    summary_score = (
        (0.4 if length_ok else 0.0) +
        (0.3 if has_domain_terms else 0.0) +
        (0.3 if has_supplier_name else 0.0)
    )
    score += summary_score * 0.10

    # ── Gold-standard bonus (when example has expected outputs) ───────────────
    if hasattr(example, "summary") and example.summary:
        expected_suppliers = set()
        try:
            ex_entities = json.loads(example.affected_entities_json)
            expected_suppliers = {s.lower() for s in ex_entities.get("suppliers", [])}
        except Exception:
            pass

        predicted_lower = " ".join([
            getattr(prediction, "summary", ""),
            getattr(prediction, "affected_entities_json", ""),
        ]).lower()

        overlap = sum(1 for s in expected_suppliers if s in predicted_lower)
        if expected_suppliers:
            gold_bonus = (overlap / len(expected_suppliers)) * 0.1  # up to +0.10 bonus
            score = min(1.0, score + gold_bonus)

    return round(score, 4)
