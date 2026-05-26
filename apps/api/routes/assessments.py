"""Assessments API routes — list and retrieve pipeline outputs."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from apps.api.db.models import Assessment, Signal, SignalRelevance
from apps.api.db.session import async_session_factory

router = APIRouter()


def _fmt_assessment(a: Assessment, sig: Signal | None) -> dict:
    payload = sig.raw_payload or {} if sig else {}
    return {
        "id": str(a.id),
        "signal_id": str(a.signal_id) if a.signal_id else None,
        "status": a.status,
        "confidence": a.confidence,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "summary": a.summary,
        "affected_entities": a.affected_entities or {},
        "affected_clauses": a.affected_clauses or [],
        "impact": a.impact or {},
        "reasoning_chain": a.reasoning_chain or [],
        "agent_version": a.agent_version,
        # Signal context
        "signal": {
            "source": sig.source if sig else None,
            "url": sig.url if sig else None,
            "title": payload.get("title") or payload.get("headline") or payload.get("ticker", ""),
            "occurred_at": sig.occurred_at.isoformat() if sig and sig.occurred_at else None,
        } if sig else None,
    }


@router.get("")
async def list_assessments(
    status: str | None = Query(default=None, description="Filter: complete|needs_review|error"),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[dict]:
    """Return recent assessments ordered by creation time."""
    async with async_session_factory() as session:
        stmt = (
            select(Assessment, Signal)
            .outerjoin(Signal, Assessment.signal_id == Signal.id)
            .order_by(Assessment.created_at.desc())
            .limit(limit)
        )
        if status:
            stmt = stmt.where(Assessment.status == status)

        rows = await session.execute(stmt)
        return [_fmt_assessment(a, sig) for a, sig in rows]


@router.get("/{assessment_id}")
async def get_assessment(assessment_id: UUID) -> dict:
    """Return a single assessment with full detail."""
    async with async_session_factory() as session:
        row = await session.execute(
            select(Assessment, Signal)
            .outerjoin(Signal, Assessment.signal_id == Signal.id)
            .where(Assessment.id == assessment_id)
        )
        result = row.first()
        if not result:
            raise HTTPException(status_code=404, detail="Assessment not found")
        a, sig = result
        return _fmt_assessment(a, sig)
