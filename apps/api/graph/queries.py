"""Named Cypher query library for the supply graph.

All queries are parametrized — never format user input into Cypher strings.
"""

from __future__ import annotations

# ── K-hop expansion from a named entity ──────────────────────────────────────

K_HOP_FROM_COMMODITY = """
MATCH path = (c:Commodity {name: $commodity_name})<-[:IS_FORM_OF]-(m:Material)
             <-[:USES_MATERIAL]-(p:Plant)-[:OPERATED_BY]->(s:Supplier)
OPTIONAL MATCH (p)-[:SHIPS_VIA]->(port:Port)-[:ON_LANE]->(lane:Lane)
RETURN c, m, p, s, port, lane
LIMIT $limit
"""

K_HOP_FROM_SUPPLIER = """
MATCH (s:Supplier {name: $supplier_name})
OPTIONAL MATCH (s)<-[:OPERATED_BY]-(p:Plant)-[:LOCATED_IN]->(co:Country)
OPTIONAL MATCH (p)-[:USES_MATERIAL]->(m:Material)-[:IS_FORM_OF]->(c:Commodity)
OPTIONAL MATCH (p)-[:SHIPS_VIA]->(port:Port)
RETURN s, p, co, m, c, port
LIMIT $limit
"""

CONTRACTS_FOR_SUPPLIER = """
MATCH (c:Contract)-[:WITH]->(s:Supplier {name: $supplier_name})
OPTIONAL MATCH (c)-[:HAS_CLAUSE]->(cl:Clause)-[:REFERENCES]->(com:Commodity)
RETURN c, cl, com
"""

SUPPLIERS_BY_COMMODITY = """
MATCH (s:Supplier)<-[:OPERATED_BY]-(p:Plant)-[:USES_MATERIAL]->(m:Material)
      -[:IS_FORM_OF]->(c:Commodity {name: $commodity_name})
RETURN DISTINCT s.name AS supplier, p.name AS plant, p.country AS country
"""

PORTS_ON_LANE = """
MATCH (port:Port)-[:ON_LANE]->(lane:Lane {name: $lane_name})
RETURN port.name AS port, port.locode AS locode
"""

# ── Contract clause lookups ───────────────────────────────────────────────────

CLAUSES_BY_TYPE = """
MATCH (c:Contract)-[:HAS_CLAUSE]->(cl:Clause {type: $clause_type})
RETURN c.external_id AS contract_id, cl
"""
