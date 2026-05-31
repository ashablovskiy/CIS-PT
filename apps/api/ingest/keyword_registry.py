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
    "ir":        ["Supplier", "Commodity", "Material"],
    "all":       ["Supplier", "Commodity", "Port", "Country", "Material", "DemandSource", "Lane"],
}


def _load_from_neo4j() -> tuple[dict[str, list[str]], dict[str, dict]]:
    """Query Neo4j and return:
      - {label -> [keyword, ...]}  for rule-filter keyword lists
      - {keyword_lower -> entity_meta}  for LLM-scorer graph priors

    entity_meta shape: {name, label, criticality, impact_weight}

    Only nodes with impact_weight >= 0.4 contribute to entity_priors — below
    that threshold the graph itself considers them noise for large power
    transformer scoring (e.g. Aluminum at 0.20, Container_Freight at 0.20).
    Keywords shorter than 4 chars are excluded from priors to reduce false
    positives (short tickers, abbreviations like "gas", "oil").
    """
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_username, settings.neo4j_password),
    )
    label_keywords: dict[str, list[str]] = {}
    entity_priors: dict[str, dict] = {}

    try:
        with driver.session() as session:
            result = session.run("""
                MATCH (n)
                WHERE n.name IS NOT NULL
                RETURN labels(n)[0]  AS label,
                       n.name        AS name,
                       n.aliases     AS aliases,
                       n.criticality   AS criticality,
                       n.impact_weight AS impact_weight
            """)
            for record in result:
                label = record["label"]
                name = record["name"]
                aliases = record["aliases"] or []
                criticality = record["criticality"]
                impact_weight = record["impact_weight"]

                terms: set[str] = set()
                terms.add(name.lower().replace("_", " "))
                terms.add(name.lower())
                for alias in aliases:
                    terms.add(alias.lower())

                if label not in label_keywords:
                    label_keywords[label] = []
                label_keywords[label].extend(terms)

                # Populate entity_priors only for well-weighted, signal-bearing nodes
                if criticality and impact_weight is not None:
                    w = float(impact_weight)
                    if w >= 0.4:
                        meta = {
                            "name": name,
                            "label": label,
                            "criticality": criticality,
                            "impact_weight": w,
                        }
                        for term in terms:
                            if len(term) >= 4:
                                # Keep the highest-weight entity for each keyword
                                existing = entity_priors.get(term)
                                if existing is None or w > existing["impact_weight"]:
                                    entity_priors[term] = meta

        logger.info(
            "[keyword_registry] Loaded from Neo4j: labels=%s prior_entries=%d",
            {k: len(v) for k, v in label_keywords.items()},
            len(entity_priors),
        )
    finally:
        driver.close()

    return label_keywords, entity_priors


class KeywordRegistry:
    """Lazy-loaded, cached keyword registry backed by Neo4j."""

    def __init__(self) -> None:
        self._data: dict[str, list[str]] | None = None
        self._entity_priors: dict[str, dict] | None = None

    def _ensure_loaded(self) -> None:
        if self._data is None:
            self._data, self._entity_priors = _load_from_neo4j()

    def get(self, agent_type: AgentType) -> list[str]:
        """Return deduplicated lowercase keywords for the given agent type."""
        self._ensure_loaded()
        labels = _LABEL_SETS.get(agent_type, [])
        combined: set[str] = set()
        for label in labels:
            combined.update(self._data.get(label, []))
        # Filter out very short terms (< 3 chars) that cause false positives
        return sorted(kw for kw in combined if len(kw) >= 3)

    def get_entity_priors(self) -> dict[str, dict]:
        """Return {keyword_lower -> entity_meta} for LLM-scorer graph-prior injection.

        Each value is a dict with keys: name, label, criticality, impact_weight.
        Only entities with impact_weight >= 0.4 are included (set at load time).
        """
        self._ensure_loaded()
        return self._entity_priors or {}

    def reload(self) -> None:
        """Force a reload from Neo4j (call after adding new entities/aliases)."""
        self._data = None
        self._entity_priors = None
        self._ensure_loaded()

    def all_keywords(self) -> list[str]:
        return self.get("all")

    def summary(self) -> dict[str, int]:
        """Return keyword counts per label for inspection."""
        self._ensure_loaded()
        return {k: len(v) for k, v in self._data.items()}


# Module-level singleton — import this everywhere
registry = KeywordRegistry()
