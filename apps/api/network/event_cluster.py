"""Cross-source event clustering for ANT pressure deduplication.

Problem: when 5 news outlets each report the same factory shutdown, the system
stores 5 separate signals that each contribute full pressure to the relevant
ANT node — inflating it 5×.

Fix: at ingest time, each new signal is embedded (Voyage AI, document type) and
checked against recently-stored signals within a 24-hour window. If a
semantically similar signal (cosine similarity > CLUSTER_THRESHOLD) already
exists from a *different* source, the new signal is assigned that signal's
event_id instead of its own. When ANT pressure is computed, it groups by
event_id and takes the MAX pressure per cluster rather than summing all, so
the same real-world event counts once regardless of how many outlets cover it.

The event_id on signals is a self-referencing FK:
  - NULL          legacy / embedding unavailable
  - event_id = id  this signal IS the canonical event
  - event_id = X   X is the canonical signal for this event
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Cosine similarity must exceed this to be considered the same real-world event.
# Higher than vector_retriever's 0.75 (historical context) because we need
# high confidence before suppressing a signal's pressure contribution.
CLUSTER_THRESHOLD = 0.85

# How far back to look for a matching event cluster.
# 72h (3 days) so a follow-up article published a day or two after the original
# coverage still attaches to the same event line rather than spawning a new one.
CLUSTER_WINDOW_HOURS = 72


def payload_to_cluster_text(payload: dict[str, Any]) -> str:
    """Build a compact text string for event-clustering embedding.

    Pulls the most identifying fields from the raw signal payload so that two
    articles about the same event (same entities, same development) embed close
    together in vector space, while articles about different events do not.
    """
    parts = []
    for key in (
        "title", "summary", "label", "themes",
        "organizations", "ticker", "company",
        "signal_type", "alert_type",
    ):
        val = payload.get(key)
        if val and isinstance(val, str):
            parts.append(val)
    return " | ".join(parts)[:2000]


async def find_event_cluster(
    session: AsyncSession,
    signal_id: uuid.UUID,
    embedding: list[float],
    occurred_at: datetime,
    source: str,
    *,
    threshold: float = CLUSTER_THRESHOLD,
    window_hours: int = CLUSTER_WINDOW_HOURS,
) -> uuid.UUID:
    """Return the canonical event_id for a signal.

    Queries the signals table for an already-stored signal that:
      - arrived within `window_hours` of this signal
      - comes from a DIFFERENT source
      - has cosine similarity > `threshold` with this signal's embedding

    If found, returns that signal's event_id (or its own id if event_id is
    NULL, meaning it is itself canonical). This chains correctly:
      Reuters (t=0)   → no match → event_id = Reuters.id  (canonical)
      Bloomberg (t+1h)→ finds Reuters (sim=0.92) → event_id = Reuters.id
      FT (t+2h)       → finds Reuters (sim=0.91) → event_id = Reuters.id

    If no match is found, returns `signal_id` itself — this signal IS the
    canonical event and will serve as the anchor for future duplicates.

    IMPORTANT: the caller must flush the session before calling this so that
    sibling signals inserted in the same batch are visible for within-batch
    cross-source dedup.
    """
    if not embedding:
        return signal_id

    cutoff = occurred_at - timedelta(hours=window_hours)

    # Inline the vector literal — asyncpg cannot bind float[] as vector type
    # (same pattern as vector_retriever.py).  Embedding is a trusted Voyage AI
    # float array, so direct interpolation is safe.
    vec_literal = "[" + ",".join(str(v) for v in embedding) + "]"

    result = await session.execute(
        text(f"""
            SELECT id, event_id
            FROM signals
            WHERE occurred_at >= :cutoff
              AND source       != :source
              AND id           != :signal_id
              AND embedding    IS NOT NULL
              AND 1 - (embedding <=> '{vec_literal}'::vector) > :threshold
            ORDER BY embedding <=> '{vec_literal}'::vector
            LIMIT 1
        """),
        {
            "cutoff": cutoff,
            "source": source,
            "signal_id": str(signal_id),
            "threshold": threshold,
        },
    )
    row = result.fetchone()

    if row is None:
        # No similar signal found — this signal is the canonical event.
        return signal_id

    matched_id, matched_event_id = row
    # If the matched signal already has an event_id (canonical pointer set),
    # follow it.  Otherwise the matched signal itself is the canonical event.
    canonical = matched_event_id if matched_event_id is not None else matched_id
    logger.debug(
        "[event_cluster] signal=%s → cluster canonical=%s (matched=%s, sim>%.2f)",
        signal_id, canonical, matched_id, threshold,
    )
    return canonical
