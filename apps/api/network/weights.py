"""Phase 0 — edge + node weighting.

Neo4j edges do not carry a numeric weight; they carry categorical `severity` /
`criticality` (or nothing). To run propagation math we derive a numeric weight
in (0, 1] per edge from:

    edge_weight = rel_base[rel_type] × severity_factor(props)

These are documented, tunable priors — not learned. They live here so a single
table governs all propagation behavior.

Node-level criticality is also mapped to a numeric multiplier used by the
health/bottleneck logic.
"""

from __future__ import annotations

# Base weight per relationship type — how strongly a disruption on the target
# propagates to the source (dependent). Higher = tighter coupling.
# Direction note: topology.py orients every edge dependent → dependency, so a
# high weight means "the dependent strongly relies on this dependency."
REL_BASE_WEIGHT: dict[str, float] = {
    "CONSTRAINS":        0.95,  # commodity/material is a hard constraint on a category
    "USES_MATERIAL":     0.85,  # plant depends on the material it consumes
    "IS_FORM_OF":        0.80,  # material derives from a commodity
    "SUB_TIER_OF":       0.75,  # supplier depends on its sub-tier supplier
    "PRODUCES":          0.70,  # plant/supplier produces a material (supply side)
    "OPERATED_BY":       0.65,  # plant operated by a supplier
    "SHIPS_VIA":         0.60,  # plant ships finished goods via a port
    "ON_LANE":           0.55,  # port feeds a shipping lane
    "DEMAND_PULLS_ON":   0.55,  # demand source pulls on a category/supplier
    "DRIVES_DEMAND_FOR": 0.55,  # demand source drives demand for a category
    "LOCATED_IN":        0.40,  # plant located in a country (geo exposure)
    "BELONGS_TO_THEME":  0.35,  # demand source belongs to a theme grouping
    # ALTERNATIVE_TO is intentionally excluded from propagation: an alternative
    # supplier *relieves* rather than transmits pressure. Handled separately.
}

# Categorical severity / criticality → numeric multiplier.
SEVERITY_FACTOR: dict[str, float] = {
    "critical": 1.0,
    "high":     0.8,
    "medium":   0.5,
    "low":      0.3,
}

_DEFAULT_REL_WEIGHT = 0.45
_DEFAULT_SEVERITY = 0.5

# Relationship types that relieve pressure rather than transmit it.
RELIEF_RELS: frozenset[str] = frozenset({"ALTERNATIVE_TO"})

# Node criticality → multiplier for health / bottleneck scoring.
NODE_CRITICALITY_FACTOR: dict[str, float] = {
    "critical": 1.0,
    "high":     0.75,
    "medium":   0.5,
    "low":      0.25,
}


def edge_weight(rel_type: str, props: dict | None) -> float:
    """Derive a numeric propagation weight in (0, 1] for an edge."""
    base = REL_BASE_WEIGHT.get(rel_type, _DEFAULT_REL_WEIGHT)
    props = props or {}
    sev = props.get("severity") or props.get("criticality")
    factor = SEVERITY_FACTOR.get(sev, _DEFAULT_SEVERITY) if sev else _DEFAULT_SEVERITY
    # If the edge itself carries an impact_weight (e.g. IS_FORM_OF), blend it in.
    iw = props.get("impact_weight")
    if isinstance(iw, (int, float)):
        factor = (factor + float(iw)) / 2.0
    w = base * factor
    return max(0.01, min(1.0, w))


def node_factor(criticality: str | None) -> float:
    """Numeric multiplier for a node's criticality (default medium)."""
    return NODE_CRITICALITY_FACTOR.get(criticality or "medium", 0.5)
