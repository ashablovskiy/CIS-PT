"""Node 2 — Graph Retriever: K-hop Neo4j traversal from triage entities.

For each identified supplier / commodity / port, runs the appropriate
Cypher query and returns a structured subgraph that the synthesizer can
reason over (affected plants, shipping routes, alternative suppliers, etc.).
"""

from __future__ import annotations

import logging
from typing import Any

from apps.api.agents.state import AssessmentState
from apps.api.graph.client import get_neo4j_client

logger = logging.getLogger(__name__)

# Max nodes returned per entity to keep context window manageable
_LIMIT = 15


def _triage_data(state: AssessmentState) -> dict[str, Any]:
    for item in state.graph_context:
        if "_triage" in item:
            return item["_triage"]
    return {}


async def graph_retriever_node(state: AssessmentState) -> AssessmentState:
    """Traverse Neo4j from triage entities and collect supply-chain context."""
    if not state.triage_passed:
        return state

    triage = _triage_data(state)
    entities = triage.get("graph_entities", {})
    event_class = triage.get("event_class", "")

    client = await get_neo4j_client()
    graph_context: list[dict[str, Any]] = [state.graph_context[0]]  # keep triage entry

    # ── Commodity → Plant → Supplier → Port expansion ────────────────────────
    for commodity in (entities.get("commodities") or [])[:3]:
        try:
            rows = await client.run("""
                MATCH (c:Commodity)
                WHERE toLower(c.name) = toLower($name)
                   OR $name IN [a IN c.aliases | toLower(a)]
                OPTIONAL MATCH (c)<-[:IS_FORM_OF]-(m:Material)<-[:USES_MATERIAL]-(p:Plant)
                              -[:OPERATED_BY]->(s:Supplier)
                OPTIONAL MATCH (p)-[:SHIPS_VIA]->(port:Port)-[:ON_LANE]->(lane:Lane)
                OPTIONAL MATCH (p)-[:LOCATED_IN]->(co:Country)
                RETURN c.name AS commodity,
                       collect(DISTINCT {
                           material: m.name, plant: p.name, supplier: s.name,
                           country: co.name, port: port.name, lane: lane.name
                       }) AS affected
                LIMIT $limit
            """, name=commodity.lower(), limit=_LIMIT)

            if rows:
                graph_context.append({
                    "type": "commodity_expansion",
                    "commodity": commodity,
                    "affected": rows[0].get("affected", []),
                })
                logger.info("[graph_retriever] Commodity %s → %d affected nodes",
                            commodity, len(rows[0].get("affected", [])))
        except Exception as exc:
            logger.warning("[graph_retriever] Commodity query failed for %s: %s", commodity, exc)

    # ── Supplier → Plants + Sub-tiers + Alternatives ─────────────────────────
    for supplier in (entities.get("suppliers") or [])[:3]:
        try:
            rows = await client.run("""
                MATCH (s:Supplier)
                WHERE toLower(s.name) = toLower($name)
                   OR $name IN [a IN s.aliases | toLower(a)]
                OPTIONAL MATCH (s)<-[:OPERATED_BY]-(p:Plant)-[:LOCATED_IN]->(co:Country)
                OPTIONAL MATCH (p)-[:USES_MATERIAL]->(m:Material)-[:IS_FORM_OF]->(c:Commodity)
                OPTIONAL MATCH (p)-[:SHIPS_VIA]->(port:Port)
                OPTIONAL MATCH (s)-[:ALTERNATIVE_TO]->(alt:Supplier)
                OPTIONAL MATCH (s)<-[:SUB_TIER_OF]-(sub:Supplier)
                RETURN s.name AS supplier, s.tier AS tier,
                       collect(DISTINCT p.name) AS plants,
                       collect(DISTINCT co.name) AS countries,
                       collect(DISTINCT c.name) AS commodities,
                       collect(DISTINCT port.name) AS ports,
                       collect(DISTINCT alt.name) AS alternatives,
                       collect(DISTINCT sub.name) AS sub_tiers
                LIMIT $limit
            """, name=supplier.lower(), limit=_LIMIT)

            if rows:
                graph_context.append({
                    "type": "supplier_expansion",
                    "supplier": supplier,
                    **{k: rows[0].get(k) for k in
                       ("tier", "plants", "countries", "commodities", "ports",
                        "alternatives", "sub_tiers")},
                })
                logger.info("[graph_retriever] Supplier %s → plants=%s alts=%s",
                            supplier,
                            rows[0].get("plants", []),
                            rows[0].get("alternatives", []))
        except Exception as exc:
            logger.warning("[graph_retriever] Supplier query failed for %s: %s", supplier, exc)

    # ── Port → Lanes + affected suppliers ────────────────────────────────────
    for port in (entities.get("ports") or [])[:2]:
        try:
            rows = await client.run("""
                MATCH (port:Port)
                WHERE toLower(port.name) = toLower($name)
                   OR port.locode = toUpper($name)
                   OR $name IN [a IN port.aliases | toLower(a)]
                OPTIONAL MATCH (port)-[:ON_LANE]->(lane:Lane)
                OPTIONAL MATCH (p:Plant)-[:SHIPS_VIA]->(port)
                              -[:OPERATED_BY|OPERATED_BY*1]->(s:Supplier)
                RETURN port.name AS port, port.locode AS locode,
                       collect(DISTINCT lane.name) AS lanes,
                       collect(DISTINCT s.name) AS suppliers_exposed
                LIMIT $limit
            """, name=port.lower(), limit=_LIMIT)

            if rows:
                graph_context.append({
                    "type": "port_expansion",
                    "port": port,
                    **{k: rows[0].get(k) for k in ("locode", "lanes", "suppliers_exposed")},
                })
        except Exception as exc:
            logger.warning("[graph_retriever] Port query failed for %s: %s", port, exc)

    # ── Demand surge: hyperscaler → transformer category ─────────────────────
    if event_class == "demand_surge":
        try:
            rows = await client.run("""
                MATCH (ds:DemandSource)-[:DRIVES_DEMAND_FOR]->(cat:Category)
                RETURN ds.name AS demand_source, collect(cat.name) AS categories
                LIMIT 6
            """)
            if rows:
                graph_context.append({
                    "type": "demand_context",
                    "demand_drivers": rows,
                })
        except Exception as exc:
            logger.warning("[graph_retriever] Demand query failed: %s", exc)

    state.graph_context = graph_context
    logger.info("[graph_retriever] Graph context: %d entries", len(graph_context))
    return state
