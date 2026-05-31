"""Phase 2 — dynamic pressure (signal-driven).

direct_pressure(a): sum of recency-decayed pressure from signals grounded to a.
propagated_pressure(a): personalized PageRank seeded by the direct-pressure
vector, so pressure diffuses along weighted dependency edges and concentrates
where multiple independent signal paths converge. This is the formal model of
"individually-minor, seemingly-unrelated signals combining into a disruption."
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import networkx as nx
from sqlalchemy import select

from apps.api.db.models import Signal, SignalActorLink
from apps.api.db.session import async_session_factory

logger = logging.getLogger(__name__)

_HALF_LIFE_DAYS = 14.0  # pressure from a signal decays to half after 14 days


def _decay(occurred_at: datetime | None, now: datetime) -> float:
    if occurred_at is None:
        return 0.5
    age_days = max(0.0, (now - occurred_at).total_seconds() / 86400.0)
    return 0.5 ** (age_days / _HALF_LIFE_DAYS)


async def direct_pressure(window_hours: int = 720) -> dict[str, float]:
    """Sum recency-decayed signal pressure per actor over the lookback window."""
    now = datetime.now(UTC)
    cutoff = now.timestamp() - window_hours * 3600
    out: dict[str, float] = {}

    async with async_session_factory() as s:
        rows = (await s.execute(
            select(
                SignalActorLink.actor_name,
                SignalActorLink.pressure,
                Signal.occurred_at,
            )
            .join(Signal, Signal.id == SignalActorLink.signal_id)
        )).all()

    for actor, pressure, occurred_at in rows:
        if occurred_at is not None and occurred_at.timestamp() < cutoff:
            continue
        out[actor] = out.get(actor, 0.0) + (pressure or 0.0) * _decay(occurred_at, now)

    return out


def propagated_pressure(
    g: nx.DiGraph, direct: dict[str, float]
) -> dict[str, float]:
    """Diffuse direct pressure through the dependency graph.

    Personalized PageRank seeded by the (normalised) direct-pressure vector.
    A node ends up high if it is itself pressured OR many pressured nodes
    depend on paths that converge on it.
    """
    if g.number_of_nodes() == 0 or not direct:
        return {n: 0.0 for n in g.nodes}

    # Seed only nodes present in the graph.
    seed = {n: direct.get(n, 0.0) for n in g.nodes}
    total = sum(seed.values())
    if total <= 0:
        return {n: 0.0 for n in g.nodes}
    personalization = {n: v / total for n, v in seed.items()}

    try:
        pp = nx.pagerank(g, alpha=0.85, weight="weight",
                         personalization=personalization, max_iter=200)
    except nx.PowerIterationFailedConvergence:
        pp = nx.pagerank(g, alpha=0.85, weight="weight",
                         personalization=personalization, max_iter=500, tol=1e-4)

    # Scale back up by total pressure so magnitudes stay interpretable.
    return {n: v * total for n, v in pp.items()}


def normalise(d: dict[str, float]) -> dict[str, float]:
    if not d:
        return {}
    hi = max(d.values())
    if hi < 1e-12:
        return {k: 0.0 for k in d}
    return {k: v / hi for k, v in d.items()}
