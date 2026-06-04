"""Layer 2 — ANT Actor Map (canonical definition, MVP v1).

Eight systemic actors: structural forces, constraints and roles that govern
the power-transformer supply chain. NOT specific companies, plants or ports —
those live in Layer 1 (Neo4j). Signals about named entities roll up via
rollup.py into these force-level actors.

MVP scope excludes GOES_Supply, Winding_Metals, Insulation_Dielectrics and
Skilled_Labor — added once more signal volume accumulates for those channels.
"""

from __future__ import annotations

from collections import Counter

BANDS = ["components", "production", "logistics", "trade_geo", "demand"]


ACTORS: list[dict] = [
    # ── COMPONENTS ───────────────────────────────────────────────────────────
    {
        "id": "Critical_Components",
        "label": "Critical Components",
        "band": "components",
        "criticality": "critical",
        "impact_weight": 0.88,
        "definition": "On-load tap changers (OLTC) and HV bushings — certified, "
                      "few-supplier sub-assemblies.",
        "why": "Reinhausen-dominated OLTCs and Trench/HSP bushings are certified "
               "per application. One late part holds the entire transformer build.",
    },

    # ── PRODUCTION ───────────────────────────────────────────────────────────
    {
        "id": "OEM_Production_Capacity",
        "label": "OEM Production Capacity",
        "band": "production",
        "criticality": "critical",
        "impact_weight": 0.92,
        "definition": "Aggregate transformer-manufacturing throughput and backlog "
                      "across all OEMs.",
        "why": "The convergence point where components, materials and labor combine "
               "and demand queues form. Factory slots booked 2–4 years out.",
    },

    # ── LOGISTICS ────────────────────────────────────────────────────────────
    {
        "id": "Heavy_Lift_Logistics",
        "label": "Heavy-Lift Logistics",
        "band": "logistics",
        "criticality": "high",
        "impact_weight": 0.68,
        "definition": "Capacity to move 100–400 t finished units: breakbulk vessels, "
                      "Schnabel rail, route permits, heavy-lift ports.",
        "why": "Finished transformers can't move by container. ~3 Schnabel cars in "
               "N. America, permits up to 9 months. Adds months after factory exit.",
    },

    # ── TRADE & GEOPOLITICS ──────────────────────────────────────────────────
    {
        "id": "Trade_Policy_Regime",
        "label": "Trade & Policy Regime",
        "band": "trade_geo",
        "criticality": "high",
        "impact_weight": 0.72,
        "definition": "Tariffs, AD/CVD duties, export controls and sanctions "
                      "touching steel, components or finished units.",
        "why": "Section 232, AD/CVD on GOES, export controls can tighten supply or "
               "reroute trade overnight — a cross-cutting amplifier.",
    },
    {
        "id": "Geographic_Concentration",
        "label": "Geographic Concentration",
        "band": "trade_geo",
        "criticality": "high",
        "impact_weight": 0.70,
        "definition": "Structural dependence on a few producing regions and the "
                      "chokepoints connecting them.",
        "why": "OEM capacity clusters in KR/JP/CN/DE; US exports funnel through "
               "Panama/Suez and a handful of ports. One regional shock exposes all.",
    },

    # ── DEMAND ───────────────────────────────────────────────────────────────
    {
        "id": "AI_Datacenter_Demand",
        "label": "AI / Data-Center Demand",
        "band": "demand",
        "criticality": "critical",
        "impact_weight": 0.90,
        "definition": "The hyperscaler / AI-compute build-out pulling transformers "
                      "out of the global queue.",
        "why": "Demand pushing toward ~9,000 units/yr by 2030. Developers pre-buy "
               "factory slots, making the backlog itself the constraint.",
    },
    {
        "id": "Grid_Modernization_Demand",
        "label": "Grid Modernization Demand",
        "band": "demand",
        "criticality": "critical",
        "impact_weight": 0.85,
        "definition": "Aging-grid replacement, electrification and renewable "
                      "interconnection — the structural demand base.",
        "why": "US fleet average age >40 yr; renewables flood the interconnection "
               "queue. Slower than AI, but larger volume and permanent.",
    },
    {
        "id": "Energy_Transition_Policy",
        "label": "Energy-Transition Policy",
        "band": "demand",
        "criticality": "high",
        "impact_weight": 0.62,
        "definition": "Public stimulus that accelerates demand: IRA, REPowerEU, "
                      "grid-funding and electrification mandates.",
        "why": "Doesn't consume transformers directly — it accelerates grid and "
               "DC demand actors, pulling demand forward in time.",
    },
]


ACTOR_EDGES: list[dict] = [
    # Component constraint
    {"type": "CONSTRAINS", "src": "Critical_Components",     "dst": "OEM_Production_Capacity", "weight": 0.90},

    # Production → logistics serial gate
    {"type": "GATES",      "src": "OEM_Production_Capacity", "dst": "Heavy_Lift_Logistics",    "weight": 0.70},

    # Demand pulls on production & components & logistics
    {"type": "PRESSURES",  "src": "AI_Datacenter_Demand",       "dst": "OEM_Production_Capacity",  "weight": 0.90},
    {"type": "PRESSURES",  "src": "Grid_Modernization_Demand",  "dst": "OEM_Production_Capacity",  "weight": 0.85},
    {"type": "PRESSURES",  "src": "AI_Datacenter_Demand",       "dst": "Critical_Components",      "weight": 0.55},
    {"type": "PRESSURES",  "src": "Grid_Modernization_Demand",  "dst": "Heavy_Lift_Logistics",     "weight": 0.50},

    # Policy amplifies demand actors
    {"type": "AMPLIFIES",  "src": "Energy_Transition_Policy",  "dst": "Grid_Modernization_Demand", "weight": 0.70},
    {"type": "AMPLIFIES",  "src": "Energy_Transition_Policy",  "dst": "AI_Datacenter_Demand",      "weight": 0.40},

    # Trade & geo amplify production and logistics
    {"type": "AMPLIFIES",  "src": "Trade_Policy_Regime",       "dst": "OEM_Production_Capacity",   "weight": 0.60},
    {"type": "AMPLIFIES",  "src": "Geographic_Concentration",  "dst": "OEM_Production_Capacity",   "weight": 0.60},
    {"type": "AMPLIFIES",  "src": "Geographic_Concentration",  "dst": "Heavy_Lift_Logistics",      "weight": 0.65},
    {"type": "AMPLIFIES",  "src": "Trade_Policy_Regime",       "dst": "Geographic_Concentration",  "weight": 0.55},
]


def actor_by_id(actor_id: str) -> dict | None:
    return next((a for a in ACTORS if a["id"] == actor_id), None)


def actor_ids() -> list[str]:
    return [a["id"] for a in ACTORS]


def summary() -> dict:
    return {
        "actors": len(ACTORS),
        "edges": len(ACTOR_EDGES),
        "by_band": dict(Counter(a["band"] for a in ACTORS)),
        "by_edge_type": dict(Counter(e["type"] for e in ACTOR_EDGES)),
    }
