"""Layer 2 — ANT Actor State engine.

Computes the current condition of the 8 systemic actors from the accumulated
Layer-1 signal pressure, rolled up via the rollup mapping.

Two pressure channels:
  1. Entity channel: signal_actor_link.pressure aggregated by L1→L2 mapping
  2. Impact-type channel: signal_relevance.impact_type → L2 actor (for actors
     with weak L1 entity backing, e.g. Trade_Policy_Regime)

The computation runs on a tiny networkx DiGraph (8 nodes, 12 edges) built from
actor_map.py — no Neo4j needed. Influence is static (topology-only). Pressure
is dynamic (recency-decayed signal accumulation).
"""

from __future__ import annotations

import logging
import math
from datetime import UTC, datetime, timedelta
from typing import Any

import networkx as nx
from sqlalchemy import select, func

from apps.api.db.models import Signal, SignalActorLink, SignalRelevance
from apps.api.db.session import async_session_factory
from apps.api.network.actor_map import ACTORS, ACTOR_EDGES, actor_by_id
from apps.api.network.rollup import (
    IMPACT_TYPE_WEIGHT_FACTOR, entity_to_l2, impact_type_to_l2,
)

logger = logging.getLogger(__name__)

_HALF_LIFE_DAYS = 14.0
_HEALTH_FRAGILE = 0.66
_HEALTH_CONSTRAINED = 0.33

# Cache the L2 graph (static topology — rebuild only on process restart)
_ANT_GRAPH: nx.DiGraph | None = None
_ANT_INFLUENCE: dict[str, float] | None = None


def _build_ant_graph() -> nx.DiGraph:
    """Build the L2 networkx DiGraph from actor_map definitions."""
    g = nx.DiGraph()
    for a in ACTORS:
        g.add_node(
            a["id"],
            label=a["label"],
            band=a["band"],
            criticality=a["criticality"],
            impact_weight=a["impact_weight"],
        )
    for e in ACTOR_EDGES:
        g.add_edge(e["src"], e["dst"], weight=e["weight"], rel_type=e["type"])
    return g


def get_ant_graph() -> nx.DiGraph:
    global _ANT_GRAPH
    if _ANT_GRAPH is None:
        _ANT_GRAPH = _build_ant_graph()
        logger.info("[ant_state] L2 graph built: %d actors, %d edges",
                    _ANT_GRAPH.number_of_nodes(), _ANT_GRAPH.number_of_edges())
    return _ANT_GRAPH


def _systemic_influence(g: nx.DiGraph) -> dict[str, float]:
    """Static influence: weighted PageRank on reversed dependency graph."""
    global _ANT_INFLUENCE
    if _ANT_INFLUENCE is not None:
        return _ANT_INFLUENCE
    rev = g.reverse(copy=False)
    iw = {n: max(0.01, g.nodes[n].get("impact_weight", 0.5)) for n in g}
    s = sum(iw.values())
    pers = {n: v / s for n, v in iw.items()}
    try:
        pr = nx.pagerank(rev, alpha=0.85, weight="weight", personalization=pers, max_iter=300)
    except nx.PowerIterationFailedConvergence:
        pr = {n: 1.0 / len(g) for n in g}
    lo, hi = min(pr.values()), max(pr.values())
    if hi - lo < 1e-9:
        _ANT_INFLUENCE = {n: 0.0 for n in g}
    else:
        _ANT_INFLUENCE = {n: (v - lo) / (hi - lo) for n, v in pr.items()}
    return _ANT_INFLUENCE


def _decay(occurred_at: datetime | None, now: datetime) -> float:
    if occurred_at is None:
        return 0.5
    age_d = max(0.0, (now - occurred_at).total_seconds() / 86400.0)
    return 0.5 ** (age_d / _HALF_LIFE_DAYS)


async def _l2_direct_pressure(window_hours: int) -> tuple[dict[str, float], dict[str, list[dict]]]:
    """Aggregate L1 pressure into L2 actors.

    Returns:
        pressure: {ant_actor_id: total_pressure}
        contributors: {ant_actor_id: [{signal_id, title, source, pressure, match}]}
    """
    now = datetime.now(UTC)
    cutoff = now - timedelta(hours=window_hours)
    pressure: dict[str, float] = {a["id"]: 0.0 for a in ACTORS}
    contributors: dict[str, list[dict]] = {a["id"]: [] for a in ACTORS}

    async with async_session_factory() as s:
        # ── Channel 1: entity-name rollup ─────────────────────────────────
        rows = (await s.execute(
            select(
                SignalActorLink.actor_name,
                SignalActorLink.pressure,
                Signal.id,
                Signal.source,
                Signal.raw_payload,
                Signal.occurred_at,
            )
            .join(Signal, Signal.id == SignalActorLink.signal_id)
            .where(Signal.occurred_at >= cutoff)
        )).all()

        for actor_name, p, sig_id, source, payload, occurred_at in rows:
            l2_id = entity_to_l2(actor_name or "")
            if l2_id is None:
                continue
            decay = _decay(occurred_at, now)
            contrib = (p or 0.0) * decay
            pressure[l2_id] = pressure.get(l2_id, 0.0) + contrib
            title = (payload or {}).get("title") or (payload or {}).get("label") or ""
            contributors[l2_id].append({
                "signal_id": str(sig_id),
                "source": source,
                "title": title[:100],
                "pressure": round(contrib, 4),
                "match": f"entity:{actor_name}",
            })

        # ── Channel 2: impact_type tag rollup ──────────────────────────────
        it_rows = (await s.execute(
            select(
                SignalRelevance.impact_type,
                SignalRelevance.llm_score,
                SignalRelevance.impact_tier,
                Signal.id,
                Signal.source,
                Signal.raw_payload,
                Signal.occurred_at,
            )
            .join(Signal, Signal.id == SignalRelevance.signal_id)
            .where(
                Signal.occurred_at >= cutoff,
                SignalRelevance.decision.in_(["escalate", "review"]),
                SignalRelevance.impact_type.isnot(None),
            )
        )).all()

        for impact_type, llm_score, tier, sig_id, source, payload, occurred_at in it_rows:
            l2_id = impact_type_to_l2(impact_type)
            if l2_id is None:
                continue
            # Weight: tier-adjusted score × impact_type channel factor
            tier_w = {1: 1.0, 2: 0.7, 3: 0.4, 4: 0.1}.get(tier, 0.4)
            score_p = (llm_score or 0.0) * tier_w * IMPACT_TYPE_WEIGHT_FACTOR
            decay = _decay(occurred_at, now)
            contrib = score_p * decay
            if contrib < 0.001:
                continue
            pressure[l2_id] = pressure.get(l2_id, 0.0) + contrib
            title = (payload or {}).get("title") or ""
            contributors[l2_id].append({
                "signal_id": str(sig_id),
                "source": source,
                "title": title[:100],
                "pressure": round(contrib, 4),
                "match": f"impact_type:{impact_type}",
            })

    # Deduplicate contributors by signal_id (same signal can arrive via both channels)
    for actor_id in contributors:
        seen: set[str] = set()
        deduped: list[dict] = []
        for c in contributors[actor_id]:
            if c["signal_id"] not in seen:
                seen.add(c["signal_id"])
                deduped.append(c)
        contributors[actor_id] = sorted(deduped, key=lambda x: x["pressure"], reverse=True)[:20]

    return pressure, contributors


def _propagate(g: nx.DiGraph, direct: dict[str, float]) -> dict[str, float]:
    """Personalized PageRank seeded by direct pressure."""
    total = sum(direct.values())
    if total <= 0:
        return {n: 0.0 for n in g}
    pers = {n: direct.get(n, 0.0) / total for n in g}
    try:
        pp = nx.pagerank(g, alpha=0.85, weight="weight", personalization=pers, max_iter=300)
    except nx.PowerIterationFailedConvergence:
        pp = {n: 1.0 / len(g) for n in g}
    return {n: v * total for n, v in pp.items()}


def _normalise(d: dict[str, float]) -> dict[str, float]:
    hi = max(d.values(), default=0.0)
    if hi < 1e-9:
        return {k: 0.0 for k in d}
    return {k: v / hi for k, v in d.items()}


async def compute_ant_state(window_hours: int = 720) -> dict[str, Any]:
    """Compute the full Layer-2 ANT actor state."""
    g = get_ant_graph()
    influence = _systemic_influence(g)
    direct, contributors = await _l2_direct_pressure(window_hours)
    propagated = _propagate(g, direct)
    prop_norm = _normalise(propagated)
    direct_norm = _normalise(direct)

    actors_out = []
    for a in ACTORS:
        aid = a["id"]
        actors_out.append({
            "id": aid,
            "label": a["label"],
            "band": a["band"],
            "criticality": a["criticality"],
            "impact_weight": a["impact_weight"],
            "definition": a["definition"],
            "why": a["why"],
            "influence": round(influence.get(aid, 0.0), 4),
            "direct_pressure": round(direct_norm.get(aid, 0.0), 4),
            "propagated_pressure": round(prop_norm.get(aid, 0.0), 4),
            "raw_direct_pressure": round(direct.get(aid, 0.0), 4),
            "signal_count": len(contributors.get(aid, [])),
            "top_signals": contributors.get(aid, [])[:5],
        })

    actors_out.sort(key=lambda x: x["propagated_pressure"], reverse=True)

    # Health: Σ(influence × propagated × criticality_factor)
    crit_map = {"critical": 1.0, "high": 0.75, "medium": 0.5, "low": 0.25}
    fragility_raw = sum(
        influence.get(a["id"], 0.0)
        * prop_norm.get(a["id"], 0.0)
        * crit_map.get(a["criticality"], 0.5)
        for a in ACTORS
    )
    active = sum(1 for a in ACTORS if prop_norm.get(a["id"], 0.0) > 0.05) or 1
    health_index = min(1.0, fragility_raw / max(1.0, math.sqrt(active)))
    health_label = (
        "fragile" if health_index >= _HEALTH_FRAGILE
        else "constrained" if health_index >= _HEALTH_CONSTRAINED
        else "resilient"
    )

    # Hotspots: propagated >> direct (convergence)
    hotspots = [
        a for a in actors_out
        if a["propagated_pressure"] >= 0.15
        and (a["direct_pressure"] < 0.01
             or a["propagated_pressure"] / max(a["direct_pressure"], 1e-6) >= 1.5)
    ]

    logger.info(
        "[ant_state] health=%s (%.3f) pressured=%d hotspots=%d",
        health_label, health_index, active, len(hotspots),
    )
    return {
        "layer": "L2_ANT",
        "window_hours": window_hours,
        "health_index": round(health_index, 4),
        "health_label": health_label,
        "actors": actors_out,
        "hotspots": [h["id"] for h in hotspots],
        "actor_count": len(ACTORS),
        "edge_count": len(ACTOR_EDGES),
        "pressured_actor_count": active,
    }
