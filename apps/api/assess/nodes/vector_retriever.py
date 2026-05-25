"""Node 3 — Vector Retriever: pgvector similarity search for past signals.

Embeds the current signal with Voyage AI and searches classified_signals
for similar past events, returning the top-k with their assessment summaries.
Gives the synthesizer historical precedent to calibrate impact estimates.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import text

from apps.api.agents.state import AssessmentState
from apps.api.assess.embeddings import embed_query
from apps.api.db.session import async_session_factory

logger = logging.getLogger(__name__)

_TOP_K = 5
_MIN_SIMILARITY = 0.75  # cosine similarity threshold


def _signal_to_text(payload: dict[str, Any]) -> str:
    """Flatten a signal payload into a single searchable string."""
    parts = []
    for key in ("title", "summary", "label", "themes", "organizations",
                "ticker", "company", "signal_type", "alert_type"):
        val = payload.get(key)
        if val and isinstance(val, str):
            parts.append(val)
    moves = payload.get("moves_pct")
    if moves:
        parts.append(f"price moves: {json.dumps(moves)}")
    return " | ".join(parts)[:2000]


async def vector_retriever_node(state: AssessmentState) -> AssessmentState:
    """Find similar past signals using pgvector cosine similarity."""
    if not state.triage_passed:
        return state

    signal_text = _signal_to_text(state.signal_payload)
    if not signal_text.strip():
        logger.debug("[vector_retriever] Empty signal text — skipping")
        return state

    try:
        embedding = await embed_query(signal_text)
    except Exception as exc:
        logger.warning("[vector_retriever] Embedding failed: %s — skipping", exc)
        state.errors.append(f"vector_retriever_embed_error: {exc}")
        return state

    # Store embedding for later use in finalizer (saves a second API call)
    state._embedding = embedding  # type: ignore[attr-defined]

    try:
        async with async_session_factory() as session:
            # Search classified_signals joined to assessments for context
            rows = await session.execute(text("""
                SELECT
                    cs.signal_id,
                    s.source,
                    s.raw_payload,
                    sr.decision,
                    a.summary        AS assessment_summary,
                    a.impact         AS assessment_impact,
                    1 - (cs.embedding <=> CAST(:embedding AS vector)) AS similarity
                FROM classified_signals cs
                JOIN signals s ON s.id = cs.signal_id
                LEFT JOIN signal_relevance sr ON sr.signal_id = cs.signal_id
                LEFT JOIN assessments a ON a.signal_id = cs.signal_id
                WHERE cs.embedding IS NOT NULL
                  AND cs.signal_id != :current_id
                  AND 1 - (cs.embedding <=> CAST(:embedding AS vector)) > :min_sim
                ORDER BY cs.embedding <=> CAST(:embedding AS vector)
                LIMIT :top_k
            """), {
                "embedding": str(embedding),
                "current_id": str(state.signal_id),
                "min_sim": _MIN_SIMILARITY,
                "top_k": _TOP_K,
            })

            similar: list[dict[str, Any]] = []
            for row in rows.mappings():
                similar.append({
                    "signal_id": str(row["signal_id"]),
                    "source": row["source"],
                    "similarity": round(float(row["similarity"]), 3),
                    "decision": row["decision"],
                    "assessment_summary": row["assessment_summary"],
                    "assessment_impact": row["assessment_impact"],
                    "payload_preview": json.dumps(
                        row["raw_payload"], default=str
                    )[:200] if row["raw_payload"] else "",
                })

        state.similar_past = similar
        logger.info("[vector_retriever] Found %d similar past signals (threshold=%.2f)",
                    len(similar), _MIN_SIMILARITY)

    except Exception as exc:
        logger.warning("[vector_retriever] DB search failed: %s", exc)
        state.errors.append(f"vector_retriever_search_error: {exc}")

    return state
