"""Phase 3 — network state snapshots.

Computes the current network state and persists it to `network_snapshot`, so the
sequence of snapshots forms a state-estimation time series ("constrained for 9
days") and the future observation series for an HMM forecasting layer.
"""

from __future__ import annotations

import logging

from apps.api.db.models import NetworkSnapshot
from apps.api.db.session import async_session_factory
from apps.api.network.state import compute_network_state

logger = logging.getLogger(__name__)


async def take_snapshot(window_hours: int = 720) -> dict:
    """Compute current L1 + L2 network state, persist a snapshot row, return summary."""
    from apps.api.network.ant_state import compute_ant_state

    state = await compute_network_state(window_hours=window_hours, top_n=12)
    ant_state = await compute_ant_state(window_hours=window_hours)

    # Count signals contributing in the window (distinct signals with a link).
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import func, select

    from apps.api.db.models import Signal, SignalActorLink

    cutoff = datetime.now(UTC) - timedelta(hours=window_hours)
    async with async_session_factory() as session:
        signal_count = (await session.execute(
            select(func.count(func.distinct(SignalActorLink.signal_id)))
            .join(Signal, Signal.id == SignalActorLink.signal_id)
            .where(Signal.occurred_at >= cutoff)
        )).scalar() or 0

        snap = NetworkSnapshot(
            health_index=state["health_index"],
            health_label=state["health_label"],
            top_actors_json=state["top_actors"],
            hotspots_json=state["hotspots"],
            bottlenecks_json=state["bottlenecks"],
            signal_window_hours=window_hours,
            signal_count=signal_count,
            ant_state_json=ant_state,
        )
        session.add(snap)
        await session.commit()
        await session.refresh(snap)

    logger.info(
        "[snapshot] %s health=%.3f (%s) actors=%d hotspots=%d signals=%d",
        snap.id, state["health_index"], state["health_label"],
        len(state["top_actors"]), len(state["hotspots"]), signal_count,
    )
    return {
        "id": str(snap.id),
        "health_index": state["health_index"],
        "health_label": state["health_label"],
        "signal_count": signal_count,
    }
