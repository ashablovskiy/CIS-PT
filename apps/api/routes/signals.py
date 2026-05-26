"""Signals API routes — list and retrieve ingested signals."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import func, select

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


@router.get("/stats")
async def signal_stats(
    hours: int = Query(default=168, ge=1, le=720, description="Lookback window in hours (default 7 days)"),
) -> dict:
    """Return signal volume stats: by source, by decision, and hourly buckets for chart."""
    cutoff = datetime.now(UTC) - timedelta(hours=hours)

    async with async_session_factory() as session:
        # All signals + their relevance in window
        stmt = (
            select(Signal, SignalRelevance)
            .outerjoin(SignalRelevance, Signal.id == SignalRelevance.signal_id)
            .where(Signal.ingested_at >= cutoff)
            .order_by(Signal.ingested_at.asc())
        )
        rows = list(await session.execute(stmt))

    # Aggregate by source and decision
    by_source: dict[str, int] = defaultdict(int)
    by_decision: dict[str, int] = defaultdict(int)

    # Hourly buckets: group by day if > 48h window, else by hour
    use_daily = hours > 48
    bucket_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for sig, rel in rows:
        src = sig.source or "unknown"
        decision = (rel.decision if rel else None) or "unscored"
        by_source[src] += 1
        by_decision[decision] += 1

        if sig.ingested_at:
            ts = sig.ingested_at
            if use_daily:
                bucket = ts.strftime("%Y-%m-%d")
            else:
                bucket = ts.strftime("%Y-%m-%dT%H:00")
            bucket_counts[bucket][src] += 1

    # Build sorted time series for chart
    all_sources = list(by_source.keys())
    time_series = [
        {"time": t, **{src: bucket_counts[t].get(src, 0) for src in all_sources}}
        for t in sorted(bucket_counts.keys())
    ]

    return {
        "window_hours": hours,
        "total": len(rows),
        "by_source": dict(by_source),
        "by_decision": dict(by_decision),
        "sources": all_sources,
        "time_series": time_series,
    }
