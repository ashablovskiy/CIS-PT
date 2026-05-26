"""Signals API routes — list and retrieve ingested signals."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import select

from apps.api.db.models import Signal, SignalRelevance
from apps.api.db.session import async_session_factory

router = APIRouter()


@router.get("")
async def list_signals(
    hours: int = Query(default=48, ge=1, le=720, description="Lookback window in hours"),
    decision: str | None = Query(default=None, description="Filter: escalate|classify|discard"),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict]:
    """Return recent signals with their relevance decisions."""
    cutoff = datetime.now(UTC) - timedelta(hours=hours)

    async with async_session_factory() as session:
        stmt = (
            select(Signal, SignalRelevance)
            .outerjoin(SignalRelevance, Signal.id == SignalRelevance.signal_id)
            .where(Signal.ingested_at >= cutoff)
            .order_by(Signal.ingested_at.desc())
            .limit(limit)
        )
        if decision:
            stmt = stmt.where(SignalRelevance.decision == decision)

        rows = await session.execute(stmt)
        results = []
        for sig, rel in rows:
            payload = sig.raw_payload or {}
            results.append({
                "id": str(sig.id),
                "source": sig.source,
                "url": sig.url,
                "ingested_at": sig.ingested_at.isoformat() if sig.ingested_at else None,
                "occurred_at": sig.occurred_at.isoformat() if sig.occurred_at else None,
                "title": payload.get("title") or payload.get("headline") or payload.get("ticker", ""),
                "summary": (payload.get("summary") or payload.get("text") or "")[:200],
                "decision": rel.decision if rel else None,
                "llm_score": rel.llm_score if rel else None,
                "rule_score": rel.rule_score if rel else None,
                "reasoning": (rel.reasoning or "")[:150] if rel else None,
            })
        return results
