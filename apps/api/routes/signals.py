"""Signals API routes — list, retrieve, and manually score ingested signals."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException
from fastapi import Query as Q
from pydantic import BaseModel, Field
from sqlalchemy import select

from apps.api.db.models import ClassifiedSignal, Signal, SignalRelevance
from apps.api.db.session import async_session_factory

router = APIRouter()


# ── Ticker → friendly commodity name (UI label only) ──────────────────────────
_TICKER_NAMES: dict[str, str] = {
    "HG=F":  "Copper",
    "ALI=F": "Aluminum",
    "HRC=F": "Steel (HRC)",
    "CL=F":  "Crude Oil",
    "^BDI":  "Baltic Dry Index",
}


def _price_movement(payload: dict) -> str | None:
    """Return a human-readable price movement string, e.g. 'Aluminum -8.3% / 24h'."""
    moves: dict = payload.get("moves_pct", {})
    if not moves:
        return None
    commodity = payload.get("commodity") or _TICKER_NAMES.get(payload.get("ticker", ""), "")

    for period_label, period_key in [("24h", "1d"), ("5d", "5d"), ("30d", "30d")]:
        if period_key in payload.get("triggered_thresholds", moves.keys()):
            pct = moves.get(period_key)
            if pct is not None:
                sign = "+" if pct > 0 else ""
                return f"{commodity} {sign}{pct:.1f}% / {period_label}"

    largest_key = max(moves, key=lambda k: abs(moves[k]))
    pct = moves[largest_key]
    sign = "+" if pct > 0 else ""
    return f"{commodity} {sign}{pct:.1f}%"


def _signal_description(source: str, payload: dict, title: str, summary: str) -> str:
    """Derive a short, human-readable signal description."""
    if source == "prices":
        label = payload.get("label") or _TICKER_NAMES.get(payload.get("ticker", ""), title)
        move = _price_movement(payload)
        return f"{label}" + (f" — {move}" if move else "")
    if title and len(title) > 4:
        return title[:140]
    if summary:
        return summary[:140]
    return "No description"


def _effective_score(rel: SignalRelevance | None) -> float | None:
    """Return analyst override if set, otherwise LLM score."""
    if rel is None:
        return None
    if rel.analyst_score is not None:
        return rel.analyst_score
    return rel.llm_score


# ── List signals ───────────────────────────────────────────────────────────────

@router.get("")
async def list_signals(
    hours: int = Q(default=48, ge=1, le=720),
    decision: str | None = Q(default=None),
    limit: int = Q(default=200, ge=1, le=500),
    min_score: float | None = Q(default=None, ge=0, le=1),
    max_tier: int | None = Q(default=None, ge=1, le=4),
) -> list[dict]:
    """Return recent signals with enriched metadata for the feed view."""
    cutoff = datetime.now(UTC) - timedelta(hours=hours)

    async with async_session_factory() as session:
        stmt = (
            select(Signal, SignalRelevance, ClassifiedSignal)
            .outerjoin(SignalRelevance, Signal.id == SignalRelevance.signal_id)
            .outerjoin(ClassifiedSignal, Signal.id == ClassifiedSignal.signal_id)
            .where(Signal.ingested_at >= cutoff)
            .order_by(Signal.ingested_at.desc())
            .limit(limit)
        )
        if decision:
            stmt = stmt.where(SignalRelevance.decision == decision)
        if min_score is not None:
            stmt = stmt.where(SignalRelevance.llm_score >= min_score)
        if max_tier is not None:
            stmt = stmt.where(SignalRelevance.impact_tier <= max_tier)

        rows = await session.execute(stmt)
        results = []
        for sig, rel, cs in rows:
            payload = sig.raw_payload or {}
            title   = payload.get("title") or payload.get("headline") or payload.get("ticker", "")
            summary = (payload.get("summary") or payload.get("text") or "")[:200]

            results.append({
                # ── I. General ───────────────────────────────────────────────
                "id":            str(sig.id),
                "source":        sig.source,
                "url":           sig.url,
                "ingested_at":   sig.ingested_at.isoformat() if sig.ingested_at else None,
                "occurred_at":   sig.occurred_at.isoformat() if sig.occurred_at else None,
                "description":   _signal_description(sig.source, payload, title, summary),
                "price_move":    _price_movement(payload) if sig.source == "prices" else None,
                # ── II. Relevance Scorer output ──────────────────────────────
                "llm_score":       rel.llm_score if rel else None,
                "impact_tier":     rel.impact_tier if rel else None,
                "signal_kind":     rel.signal_kind if rel else None,
                "impact_type":     rel.impact_type if rel else None,
                "what_changed":    rel.what_changed if rel else None,
                "mechanism":       rel.mechanism if rel else None,
                "scorer_reasoning": (rel.reasoning or "")[:300] if rel else None,
                # Analyst override
                "analyst_score":   rel.analyst_score if rel else None,
                "effective_score": _effective_score(rel),
                "decision":        rel.decision if rel else None,
                # ── III. Triage Classifier output ────────────────────────────
                "event_class":              cs.event_class if cs else None,
                "secondary_event_classes":  cs.secondary_event_classes if cs else None,
                "state_change":             cs.state_change if cs else None,
                "graph_entities":           cs.graph_entities if cs else None,
                "geo_tags":                 cs.geo_tags if cs else None,
                "confidence":               cs.confidence if cs else None,
                "triage_reasoning":         (cs.triage_reasoning or "")[:300] if cs else None,
            })
        return results


# ── Analyst score override ─────────────────────────────────────────────────────

class ScorePatch(BaseModel):
    score: float = Field(..., ge=0.0, le=1.0)


@router.patch("/{signal_id}/score")
async def set_analyst_score(signal_id: str, body: ScorePatch) -> dict:
    """Store an analyst-overridden score. Writes to signal_relevance.analyst_score
    (NOT rule_score — rule_score is the keyword-filter score set at ingestion)."""
    async with async_session_factory() as session:
        rel = await session.get(SignalRelevance, signal_id)
        if rel is None:
            rel = SignalRelevance(signal_id=signal_id, analyst_score=body.score)  # type: ignore[call-arg]
            session.add(rel)
        else:
            rel.analyst_score = body.score
        await session.commit()
    return {"signal_id": signal_id, "analyst_score": body.score}


# ── Stats ──────────────────────────────────────────────────────────────────────

@router.get("/stats")
async def signal_stats(hours: int = Q(default=168, ge=1, le=720)) -> dict:
    cutoff = datetime.now(UTC) - timedelta(hours=hours)

    async with async_session_factory() as session:
        stmt = (
            select(Signal, SignalRelevance)
            .outerjoin(SignalRelevance, Signal.id == SignalRelevance.signal_id)
            .where(Signal.ingested_at >= cutoff)
            .order_by(Signal.ingested_at.asc())
        )
        rows = list(await session.execute(stmt))

    by_source: dict[str, int] = defaultdict(int)
    by_decision: dict[str, int] = defaultdict(int)
    use_daily = hours > 48
    bucket_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for sig, rel in rows:
        src = sig.source or "unknown"
        decision = (rel.decision if rel else None) or "unscored"
        by_source[src] += 1
        by_decision[decision] += 1
        if sig.ingested_at:
            ts = sig.ingested_at
            bucket = ts.strftime("%Y-%m-%d") if use_daily else ts.strftime("%Y-%m-%dT%H:00")
            bucket_counts[bucket][src] += 1

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
