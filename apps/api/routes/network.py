"""Network State Intelligence API.

Surfaces the industrial-network condition computed by apps/api/network/*:
  GET /state             current full network-state object
  GET /actors            actors ranked by systemic influence
  GET /hotspots          current pressure hotspots
  GET /propagation/{a}   propagation paths from an actor to critical sinks
  GET /health            health-index time series (from snapshots)
  GET /actor/{name}      detail for one actor incl. contributing signals
  POST /snapshot         compute + persist a snapshot now
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi import Query as Q
from sqlalchemy import select

from apps.api.db.models import NetworkSnapshot, Signal, SignalActorLink, SignalRelevance
from apps.api.db.session import async_session_factory
from apps.api.network.state import compute_network_state, propagation_paths

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/state")
async def get_state(hours: int = Q(default=720, ge=1, le=2160)) -> dict:
    """Current full network-state object."""
    return await compute_network_state(window_hours=hours, top_n=12)


@router.get("/actors")
async def get_actors(hours: int = Q(default=720, ge=1, le=2160), limit: int = Q(default=25, ge=1, le=100)) -> list[dict]:
    """Actors ranked by systemic influence (with pressure)."""
    state = await compute_network_state(window_hours=hours, top_n=limit)
    return state["top_actors"]


@router.get("/hotspots")
async def get_hotspots(hours: int = Q(default=720, ge=1, le=2160)) -> list[dict]:
    """Pressure hotspots — where multiple signal paths converge."""
    state = await compute_network_state(window_hours=hours, top_n=15)
    return state["hotspots"]


@router.get("/propagation/{actor}")
async def get_propagation(actor: str, max_paths: int = Q(default=6, ge=1, le=20)) -> list[dict]:
    """Strongest propagation paths from an actor to critical downstream sinks."""
    paths = await propagation_paths(actor, max_paths=max_paths)
    if not paths:
        return []
    return paths


@router.get("/health")
async def get_health(limit: int = Q(default=60, ge=1, le=500)) -> list[dict]:
    """Health-index time series from persisted snapshots (oldest → newest)."""
    async with async_session_factory() as session:
        rows = (await session.execute(
            select(NetworkSnapshot)
            .order_by(NetworkSnapshot.computed_at.desc())
            .limit(limit)
        )).scalars().all()
    rows = list(reversed(rows))
    return [
        {
            "computed_at": r.computed_at.isoformat() if r.computed_at else None,
            "health_index": r.health_index,
            "health_label": r.health_label,
            "signal_count": r.signal_count,
        }
        for r in rows
    ]


@router.get("/actor/{name}")
async def get_actor_detail(name: str, hours: int = Q(default=720, ge=1, le=2160)) -> dict:
    """Detail for one actor: its influence/pressure + the signals pressuring it."""
    state = await compute_network_state(window_hours=hours, top_n=1000)
    actor = next((a for a in state["top_actors"] if a["actor"] == name), None)

    async with async_session_factory() as session:
        rows = (await session.execute(
            select(Signal, SignalActorLink, SignalRelevance)
            .join(SignalActorLink, SignalActorLink.signal_id == Signal.id)
            .outerjoin(SignalRelevance, SignalRelevance.signal_id == Signal.id)
            .where(SignalActorLink.actor_name == name)
            .order_by(SignalActorLink.pressure.desc())
            .limit(20)
        )).all()

    signals = []
    for sig, link, rel in rows:
        payload = sig.raw_payload or {}
        title = payload.get("title") or payload.get("headline") or payload.get("label") or payload.get("ticker", "")
        signals.append({
            "id": str(sig.id),
            "source": sig.source,
            "title": title[:140],
            "url": sig.url,
            "occurred_at": sig.occurred_at.isoformat() if sig.occurred_at else None,
            "pressure": link.pressure,
            "match_kind": link.match_kind,
            "impact_tier": rel.impact_tier if rel else None,
            "impact_type": rel.impact_type if rel else None,
        })

    paths = await propagation_paths(name, max_paths=6)
    return {
        "actor": name,
        "influence": actor["influence"] if actor else None,
        "label": actor["label"] if actor else None,
        "criticality": actor["criticality"] if actor else None,
        "direct_pressure": actor["direct_pressure"] if actor else None,
        "propagated_pressure": actor["propagated_pressure"] if actor else None,
        "signals": signals,
        "propagation": paths,
    }


@router.post("/snapshot")
async def post_snapshot(hours: int = Q(default=720, ge=1, le=2160)) -> dict:
    """Compute and persist a network snapshot immediately."""
    from apps.api.network.snapshot import take_snapshot
    return await take_snapshot(window_hours=hours)


# ── Layer 2 — ANT Actor Map endpoints ────────────────────────────────────────

@router.get("/ant/state")
async def get_ant_state(hours: int = Q(default=720, ge=1, le=2160)) -> dict:
    """Current Layer-2 ANT actor state: 8 systemic forces, each with
    direct + propagated pressure accumulated from Layer-1 signals via rollup."""
    from apps.api.network.ant_state import compute_ant_state
    return await compute_ant_state(window_hours=hours)


@router.get("/ant/actor/{actor_id}")
async def get_ant_actor(actor_id: str, hours: int = Q(default=720, ge=1, le=2160)) -> dict:
    """Detail for one Layer-2 actor: pressure, influence, and the specific
    signals (with their L1 entity or impact_type match) driving it."""
    from apps.api.network.ant_state import compute_ant_state
    from apps.api.network.actor_map import actor_by_id
    meta = actor_by_id(actor_id)
    if meta is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Unknown ANT actor: {actor_id}")
    state = await compute_ant_state(window_hours=hours)
    actor_state = next((a for a in state["actors"] if a["id"] == actor_id), {})
    return {**meta, **actor_state}
