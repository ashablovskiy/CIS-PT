"""LangGraph impact assessment pipeline — 7 nodes.

Graph topology:
    triage → graph_retriever → vector_retriever → contract_scanner
           → synthesizer → critic → finalizer

Short-circuits at triage if signal is not assessment-worthy.

Entry point:
    from apps.api.assess.pipeline import run_assessment
    state = await run_assessment(signal_id, signal_payload)
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID, uuid4

from langgraph.graph import END, START, StateGraph

from apps.api.agents.state import AssessmentState
from apps.api.assess.nodes.contract_scanner import contract_scanner_node
from apps.api.assess.nodes.critic import critic_node
from apps.api.assess.nodes.finalizer import finalizer_node
from apps.api.assess.nodes.graph_retriever import graph_retriever_node
from apps.api.assess.nodes.synthesizer import synthesizer_node
from apps.api.assess.nodes.triage import triage_node
from apps.api.assess.nodes.vector_retriever import vector_retriever_node

logger = logging.getLogger(__name__)


# ── Graph definition ──────────────────────────────────────────────────────────

def _should_continue(state: AssessmentState) -> str:
    """After triage: proceed or short-circuit to END."""
    return "graph_retriever" if state.triage_passed else END


def _build_graph() -> Any:
    builder = StateGraph(AssessmentState)

    builder.add_node("triage",           triage_node)
    builder.add_node("graph_retriever",  graph_retriever_node)
    builder.add_node("vector_retriever", vector_retriever_node)
    builder.add_node("contract_scanner", contract_scanner_node)
    builder.add_node("synthesizer",      synthesizer_node)
    builder.add_node("critic",           critic_node)
    builder.add_node("finalizer",        finalizer_node)

    builder.add_edge(START, "triage")
    builder.add_conditional_edges("triage", _should_continue)
    builder.add_edge("graph_retriever",  "vector_retriever")
    builder.add_edge("vector_retriever", "contract_scanner")
    builder.add_edge("contract_scanner", "synthesizer")
    builder.add_edge("synthesizer",      "critic")
    builder.add_edge("critic",           "finalizer")
    builder.add_edge("finalizer",        END)

    return builder.compile()


# Compiled graph — module-level singleton
_graph = _build_graph()


# ── Public API ────────────────────────────────────────────────────────────────

async def run_assessment(
    signal_id: UUID,
    signal_payload: dict[str, Any],
    trace_id: str | None = None,
) -> AssessmentState:
    """Run the full 7-node assessment pipeline for a single escalated signal.

    Args:
        signal_id:      UUID of the signal row in Neon
        signal_payload: raw_payload dict from the signals table
        trace_id:       optional trace identifier for observability

    Returns:
        Final AssessmentState with all node outputs populated.
    """
    initial = AssessmentState(
        signal_id=signal_id,
        signal_payload=signal_payload,
        trace_id=trace_id or str(uuid4()),
    )

    logger.info(
        "[pipeline] Starting assessment | signal_id=%s source=%s trace=%s",
        signal_id,
        signal_payload.get("source", "?"),
        initial.trace_id,
    )

    result = await _graph.ainvoke(initial)
    # LangGraph returns a dict when state is Pydantic model — reconstruct
    if isinstance(result, dict):
        final_state = AssessmentState.model_validate(result)
    else:
        final_state = result

    logger.info(
        "[pipeline] Done | triage=%s critic=%s confidence=%.2f errors=%d",
        final_state.triage_passed,
        final_state.critic_passed,
        final_state.confidence,
        len(final_state.errors),
    )
    return final_state


async def run_assessments_for_escalated(lookback_hours: int = 2) -> list[AssessmentState]:
    """Fetch all escalated signals without an assessment and run the pipeline.

    Called by the Inngest cron or manual backfill script.
    """
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import select, text

    from apps.api.db.models import Assessment, Signal, SignalRelevance
    from apps.api.db.session import async_session_factory

    cutoff = datetime.now(UTC) - timedelta(hours=lookback_hours)

    async with async_session_factory() as session:
        rows = await session.execute(
            select(Signal.id, Signal.raw_payload, Signal.source)
            .join(SignalRelevance, Signal.id == SignalRelevance.signal_id)
            .outerjoin(Assessment, Signal.id == Assessment.signal_id)
            .where(
                SignalRelevance.decision == "escalate",
                Signal.ingested_at >= cutoff,
                Assessment.id.is_(None),  # not yet assessed
            )
            .order_by(Signal.ingested_at.desc())
            .limit(50)
        )
        signals = rows.fetchall()

    logger.info("[pipeline] %d unassessed escalated signals to process", len(signals))

    results = []
    for signal_id, raw_payload, source in signals:
        try:
            state = await run_assessment(signal_id, raw_payload)
            results.append(state)
        except Exception as exc:
            logger.exception("[pipeline] Failed for signal %s: %s", signal_id, exc)

    return results
