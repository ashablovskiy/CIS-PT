"""KeywordRegistry — builds rule-filter keyword lists from the Neo4j graph.

Instead of maintaining hand-typed keyword lists in each agent, this module
queries Neo4j once at startup and returns keyword sets per agent type.

Every entity name AND every alias is included, all lowercased.
Agents call KeywordRegistry.get(...) to get their keyword list.

Usage:
    from apps.api.ingest.keyword_registry import registry
    keywords = registry.get("press")   # -> list[str]

The registry is a module-level singleton, loaded lazily on first access.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Literal

from neo4j import GraphDatabase

from apps.api.settings import settings

logger = logging.getLogger(__name__)

AgentType = Literal["prices", "gdelt", "logistics", "press", "demand", "sec", "all"]

# Which node labels to pull for each agent type.
# Agents that care about different signal domains get different subsets.
_LABEL_SETS: dict[str, list[str]] = {
    "prices":    ["Commodity"],
    "gdelt":     ["Supplier", "Port", "Country", "Commodity"],
    "logistics": ["Port", "Lane", "Supplier"],
    "press":     ["Supplier", "Commodity", "Port", "DemandSource", "Material"],
    "demand":    ["DemandSource", "Supplier", "Commodity"],
    "sec":       ["Supplier", "Commodity"],
    "all":       ["Supplier", "Commodity", "Port", "Country", "Material", "DemandSource", "Lane"],
}


def _load_from_neo4j() -> dict[str, list[str]]:
    """Query Neo4j and return {label -> [keyword, ...]} with aliases expanded."""
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_username, settings.neo4j_password),
    )
    label_keywords: dict[str, list[str]] = {}

    try:
        with driver.session() as session:
            # Pull name + aliases for every node that has them
            result = session.run("""
                MATCH (n)
                WHERE n.name IS NOT NULL
                RETURN labels(n)[0] AS label,
                       n.name      AS name,
                       n.aliases   AS aliases
            """)
            for record in result:
                label = record["label"]
                name = record["name"]
                aliases = record["aliases"] or []

                terms = set()
                # Primary name — split on underscores (e.g. "Crude_Oil_Freight" → "crude oil freight")
                terms.add(name.lower().replace("_", " "))
                terms.add(name.lower())  # also keep original form

                for alias in aliases:
                    terms.add(alias.lower())

                if label not in label_keywords:
                    label_keywords[label] = []
                label_keywords[label].extend(terms)

        logger.info(
            "[keyword_registry] Loaded from Neo4j: %s",
            {k: len(v) for k, v in label_keywords.items()},
        )
    finally:
        driver.close()

    return label_keywords


class KeywordRegistry:
    """Lazy-loaded, cached keyword registry backed by Neo4j."""

    def __init__(self) -> None:
        self._data: dict[str, list[str]] | None = None

    def _ensure_loaded(self) -> None:
        if self._data is None:
            self._data = _load_from_neo4j()

    def get(self, agent_type: AgentType) -> list[str]:
        """Return deduplicated lowercase keywords for the given agent type."""
        self._ensure_loaded()
        labels = _LABEL_SETS.get(agent_type, [])
        combined: set[str] = set()
        for label in labels:
            combined.update(self._data.get(label, []))
        # Filter out very short terms (< 3 chars) that cause false positives
        return sorted(kw for kw in combined if len(kw) >= 3)

    def reload(self) -> None:
        """Force a reload from Neo4j (call after adding new entities/aliases)."""
        self._data = None
        self._ensure_loaded()

    def all_keywords(self) -> list[str]:
        return self.get("all")

    def summary(self) -> dict[str, int]:
        """Return keyword counts per label for inspection."""
        self._ensure_loaded()
        return {k: len(v) for k, v in self._data.items()}


# Module-level singleton — import this everywhere
registry = KeywordRegistry()
