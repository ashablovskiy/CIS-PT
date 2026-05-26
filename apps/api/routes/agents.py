"""Agent observability routes — last run stats from signals table."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Query
from sqlalchemy import func, select, text

from apps.api.db.models import Signal, SignalRelevance
from apps.api.db.session import async_session_factory

router = APIRouter()

_SOURCES = ["prices", "gdelt", "logistics", "press", "demand", "sec"]


@router.get("/status")
async def agents_status(hours: int = Query(default=24, ge=1, le=168)) -> list[dict]:
    """Return per-source ingestion stats for the last N hours."""
    cutoff = datetime.now(UTC) - timedelta(hours=hours)

    async with async_session_factory() as session:
        rows = await session.execute(
            select(
                Signal.source,
                func.count(Signal.id).label("total"),
                func.max(Signal.ingested_at).label("last_seen"),
            )
            .where(Signal.ingested_at >= cutoff)
            .group_by(Signal.source)
        )
        by_source: dict[str, dict] = {}
        for source, total, last_seen in rows:
            by_source[source] = {
                "source": source,
                "total": total,
                "last_seen": last_seen.isoformat() if last_seen else None,
                "escalated": 0,
                "discarded": 0,
            }

        # Decision breakdown
        drows = await session.execute(
            select(
                Signal.source,
                SignalRelevance.decision,
                func.count(Signal.id).label("cnt"),
            )
            .join(SignalRelevance, Signal.id == SignalRelevance.signal_id)
            .where(Signal.ingested_at >= cutoff)
            .group_by(Signal.source, SignalRelevance.decision)
        )
        for source, decision, cnt in drows:
            if source not in by_source:
                continue
            if decision == "escalate":
                by_source[source]["escalated"] = cnt
            elif decision == "discard":
                by_source[source]["discarded"] = cnt

        return sorted(by_source.values(), key=lambda x: x["source"])
