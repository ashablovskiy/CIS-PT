"""Phase 2 — topology loader.

Loads the Neo4j actor graph into a weighted networkx.DiGraph, applying the
Phase-0 edge weights. Edges are oriented **dependent → dependency** so that
influence (PageRank on the reverse) flows toward the most depended-upon actors,
and pressure (personalized PageRank) flows from a stressed dependency outward
to everything that relies on it.

Cached in-process; call `load_graph(force=True)` to refresh after a reseed.
"""

from __future__ import annotations

import logging

import networkx as nx

from apps.api.graph.client import get_neo4j_client
from apps.api.network.weights import RELIEF_RELS, edge_weight, node_factor

logger = logging.getLogger(__name__)

_CACHE: nx.DiGraph | None = None

# Relationships already oriented dependent → dependency in the seed.
# (start node depends on / is constrained by end node)
# We keep Neo4j's native direction for these; reverse the supply-side ones.
_SUPPLY_SIDE_REVERSE: frozenset[str] = frozenset({
    "PRODUCES",        # (plant)-[PRODUCES]->(material): material depends on plant → reverse
    "IS_FORM_OF",      # (material)-[IS_FORM_OF]->(commodity): keep (material dep on commodity)
})
# Note: IS_FORM_OF is actually dependent→dependency already, so only PRODUCES reverses.
_REVERSE_RELS: frozenset[str] = frozenset({"PRODUCES"})


async def _fetch_nodes_edges() -> tuple[list[dict], list[dict]]:
    client = await get_neo4j_client()
    nodes = await client.run("""
        MATCH (n)
        RETURN elementId(n) AS id, labels(n)[0] AS label, n.name AS name,
               n.criticality AS criticality, n.impact_weight AS impact_weight
    """)
    edges = await client.run("""
        MATCH (a)-[e]->(b)
        RETURN elementId(a) AS src, elementId(b) AS dst,
               type(e) AS rel, properties(e) AS props
    """)
    return nodes, edges


async def load_graph(force: bool = False) -> nx.DiGraph:
    """Return the weighted dependency DiGraph (cached).
    Returns an empty graph when Neo4j is unavailable so callers degrade gracefully."""
    global _CACHE
    if _CACHE is not None and not force:
        return _CACHE

    try:
        nodes, edges = await _fetch_nodes_edges()
    except Exception as exc:
        logger.warning("[topology] Neo4j unavailable — returning empty graph: %s", exc)
        return nx.DiGraph()
    g = nx.DiGraph()

    for n in nodes:
        name = n.get("name")
        if not name:
            continue
        g.add_node(
            name,
            label=n.get("label"),
            criticality=n.get("criticality"),
            impact_weight=float(n["impact_weight"]) if n.get("impact_weight") is not None else 0.5,
            node_factor=node_factor(n.get("criticality")),
        )

    # elementId → name map for edge wiring
    id_to_name = {n["id"]: n.get("name") for n in nodes if n.get("name")}

    relief_count = 0
    for e in edges:
        rel = e["rel"]
        src = id_to_name.get(e["src"])
        dst = id_to_name.get(e["dst"])
        if not src or not dst:
            continue
        if rel in RELIEF_RELS:
            relief_count += 1
            # store relief edges separately as a node attribute count (used to
            # discount pressure where alternatives exist)
            g.nodes[src].setdefault("alternatives", 0)
            g.nodes[src]["alternatives"] += 1
            continue

        w = edge_weight(rel, e.get("props"))
        # Orient dependent → dependency
        u, v = (dst, src) if rel in _REVERSE_RELS else (src, dst)
        if g.has_edge(u, v):
            # keep the strongest coupling if multiple rels connect the pair
            g[u][v]["weight"] = max(g[u][v]["weight"], w)
            g[u][v]["rels"].append(rel)
        else:
            g.add_edge(u, v, weight=w, rels=[rel])

    logger.info(
        "[topology] Loaded graph: %d nodes, %d edges (%d relief edges folded)",
        g.number_of_nodes(), g.number_of_edges(), relief_count,
    )
    _CACHE = g
    return g


def clear_cache() -> None:
    global _CACHE
    _CACHE = None
