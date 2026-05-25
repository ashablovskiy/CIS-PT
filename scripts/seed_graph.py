"""Seed the Neo4j supply graph with power-transformer domain entities.

Loads node + edge data from scripts/seed_data/transformers_graph.py and
MERGEs into Neo4j. Idempotent — safe to re-run.

Run:
    uv run python scripts/seed_graph.py

Requires environment variables:
    NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD
(read from .env via apps.api.settings)

Per PROJECT_SPEC.md §7.1 and ADR-0001.
"""

from __future__ import annotations

import logging
import sys
from collections import defaultdict
from pathlib import Path

# Add repo root to path so we can import apps.api.* and scripts.seed_data.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from neo4j import GraphDatabase

from apps.api.settings import settings
from scripts.seed_data import transformers_graph as g

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("seed_graph")


# ─────────────────────────────────────────────────────────────────────────────
# Node-loading order matters: load entities BEFORE the edges that reference them.
# Each tuple is (label, list_of_dicts, primary_key_property).
# ─────────────────────────────────────────────────────────────────────────────
NODE_GROUPS: list[tuple[str, list[dict], str]] = [
    ("Commodity", g.COMMODITIES, "name"),
    ("Material", g.MATERIALS, "name"),
    ("Country", g.COUNTRIES, "name"),
    ("Supplier", g.SUPPLIERS, "name"),
    ("Plant", g.PLANTS, "name"),
    ("Port", g.PORTS, "name"),
    ("Lane", g.LANES, "name"),
    ("Category", g.CATEGORIES, "name"),
    ("DemandSource", g.DEMAND_SOURCES, "name"),
]


def reset_graph(driver) -> None:
    """Wipe the database. Used when --reset flag is passed."""
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
    logger.warning("Graph wiped.")


def create_constraints(driver) -> None:
    """Create uniqueness constraints on `name` for every label."""
    with driver.session() as session:
        for label, _, key in NODE_GROUPS:
            session.run(
                f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) "
                f"REQUIRE n.{key} IS UNIQUE"
            )
    logger.info("Uniqueness constraints ensured for %d labels.", len(NODE_GROUPS))


def load_nodes(driver) -> None:
    with driver.session() as session:
        for label, items, key in NODE_GROUPS:
            cypher = (
                f"UNWIND $items AS row "
                f"MERGE (n:{label} {{{key}: row.{key}}}) "
                f"SET n += row"
            )
            session.run(cypher, items=items)
            logger.info("Loaded %3d %s nodes", len(items), label)


def load_edges(driver) -> None:
    # Group edges by (type, start_label, end_label) for efficient UNWIND.
    buckets: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for rel_type, start_label, start_name, end_label, end_name, props in g.EDGES:
        buckets[(rel_type, start_label, end_label)].append(
            {"start": start_name, "end": end_name, "props": props or {}}
        )

    with driver.session() as session:
        total = 0
        for (rel_type, start_label, end_label), rows in buckets.items():
            cypher = (
                f"UNWIND $rows AS row "
                f"MATCH (s:{start_label} {{name: row.start}}) "
                f"MATCH (e:{end_label} {{name: row.end}}) "
                f"MERGE (s)-[r:{rel_type}]->(e) "
                f"SET r += row.props"
            )
            session.run(cypher, rows=rows)
            total += len(rows)
            logger.info(
                "Loaded %3d (%s)-[:%s]->(%s) edges",
                len(rows), start_label, rel_type, end_label,
            )
        logger.info("Edges total: %d", total)


def summary(driver) -> None:
    with driver.session() as session:
        n = session.run("MATCH (n) RETURN count(n) AS n").single()["n"]
        r = session.run("MATCH ()-[r]->() RETURN count(r) AS r").single()["r"]
    logger.info("══ Graph now contains %d nodes and %d relationships ══", n, r)


def main() -> int:
    reset = "--reset" in sys.argv

    logger.info("Connecting to Neo4j at %s", settings.neo4j_uri)
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_username, settings.neo4j_password),
    )
    try:
        driver.verify_connectivity()
    except Exception as exc:
        logger.error("Could not connect to Neo4j: %s", exc)
        return 1

    try:
        if reset:
            reset_graph(driver)
        create_constraints(driver)
        load_nodes(driver)
        load_edges(driver)
        summary(driver)
    finally:
        driver.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
