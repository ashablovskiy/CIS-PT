"""Phase 2 — systemic influence (static, topology-driven).

An actor is *influential* not because it is large, but because many (and
themselves-influential) actors depend on it. That is weighted PageRank on the
**reversed** dependency graph: edges point dependent → dependency, so reversing
makes rank flow into the most depended-upon nodes.

Blended with each node's `impact_weight` prior so domain knowledge anchors the
purely-topological score.
"""

from __future__ import annotations

import logging

import networkx as nx

logger = logging.getLogger(__name__)

_PRIOR_BLEND = 0.35  # weight of the impact_weight prior vs. topological PageRank


def systemic_influence(g: nx.DiGraph) -> dict[str, float]:
    """Return {actor_name: influence_score in 0–1}, normalised."""
    if g.number_of_nodes() == 0:
        return {}

    # Reverse: rank flows toward dependencies (the depended-upon).
    rev = g.reverse(copy=False)

    # Personalization by impact_weight so critical actors get a topological boost.
    prior = {n: max(0.01, d.get("impact_weight", 0.5)) for n, d in g.nodes(data=True)}
    psum = sum(prior.values()) or 1.0
    personalization = {n: v / psum for n, v in prior.items()}

    try:
        pr = nx.pagerank(rev, alpha=0.85, weight="weight",
                         personalization=personalization, max_iter=200)
    except nx.PowerIterationFailedConvergence:
        pr = nx.pagerank(rev, alpha=0.85, weight="weight", max_iter=500, tol=1e-4)

    # Blend topological PageRank with the raw impact_weight prior.
    blended = {
        n: (1 - _PRIOR_BLEND) * pr.get(n, 0.0) + _PRIOR_BLEND * (prior[n] / psum)
        for n in g.nodes
    }
    return _normalise(blended)


def _normalise(d: dict[str, float]) -> dict[str, float]:
    if not d:
        return {}
    lo, hi = min(d.values()), max(d.values())
    if hi - lo < 1e-12:
        return {k: 0.0 for k in d}
    return {k: (v - lo) / (hi - lo) for k, v in d.items()}
