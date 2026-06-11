"""Signals API routes — list, retrieve, and manually score ingested signals."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi import Query as Q
from pydantic import BaseModel, Field
from sqlalchemy import or_, select, update

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
                # event_id groups duplicate coverage of the same real-world event.
                # NULL → treat the signal as its own event (frontend falls back to id).
                "event_id":      str(sig.event_id) if sig.event_id else None,
                "source":        sig.source,
                "url":           sig.url,
                "ingested_at":   sig.ingested_at.isoformat() if sig.ingested_at else None,
                "occurred_at":   sig.occurred_at.isoformat() if sig.occurred_at else None,
                "description":   _signal_description(sig.source, payload, title, summary),
                "price_move":    _price_movement(payload) if sig.source == "prices" else None,
                # Per-horizon % moves ({"1d":…, "5d":…, "30d":…}) for the UI sparkline.
                "moves_pct":     payload.get("moves_pct") if sig.source == "prices" else None,
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


# ── Manual event clustering (analyst merge / unlink) ───────────────────────────
#
# event_id semantics (self-referencing FK on signals.event_id):
#   NULL           legacy / not yet clustered  → treated as its own event
#   event_id == id this signal IS the canonical anchor for its event
#   event_id == X  X is the canonical anchor; this signal is a duplicate of it
#
# The frontend groups signals by event_id and shows the highest-relevance member
# as the event's representative, so the *choice* of canonical id is only a
# grouping key — display always recomputes the representative.


def _eff(analyst: float | None, llm: float | None) -> float:
    """Effective relevance: analyst override if set, else llm score, else 0."""
    if analyst is not None:
        return analyst
    return llm if llm is not None else 0.0


class MergeRequest(BaseModel):
    signal_ids: list[str] = Field(..., min_length=2)


@router.post("/merge")
async def merge_signals(body: MergeRequest) -> dict:
    """Merge several signals into one event.

    Picks the highest-relevance signal as the canonical anchor and repoints
    every selected signal — plus any signal already pointing at one of them —
    to that anchor. Idempotent and safe to call repeatedly.
    """
    try:
        ids = [UUID(s) for s in body.signal_ids]
    except ValueError as exc:
        raise HTTPException(400, f"Invalid signal id: {exc}") from exc

    async with async_session_factory() as session:
        rows = (await session.execute(
            select(Signal.id, SignalRelevance.analyst_score, SignalRelevance.llm_score)
            .outerjoin(SignalRelevance, Signal.id == SignalRelevance.signal_id)
            .where(Signal.id.in_(ids))
        )).all()
        if len(rows) < 2:
            raise HTTPException(400, "Need at least 2 valid signals to merge")

        canonical = max(rows, key=lambda r: _eff(r[1], r[2]))[0]

        # Repoint selected signals AND anything already clustered under them.
        await session.execute(
            update(Signal)
            .where(or_(Signal.id.in_(ids), Signal.event_id.in_(ids)))
            .values(event_id=canonical)
        )
        await session.commit()

    return {"event_id": str(canonical), "merged_signals": len(rows)}


@router.post("/{signal_id}/unlink")
async def unlink_signal(signal_id: str) -> dict:
    """Detach one signal from its event, making it its own standalone event.

    If the detached signal was the canonical anchor and had followers, the
    remaining members are first re-anchored to their highest-relevance member
    so the rest of the cluster stays intact.
    """
    try:
        sid = UUID(signal_id)
    except ValueError as exc:
        raise HTTPException(400, f"Invalid signal id: {exc}") from exc

    async with async_session_factory() as session:
        sig = await session.get(Signal, sid)
        if sig is None:
            raise HTTPException(404, "Signal not found")

        # If this signal anchors others, reassign them to a new canonical first.
        if sig.event_id == sid:
            followers = (await session.execute(
                select(Signal.id, SignalRelevance.analyst_score, SignalRelevance.llm_score)
                .outerjoin(SignalRelevance, Signal.id == SignalRelevance.signal_id)
                .where(Signal.event_id == sid, Signal.id != sid)
            )).all()
            if followers:
                new_anchor = max(followers, key=lambda r: _eff(r[1], r[2]))[0]
                await session.execute(
                    update(Signal)
                    .where(Signal.event_id == sid, Signal.id != sid)
                    .values(event_id=new_anchor)
                )

        # Detach: this signal becomes its own single-member event.
        sig.event_id = sid
        await session.commit()

    return {"signal_id": signal_id, "detached": True}


# ── Admin: one-shot recluster all signals with NULL event_id ──────────────────
# Safe to call repeatedly (idempotent). Uses the same Voyage AI embeddings
# already stored on signals — no new embedding API calls.

@router.post("/admin/recluster")
async def admin_recluster() -> dict:
    """Re-run event clustering across ALL signals that have an embedding but
    no event_id (event_id IS NULL or event_id = own id treated as un-clustered).

    Uses in-DB cosine similarity (pgvector) with the same threshold and window
    as live ingestion. Safe to call repeatedly — idempotent.
    """
    import numpy as np
    from collections import defaultdict as _dd
    from datetime import timedelta as _td
    from apps.api.network.event_cluster import CLUSTER_THRESHOLD, CLUSTER_WINDOW_HOURS

    async with async_session_factory() as session:
        # Load all signals with embeddings
        rows = (await session.execute(
            select(Signal.id, Signal.source, Signal.source_id,
                   Signal.occurred_at, Signal.event_id, Signal.embedding)
            .where(Signal.embedding.isnot(None))
            .order_by(Signal.occurred_at)
        )).all()

    if not rows:
        return {"status": "ok", "merged": 0, "message": "No embedded signals found"}

    # Build quick lookup
    sigs = {str(r.id): r for r in rows}
    embs = {str(r.id): np.array(r.embedding) for r in rows}

    # Union-Find
    parent = {sid: sid for sid in sigs}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra == rb:
            return
        # Canonical = earliest occurred_at
        if sigs[ra].occurred_at <= sigs[rb].occurred_at:
            parent[rb] = ra
        else:
            parent[ra] = rb

    ids = list(sigs.keys())
    window = _td(hours=CLUSTER_WINDOW_HOURS)
    merges = 0
    for i, id_a in enumerate(ids):
        ra = sigs[id_a]
        ea = embs[id_a]
        t_lo = ra.occurred_at - window
        t_hi = ra.occurred_at + window
        for id_b in ids[i + 1:]:
            rb = sigs[id_b]
            if rb.occurred_at > t_hi:
                break
            if rb.occurred_at < t_lo:
                continue
            if ra.source_id == rb.source_id:
                continue
            sim = float(np.dot(ea, embs[id_b]) /
                        (np.linalg.norm(ea) * np.linalg.norm(embs[id_b])))
            if sim > CLUSTER_THRESHOLD:
                union(id_a, id_b)
                merges += 1

    # Build update map: signal → canonical
    canonical_map = {sid: find(sid) for sid in ids if find(sid) != sid}

    if not canonical_map:
        return {"status": "ok", "merged": 0, "message": "All signals already correctly clustered"}

    # Apply updates
    import uuid as _uuid
    async with async_session_factory() as session:
        async with session.begin():
            for sig_id, canonical_id in canonical_map.items():
                await session.execute(
                    update(Signal)
                    .where(Signal.id == _uuid.UUID(sig_id))
                    .values(event_id=_uuid.UUID(canonical_id))
                )
            # Ensure all canonicals have event_id = self
            for canonical_id in set(canonical_map.values()):
                await session.execute(
                    update(Signal)
                    .where(Signal.id == _uuid.UUID(canonical_id))
                    .values(event_id=_uuid.UUID(canonical_id))
                )

    return {
        "status": "ok",
        "signals_processed": len(rows),
        "merged": len(canonical_map),
        "message": f"Re-pointed {len(canonical_map)} signals to canonical event_ids",
    }


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
