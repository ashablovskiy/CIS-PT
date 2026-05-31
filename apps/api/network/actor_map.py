"""Layer 2 — ANT Actor Map (canonical definition).

This is the Actor-Network Theory layer: systemic *forces, structural conditions
and roles* that govern the power-transformer supply chain — NOT specific
companies, plants or ports (those live in Layer 1, the Neo4j ingestion entity
map).

An actor here is a thing like "the structural scarcity of grain-oriented
electrical steel," not "Nippon Steel." Nippon Steel, POSCO and Cleveland-Cliffs
are *expressions* of the GOES_Supply actor. Signals about any of them roll up
into pressure on that one actor.

This module is DEFINITION ONLY (data + the Layer-1→Layer-2 rollup spec). It is
intentionally not yet wired into the state engine — that is a later step. See
docs/decisions/ADR-0003-network-state-intelligence.md and the actor-map diagram
at docs/diagram-actor-map.html.

Design depth: 12 actors across 5 bands. Reasonable resolution — every actor is a
real, separately-actionable lever in LPT supply; none is a specific company.
"""

from __future__ import annotations

# ── Bands (purely for grouping / display) ─────────────────────────────────────
BANDS = ["material_inputs", "components", "production", "logistics",
         "trade_geo", "demand"]


# ── ACTORS ────────────────────────────────────────────────────────────────────
# id            stable key
# label         display name
# band          grouping
# criticality   critical | high | medium
# impact_weight 0–1 systemic prior (seed for influence blend)
# definition    what the actor IS (the force, not the companies)
# why           why it matters in LPT supply
# fed_by        Layer-1 entity selectors that roll up into this actor
#               (label[:type/filter]) — the aggregation spec, reviewed here,
#               implemented in a later step.

ACTORS: list[dict] = [
    # ── MATERIAL INPUTS ──────────────────────────────────────────────────────
    {
        "id": "GOES_Supply",
        "label": "GOES Supply",
        "band": "material_inputs",
        "criticality": "critical",
        "impact_weight": 0.95,
        "definition": "Structural scarcity of grain-oriented electrical steel — "
                      "the transformer core material.",
        "why": "~10 capable mills worldwide, processing- and know-how-bound (not "
               "ore-bound), multi-year qualification, prices up 60–77% since 2020. "
               "The single hardest constraint in the industry.",
        "fed_by": ["Commodity:GOES", "Material:GOES_*",
                   "Supplier(type=goes_mill)", "Plant(specialty=goes_mill)"],
    },
    {
        "id": "Winding_Metals",
        "label": "Winding Metals",
        "band": "material_inputs",
        "criticality": "high",
        "impact_weight": 0.70,
        "definition": "Copper (and, for distribution, aluminum) for the windings.",
        "why": "Globally available, so rarely an availability bottleneck — but "
               "highly price-volatile, the main material cost driver.",
        "fed_by": ["Commodity:Copper", "Commodity:Aluminum",
                   "Material:Cu_*", "Material:Al_*"],
    },
    {
        "id": "Insulation_Dielectrics",
        "label": "Insulation & Dielectrics",
        "band": "material_inputs",
        "criticality": "high",
        "impact_weight": 0.62,
        "definition": "Pressboard, aramid paper, naphthenic transformer oil and "
                      "ester fluids — the dielectric system.",
        "why": "Concentrated suppliers (Weidmann pressboard, DuPont Nomex) and "
               "refining-constrained naphthenic oil; long approval cycles. Second-"
               "sourcing exists, so elevated rather than binding.",
        "fed_by": ["Commodity:Transformer_Oil_Naphthenic", "Commodity:Cellulose_Pressboard",
                   "Commodity:Aramid_Paper", "Commodity:Ester_Fluid",
                   "Supplier(type=insulation)", "Supplier(type=oil_refinery)"],
    },

    # ── COMPONENTS ───────────────────────────────────────────────────────────
    {
        "id": "Critical_Components",
        "label": "Critical Components",
        "band": "components",
        "criticality": "critical",
        "impact_weight": 0.88,
        "definition": "On-load tap changers (OLTC) and HV bushings — the "
                      "certified, few-supplier sub-assemblies.",
        "why": "OLTCs (Reinhausen-dominated) and bushings (Trench/HSP) are "
               "certified per application and served by a handful of suppliers; "
               "one late part holds the whole transformer.",
        "fed_by": ["Supplier(type=tap_changer_oltc)", "Supplier(type=bushings)",
                   "Material:OLTC_*", "Material:Bushing_*",
                   "Plant(specialty=oltc)", "Plant(specialty=bushings)"],
    },

    # ── PRODUCTION (the convergence) ─────────────────────────────────────────
    {
        "id": "OEM_Production_Capacity",
        "label": "OEM Production Capacity",
        "band": "production",
        "criticality": "critical",
        "impact_weight": 0.92,
        "definition": "Aggregate transformer-manufacturing throughput and backlog "
                      "across all OEMs.",
        "why": "The convergence point: materials, components and labor combine "
               "here and demand queues form here. Slots booked 2–4 years out. "
               "Where almost every pressure path ultimately lands.",
        "fed_by": ["Supplier(type=transformer_oem)",
                   "Plant(specialty IN large_power,uhv,hvdc,gsu,"
                   "data_center_class,distribution,mobile_substation)",
                   "Category(all transformer types)"],
    },
    {
        "id": "Skilled_Labor",
        "label": "Skilled Labor",
        "band": "production",
        "criticality": "high",
        "impact_weight": 0.60,
        "definition": "The specialised workforce — coil winders, core stackers, "
                      "HV test engineers.",
        "why": "A distinct lever from factory slots: capacity is useless without "
               "trained winders. Repeatedly cited; strikes / retirements / hiring "
               "gate output. NOTE: weak direct entity backing in Layer 1 — "
               "populated mainly by labor-themed signals on OEM plants.",
        "fed_by": ["(signal impact_type ~ labor)", "Plant(specialty=large_power) [labor events]"],
    },

    # ── LOGISTICS (the exit gate) ────────────────────────────────────────────
    {
        "id": "Heavy_Lift_Logistics",
        "label": "Heavy-Lift Logistics",
        "band": "logistics",
        "criticality": "high",
        "impact_weight": 0.68,
        "definition": "The capacity to physically move 100–400 t finished units: "
                      "breakbulk vessels, Schnabel rail, route permits, heavy-lift ports.",
        "why": "Finished transformers can't move by container. Few Schnabel cars "
               "(~3 in N. America), permits up to ~9 months, congestion at the "
               "handful of heavy-lift ports. Adds months downstream of the factory.",
        "fed_by": ["Commodity:Heavy_Lift_Freight", "Port(all)", "Lane(all)"],
    },

    # ── TRADE & GEOPOLITICS (cross-cutting amplifiers) ───────────────────────
    {
        "id": "Trade_Policy_Regime",
        "label": "Trade & Policy Regime",
        "band": "trade_geo",
        "criticality": "high",
        "impact_weight": 0.72,
        "definition": "Tariffs, anti-dumping / countervailing duties, export "
                      "controls and sanctions touching steel, components or units.",
        "why": "Section 232 steel tariffs, AD/CVD on GOES, export controls can "
               "tighten supply or reroute trade overnight. A cross-cutting force "
               "that amplifies material and production constraints. NOTE: weak "
               "direct entity backing in Layer 1 — populated mainly by "
               "impact_type='Regulatory / trade' signals + Country trade flags.",
        "fed_by": ["(signal impact_type = Regulatory / trade)",
                   "Country(trade_policy events)"],
    },
    {
        "id": "Geographic_Concentration",
        "label": "Geographic Concentration",
        "band": "trade_geo",
        "criticality": "high",
        "impact_weight": 0.70,
        "definition": "Structural dependence on a few producing regions and the "
                      "chokepoints that connect them.",
        "why": "GOES mills and Tier-1 OEM capacity cluster in KR / JP / CN / DE; "
               "exports to the US funnel through Panama/Suez and a few ports. A "
               "single regional shock or lane closure exposes the whole chain.",
        "fed_by": ["Country(goes_producer=true)", "Country(oem_hub=true)",
                   "Lane(chokepoint != none)"],
    },

    # ── DEMAND (the pull) ────────────────────────────────────────────────────
    {
        "id": "AI_Datacenter_Demand",
        "label": "AI / Data-Center Demand",
        "band": "demand",
        "criticality": "critical",
        "impact_weight": 0.90,
        "definition": "The hyperscaler / AI-compute build-out pulling transformers "
                      "out of the global queue.",
        "why": "Pushes demand from ~1,500 toward ~9,000 units/yr by 2030. "
               "Developers pre-buy factory slots, so the backlog itself becomes "
               "the constraint for everyone behind them.",
        "fed_by": ["DemandSource(theme=Data_Center_AI_Demand)",
                   "DemandSource(actors: Microsoft, Google, Amazon, Meta, "
                   "OpenAI, Anthropic, Oracle, CoreWeave, …)"],
    },
    {
        "id": "Grid_Modernization_Demand",
        "label": "Grid Modernization Demand",
        "band": "demand",
        "criticality": "critical",
        "impact_weight": 0.85,
        "definition": "Aging-grid replacement, electrification and renewable "
                      "interconnection — the structural demand base.",
        "why": "US fleet average age >40 yr; electrification + renewables flood the "
               "interconnection queue. Slower-moving than AI but larger and "
               "permanent.",
        "fed_by": ["DemandSource(theme=Grid_Replacement_Aging)",
                   "DemandSource(theme=Renewable_Interconnection)",
                   "DemandSource(theme=Electrification)"],
    },
    {
        "id": "Energy_Transition_Policy",
        "label": "Energy-Transition Policy",
        "band": "demand",
        "criticality": "high",
        "impact_weight": 0.62,
        "definition": "Public stimulus that accelerates demand: IRA, REPowerEU, "
                      "grid-funding and electrification mandates.",
        "why": "Doesn't consume transformers itself — it accelerates the grid and "
               "DC demand actors, pulling demand forward in time.",
        "fed_by": ["DemandSource(theme=IRA_Grid_Investment)",
                   "DemandSource(theme=REPowerEU)",
                   "DemandSource(policy themes)"],
    },
]


# ── INTER-ACTOR EDGES (the ANT web) ───────────────────────────────────────────
# How forces act on each other. Edge semantics:
#   CONSTRAINS  supply-side actor limits another (lack of it blocks output)
#   PRESSURES   demand-side actor pulls on another (raises load / queue)
#   GATES       output must pass through (a serial dependency)
#   AMPLIFIES   a force strengthens another force (cross-cutting)
#
# weight is the base coupling strength (0–1); severity/recency applied later.

ACTOR_EDGES: list[dict] = [
    # Supply & components constrain production
    {"type": "CONSTRAINS", "src": "GOES_Supply",            "dst": "OEM_Production_Capacity", "weight": 0.95},
    {"type": "CONSTRAINS", "src": "Critical_Components",    "dst": "OEM_Production_Capacity", "weight": 0.90},
    {"type": "CONSTRAINS", "src": "Winding_Metals",         "dst": "OEM_Production_Capacity", "weight": 0.70},
    {"type": "CONSTRAINS", "src": "Insulation_Dielectrics", "dst": "OEM_Production_Capacity", "weight": 0.65},
    {"type": "CONSTRAINS", "src": "Skilled_Labor",          "dst": "OEM_Production_Capacity", "weight": 0.65},

    # Production output gated by logistics
    {"type": "GATES",      "src": "OEM_Production_Capacity", "dst": "Heavy_Lift_Logistics",   "weight": 0.70},

    # Demand pulls on production (and components / logistics)
    {"type": "PRESSURES",  "src": "AI_Datacenter_Demand",      "dst": "OEM_Production_Capacity", "weight": 0.90},
    {"type": "PRESSURES",  "src": "Grid_Modernization_Demand", "dst": "OEM_Production_Capacity", "weight": 0.85},
    {"type": "PRESSURES",  "src": "AI_Datacenter_Demand",      "dst": "Critical_Components",     "weight": 0.55},
    {"type": "PRESSURES",  "src": "Grid_Modernization_Demand", "dst": "Heavy_Lift_Logistics",   "weight": 0.50},

    # Policy amplifies demand
    {"type": "AMPLIFIES",  "src": "Energy_Transition_Policy", "dst": "Grid_Modernization_Demand", "weight": 0.70},
    {"type": "AMPLIFIES",  "src": "Energy_Transition_Policy", "dst": "AI_Datacenter_Demand",      "weight": 0.40},

    # Trade & geo amplify supply / production constraints (cross-cutting)
    {"type": "AMPLIFIES",  "src": "Trade_Policy_Regime",       "dst": "GOES_Supply",             "weight": 0.70},
    {"type": "AMPLIFIES",  "src": "Trade_Policy_Regime",       "dst": "OEM_Production_Capacity",  "weight": 0.60},
    {"type": "AMPLIFIES",  "src": "Geographic_Concentration",  "dst": "GOES_Supply",             "weight": 0.65},
    {"type": "AMPLIFIES",  "src": "Geographic_Concentration",  "dst": "OEM_Production_Capacity",  "weight": 0.60},
    {"type": "AMPLIFIES",  "src": "Geographic_Concentration",  "dst": "Heavy_Lift_Logistics",    "weight": 0.65},
    {"type": "AMPLIFIES",  "src": "Trade_Policy_Regime",       "dst": "Geographic_Concentration", "weight": 0.55},
]


def actor_ids() -> list[str]:
    return [a["id"] for a in ACTORS]


def summary() -> dict:
    from collections import Counter
    return {
        "actors": len(ACTORS),
        "edges": len(ACTOR_EDGES),
        "by_band": dict(Counter(a["band"] for a in ACTORS)),
        "by_edge_type": dict(Counter(e["type"] for e in ACTOR_EDGES)),
    }
