"""Daily briefs API routes."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from apps.api.db.models import DailyBrief
from apps.api.db.session import async_session_factory

router = APIRouter()


@router.get("/latest")
async def get_latest_brief() -> dict:
    """Return the most recent daily brief."""
    async with async_session_factory() as session:
        row = await session.execute(
            select(DailyBrief).order_by(DailyBrief.brief_date.desc()).limit(1)
        )
        brief = row.scalar_one_or_none()
        if not brief:
            raise HTTPException(status_code=404, detail="No briefs available yet")
        return _fmt_brief(brief)


@router.get("")
async def list_briefs(limit: int = Query(default=10, ge=1, le=60)) -> list[dict]:
    """Return recent daily briefs."""
    async with async_session_factory() as session:
        rows = await session.execute(
            select(DailyBrief).order_by(DailyBrief.brief_date.desc()).limit(limit)
        )
        return [_fmt_brief(b) for b in rows.scalars()]


def _fmt_brief(b: DailyBrief) -> dict:
    return {
        "id": str(b.id),
        "brief_date": b.brief_date.isoformat() if b.brief_date else None,
        "signal_count": b.signal_count,
        "themes": b.themes or {},
        "body_markdown": b.body_markdown or "",
        "flagged_for_assessment": b.flagged_for_assessment or [],
        "created_at": b.created_at.isoformat() if b.created_at else None,
    }
