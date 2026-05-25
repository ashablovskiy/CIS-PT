"""Node 7 — Finalizer: persist assessment to Neon Postgres.

Writes two rows:
  1. classified_signals — entity classification + Voyage embedding
  2. assessments — full structured impact assessment

Status:
  complete      — critic passed, ready for frontend
  needs_review  — critic flagged issues; shows in human review queue
  error         — synthesizer failed; partial data stored for debugging
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from apps.api.agents.state import AssessmentState
from apps.api.classify.schemas import EventClass
from apps.api.db.models import Assessment, ClassifiedSignal
from apps.api.db.session import async_session_factory

logger = logging.getLogger(__name__)


def _triage_data(state: AssessmentState) -> dict[str, Any]:
    for item in state.graph_context:
        if "_triage" in item:
            return item["_triage"]
    return {}


async def finalizer_node(state: AssessmentState) -> AssessmentState:
    """Persist ClassifiedSignal and Assessment rows to Neon."""
    triage = _triage_data(state)

    # Determine status
    if state.errors and not state.summary:
        status = "error"
    elif not state.critic_passed:
        status = "needs_review"
    else:
        status = "complete"

    embedding = getattr(state, "_embedding", None)

    async with async_session_factory() as session:
        async with session.begin():

            # ── 1. Upsert classified_signals ─────────────────────────────────
            cs_values: dict[str, Any] = {
                "signal_id": state.signal_id,
                "event_class": triage.get("event_class", EventClass.OTHER),
                "geo_tags": triage.get("geo_tags", []),
                "graph_entities": triage.get("graph_entities", {}),
                "commodities": triage.get("commodities", []),
                "impact_dimensions": triage.get("impact_dimensions", []),
                "confidence": triage.get("confidence", 0.0),
                "classifier_version": state.agent_version,
            }
            if embedding is not None:
                cs_values["embedding"] = embedding

            cs_stmt = (
                insert(ClassifiedSignal)
                .values(**cs_values)
                .on_conflict_do_update(
                    index_elements=["signal_id"],
                    set_={k: v for k, v in cs_values.items() if k != "signal_id"},
                )
            )
            await session.execute(cs_stmt)

            # ── 2. Insert assessment ──────────────────────────────────────────
            reasoning_data = [r.model_dump() for r in state.reasoning_chain]

            # Build notes including critic feedback
            notes: dict[str, Any] = {}
            if state.critic_notes:
                notes["critic_notes"] = state.critic_notes
            if state.errors:
                notes["errors"] = state.errors

            assess_stmt = (
                insert(Assessment)
                .values(
                    signal_id=state.signal_id,
                    agent_version=state.agent_version,
                    dspy_program_version=state.dspy_program_version,
                    summary=state.summary,
                    affected_entities=state.affected_entities,
                    affected_clauses={"clauses": state.affected_clauses},
                    impact=state.impact_by_dimension,
                    reasoning_chain={"steps": reasoning_data},
                    confidence=state.confidence,
                    status=status,
                    raw_trace_id=state.trace_id,
                )
                .on_conflict_do_nothing()  # idempotent re-runs
            )
            result = await session.execute(assess_stmt)

    logger.info(
        "[finalizer] Persisted | signal_id=%s status=%s confidence=%.2f critic=%s",
        state.signal_id, status, state.confidence, state.critic_passed,
    )
    return state
