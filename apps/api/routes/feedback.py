"""Feedback API — capture analyst actions on assessments (RLHF training data)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from apps.api.db.models import Assessment, Feedback
from apps.api.db.session import async_session_factory

router = APIRouter()


class FeedbackRequest(BaseModel):
    assessment_id: UUID
    user_action: str  # accept | edit | reject
    corrected_summary: str | None = None
    corrected_impact: dict | None = None
    rationale: str | None = None


@router.post("")
async def submit_feedback(req: FeedbackRequest) -> dict:
    """Record analyst feedback on an assessment."""
    async with async_session_factory() as session:
        # Verify assessment exists
        a = await session.get(Assessment, req.assessment_id)
        if not a:
            raise HTTPException(status_code=404, detail="Assessment not found")

        corrected = {}
        if req.corrected_summary:
            corrected["summary"] = req.corrected_summary
        if req.corrected_impact:
            corrected["impact"] = req.corrected_impact

        fb = Feedback(
            assessment_id=req.assessment_id,
            user_action=req.user_action,
            original_payload={
                "summary": a.summary,
                "impact": a.impact,
                "affected_clauses": a.affected_clauses,
            },
            corrected_payload=corrected or None,
            rationale=req.rationale,
        )
        session.add(fb)
        await session.commit()
        await session.refresh(fb)
        return {"id": str(fb.id), "status": "recorded"}


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
