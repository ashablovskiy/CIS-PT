"""Phase 2 — derived network-state outputs.

Combines static influence + dynamic pressure into the product-level answers:
  - systemic influence leaderboard
  - pressure hotspots (multi-path convergence)
  - emerging bottlenecks (influence ∧ rising pressure ∧ criticality)
  - propagation paths (how pressure reaches critical downstream actors)
  - ecosystem health index + label
"""

from __future__ import annotations

import logging
from typing import Any

import networkx as nx

from apps.api.network import pressure as pressure_mod
from apps.api.network.influence import systemic_influence
from apps.api.network.topology import load_graph

logger = logging.getLogger(__name__)

# Downstream actor labels that represent "the thing we ultimately care about
# delivering" — propagation paths are traced toward these.
_CRITICAL_SINK_LABELS = {"Category", "DemandSource"}

_HOTSPOT_RATIO = 1.5     # propagated ≥ 1.5× direct → convergence hotspot
_HEALTH_FRAGILE = 0.66
_HEALTH_CONSTRAINED = 0.33


async def compute_network_state(window_hours: int = 720, top_n: int = 10) -> dict[str, Any]:
    """Compute the full network-state object."""
    g = await load_graph()
    influence = systemic_influence(g)
    direct = await pressure_mod.direct_pressure(window_hours=window_hours)
    propagated = pressure_mod.propagated_pressure(g, direct)

    prop_norm = pressure_mod.normalise(propagated)
    direct_norm = pressure_mod.normalise(direct)

    # ── Influence leaderboard ────────────────────────────────────────────────
    top_actors = [
        {
            "actor": n,
            "label": g.nodes[n].get("label"),
            "influence": round(influence.get(n, 0.0), 4),
            "criticality": g.nodes[n].get("criticality"),
            "direct_pressure": round(direct_norm.get(n, 0.0), 4),
            "propagated_pressure": round(prop_norm.get(n, 0.0), 4),
        }
        for n in sorted(influence, key=lambda x: influence[x], reverse=True)[:top_n]
    ]

    # ── Pressure hotspots: propagated ≫ direct (pressure arriving via paths) ──
    hotspots = []
    for n in g.nodes:
        p = prop_norm.get(n, 0.0)
        d = direct_norm.get(n, 0.0)
        if p < 0.15:
            continue
        ratio = p / d if d > 1e-6 else float("inf")
        if ratio >= _HOTSPOT_RATIO:
            hotspots.append({
                "actor": n,
                "label": g.nodes[n].get("label"),
                "propagated_pressure": round(p, 4),
                "direct_pressure": round(d, 4),
                "convergence_ratio": round(ratio, 2) if ratio != float("inf") else None,
                "criticality": g.nodes[n].get("criticality"),
            })
    hotspots.sort(key=lambda h: h["propagated_pressure"], reverse=True)
    hotspots = hotspots[:top_n]

    # ── Emerging bottlenecks: influence ∧ pressure ∧ criticality ─────────────
    bottlenecks = []
    for n in g.nodes:
        inf = influence.get(n, 0.0)
        p = prop_norm.get(n, 0.0)
        nf = g.nodes[n].get("node_factor", 0.5)
        score = inf * 0.4 + p * 0.4 + nf * 0.2
        if inf > 0.3 and p > 0.2:
            bottlenecks.append({
                "actor": n,
                "label": g.nodes[n].get("label"),
                "score": round(score, 4),
                "influence": round(inf, 4),
                "pressure": round(p, 4),
                "criticality": g.nodes[n].get("criticality"),
            })
    bottlenecks.sort(key=lambda b: b["score"], reverse=True)
    bottlenecks = bottlenecks[:top_n]

    # ── Ecosystem health: Σ(influence × propagated pressure) over critical mass ──
    fragility_raw = sum(
        influence.get(n, 0.0) * prop_norm.get(n, 0.0) * g.nodes[n].get("node_factor", 0.5)
        for n in g.nodes
    )
    # Normalise by an active-node count so it reads 0–1 on this graph size.
    active = sum(1 for n in g.nodes if prop_norm.get(n, 0.0) > 0.05) or 1
    health_index = min(1.0, fragility_raw / (active ** 0.5))
    health_label = (
        "fragile" if health_index >= _HEALTH_FRAGILE
        else "constrained" if health_index >= _HEALTH_CONSTRAINED
        else "resilient"
    )

    return {
        "window_hours": window_hours,
        "health_index": round(health_index, 4),
        "health_label": health_label,
        "top_actors": top_actors,
        "hotspots": hotspots,
        "bottlenecks": bottlenecks,
        "node_count": g.number_of_nodes(),
        "edge_count": g.number_of_edges(),
        "pressured_actor_count": active,
    }


async def propagation_paths(actor: str, max_paths: int = 5) -> list[dict[str, Any]]:
    """Strongest weighted paths from `actor` to critical downstream sinks."""
    g = await load_graph()
    if actor not in g:
        return []

    # Use 1/weight as distance so high-weight edges = short paths.
    def dist(u, v, d):
        return 1.0 / max(d.get("weight", 0.01), 0.01)

    sinks = [n for n in g.nodes if g.nodes[n].get("label") in _CRITICAL_SINK_LABELS]
    results = []
    for sink in sinks:
        if sink == actor:
            continue
        try:
            path = nx.shortest_path(g, actor, sink, weight=dist)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            continue
        if len(path) < 2:
            continue
        strength = 1.0
        for u, v in zip(path, path[1:], strict=False):
            strength *= g[u][v].get("weight", 0.01)
        results.append({
            "target": sink,
            "target_label": g.nodes[sink].get("label"),
            "path": path,
            "hops": len(path) - 1,
            "strength": round(strength, 4),
        })
    results.sort(key=lambda r: r["strength"], reverse=True)
    return results[:max_paths]
