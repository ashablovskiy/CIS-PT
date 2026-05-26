"""Feedback API — capture analyst actions on assessments (RLHF training data).

When an analyst accepts an assessment (user_action="accept"), a DspyTrainingExample
row is also written so the weekly optimizer has real signal to train on.
Edits (user_action="edit") write a training example with the corrected outputs.
Rejects (user_action="reject") only write the Feedback row (negative signal for Tier 3 eval).
"""

from __future__ import annotations

import json
import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from apps.api.db.models import Assessment, DspyTrainingExample, Feedback, Signal
from apps.api.db.session import async_session_factory

router = APIRouter()
logger = logging.getLogger(__name__)


class FeedbackRequest(BaseModel):
    assessment_id: UUID
    user_action: str          # accept | edit | reject
    corrected_summary: str | None = None
    corrected_impact: dict | None = None
    corrected_entities: dict | None = None
    corrected_clauses: list | None = None
    rationale: str | None = None


@router.post("")
async def submit_feedback(req: FeedbackRequest) -> dict:
    """Record analyst feedback and (for accept/edit) write a DSPy training example."""
    if req.user_action not in ("accept", "edit", "reject"):
        raise HTTPException(status_code=422, detail="user_action must be accept|edit|reject")

    async with async_session_factory() as session:
        # Load assessment + signal for context
        row = await session.execute(
            select(Assessment, Signal)
            .outerjoin(Signal, Assessment.signal_id == Signal.id)
            .where(Assessment.id == req.assessment_id)
        )
        result = row.first()
        if not result:
            raise HTTPException(status_code=404, detail="Assessment not found")
        a, sig = result

        # Build corrected payload (only fields the analyst changed)
        corrected: dict = {}
        if req.corrected_summary:
            corrected["summary"] = req.corrected_summary
        if req.corrected_impact:
            corrected["impact"] = req.corrected_impact
        if req.corrected_entities:
            corrected["affected_entities"] = req.corrected_entities
        if req.corrected_clauses is not None:
            corrected["affected_clauses"] = req.corrected_clauses

        fb = Feedback(
            assessment_id=req.assessment_id,
            user_action=req.user_action,
            original_payload={
                "summary": a.summary,
                "impact": a.impact,
                "affected_entities": a.affected_entities,
                "affected_clauses": a.affected_clauses,
            },
            corrected_payload=corrected or None,
            rationale=req.rationale,
        )
        session.add(fb)
        await session.flush()  # get fb.id before writing training example

        # ── Write DspyTrainingExample for accept or edit ────────────────────
        if req.user_action in ("accept", "edit"):
            training_ex = _build_training_example(
                feedback_id=fb.id,
                assessment=a,
                signal=sig,
                corrected=corrected,
                action=req.user_action,
            )
            if training_ex:
                session.add(training_ex)
                logger.info(
                    "[feedback] Writing DspyTrainingExample for assessment %s (action=%s)",
                    str(req.assessment_id)[:8], req.user_action,
                )

        await session.commit()
        await session.refresh(fb)

    return {
        "id": str(fb.id),
        "status": "recorded",
        "training_example_written": req.user_action in ("accept", "edit"),
    }


def _build_training_example(
    feedback_id,
    assessment: Assessment,
    signal: Signal | None,
    corrected: dict,
    action: str,
) -> DspyTrainingExample | None:
    """Construct a DspyTrainingExample from an accepted/edited assessment.

    Inputs mirror ImpactAssessment.InputField names exactly so they can be fed
    directly to dspy.Example(**inputs) in training_data.load_feedback_examples().
    """
    try:
        # Build signal_summary from raw payload (same logic as synthesizer_node)
        payload = signal.raw_payload or {} if signal else {}
        parts = [f"source={payload.get('source', 'unknown')}"]
        for key in ("title", "label", "alert_type", "signal_type", "ticker"):
            if payload.get(key):
                parts.append(f"{key}={payload[key]}")
        moves = payload.get("moves_pct")
        if moves:
            parts.append(f"price_moves={json.dumps(moves)}")
        summary_text = payload.get("summary", "")
        if summary_text:
            parts.append(f"summary={summary_text[:300]}")
        signal_summary = " | ".join(parts)

        inputs = {
            "signal_summary": signal_summary,
            # graph_context/similar_past/contract_clauses not stored on Assessment,
            # so we leave them empty — the metric will ignore missing inputs
            "graph_context": "{}",
            "similar_past": "[]",
            "contract_clauses": "[]",
            "event_class": _extract_event_class(assessment),
            "impact_dimensions": _extract_impact_dims(assessment),
        }

        # Prefer corrected outputs for edit, original for accept
        out_summary = corrected.get("summary") or assessment.summary or ""
        out_entities = corrected.get("affected_entities") or assessment.affected_entities or {}
        out_clauses  = corrected.get("affected_clauses")
        if out_clauses is None:
            out_clauses = (assessment.affected_clauses or [])
        out_impact = corrected.get("impact") or assessment.impact or {}

        # reasoning_chain stored as list[dict] in DB (after Finalizer serialises it)
        reasoning_raw = assessment.reasoning_chain or []
        if isinstance(reasoning_raw, dict):
            reasoning_raw = reasoning_raw.get("steps", [])

        expected_outputs = {
            "summary": out_summary,
            "affected_entities_json": json.dumps(out_entities),
            "affected_clauses_json": json.dumps(out_clauses),
            "impact_json": json.dumps(out_impact),
            "reasoning_chain_json": json.dumps(reasoning_raw),
            "confidence": assessment.confidence or 0.5,
        }

        # Higher weight for analyst edits (corrected outputs > mere acceptance)
        weight = 1.5 if action == "edit" and corrected else 1.0

        return DspyTrainingExample(
            feedback_id=feedback_id,
            inputs=inputs,
            expected_outputs=expected_outputs,
            weight=weight,
        )

    except Exception as exc:
        logger.warning("[feedback] Failed to build training example: %s", exc)
        return None


def _extract_event_class(a: Assessment) -> str:
    rc = a.reasoning_chain or []
    if isinstance(rc, dict):
        return rc.get("event_class", "other")
    # Some assessments store event_class in agent_version field or not at all
    return "other"


def _extract_impact_dims(a: Assessment) -> str:
    impact = a.impact or {}
    dims = [k for k, v in impact.items() if isinstance(v, dict) and v]
    return ", ".join(dims) if dims else "price, availability"


@router.get("")
async def list_feedback(limit: int = 50) -> list[dict]:
    """Return recent feedback entries (for DSPy training pipeline)."""
    async with async_session_factory() as session:
        rows = await session.execute(
            select(Feedback).order_by(Feedback.created_at.desc()).limit(limit)
        )
        return [
            {
                "id": str(f.id),
                "assessment_id": str(f.assessment_id),
                "user_action": f.user_action,
                "rationale": f.rationale,
                "has_correction": bool(f.corrected_payload),
                "created_at": f.created_at.isoformat() if f.created_at else None,
            }
            for f in rows.scalars()
        ]


@router.get("/stats")
async def feedback_stats() -> dict:
    """Return feedback counts and training example stats."""
    from sqlalchemy import func
    async with async_session_factory() as session:
        counts = await session.execute(
            select(Feedback.user_action, func.count(Feedback.id))
            .group_by(Feedback.user_action)
        )
        action_counts = {row[0]: row[1] for row in counts}

        te_count = await session.execute(
            select(func.count(DspyTrainingExample.id))
        )
        training_examples = te_count.scalar() or 0

    return {
        "accept": action_counts.get("accept", 0),
        "edit": action_counts.get("edit", 0),
        "reject": action_counts.get("reject", 0),
        "total": sum(action_counts.values()),
        "training_examples": training_examples,
        "optimizer_ready": training_examples >= 5,
    }
