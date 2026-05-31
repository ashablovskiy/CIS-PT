"""Power-transformer supply graph seed data — v3 (impact-first rebuild).

═══════════════════════════════════════════════════════════════════════════════
WHAT CHANGED vs v2 (and WHY)
═══════════════════════════════════════════════════════════════════════════════
v2 was a broad "cover the whole industry" map (~530 nodes). It carried a lot of
low-impact mass: iron-ore miners, coking coal, minor metals, HV cable makers,
and a long tail of pure-distribution OEMs. Those inflate the graph and dilute the
relevance signal without changing a single lead-time or cost outcome for a LARGE
power transformer.

v3 is scoped to **large / industrial power transformers** — the units that serve
data centers, power stations (generator step-up), HVDC links and grid backbones —
and it is built impact-first: every material entity carries a TRANSPARENT prior
about how much it actually moves transformer cost / availability / lead time.

These priors (`criticality`, `concentration`, `impact_weight`, `impact_rationale`)
are a *starting belief*, not a verdict. The assessment pipeline reads them, and
the analyst-feedback / DSPy loop corrects them over time: if an assessment over- or
under-weights a factor, the analyst's edit becomes a training example and the next
similar signal is scored from the lesson learned. The graph states the hypothesis;
the feedback loop refines it.

───────────────────────────────────────────────────────────────────────────────
FACT-CHECKED DECISIONS (sources: DOE LPT Resilience Report 2024; CISA/NIAC 2024;
Wood Mackenzie 2025; Utility Dive; CWIEME; trade & market reports)
───────────────────────────────────────────────────────────────────────────────
KEPT AS PRIMARY (the real binding constraints):
  • GOES (grain-oriented electrical steel) — THE core-material bottleneck. Few
    global mills, processing/know-how bound, prices +60–77% since 2020.
  • Copper — primary winding metal for LARGE power transformers; price-volatile.
  • On-load tap changers (OLTC) & HV bushings — the two COMPONENTS most often
    flagged as build-schedule bottlenecks (few certified suppliers; one delay
    holds the whole build).
  • Naphthenic transformer oil — supply-constrained by crude slate + refining.
  • Pressboard / aramid (Nomex) insulation — concentrated (Weidmann, DuPont).
  • Heavy-lift logistics — ~3 Schnabel cars in N. America, 9-month route permits,
    scarce breakbulk vessels. A genuine lead-time driver, not noise.

DELIBERATELY EXCLUDED / DEMOTED (considered, judged low-impact for LPT):
  • Iron ore & coking coal — CUT. GOES scarcity is processing capacity + grain-
    orientation metallurgy, NOT ore. Ordinary low-carbon steel + ~3% Si.
  • Aluminum — DEMOTED to low. Distribution / dry-type winding metal; large power
    transformers use copper. Abundant, never the LPT bottleneck.
  • Amorphous metal — DEMOTED to low. Distribution-transformer core material.
  • Minor metals (nickel, silver, tin, rare earths) — CUT. Negligible BoM share.
  • HV cable & GIS switchgear makers — CUT from suppliers. Bundled in grid
    projects but separate supply chains; not a transformer bottleneck.
  • Pure pad-mount distribution OEMs — most CUT; a few medium-power players kept
    at low criticality because data-center campuses also pull on them.

───────────────────────────────────────────────────────────────────────────────
PRIOR SCALE (transparent, auditable)
───────────────────────────────────────────────────────────────────────────────
  criticality:    "critical" | "high" | "medium" | "low"
  concentration:  "monopoly" | "oligopoly" | "concentrated" | "competitive" | "commodity"
  impact_weight:  float 0.0–1.0   (numeric prior for the scorer / assessment)
  impact_rationale: short plain-English WHY (so a human can audit the prior)

The `aliases` lists remain the SEARCH KEYWORDS that KeywordRegistry uses to filter
incoming GDELT/press/SEC/demand signals — richer aliases = better recall.

NOTE: plain data only — no Neo4j imports. scripts/seed_graph.py translates to
Cypher MERGE. Module-level names (COMMODITIES, …, EDGES) and the EDGES tuple
format (rel_type, start_label, start_name, end_label, end_name, props|None) are a
contract with the loader — keep them stable.
"""

from __future__ import annotations

# ═════════════════════════════════════════════════════════════════════════════
# COMMODITIES — raw materials at the market level, with impact priors
# ═════════════════════════════════════════════════════════════════════════════

COMMODITIES: list[dict] = [
    # ── PRIMARY core materials (the binding constraints) ─────────────────────
    {"name": "GOES", "full_name": "Grain-Oriented Electrical Steel", "ticker_proxy": "HRC=F",
     "category": "ferrous_specialty", "criticality": "critical", "concentration": "oligopoly",
     "impact_weight": 0.95,
     "impact_rationale": "Transformer core steel. ~10 capable mills worldwide; processing/grain-orientation bound, not ore. Prices +60–77% since 2020. Single largest cost & lead-time driver.",
     "aliases": ["grain-oriented electrical steel", "grain oriented steel", "electrical steel",
                 "transformer steel", "silicon steel", "CRGO", "cold-rolled grain-oriented",
                 "Hi-B steel", "HiB", "M3 steel", "M4 steel", "M5 steel", "M6 steel",
                 "23P090", "27P090", "30P110", "27ZDKH", "domain refined steel", "laser scribed steel",
                 "oriented silicon steel", "GOES strip", "core steel"]},
    {"name": "Copper", "full_name": "Copper (winding metal)", "ticker_proxy": "HG=F",
     "category": "non_ferrous", "criticality": "critical", "concentration": "commodity",
     "impact_weight": 0.85,
     "impact_rationale": "Primary winding conductor for large power transformers (copper, not aluminum). Globally available but highly price-volatile; second-largest BoM cost after GOES.",
     "aliases": ["copper cathode", "copper rod", "copper wire", "CTC conductor",
                 "continuously transposed conductor", "copper winding", "HG=F", "copper futures",
                 "LME copper", "Comex copper", "electrolytic copper", "Grade A copper", "magnet wire copper"]},
    # ── HIGH-impact components / fluids / insulation ─────────────────────────
    {"name": "Transformer_Oil_Naphthenic", "full_name": "Naphthenic Transformer (Insulating) Oil",
     "ticker_proxy": "CL=F", "category": "petrochemical", "criticality": "high",
     "concentration": "concentrated", "impact_weight": 0.65,
     "impact_rationale": "Dielectric + cooling fluid. Supply-constrained by finite naphthenic crude slate and few spec-grade refineries (Nynas, Ergon, Apar). Europe has seen naphthenic squeezes.",
     "aliases": ["transformer oil", "insulating oil", "dielectric oil", "naphthenic oil",
                 "naphthenic base oil", "Nynas Nytro", "Nytro", "Ergon HyVolt", "IEC 60296",
                 "uninhibited mineral oil", "inhibited mineral oil", "transformer fluid"]},
    {"name": "Cellulose_Pressboard", "full_name": "Cellulose Pressboard / Transformerboard",
     "ticker_proxy": None, "category": "cellulosic", "criticality": "high",
     "concentration": "concentrated", "impact_weight": 0.6,
     "impact_rationale": "Structural solid insulation between windings. Spec-grade transformerboard is concentrated (Weidmann dominant). Long qualification cycles.",
     "aliases": ["transformerboard", "transformer board", "pressboard", "cellulose pressboard",
                 "Weidmann pressboard", "calendered pressboard", "moulded pressboard",
                 "transformer paper", "kraft insulation paper", "insulating paper"]},
    {"name": "Aramid_Paper", "full_name": "Aramid (Nomex) High-Temperature Insulation",
     "ticker_proxy": None, "category": "polymer_paper", "criticality": "high",
     "concentration": "monopoly", "impact_weight": 0.6,
     "impact_rationale": "High-temp (220°C) insulation enabling compact / higher-rated and data-center transformers. DuPont Nomex is effectively the sole qualified aramid source.",
     "aliases": ["Nomex", "Nomex 410", "aramid paper", "aramid insulation", "meta-aramid",
                 "high temperature insulation", "DuPont Nomex", "Nomex transformerboard"]},
    {"name": "Ester_Fluid", "full_name": "Natural / Synthetic Ester Insulating Fluid",
     "ticker_proxy": None, "category": "biofluid", "criticality": "medium",
     "concentration": "competitive", "impact_weight": 0.4,
     "impact_rationale": "Fire-safe biodegradable alternative to mineral oil — increasingly specified for indoor / data-center / urban transformers. Substitutable, several suppliers.",
     "aliases": ["ester fluid", "natural ester", "synthetic ester", "FR3", "Midel", "Midel 7131",
                 "fire-safe fluid", "biodegradable transformer fluid", "K-class fluid", "Envirotemp"]},
    # ── MEDIUM / supporting ──────────────────────────────────────────────────
    {"name": "Silicon_Steel_NGOES", "full_name": "Non-Grain-Oriented Electrical Steel",
     "ticker_proxy": "HRC=F", "category": "ferrous_specialty", "criticality": "medium",
     "concentration": "competitive", "impact_weight": 0.35,
     "impact_rationale": "Used in reactors / rotating machines and some small cores. Less critical for large transformer cores (GOES dominates). More producers than GOES.",
     "aliases": ["NGOES", "non-oriented electrical steel", "NOES", "CRNGO", "M-19", "M19",
                 "non grain oriented", "fully processed electrical steel"]},
    {"name": "Natural_Gas", "full_name": "Natural Gas (mill energy / drying)",
     "ticker_proxy": "NG=F", "category": "energy", "criticality": "medium",
     "concentration": "commodity", "impact_weight": 0.3,
     "impact_rationale": "GOES annealing and transformer vapor-phase drying are energy-intensive; EU gas spikes raised electrical-steel and OEM costs in 2022–23.",
     "aliases": ["natural gas", "natgas", "NG=F", "Henry Hub", "TTF gas", "Dutch TTF",
                 "European gas", "LNG", "JKM"]},
    {"name": "Industrial_Electricity", "full_name": "Industrial Electricity Price",
     "ticker_proxy": None, "category": "energy", "criticality": "medium",
     "concentration": "commodity", "impact_weight": 0.3,
     "impact_rationale": "Electric-arc steelmaking + annealing are power-intensive; sustained high industrial power prices feed into GOES and OEM cost.",
     "aliases": ["electricity price", "power price", "wholesale electricity", "industrial power tariff",
                 "PJM power", "ERCOT power", "EPEX power", "Nordpool"]},
    # ── LOGISTICS inputs (heavy-lift is a genuine LPT constraint) ────────────
    {"name": "Heavy_Lift_Freight", "full_name": "Heavy-Lift / Breakbulk Freight Capacity",
     "ticker_proxy": None, "category": "logistics", "criticality": "high",
     "concentration": "concentrated", "impact_weight": 0.6,
     "impact_rationale": "100–400 t units need breakbulk vessels + Schnabel rail (~3 in N. America) + multi-month route permits. Logistics alone adds months to delivery.",
     "aliases": ["heavy lift shipping", "breakbulk", "project cargo", "Schnabel car", "Schnabel railcar",
                 "heavy haul", "BBC Chartering", "AAL Shipping", "SAL Heavy Lift", "Jumbo Shipping",
                 "Cosco Heavy Transport", "super heavy load", "out of gauge cargo"]},
    {"name": "Container_Freight", "full_name": "Container / General Ocean Freight Index",
     "ticker_proxy": None, "category": "logistics", "criticality": "low",
     "concentration": "commodity", "impact_weight": 0.2,
     "impact_rationale": "Weak proxy — large transformers do not move in containers; only components/accessories do. Minor cost signal.",
     "aliases": ["container freight", "SCFI", "Shanghai Containerized Freight Index", "Drewry WCI",
                 "Baltic Dry Index", "BDI", "ocean freight rate"]},
    {"name": "Bunker_Fuel", "full_name": "Marine Bunker Fuel (freight cost proxy)",
     "ticker_proxy": "CL=F", "category": "logistics", "criticality": "low",
     "concentration": "commodity", "impact_weight": 0.15,
     "impact_rationale": "Indirect freight-cost proxy via crude. Far downstream of transformer cost.",
     "aliases": ["bunker fuel", "VLSFO", "marine fuel", "MGO", "IFO 380", "low-sulfur fuel oil"]},
    # ── LOW-impact (kept for completeness / distribution context, demoted) ───
    {"name": "Aluminum", "full_name": "Aluminum (distribution winding metal)",
     "ticker_proxy": "ALI=F", "category": "non_ferrous", "criticality": "low",
     "concentration": "commodity", "impact_weight": 0.2,
     "impact_rationale": "Winding metal for DISTRIBUTION / dry-type units only. Large power transformers use copper. Abundant — never an LPT bottleneck (fact-checked).",
     "aliases": ["aluminium", "aluminum strip", "aluminum winding", "ALI=F", "EC-grade aluminum",
                 "1350 aluminum", "LME aluminum", "primary aluminum"]},
    {"name": "Amorphous_Metal", "full_name": "Amorphous Metal Alloy (distribution cores)",
     "ticker_proxy": None, "category": "alloy", "criticality": "low",
     "concentration": "concentrated", "impact_weight": 0.15,
     "impact_rationale": "Low-loss core ribbon for DISTRIBUTION transformers. Not used in large power cores.",
     "aliases": ["amorphous alloy", "amorphous core", "metglas", "Metglas 2605", "AMDT"]},
]

# ═════════════════════════════════════════════════════════════════════════════
# MATERIALS — engineered forms used in plants (each maps to a Commodity if any)
# ═════════════════════════════════════════════════════════════════════════════

MATERIALS: list[dict] = [
    # ── GOES grades (criticality tracks how scarce / specialised the grade is) ─
    {"name": "GOES_HiB", "commodity": "GOES", "spec": "Hi-B 0.23–0.27mm, B800≥1.92T",
     "criticality": "critical", "impact_weight": 0.95},
    {"name": "GOES_DomainRefined", "commodity": "GOES", "spec": "Laser/plasma domain-refined, lowest loss",
     "criticality": "critical", "impact_weight": 0.9},
    {"name": "GOES_M3", "commodity": "GOES", "spec": "0.23mm conventional", "criticality": "high", "impact_weight": 0.8},
    {"name": "GOES_M4", "commodity": "GOES", "spec": "0.27mm conventional", "criticality": "high", "impact_weight": 0.75},
    {"name": "GOES_M5", "commodity": "GOES", "spec": "0.30mm conventional", "criticality": "medium", "impact_weight": 0.6},
    {"name": "NGOES_Reactor_Grade", "commodity": "Silicon_Steel_NGOES", "spec": "Reactor / small-core NGOES",
     "criticality": "medium", "impact_weight": 0.35},
    # ── Copper forms ─────────────────────────────────────────────────────────
    {"name": "Cu_CTC", "commodity": "Copper", "spec": "Continuously Transposed Conductor (LPT winding)",
     "criticality": "critical", "impact_weight": 0.85},
    {"name": "Cu_PICC", "commodity": "Copper", "spec": "Paper-insulated copper conductor",
     "criticality": "high", "impact_weight": 0.7},
    {"name": "Cu_Bar_Bus", "commodity": "Copper", "spec": "Electrolytic busbar / lead", "criticality": "medium", "impact_weight": 0.4},
    # ── Aluminum (low — distribution) ────────────────────────────────────────
    {"name": "Al_Winding_Strip", "commodity": "Aluminum", "spec": "EC-grade distribution winding",
     "criticality": "low", "impact_weight": 0.2},
    # ── Fluids ───────────────────────────────────────────────────────────────
    {"name": "Naphthenic_Oil_IEC60296", "commodity": "Transformer_Oil_Naphthenic", "spec": "IEC 60296 Ed.5",
     "criticality": "high", "impact_weight": 0.65},
    {"name": "Ester_KClass", "commodity": "Ester_Fluid", "spec": "K-class fire-safe ester",
     "criticality": "medium", "impact_weight": 0.4},
    # ── Solid insulation ─────────────────────────────────────────────────────
    {"name": "Transformerboard", "commodity": "Cellulose_Pressboard", "spec": "Calendered HD transformerboard",
     "criticality": "high", "impact_weight": 0.6},
    {"name": "Kraft_Insulation_Paper", "commodity": "Cellulose_Pressboard", "spec": "Thermally-upgraded kraft",
     "criticality": "medium", "impact_weight": 0.45},
    {"name": "Nomex_410_Aramid", "commodity": "Aramid_Paper", "spec": "Nomex 410, 220°C class",
     "criticality": "high", "impact_weight": 0.6},
    # ── Critical COMPONENTS (no base commodity — bottleneck lives at supplier) ─
    {"name": "OLTC_Assembly", "commodity": None, "spec": "On-load tap changer assembly",
     "criticality": "high", "impact_weight": 0.7},
    {"name": "Bushing_RIP", "commodity": None, "spec": "Resin-impregnated paper HV bushing ≥220kV",
     "criticality": "high", "impact_weight": 0.6},
    {"name": "Bushing_RIS", "commodity": None, "spec": "Resin-impregnated synthetic HV bushing",
     "criticality": "high", "impact_weight": 0.55},
    {"name": "Bushing_OIP_Porcelain", "commodity": None, "spec": "Oil-impregnated paper / porcelain bushing",
     "criticality": "medium", "impact_weight": 0.5},
    # ── Structural / cooling / logistics (low) ───────────────────────────────
    {"name": "Tank_Structural_Steel", "commodity": None, "spec": "Tank / clamping structural steel",
     "criticality": "low", "impact_weight": 0.2},
    {"name": "Radiator_Cooling_Assembly", "commodity": None, "spec": "Radiators, fans, pumps",
     "criticality": "low", "impact_weight": 0.2},
    {"name": "Heavy_Lift_Crate", "commodity": None, "spec": "Bespoke breakbulk crating per unit",
     "criticality": "low", "impact_weight": 0.25},
]

# ═════════════════════════════════════════════════════════════════════════════
# COUNTRIES — production origins + key import destinations
# ═════════════════════════════════════════════════════════════════════════════

COUNTRIES: list[dict] = [
    # GOES / OEM heartlands (APAC)
    {"name": "South Korea",  "iso2": "KR", "region": "APAC", "goes_producer": True,  "oem_hub": True,
     "geo_note": "Largest LPT exporter to US; POSCO GOES; heavy-lift via Busan/Ulsan."},
    {"name": "Japan",        "iso2": "JP", "region": "APAC", "goes_producer": True,  "oem_hub": True,
     "geo_note": "Nippon Steel & JFE = top GOES; Mitsubishi/Toshiba OEMs."},
    {"name": "China",        "iso2": "CN", "region": "APAC", "goes_producer": True,  "oem_hub": True,
     "geo_note": "Baowu/Shougang GOES; TBEA UHV. Export-control / tariff exposure."},
    {"name": "India",        "iso2": "IN", "region": "APAC", "goes_producer": True,  "oem_hub": True,
     "geo_note": "Growing GOES (TKES Nashik, JSW-JFE) + OEM capacity."},
    # Europe
    {"name": "Germany",      "iso2": "DE", "region": "EU", "goes_producer": True,  "oem_hub": True,
     "geo_note": "thyssenkrupp GOES; Siemens Energy; Reinhausen OLTC; Trench/HSP bushings."},
    {"name": "France",       "iso2": "FR", "region": "EU", "goes_producer": True,  "oem_hub": True,
     "geo_note": "Aperam GOES/NGOES; GE Vernova HVDC (Villeurbanne)."},
    {"name": "Poland",       "iso2": "PL", "region": "EU", "goes_producer": True,  "oem_hub": False,
     "geo_note": "Stalprodukt — main EU-domestic GOES finisher."},
    {"name": "Switzerland",  "iso2": "CH", "region": "EU", "goes_producer": False, "oem_hub": True,
     "geo_note": "Hitachi Energy HQ; Weidmann insulation HQ."},
    {"name": "Sweden",       "iso2": "SE", "region": "EU", "goes_producer": False, "oem_hub": True,
     "geo_note": "Hitachi Ludvika (HVDC); Nynas oil."},
    {"name": "Austria",      "iso2": "AT", "region": "EU", "goes_producer": False, "oem_hub": True},
    {"name": "Finland",      "iso2": "FI", "region": "EU", "goes_producer": False, "oem_hub": True},
    {"name": "Italy",        "iso2": "IT", "region": "EU", "goes_producer": False, "oem_hub": True},
    {"name": "Spain",        "iso2": "ES", "region": "EU", "goes_producer": False, "oem_hub": True},
    {"name": "Netherlands",  "iso2": "NL", "region": "EU", "goes_producer": False, "oem_hub": True},
    {"name": "Portugal",     "iso2": "PT", "region": "EU", "goes_producer": False, "oem_hub": True},
    {"name": "United Kingdom","iso2": "GB","region": "EU", "goes_producer": False, "oem_hub": True},
    {"name": "Norway",       "iso2": "NO", "region": "EU", "goes_producer": False, "oem_hub": True},
    # Americas
    {"name": "United States","iso2": "US", "region": "AMER", "goes_producer": True,  "oem_hub": True,
     "geo_note": "Cleveland-Cliffs = sole US GOES (Butler PA). Heavy LPT import dependence (DOE)."},
    {"name": "Canada",       "iso2": "CA", "region": "AMER", "goes_producer": False, "oem_hub": True},
    {"name": "Mexico",       "iso2": "MX", "region": "AMER", "goes_producer": False, "oem_hub": True,
     "geo_note": "Prolec GE (Monterrey/Apodaca) — major nearshore LPT source for US."},
    {"name": "Brazil",       "iso2": "BR", "region": "LATAM", "goes_producer": False, "oem_hub": True,
     "geo_note": "WEG global OEM."},
    # MENA / other producers + destinations
    {"name": "Turkey",       "iso2": "TR", "region": "MENA", "goes_producer": True,  "oem_hub": True,
     "geo_note": "Erdemir NGOES; BEST/competitive OEMs exporting to EU/US."},
    {"name": "Saudi Arabia", "iso2": "SA", "region": "MENA", "goes_producer": False, "oem_hub": False,
     "geo_note": "Vision 2030 / NEOM grid demand."},
    {"name": "United Arab Emirates", "iso2": "AE", "region": "MENA", "goes_producer": False, "oem_hub": False},
    {"name": "Australia",    "iso2": "AU", "region": "APAC", "goes_producer": False, "oem_hub": False,
     "geo_note": "Rewiring the Nation grid demand."},
    # Producers under sanction / geopolitical constraint
    {"name": "Russia",       "iso2": "RU", "region": "EUROPE_NON_EU", "goes_producer": True, "oem_hub": True,
     "geo_note": "NLMK/VIZ-Stal GOES + Power Machines — largely sanction-restricted for Western buyers."},
]

# ═════════════════════════════════════════════════════════════════════════════
# SUPPLIERS — large-power OEMs, GOES mills, and the bottleneck sub-components
# ═════════════════════════════════════════════════════════════════════════════

SUPPLIERS: list[dict] = [
    # ═══ LARGE-POWER TRANSFORMER OEMs ═══════════════════════════════════════
    {"name": "Hitachi Energy", "tier": 1, "type": "transformer_oem", "hq_country": "CH", "sec_cik": None,
     "criticality": "critical", "concentration": "oligopoly", "impact_weight": 0.9,
     "impact_rationale": "Global #1 in power transformers (ex-ABB). $1.5B global capacity expansion incl. US (VA/MO/MS) & Canada.",
     "aliases": ["Hitachi ABB Power Grids", "ABB Power Grids", "Hitachi-ABB", "Hitachi Energy Ltd", "ABB transformers"]},
    {"name": "Siemens Energy", "tier": 1, "type": "transformer_oem", "hq_country": "DE", "sec_cik": None,
     "criticality": "critical", "concentration": "oligopoly", "impact_weight": 0.9,
     "impact_rationale": "Top-3 global OEM; expanding US footprint (NC/Charlotte) for large power transformers.",
     "aliases": ["Siemens-Energy", "Siemens Energy AG", "ENR.DE", "Siemens transformers"]},
    {"name": "GE Vernova", "tier": 1, "type": "transformer_oem", "hq_country": "US", "sec_cik": "1996862",
     "criticality": "critical", "concentration": "oligopoly", "impact_weight": 0.85,
     "impact_rationale": "Top-3 OEM (Grid Solutions); HVDC + large power; US grid-manufacturing investment.",
     "aliases": ["GE Grid Solutions", "General Electric Grid", "GEV", "GE Power", "GE T&D", "GE Vernova Grid"]},
    {"name": "Hyundai Electric", "tier": 1, "type": "transformer_oem", "hq_country": "KR", "sec_cik": None,
     "criticality": "high", "concentration": "oligopoly", "impact_weight": 0.8,
     "impact_rationale": "Major Korean LPT exporter; Alabama plant scaling to ~150 units/yr for US grid & DC demand.",
     "aliases": ["HD Hyundai Electric", "Hyundai Electric & Energy", "Hyundai Heavy Industries Electric",
                 "Hyundai Power Transformers USA", "Hyundai Montgomery"]},
    {"name": "Hyosung Heavy Industries", "tier": 1, "type": "transformer_oem", "hq_country": "KR", "sec_cik": None,
     "criticality": "high", "concentration": "oligopoly", "impact_weight": 0.8,
     "impact_rationale": "Korean UHV leader; Memphis (HICO) plant doubling to >250 units/yr by 2027 for US market.",
     "aliases": ["Hyosung", "Hyosung HICO", "Hico America", "효성중공업", "HSHI", "Hyosung HICO Memphis"]},
    {"name": "Mitsubishi Electric", "tier": 1, "type": "transformer_oem", "hq_country": "JP", "sec_cik": None,
     "criticality": "high", "concentration": "oligopoly", "impact_weight": 0.75,
     "impact_rationale": "Major Japanese LPT/GSU OEM; US presence via MEPPI.",
     "aliases": ["MELCO", "三菱電機", "Mitsubishi Electric Power Products", "MEPPI"]},
    {"name": "Toshiba Energy Systems", "tier": 1, "type": "transformer_oem", "hq_country": "JP", "sec_cik": None,
     "criticality": "high", "concentration": "oligopoly", "impact_weight": 0.7,
     "impact_rationale": "Japanese large-power & GSU OEM; US plant (Houston).",
     "aliases": ["Toshiba", "東芝", "Toshiba Energy Systems & Solutions", "Toshiba T&D", "Toshiba International"]},
    {"name": "TBEA", "tier": 1, "type": "transformer_oem", "hq_country": "CN", "sec_cik": None,
     "criticality": "high", "concentration": "oligopoly", "impact_weight": 0.7,
     "impact_rationale": "China's largest transformer maker; UHV AC/DC leader. Tariff/geo exposure for Western buyers.",
     "aliases": ["特变电工", "TBEA Co", "Tebian Electric", "TBEA Shenyang"]},
    {"name": "Prolec GE", "tier": 1, "type": "transformer_oem", "hq_country": "MX", "sec_cik": None,
     "criticality": "high", "concentration": "oligopoly", "impact_weight": 0.75,
     "impact_rationale": "Key nearshore LPT source for US (Monterrey/Apodaca) + US plants (Waukesha, Goldsboro NC +$140M).",
     "aliases": ["Prolec-GE", "Prolec Mexico", "Prolec Apodaca", "Prolec Monterrey", "Prolec Energy"]},
    {"name": "Virginia Transformer", "tier": 1, "type": "transformer_oem", "hq_country": "US", "sec_cik": None,
     "criticality": "high", "concentration": "competitive", "impact_weight": 0.65,
     "impact_rationale": "Largest US-owned LPT maker; expanding capacity for grid & data-center demand.",
     "aliases": ["VTC", "Virginia Transformer Corp", "Roanoke transformer", "VA Transformer"]},
    {"name": "WEG", "tier": 1, "type": "transformer_oem", "hq_country": "BR", "sec_cik": None,
     "criticality": "medium", "concentration": "competitive", "impact_weight": 0.6,
     "impact_rationale": "Global Brazilian OEM expanding US transformer footprint.",
     "aliases": ["WEG S.A.", "WEG Industries", "WEG Electric", "WEGE3"]},
    {"name": "SGB-SMIT", "tier": 1, "type": "transformer_oem", "hq_country": "DE", "sec_cik": None,
     "criticality": "medium", "concentration": "competitive", "impact_weight": 0.6,
     "impact_rationale": "Independent European large/medium power OEM; US plant (Louisville).",
     "aliases": ["SGB SMIT", "Starkstrom-Gerätebau", "SMIT Transformatoren", "SGB Group"]},
    {"name": "Pennsylvania Transformer Tech", "tier": 1, "type": "transformer_oem", "hq_country": "US", "sec_cik": None,
     "criticality": "medium", "concentration": "competitive", "impact_weight": 0.55,
     "impact_rationale": "US-owned large power transformer maker (Canonsburg PA).",
     "aliases": ["PTTI", "PA Transformer", "Penn Transformer", "Pennsylvania Transformer"]},
    {"name": "Delta Star", "tier": 1, "type": "transformer_oem", "hq_country": "US", "sec_cik": None,
     "criticality": "medium", "concentration": "competitive", "impact_weight": 0.5,
     "impact_rationale": "US medium/large power + mobile substations (emergency replacement).",
     "aliases": ["Delta Star Inc", "Delta Star Lynchburg", "Delta Star San Carlos"]},
    {"name": "CG Power", "tier": 1, "type": "transformer_oem", "hq_country": "IN", "sec_cik": None,
     "criticality": "medium", "concentration": "competitive", "impact_weight": 0.55,
     "impact_rationale": "Major Indian power-transformer OEM exporting globally.",
     "aliases": ["CG Power and Industrial Solutions", "Crompton Greaves", "CG Industrial"]},
    {"name": "BHEL", "tier": 1, "type": "transformer_oem", "hq_country": "IN", "sec_cik": None,
     "criticality": "medium", "concentration": "competitive", "impact_weight": 0.5,
     "impact_rationale": "Indian state heavy-electrical OEM; large power & UHV.",
     "aliases": ["Bharat Heavy Electricals", "Bharat Heavy Electricals Limited"]},
    {"name": "Efacec", "tier": 1, "type": "transformer_oem", "hq_country": "PT", "sec_cik": None,
     "criticality": "medium", "concentration": "competitive", "impact_weight": 0.45,
     "impact_rationale": "Portuguese power-transformer OEM with US/EU project supply.",
     "aliases": ["Efacec Power Solutions", "Efacec Transformers"]},
    {"name": "Royal SMIT Transformers", "tier": 1, "type": "transformer_oem", "hq_country": "NL", "sec_cik": None,
     "criticality": "medium", "concentration": "competitive", "impact_weight": 0.45,
     "impact_rationale": "Dutch large-power OEM (part of SGB-SMIT group).",
     "aliases": ["Royal SMIT", "SMIT Nijmegen", "Koninklijke SMIT"]},
    {"name": "Tamini", "tier": 1, "type": "transformer_oem", "hq_country": "IT", "sec_cik": None,
     "criticality": "medium", "concentration": "competitive", "impact_weight": 0.4,
     "impact_rationale": "Italian large-power & furnace transformers (Terna group).",
     "aliases": ["Tamini Trasformatori", "Tamini Group", "Terna Tamini"]},
    {"name": "Brush Group", "tier": 1, "type": "transformer_oem", "hq_country": "GB", "sec_cik": None,
     "criticality": "medium", "concentration": "competitive", "impact_weight": 0.4,
     "impact_rationale": "UK large-power / generator transformers.",
     "aliases": ["Brush Electrical Machines", "Brush Loughborough"]},
    {"name": "BEST Transformer", "tier": 1, "type": "transformer_oem", "hq_country": "TR", "sec_cik": None,
     "criticality": "medium", "concentration": "competitive", "impact_weight": 0.45,
     "impact_rationale": "Turkish large-power OEM, cost-competitive exporter to EU/US.",
     "aliases": ["BEST Trafo", "Balikesir Elektromekanik", "BEST AS"]},
    {"name": "Power Machines", "tier": 1, "type": "transformer_oem", "hq_country": "RU", "sec_cik": None,
     "criticality": "low", "concentration": "competitive", "impact_weight": 0.3,
     "impact_rationale": "Russian heavy-electrical OEM — largely off-limits to Western buyers (sanctions).",
     "aliases": ["Силовые машины", "Silovye Mashiny", "Power Machines OJSC"]},
    # ── Medium-power / distribution OEMs kept LOW (data centers pull on them) ─
    {"name": "Eaton", "tier": 2, "type": "medium_power_oem", "hq_country": "US", "sec_cik": "1551182",
     "criticality": "medium", "concentration": "competitive", "impact_weight": 0.45,
     "impact_rationale": "Major US electrical OEM; medium-power & dry-type units heavily used in data centers.",
     "aliases": ["Eaton Corporation", "Eaton Electrical", "ETN", "Cooper Power"]},
    {"name": "Schneider Electric", "tier": 2, "type": "medium_power_oem", "hq_country": "FR", "sec_cik": None,
     "criticality": "medium", "concentration": "competitive", "impact_weight": 0.4,
     "impact_rationale": "Medium-voltage / dry-type transformers for data centers & industry.",
     "aliases": ["Schneider Electric T&D", "Schneider Transformers", "SU.PA"]},
    {"name": "ERMCO", "tier": 2, "type": "distribution_oem", "hq_country": "US", "sec_cik": None,
     "criticality": "low", "concentration": "competitive", "impact_weight": 0.3,
     "impact_rationale": "High-volume US distribution transformers; capacity squeezed by overall shortage.",
     "aliases": ["Electric Research and Manufacturing", "ERMCO Dyersburg"]},
    {"name": "Howard Industries", "tier": 2, "type": "distribution_oem", "hq_country": "US", "sec_cik": None,
     "criticality": "low", "concentration": "competitive", "impact_weight": 0.3,
     "impact_rationale": "Largest US distribution transformer maker; indirect lead-time signal.",
     "aliases": ["Howard Power Solutions", "Howard Laurel"]},

    # ═══ GOES MILLS — the binding upstream constraint ════════════════════════
    {"name": "Nippon Steel", "tier": 2, "type": "goes_mill", "hq_country": "JP", "sec_cik": None,
     "criticality": "critical", "concentration": "oligopoly", "impact_weight": 0.95,
     "impact_rationale": "World's top GOES producer incl. premium Hi-B / domain-refined grades.",
     "aliases": ["NSSMC", "Nippon Steel Corporation", "新日鉄", "Nippon Steel & Sumitomo Metal", "NSC"]},
    {"name": "JFE Steel", "tier": 2, "type": "goes_mill", "hq_country": "JP", "sec_cik": None,
     "criticality": "critical", "concentration": "oligopoly", "impact_weight": 0.9,
     "impact_rationale": "Top-tier GOES; green-GOES (JGreeX); India JV (JSW-JFE).",
     "aliases": ["JFE", "Kawasaki Steel", "NKK", "JFE Holdings", "JFE Steel Corporation"]},
    {"name": "POSCO", "tier": 2, "type": "goes_mill", "hq_country": "KR", "sec_cik": None,
     "criticality": "critical", "concentration": "oligopoly", "impact_weight": 0.9,
     "impact_rationale": "Korea's GOES producer; supplies Korean & global OEMs.",
     "aliases": ["POSCO Holdings", "포스코", "Pohang Iron and Steel", "POSCO International"]},
    {"name": "Baowu Steel", "tier": 2, "type": "goes_mill", "hq_country": "CN", "sec_cik": None,
     "criticality": "critical", "concentration": "oligopoly", "impact_weight": 0.85,
     "impact_rationale": "World's largest steelmaker; Baoshan + Wuhan (ex-WISCO) GOES — China's dominant electrical-steel supplier.",
     "aliases": ["Baosteel", "Baoshan Iron & Steel", "China Baowu", "宝钢", "Bao Steel", "WISCO", "Wuhan Iron and Steel"]},
    {"name": "Shougang", "tier": 2, "type": "goes_mill", "hq_country": "CN", "sec_cik": None,
     "criticality": "high", "concentration": "oligopoly", "impact_weight": 0.6,
     "impact_rationale": "Major Chinese electrical-steel producer (GOES/NGOES) expanding high-grade capacity.",
     "aliases": ["Shougang Group", "首钢", "Shougang Zhixin", "Beijing Shougang"]},
    {"name": "TISCO", "tier": 2, "type": "goes_mill", "hq_country": "CN", "sec_cik": None,
     "criticality": "medium", "concentration": "oligopoly", "impact_weight": 0.5,
     "impact_rationale": "Chinese GOES/specialty steel producer.",
     "aliases": ["Taiyuan Iron and Steel", "太钢", "Taigang"]},
    {"name": "thyssenkrupp Electrical Steel", "tier": 2, "type": "goes_mill", "hq_country": "DE", "sec_cik": None,
     "criticality": "critical", "concentration": "oligopoly", "impact_weight": 0.85,
     "impact_rationale": "Main Western-Europe GOES maker (PowerCore); DE + FR + India (Nashik) capacity.",
     "aliases": ["thyssenkrupp", "TKES", "TK Electrical Steel", "PowerCore", "ThyssenKrupp Steel Europe"]},
    {"name": "Cleveland-Cliffs", "tier": 2, "type": "goes_mill", "hq_country": "US", "sec_cik": "764065",
     "criticality": "critical", "concentration": "monopoly", "impact_weight": 0.9,
     "impact_rationale": "SOLE domestic US GOES producer (Butler PA). Single point of failure for US-made transformer cores; building Weirton WV transformer plant.",
     "aliases": ["Cliffs", "AK Steel", "Cleveland Cliffs", "CLF", "AK Steel Butler", "Butler Works"]},
    {"name": "Stalprodukt", "tier": 2, "type": "goes_mill", "hq_country": "PL", "sec_cik": None,
     "criticality": "high", "concentration": "oligopoly", "impact_weight": 0.6,
     "impact_rationale": "Principal EU-domestic GOES finisher (Bochnia).",
     "aliases": ["Stalprodukt Bochnia", "Stalprodukt S.A."]},
    {"name": "Aperam", "tier": 2, "type": "goes_mill", "hq_country": "FR", "sec_cik": None,
     "criticality": "medium", "concentration": "oligopoly", "impact_weight": 0.5,
     "impact_rationale": "French electrical-steel (GOES/NGOES) producer.",
     "aliases": ["Aperam Imphy", "Aperam Stainless", "ArcelorMittal Stainless"]},
    {"name": "JSW JFE Electrical Steel", "tier": 2, "type": "goes_mill", "hq_country": "IN", "sec_cik": None,
     "criticality": "medium", "concentration": "oligopoly", "impact_weight": 0.45,
     "impact_rationale": "India GOES JV (JSW + JFE), Bellary — production from ~2027 to cut India's import reliance.",
     "aliases": ["JSW JFE", "JSW Steel electrical", "JSW JFE Bellary"]},
    {"name": "NLMK", "tier": 2, "type": "goes_mill", "hq_country": "RU", "sec_cik": None,
     "criticality": "high", "concentration": "oligopoly", "impact_weight": 0.55,
     "impact_rationale": "Major GOES (VIZ-Stal) — significant capacity but sanction-restricted for Western buyers.",
     "aliases": ["Novolipetsk Steel", "НЛМК", "NLMK Lipetsk", "VIZ-Stal", "VIZ Stal"]},
    {"name": "Erdemir", "tier": 2, "type": "goes_mill", "hq_country": "TR", "sec_cik": None,
     "criticality": "low", "concentration": "competitive", "impact_weight": 0.35,
     "impact_rationale": "Turkish electrical steel (mainly NGOES); minor GOES role.",
     "aliases": ["Eregli Iron and Steel", "ERDEMIR", "OYAK Erdemir"]},

    # ═══ ON-LOAD TAP CHANGERS (OLTC) — top component bottleneck ══════════════
    {"name": "Reinhausen", "tier": 2, "type": "tap_changer_oltc", "hq_country": "DE", "sec_cik": None,
     "criticality": "critical", "concentration": "concentrated", "impact_weight": 0.85,
     "impact_rationale": "Dominant global OLTC maker (MR). OLTCs are a top build-schedule bottleneck — one delay holds the whole transformer.",
     "aliases": ["MR Reinhausen", "Maschinenfabrik Reinhausen", "MR Group", "OILTAP", "VACUTAP"]},
    {"name": "Hitachi Energy OLTC", "tier": 2, "type": "tap_changer_oltc", "hq_country": "CH", "sec_cik": None,
     "criticality": "high", "concentration": "concentrated", "impact_weight": 0.6,
     "impact_rationale": "Second major OLTC source (ex-ABB UZ/UC tap changers).",
     "aliases": ["ABB tap changer", "Hitachi tap changer", "UZ tap changer", "UC tap changer"]},
    {"name": "Huaming Power Equipment", "tier": 2, "type": "tap_changer_oltc", "hq_country": "CN", "sec_cik": None,
     "criticality": "high", "concentration": "concentrated", "impact_weight": 0.6,
     "impact_rationale": "Leading Chinese OLTC maker — main non-Western alternative.",
     "aliases": ["华明电力", "Huaming", "Huaming Tap Changer"]},

    # ═══ HV BUSHINGS — second top component bottleneck ═══════════════════════
    {"name": "Trench Group", "tier": 2, "type": "bushings", "hq_country": "DE", "sec_cik": None,
     "criticality": "high", "concentration": "concentrated", "impact_weight": 0.7,
     "impact_rationale": "Leading HV bushing & instrument-transformer maker (Siemens Energy). Bushings = certified-per-application, few qualified suppliers.",
     "aliases": ["Trench", "Trench Bushings", "Trench Italia", "Trench Austria", "Trench Bayreuth"]},
    {"name": "HSP Hochspannungsgeraete", "tier": 2, "type": "bushings", "hq_country": "DE", "sec_cik": None,
     "criticality": "high", "concentration": "concentrated", "impact_weight": 0.6,
     "impact_rationale": "Major HV bushing specialist (Troisdorf).",
     "aliases": ["HSP", "HSP Hochspannungsgeräte", "HSP Troisdorf"]},
    {"name": "Hitachi Energy Bushings", "tier": 2, "type": "bushings", "hq_country": "SE", "sec_cik": None,
     "criticality": "high", "concentration": "concentrated", "impact_weight": 0.6,
     "impact_rationale": "RIP/RIS HV bushings (ex-ABB components, Ludvika).",
     "aliases": ["ABB Bushings", "ABB Components", "Hitachi bushings", "ABB High Voltage Components"]},
    {"name": "Pfisterer", "tier": 2, "type": "bushings", "hq_country": "DE", "sec_cik": None,
     "criticality": "medium", "concentration": "concentrated", "impact_weight": 0.5,
     "impact_rationale": "HV connectors & bushings; growing share of certified supply.",
     "aliases": ["Pfisterer Holding", "Pfisterer SEFAG"]},

    # ═══ SOLID INSULATION (pressboard / aramid) ═════════════════════════════
    {"name": "Weidmann Electrical Technology", "tier": 2, "type": "insulation", "hq_country": "CH", "sec_cik": None,
     "criticality": "critical", "concentration": "concentrated", "impact_weight": 0.8,
     "impact_rationale": "Dominant transformerboard / pressboard supplier worldwide; spec-grade insulation is hard to second-source.",
     "aliases": ["Weidmann", "Weidmann Rapperswil", "WICOR", "Wicor", "Weidmann insulation"]},
    {"name": "DuPont", "tier": 2, "type": "insulation", "hq_country": "US", "sec_cik": "1666700",
     "criticality": "high", "concentration": "monopoly", "impact_weight": 0.7,
     "impact_rationale": "Nomex aramid — effectively sole qualified high-temp (220°C) insulation source.",
     "aliases": ["DuPont de Nemours", "Nomex", "DD", "DuPont Nomex"]},
    {"name": "Krempel Group", "tier": 2, "type": "insulation", "hq_country": "DE", "sec_cik": None,
     "criticality": "medium", "concentration": "competitive", "impact_weight": 0.45,
     "impact_rationale": "Electrical insulation laminates & papers.",
     "aliases": ["Krempel", "Krempel Vaihingen", "August Krempel"]},

    # ═══ WINDING WIRE (CTC / magnet wire) ═══════════════════════════════════
    {"name": "Essex Furukawa Magnet Wire", "tier": 2, "type": "winding_wire", "hq_country": "US", "sec_cik": None,
     "criticality": "high", "concentration": "concentrated", "impact_weight": 0.65,
     "impact_rationale": "Leading global CTC / magnet-wire maker — 'only one with capacity & expertise to serve the energy market' at scale.",
     "aliases": ["Essex Furukawa", "Essex Magnet Wire", "Furukawa Electric Magnet", "Essex Solutions"]},
    {"name": "Superior Essex", "tier": 2, "type": "winding_wire", "hq_country": "US", "sec_cik": None,
     "criticality": "medium", "concentration": "competitive", "impact_weight": 0.45,
     "impact_rationale": "Magnet wire / winding conductor supplier.",
     "aliases": ["Superior Essex Communications", "Essex Group"]},

    # ═══ TRANSFORMER OIL (naphthenic / ester) ═══════════════════════════════
    {"name": "Nynas", "tier": 2, "type": "transformer_oil", "hq_country": "SE", "sec_cik": None,
     "criticality": "high", "concentration": "concentrated", "impact_weight": 0.7,
     "impact_rationale": "World's leading naphthenic transformer-oil supplier; feedstock/refining-constrained (historic Venezuela crude exposure).",
     "aliases": ["Nynas AB", "Nynas Nytro", "Nytro", "Nynas oil"]},
    {"name": "Ergon", "tier": 2, "type": "transformer_oil", "hq_country": "US", "sec_cik": None,
     "criticality": "high", "concentration": "concentrated", "impact_weight": 0.65,
     "impact_rationale": "World's largest specialty naphthenic oil producer (Vicksburg MS); HyVolt/OmniVolt dielectrics.",
     "aliases": ["Ergon Refining", "Ergon Specialty Oils", "HyVolt", "OmniVolt"]},
    {"name": "Apar Industries", "tier": 2, "type": "transformer_oil", "hq_country": "IN", "sec_cik": None,
     "criticality": "medium", "concentration": "competitive", "impact_weight": 0.5,
     "impact_rationale": "Major Indian transformer-oil & conductor supplier.",
     "aliases": ["Apar", "APAR Industries Limited", "Apar transformer oil"]},
]

# ═════════════════════════════════════════════════════════════════════════════
# PLANTS — production sites (large-power / GOES / critical sub-components).
# Distribution-only sites intentionally excluded. lat/lon for map rendering.
# specialty drives the USES_MATERIAL edges (see PLANT_MATERIAL_MAP).
# ═════════════════════════════════════════════════════════════════════════════

PLANTS: list[dict] = [
    # ── Hitachi Energy ───────────────────────────────────────────────────────
    {"name": "Hitachi Ludvika",         "operator": "Hitachi Energy", "country": "SE", "lat": 60.15, "lon": 15.18, "specialty": "hvdc", "criticality": "critical"},
    {"name": "Hitachi Bad Honnef",      "operator": "Hitachi Energy", "country": "DE", "lat": 50.65, "lon":  7.22, "specialty": "large_power", "criticality": "high"},
    {"name": "Hitachi Vaasa",           "operator": "Hitachi Energy", "country": "FI", "lat": 63.10, "lon": 21.62, "specialty": "large_power", "criticality": "high"},
    {"name": "Hitachi South Boston VA", "operator": "Hitachi Energy", "country": "US", "lat": 36.70, "lon": -78.90, "specialty": "large_power", "criticality": "critical"},
    {"name": "Hitachi Jefferson City MO","operator": "Hitachi Energy","country": "US", "lat": 38.58, "lon": -92.17, "specialty": "large_power", "criticality": "high"},
    {"name": "Hitachi Varennes QC",     "operator": "Hitachi Energy", "country": "CA", "lat": 45.68, "lon": -73.43, "specialty": "large_power", "criticality": "high"},
    {"name": "Hitachi Vadodara",        "operator": "Hitachi Energy", "country": "IN", "lat": 22.31, "lon": 73.18, "specialty": "large_power", "criticality": "high"},
    # ── Siemens Energy ───────────────────────────────────────────────────────
    {"name": "Siemens Nuremberg",       "operator": "Siemens Energy", "country": "DE", "lat": 49.45, "lon": 11.08, "specialty": "large_power", "criticality": "critical"},
    {"name": "Siemens Weiz",            "operator": "Siemens Energy", "country": "AT", "lat": 47.22, "lon": 15.62, "specialty": "large_power", "criticality": "high"},
    {"name": "Siemens Charlotte NC",    "operator": "Siemens Energy", "country": "US", "lat": 35.23, "lon": -80.84, "specialty": "large_power", "criticality": "critical"},
    {"name": "Siemens Cordoba",         "operator": "Siemens Energy", "country": "ES", "lat": 37.89, "lon":  -4.78, "specialty": "large_power", "criticality": "high"},
    {"name": "Siemens Drammen",         "operator": "Siemens Energy", "country": "NO", "lat": 59.74, "lon": 10.20, "specialty": "large_power", "criticality": "medium"},
    {"name": "Siemens Mumbai",          "operator": "Siemens Energy", "country": "IN", "lat": 19.08, "lon": 72.88, "specialty": "large_power", "criticality": "high"},
    # ── GE Vernova ───────────────────────────────────────────────────────────
    {"name": "GE Vernova Charleroi PA", "operator": "GE Vernova", "country": "US", "lat": 40.14, "lon": -79.90, "specialty": "large_power", "criticality": "high"},
    {"name": "GE Vernova Villeurbanne", "operator": "GE Vernova", "country": "FR", "lat": 45.77, "lon":  4.88, "specialty": "hvdc", "criticality": "high"},
    {"name": "GE Vernova Stafford",     "operator": "GE Vernova", "country": "GB", "lat": 52.81, "lon": -2.12, "specialty": "hvdc", "criticality": "high"},
    # ── Prolec GE ────────────────────────────────────────────────────────────
    {"name": "Prolec Apodaca",          "operator": "Prolec GE", "country": "MX", "lat": 25.78, "lon": -100.19, "specialty": "large_power", "criticality": "critical"},
    {"name": "Prolec Monterrey",        "operator": "Prolec GE", "country": "MX", "lat": 25.67, "lon": -100.31, "specialty": "large_power", "criticality": "high"},
    {"name": "Prolec Goldsboro NC",     "operator": "Prolec GE", "country": "US", "lat": 35.38, "lon": -77.99, "specialty": "data_center_class", "criticality": "high"},
    {"name": "Prolec Waukesha WI",      "operator": "Prolec GE", "country": "US", "lat": 43.01, "lon": -88.23, "specialty": "large_power", "criticality": "high"},
    # ── Hyundai Electric ─────────────────────────────────────────────────────
    {"name": "Hyundai Ulsan",           "operator": "Hyundai Electric", "country": "KR", "lat": 35.55, "lon": 129.32, "specialty": "large_power", "criticality": "critical"},
    {"name": "Hyundai Montgomery AL",   "operator": "Hyundai Electric", "country": "US", "lat": 32.37, "lon": -86.30, "specialty": "large_power", "criticality": "critical"},
    # ── Hyosung ──────────────────────────────────────────────────────────────
    {"name": "Hyosung Changwon",        "operator": "Hyosung Heavy Industries", "country": "KR", "lat": 35.23, "lon": 128.68, "specialty": "uhv", "criticality": "critical"},
    {"name": "Hyosung HICO Memphis TN", "operator": "Hyosung Heavy Industries", "country": "US", "lat": 35.15, "lon": -90.05, "specialty": "large_power", "criticality": "critical"},
    # ── Mitsubishi / Toshiba ─────────────────────────────────────────────────
    {"name": "Mitsubishi Ako",          "operator": "Mitsubishi Electric", "country": "JP", "lat": 34.74, "lon": 134.39, "specialty": "large_power", "criticality": "high"},
    {"name": "Toshiba Hamakawasaki",    "operator": "Toshiba Energy Systems", "country": "JP", "lat": 35.53, "lon": 139.71, "specialty": "large_power", "criticality": "high"},
    {"name": "Toshiba Houston TX",      "operator": "Toshiba Energy Systems", "country": "US", "lat": 29.76, "lon": -95.37, "specialty": "large_power", "criticality": "high"},
    # ── TBEA (China UHV) ─────────────────────────────────────────────────────
    {"name": "TBEA Shenyang",           "operator": "TBEA", "country": "CN", "lat": 41.81, "lon": 123.43, "specialty": "uhv", "criticality": "high"},
    {"name": "TBEA Hengyang",           "operator": "TBEA", "country": "CN", "lat": 26.89, "lon": 112.57, "specialty": "large_power", "criticality": "medium"},
    # ── Other large-power OEMs ───────────────────────────────────────────────
    {"name": "WEG Blumenau",            "operator": "WEG", "country": "BR", "lat": -26.91, "lon": -49.07, "specialty": "large_power", "criticality": "medium"},
    {"name": "WEG Washington MO",       "operator": "WEG", "country": "US", "lat": 38.56, "lon": -91.01, "specialty": "large_power", "criticality": "medium"},
    {"name": "SGB Regensburg",          "operator": "SGB-SMIT", "country": "DE", "lat": 49.01, "lon": 12.10, "specialty": "large_power", "criticality": "medium"},
    {"name": "SGB Louisville KY",       "operator": "SGB-SMIT", "country": "US", "lat": 38.25, "lon": -85.76, "specialty": "large_power", "criticality": "medium"},
    {"name": "Royal SMIT Nijmegen",     "operator": "Royal SMIT Transformers", "country": "NL", "lat": 51.81, "lon": 5.84, "specialty": "large_power", "criticality": "medium"},
    {"name": "Tamini Legnano",          "operator": "Tamini", "country": "IT", "lat": 45.59, "lon": 8.92, "specialty": "large_power", "criticality": "medium"},
    {"name": "Brush Loughborough",      "operator": "Brush Group", "country": "GB", "lat": 52.77, "lon": -1.21, "specialty": "large_power", "criticality": "medium"},
    {"name": "Efacec Porto",            "operator": "Efacec", "country": "PT", "lat": 41.18, "lon": -8.61, "specialty": "large_power", "criticality": "medium"},
    {"name": "BEST Trafo Sakarya",      "operator": "BEST Transformer", "country": "TR", "lat": 40.78, "lon": 30.40, "specialty": "large_power", "criticality": "medium"},
    {"name": "PTTI Canonsburg PA",      "operator": "Pennsylvania Transformer Tech", "country": "US", "lat": 40.26, "lon": -80.19, "specialty": "large_power", "criticality": "high"},
    {"name": "Virginia Transformer Roanoke","operator": "Virginia Transformer", "country": "US", "lat": 37.27, "lon": -79.94, "specialty": "large_power", "criticality": "high"},
    {"name": "Delta Star Lynchburg VA", "operator": "Delta Star", "country": "US", "lat": 37.41, "lon": -79.14, "specialty": "large_power", "criticality": "medium"},
    {"name": "Delta Star San Carlos CA","operator": "Delta Star", "country": "US", "lat": 37.51, "lon": -122.26, "specialty": "mobile_substation", "criticality": "medium"},
    {"name": "CG Power Bhopal",         "operator": "CG Power", "country": "IN", "lat": 23.26, "lon": 77.41, "specialty": "large_power", "criticality": "medium"},
    {"name": "BHEL Bhopal",             "operator": "BHEL", "country": "IN", "lat": 23.26, "lon": 77.41, "specialty": "large_power", "criticality": "medium"},
    {"name": "BHEL Hardwar",            "operator": "BHEL", "country": "IN", "lat": 29.96, "lon": 78.16, "specialty": "uhv", "criticality": "medium"},
    {"name": "Power Machines SPb",      "operator": "Power Machines", "country": "RU", "lat": 59.94, "lon": 30.31, "specialty": "large_power", "criticality": "low"},
    # ── Medium-power / DC-class & distribution (kept low) ─────────────────────
    {"name": "Eaton Waukesha WI",       "operator": "Eaton", "country": "US", "lat": 43.01, "lon": -88.23, "specialty": "data_center_class", "criticality": "medium"},
    {"name": "Schneider Smyrna TN",     "operator": "Schneider Electric", "country": "US", "lat": 35.98, "lon": -86.52, "specialty": "data_center_class", "criticality": "medium"},
    {"name": "ERMCO Dyersburg TN",      "operator": "ERMCO", "country": "US", "lat": 36.03, "lon": -89.39, "specialty": "distribution", "criticality": "low"},
    {"name": "Howard Laurel MS",        "operator": "Howard Industries", "country": "US", "lat": 31.69, "lon": -89.13, "specialty": "distribution", "criticality": "low"},

    # ═══ GOES MILLS ═════════════════════════════════════════════════════════
    {"name": "Nippon Steel Hirohata",   "operator": "Nippon Steel", "country": "JP", "lat": 34.79, "lon": 134.65, "specialty": "goes_mill", "criticality": "critical"},
    {"name": "Nippon Steel Yawata",     "operator": "Nippon Steel", "country": "JP", "lat": 33.86, "lon": 130.81, "specialty": "goes_mill", "criticality": "critical"},
    {"name": "JFE Kurashiki",           "operator": "JFE Steel", "country": "JP", "lat": 34.59, "lon": 133.77, "specialty": "goes_mill", "criticality": "critical"},
    {"name": "JFE Chiba",               "operator": "JFE Steel", "country": "JP", "lat": 35.61, "lon": 140.10, "specialty": "goes_mill", "criticality": "high"},
    {"name": "POSCO Pohang",            "operator": "POSCO", "country": "KR", "lat": 36.04, "lon": 129.36, "specialty": "goes_mill", "criticality": "critical"},
    {"name": "POSCO Gwangyang",         "operator": "POSCO", "country": "KR", "lat": 34.94, "lon": 127.69, "specialty": "goes_mill", "criticality": "high"},
    {"name": "Baowu Baoshan Shanghai",  "operator": "Baowu Steel", "country": "CN", "lat": 31.40, "lon": 121.49, "specialty": "goes_mill", "criticality": "critical"},
    {"name": "Baowu Wuhan (WISCO)",     "operator": "Baowu Steel", "country": "CN", "lat": 30.59, "lon": 114.31, "specialty": "goes_mill", "criticality": "high"},
    {"name": "Shougang Qian'an",        "operator": "Shougang", "country": "CN", "lat": 39.99, "lon": 118.70, "specialty": "goes_mill", "criticality": "high"},
    {"name": "TISCO Taiyuan",           "operator": "TISCO", "country": "CN", "lat": 37.87, "lon": 112.55, "specialty": "goes_mill", "criticality": "medium"},
    {"name": "TKES Gelsenkirchen",      "operator": "thyssenkrupp Electrical Steel", "country": "DE", "lat": 51.51, "lon": 7.10, "specialty": "goes_mill", "criticality": "critical"},
    {"name": "TKES Isbergues",          "operator": "thyssenkrupp Electrical Steel", "country": "FR", "lat": 50.62, "lon": 2.46, "specialty": "goes_mill", "criticality": "high"},
    {"name": "TKES Nashik",             "operator": "thyssenkrupp Electrical Steel", "country": "IN", "lat": 19.99, "lon": 73.79, "specialty": "goes_mill", "criticality": "high"},
    {"name": "Cleveland-Cliffs Butler PA","operator": "Cleveland-Cliffs", "country": "US", "lat": 40.86, "lon": -79.90, "specialty": "goes_mill", "criticality": "critical"},
    {"name": "Cleveland-Cliffs Zanesville OH","operator": "Cleveland-Cliffs", "country": "US", "lat": 39.94, "lon": -82.01, "specialty": "goes_mill", "criticality": "high"},
    {"name": "Stalprodukt Bochnia",     "operator": "Stalprodukt", "country": "PL", "lat": 49.97, "lon": 20.43, "specialty": "goes_mill", "criticality": "high"},
    {"name": "Aperam Imphy",            "operator": "Aperam", "country": "FR", "lat": 46.94, "lon": 3.27, "specialty": "goes_mill", "criticality": "medium"},
    {"name": "JSW JFE Bellary",         "operator": "JSW JFE Electrical Steel", "country": "IN", "lat": 15.14, "lon": 76.92, "specialty": "goes_mill", "criticality": "medium"},
    {"name": "NLMK VIZ-Stal Yekaterinburg","operator": "NLMK", "country": "RU", "lat": 56.84, "lon": 60.60, "specialty": "goes_mill", "criticality": "high"},
    {"name": "Erdemir Eregli",          "operator": "Erdemir", "country": "TR", "lat": 41.28, "lon": 31.42, "specialty": "goes_mill", "criticality": "low"},

    # ═══ OLTC PLANTS ════════════════════════════════════════════════════════
    {"name": "Reinhausen Regensburg",   "operator": "Reinhausen", "country": "DE", "lat": 49.01, "lon": 12.10, "specialty": "oltc", "criticality": "critical"},
    {"name": "Reinhausen Humboldt TN",  "operator": "Reinhausen", "country": "US", "lat": 35.82, "lon": -88.91, "specialty": "oltc", "criticality": "high"},
    {"name": "Huaming Shanghai",        "operator": "Huaming Power Equipment", "country": "CN", "lat": 31.23, "lon": 121.47, "specialty": "oltc", "criticality": "high"},
    # ═══ BUSHING PLANTS ═════════════════════════════════════════════════════
    {"name": "Trench Bayreuth",         "operator": "Trench Group", "country": "DE", "lat": 49.95, "lon": 11.58, "specialty": "bushings", "criticality": "high"},
    {"name": "Trench St-Louis QC",      "operator": "Trench Group", "country": "CA", "lat": 46.59, "lon": -72.91, "specialty": "bushings", "criticality": "high"},
    {"name": "HSP Troisdorf",           "operator": "HSP Hochspannungsgeraete", "country": "DE", "lat": 50.81, "lon": 7.16, "specialty": "bushings", "criticality": "high"},
    {"name": "Hitachi Bushings Ludvika","operator": "Hitachi Energy Bushings", "country": "SE", "lat": 60.15, "lon": 15.18, "specialty": "bushings", "criticality": "high"},
    {"name": "Pfisterer Winterbach",    "operator": "Pfisterer", "country": "DE", "lat": 48.81, "lon": 9.55, "specialty": "bushings", "criticality": "medium"},
    # ═══ INSULATION PLANTS ══════════════════════════════════════════════════
    {"name": "Weidmann Rapperswil",     "operator": "Weidmann Electrical Technology", "country": "CH", "lat": 47.23, "lon": 8.82, "specialty": "insulation", "criticality": "critical"},
    {"name": "Weidmann St Johnsbury VT","operator": "Weidmann Electrical Technology", "country": "US", "lat": 44.42, "lon": -72.02, "specialty": "insulation", "criticality": "high"},
    {"name": "DuPont Richmond VA",      "operator": "DuPont", "country": "US", "lat": 37.54, "lon": -77.43, "specialty": "insulation", "criticality": "high"},
    {"name": "Krempel Vaihingen",       "operator": "Krempel Group", "country": "DE", "lat": 48.93, "lon": 8.97, "specialty": "insulation", "criticality": "medium"},
    # ═══ WINDING-WIRE PLANTS ════════════════════════════════════════════════
    {"name": "Essex Furukawa Fort Wayne IN","operator": "Essex Furukawa Magnet Wire", "country": "US", "lat": 41.08, "lon": -85.14, "specialty": "winding_wire", "criticality": "high"},
    {"name": "Superior Essex Hoisington KS","operator": "Superior Essex", "country": "US", "lat": 38.52, "lon": -98.78, "specialty": "winding_wire", "criticality": "medium"},
    # ═══ TRANSFORMER-OIL REFINERIES ═════════════════════════════════════════
    {"name": "Nynas Nynashamn",         "operator": "Nynas", "country": "SE", "lat": 58.90, "lon": 17.95, "specialty": "oil_refinery", "criticality": "high"},
    {"name": "Ergon Vicksburg MS",      "operator": "Ergon", "country": "US", "lat": 32.35, "lon": -90.87, "specialty": "oil_refinery", "criticality": "high"},
    {"name": "Apar Rabale",             "operator": "Apar Industries", "country": "IN", "lat": 19.16, "lon": 73.00, "specialty": "oil_refinery", "criticality": "medium"},
]

# ═════════════════════════════════════════════════════════════════════════════
# PORTS — heavy-lift / breakbulk capability is what matters for LPTs
# ═════════════════════════════════════════════════════════════════════════════

PORTS: list[dict] = [
    # APAC export hubs (Korea/Japan/China/India = the LPT export origins)
    {"name": "Busan",      "locode": "KRPUS", "country": "KR", "heavy_lift_capable": True, "criticality": "critical",
     "aliases": ["Pusan", "Port of Busan", "부산항", "KRPUS"]},
    {"name": "Ulsan",      "locode": "KRUSN", "country": "KR", "heavy_lift_capable": True, "criticality": "high",
     "aliases": ["Port of Ulsan", "울산항", "KRUSN"]},
    {"name": "Gwangyang",  "locode": "KRKAN", "country": "KR", "heavy_lift_capable": True, "criticality": "high",
     "aliases": ["Kwangyang", "광양항", "KRKAN"]},
    {"name": "Masan",      "locode": "KRMAS", "country": "KR", "heavy_lift_capable": True, "criticality": "medium",
     "aliases": ["Port of Masan", "마산항", "KRMAS"]},
    {"name": "Kobe",       "locode": "JPUKB", "country": "JP", "heavy_lift_capable": True, "criticality": "high",
     "aliases": ["Port of Kobe", "神戸港", "JPUKB"]},
    {"name": "Yokohama",   "locode": "JPYOK", "country": "JP", "heavy_lift_capable": True, "criticality": "medium",
     "aliases": ["Port of Yokohama", "横浜港", "JPYOK"]},
    {"name": "Nagoya",     "locode": "JPNGO", "country": "JP", "heavy_lift_capable": True, "criticality": "medium",
     "aliases": ["Port of Nagoya", "名古屋港", "JPNGO"]},
    {"name": "Shanghai",   "locode": "CNSHA", "country": "CN", "heavy_lift_capable": True, "criticality": "high",
     "aliases": ["Port of Shanghai", "上海港", "Yangshan", "CNSHA"]},
    {"name": "Tianjin",    "locode": "CNTSN", "country": "CN", "heavy_lift_capable": True, "criticality": "medium",
     "aliases": ["Port of Tianjin", "天津港", "Xingang", "CNTSN"]},
    {"name": "Mundra",     "locode": "INMUN", "country": "IN", "heavy_lift_capable": True, "criticality": "medium",
     "aliases": ["Port of Mundra", "Adani Mundra", "INMUN"]},
    {"name": "Nhava Sheva","locode": "INNSA", "country": "IN", "heavy_lift_capable": True, "criticality": "medium",
     "aliases": ["JNPT", "Jawaharlal Nehru Port", "Nhava Sheva", "INNSA"]},
    # EU heavy-lift hubs
    {"name": "Antwerp",    "locode": "BEANR", "country": "NL", "heavy_lift_capable": True, "criticality": "high",
     "aliases": ["Port of Antwerp", "Antwerp-Bruges", "BEANR"]},
    {"name": "Rotterdam",  "locode": "NLRTM", "country": "NL", "heavy_lift_capable": True, "criticality": "high",
     "aliases": ["Port of Rotterdam", "NLRTM"]},
    {"name": "Hamburg",    "locode": "DEHAM", "country": "DE", "heavy_lift_capable": True, "criticality": "high",
     "aliases": ["Port of Hamburg", "DEHAM"]},
    {"name": "Bremerhaven","locode": "DEBRV", "country": "DE", "heavy_lift_capable": True, "criticality": "medium",
     "aliases": ["Port of Bremerhaven", "Bremen", "DEBRV"]},
    {"name": "Genoa",      "locode": "ITGOA", "country": "IT", "heavy_lift_capable": True, "criticality": "medium",
     "aliases": ["Port of Genoa", "Genova", "ITGOA"]},
    {"name": "Bilbao",     "locode": "ESBIO", "country": "ES", "heavy_lift_capable": True, "criticality": "medium",
     "aliases": ["Port of Bilbao", "ESBIO"]},
    {"name": "Gothenburg", "locode": "SEGOT", "country": "SE", "heavy_lift_capable": True, "criticality": "medium",
     "aliases": ["Port of Gothenburg", "Goteborg", "SEGOT"]},
    {"name": "Leixoes",    "locode": "PTLEI", "country": "PT", "heavy_lift_capable": True, "criticality": "low",
     "aliases": ["Port of Leixoes", "Porto", "PTLEI"]},
    # US import gateways (the demand side of the heavy-lift problem)
    {"name": "Houston",    "locode": "USHOU", "country": "US", "heavy_lift_capable": True, "criticality": "critical",
     "aliases": ["Port of Houston", "Port Houston", "USHOU"]},
    {"name": "Norfolk",    "locode": "USORF", "country": "US", "heavy_lift_capable": True, "criticality": "high",
     "aliases": ["Port of Virginia", "Port of Norfolk", "USORF"]},
    {"name": "Savannah",   "locode": "USSAV", "country": "US", "heavy_lift_capable": True, "criticality": "high",
     "aliases": ["Port of Savannah", "Georgia Ports", "USSAV"]},
    {"name": "Baltimore",  "locode": "USBAL", "country": "US", "heavy_lift_capable": True, "criticality": "medium",
     "aliases": ["Port of Baltimore", "USBAL"]},
    {"name": "New Orleans","locode": "USMSY", "country": "US", "heavy_lift_capable": True, "criticality": "high",
     "aliases": ["Port of New Orleans", "Port NOLA", "USMSY"]},
    {"name": "Long Beach", "locode": "USLGB", "country": "US", "heavy_lift_capable": True, "criticality": "medium",
     "aliases": ["Port of Long Beach", "San Pedro Bay", "USLGB"]},
    {"name": "Newark",     "locode": "USEWR", "country": "US", "heavy_lift_capable": True, "criticality": "medium",
     "aliases": ["Port Newark", "Port of New York and New Jersey", "USEWR"]},
    # Latam / Canada
    {"name": "Itajai",     "locode": "BRITJ", "country": "BR", "heavy_lift_capable": True, "criticality": "low",
     "aliases": ["Port of Itajai", "Navegantes", "BRITJ"]},
    {"name": "Montreal",   "locode": "CAMTR", "country": "CA", "heavy_lift_capable": True, "criticality": "low",
     "aliases": ["Port of Montreal", "CAMTR"]},
    {"name": "Manzanillo", "locode": "MXZLO", "country": "MX", "heavy_lift_capable": True, "criticality": "low",
     "aliases": ["Port of Manzanillo", "MXZLO"]},
]

# ═════════════════════════════════════════════════════════════════════════════
# LANES — heavy-lift shipping corridors (origin→destination), with chokepoints
# ═════════════════════════════════════════════════════════════════════════════

LANES: list[dict] = [
    {"name": "Korea_USEC",   "origin_region": "APAC", "destination_region": "AMER", "transit_days": 30, "chokepoint": "Panama", "criticality": "critical"},
    {"name": "Korea_USWC",   "origin_region": "APAC", "destination_region": "AMER", "transit_days": 16, "chokepoint": "none",   "criticality": "high"},
    {"name": "Korea_USGulf", "origin_region": "APAC", "destination_region": "AMER", "transit_days": 35, "chokepoint": "Panama", "criticality": "high"},
    {"name": "Korea_EU",     "origin_region": "APAC", "destination_region": "EU",   "transit_days": 38, "chokepoint": "Suez",   "criticality": "high"},
    {"name": "Japan_USEC",   "origin_region": "APAC", "destination_region": "AMER", "transit_days": 28, "chokepoint": "Panama", "criticality": "high"},
    {"name": "Japan_USWC",   "origin_region": "APAC", "destination_region": "AMER", "transit_days": 14, "chokepoint": "none",   "criticality": "high"},
    {"name": "China_USEC",   "origin_region": "APAC", "destination_region": "AMER", "transit_days": 32, "chokepoint": "Panama", "criticality": "medium"},
    {"name": "China_USWC",   "origin_region": "APAC", "destination_region": "AMER", "transit_days": 18, "chokepoint": "none",   "criticality": "medium"},
    {"name": "China_EU",     "origin_region": "APAC", "destination_region": "EU",   "transit_days": 40, "chokepoint": "Suez",   "criticality": "medium"},
    {"name": "India_EU",     "origin_region": "APAC", "destination_region": "EU",   "transit_days": 22, "chokepoint": "Suez",   "criticality": "medium"},
    {"name": "India_USEC",   "origin_region": "APAC", "destination_region": "AMER", "transit_days": 32, "chokepoint": "Suez",   "criticality": "medium"},
    {"name": "EU_USEC",      "origin_region": "EU",   "destination_region": "AMER", "transit_days": 16, "chokepoint": "none",   "criticality": "high"},
    {"name": "EU_USGulf",    "origin_region": "EU",   "destination_region": "AMER", "transit_days": 20, "chokepoint": "none",   "criticality": "medium"},
    {"name": "Mexico_USGulf","origin_region": "AMER", "destination_region": "AMER", "transit_days": 5,  "chokepoint": "none",   "criticality": "high"},
    {"name": "Brazil_USEC",  "origin_region": "LATAM","destination_region": "AMER", "transit_days": 18, "chokepoint": "none",   "criticality": "low"},
    {"name": "Turkey_EU",    "origin_region": "MENA", "destination_region": "EU",   "transit_days": 7,  "chokepoint": "none",   "criticality": "medium"},
]

# ═════════════════════════════════════════════════════════════════════════════
# CATEGORIES — large/industrial transformer product classes (procurement view)
# ═════════════════════════════════════════════════════════════════════════════

CATEGORIES: list[dict] = [
    {"name": "Power_Transformer_Large", "description": "Large power transformers ≥100 MVA (grid backbone)",
     "criticality": "critical", "impact_weight": 0.95},
    {"name": "Generator_StepUp_GSU", "description": "Generator step-up transformers (power stations)",
     "criticality": "critical", "impact_weight": 0.9},
    {"name": "HVDC_Converter_Transformer", "description": "HVDC converter transformers (interconnects, long-haul)",
     "criticality": "critical", "impact_weight": 0.9},
    {"name": "Data_Center_Transformer", "description": "Medium/large power + MV step-down for hyperscale campuses",
     "criticality": "high", "impact_weight": 0.85},
    {"name": "Autotransformer", "description": "Autotransformers for inter-system / EHV coupling",
     "criticality": "high", "impact_weight": 0.7},
    {"name": "Phase_Shifting_Transformer", "description": "Phase-shifting transformers for power-flow control",
     "criticality": "medium", "impact_weight": 0.55},
    {"name": "Shunt_Reactor", "description": "Shunt reactors for reactive-power compensation",
     "criticality": "medium", "impact_weight": 0.5},
    {"name": "Medium_Power_Substation", "description": "Medium-power substation transformers (industrial / DC)",
     "criticality": "medium", "impact_weight": 0.5},
    {"name": "Mobile_Substation", "description": "Trailer-mounted mobile substations (emergency replacement)",
     "criticality": "medium", "impact_weight": 0.45},
]

# ═════════════════════════════════════════════════════════════════════════════
# DEMAND SOURCES — themes (the 6 forces) + named real actors pulling capacity.
# kind="theme" nodes are the abstract drivers; kind="actor" nodes are concrete
# companies/programs linked to a theme via BELONGS_TO_THEME.
# ═════════════════════════════════════════════════════════════════════════════

DEMAND_SOURCES: list[dict] = [
    # ── THE 6 DEMAND THEMES ──────────────────────────────────────────────────
    {"name": "Data_Center_AI_Demand", "kind": "theme", "theme": "Data_Center_AI_Demand", "horizon": "near",
     "region": "GLOBAL", "criticality": "critical", "impact_weight": 0.95,
     "impact_rationale": "Dominant new demand force. Transformer demand ~1,500→9,000 units/yr by 2030; DC developers pre-buy capacity, crowding out utilities.",
     "aliases": ["data center", "datacenter", "AI data center", "hyperscale", "AI buildout", "compute buildout",
                 "data center power", "AI power demand", "data center transformer"]},
    {"name": "Grid_Replacement_Aging", "kind": "theme", "theme": "Grid_Replacement_Aging", "horizon": "medium",
     "region": "GLOBAL", "criticality": "high", "impact_weight": 0.8,
     "impact_rationale": "Large installed transformer fleet is past design life (esp. US/EU); steady replacement demand competing with new load.",
     "aliases": ["grid replacement", "aging grid", "transformer replacement", "grid reliability",
                 "aging infrastructure", "fleet replacement", "end of life transformer"]},
    {"name": "Renewable_Interconnection", "kind": "theme", "theme": "Renewable_Interconnection", "horizon": "medium",
     "region": "GLOBAL", "criticality": "high", "impact_weight": 0.75,
     "impact_rationale": "Wind/solar + offshore need step-up & GSU transformers; interconnection queues (PJM ~7-8 yrs) gate projects.",
     "aliases": ["interconnection queue", "grid interconnection", "renewable integration", "offshore wind",
                 "solar interconnection", "wind interconnection", "GSU demand", "step-up transformer"]},
    {"name": "Electrification_Demand", "kind": "theme", "theme": "Electrification_Demand", "horizon": "medium",
     "region": "GLOBAL", "criticality": "medium", "impact_weight": 0.6,
     "impact_rationale": "EV charging, heat pumps, industrial electrification raise load → more substation/distribution transformers.",
     "aliases": ["electrification", "EV charging", "heat pump", "load growth", "industrial electrification",
                 "transport electrification"]},
    {"name": "Policy_Stimulus", "kind": "theme", "theme": "Policy_Stimulus", "horizon": "medium",
     "region": "GLOBAL", "criticality": "high", "impact_weight": 0.65,
     "impact_rationale": "Government grid funding (IRA, IIJA, REPowerEU) accelerates orders and can mandate domestic content.",
     "aliases": ["grid funding", "IRA", "Inflation Reduction Act", "REPowerEU", "infrastructure bill",
                 "grid modernization program", "DOE grid", "domestic content"]},
    {"name": "Industrial_Reshoring", "kind": "theme", "theme": "Industrial_Reshoring", "horizon": "medium",
     "region": "AMER", "criticality": "medium", "impact_weight": 0.55,
     "impact_rationale": "Chip fabs, battery gigafactories & new plants need large dedicated substations.",
     "aliases": ["reshoring", "chip fab", "semiconductor fab", "gigafactory", "CHIPS Act", "new factory",
                 "industrial expansion", "manufacturing investment"]},

    # ── HYPERSCALERS (theme: Data_Center_AI_Demand) ──────────────────────────
    {"name": "Microsoft", "kind": "actor", "theme": "Data_Center_AI_Demand", "horizon": "near", "region": "GLOBAL",
     "criticality": "critical", "impact_weight": 0.9,
     "aliases": ["Microsoft", "Azure", "Microsoft datacenter", "MSFT", "Microsoft AI"]},
    {"name": "Google", "kind": "actor", "theme": "Data_Center_AI_Demand", "horizon": "near", "region": "GLOBAL",
     "criticality": "critical", "impact_weight": 0.9,
     "aliases": ["Google", "Alphabet", "Google Cloud", "GCP", "Google datacenter", "DeepMind"]},
    {"name": "Amazon AWS", "kind": "actor", "theme": "Data_Center_AI_Demand", "horizon": "near", "region": "GLOBAL",
     "criticality": "critical", "impact_weight": 0.9,
     "aliases": ["Amazon", "AWS", "Amazon Web Services", "Amazon datacenter", "AMZN"]},
    {"name": "Meta", "kind": "actor", "theme": "Data_Center_AI_Demand", "horizon": "near", "region": "GLOBAL",
     "criticality": "critical", "impact_weight": 0.88,
     "aliases": ["Meta", "Facebook", "Meta datacenter", "Meta AI", "Hyperion datacenter"]},
    {"name": "Oracle", "kind": "actor", "theme": "Data_Center_AI_Demand", "horizon": "near", "region": "GLOBAL",
     "criticality": "high", "impact_weight": 0.75,
     "aliases": ["Oracle", "OCI", "Oracle Cloud", "Oracle datacenter"]},
    {"name": "OpenAI Stargate", "kind": "actor", "theme": "Data_Center_AI_Demand", "horizon": "near", "region": "AMER",
     "criticality": "high", "impact_weight": 0.8,
     "aliases": ["OpenAI", "Stargate", "Stargate project", "OpenAI datacenter", "Stargate Abilene"]},
    {"name": "xAI", "kind": "actor", "theme": "Data_Center_AI_Demand", "horizon": "near", "region": "AMER",
     "criticality": "medium", "impact_weight": 0.6,
     "aliases": ["xAI", "Colossus", "xAI Memphis", "Grok datacenter"]},
    {"name": "CoreWeave", "kind": "actor", "theme": "Data_Center_AI_Demand", "horizon": "near", "region": "AMER",
     "criticality": "medium", "impact_weight": 0.55,
     "aliases": ["CoreWeave", "CoreWeave datacenter", "neocloud"]},
    # ── DATA-CENTER DEVELOPERS / COLO (theme: Data_Center_AI_Demand) ──────────
    {"name": "Equinix", "kind": "actor", "theme": "Data_Center_AI_Demand", "horizon": "near", "region": "GLOBAL",
     "criticality": "medium", "impact_weight": 0.55, "aliases": ["Equinix", "Equinix IBX"]},
    {"name": "Digital Realty", "kind": "actor", "theme": "Data_Center_AI_Demand", "horizon": "near", "region": "GLOBAL",
     "criticality": "medium", "impact_weight": 0.55, "aliases": ["Digital Realty", "DLR", "Digital Realty Trust"]},
    {"name": "Vantage Data Centers", "kind": "actor", "theme": "Data_Center_AI_Demand", "horizon": "near", "region": "AMER",
     "criticality": "medium", "impact_weight": 0.5, "aliases": ["Vantage", "Vantage Data Centers"]},
    {"name": "QTS Realty", "kind": "actor", "theme": "Data_Center_AI_Demand", "horizon": "near", "region": "AMER",
     "criticality": "medium", "impact_weight": 0.5, "aliases": ["QTS", "QTS Realty", "QTS data centers"]},
    {"name": "Switch", "kind": "actor", "theme": "Data_Center_AI_Demand", "horizon": "near", "region": "AMER",
     "criticality": "low", "impact_weight": 0.4, "aliases": ["Switch", "Switch data centers"]},
    # ── POWER-FOR-DC GENERATION (the "power station" angle for DCs) ───────────
    {"name": "Behind-the-Meter Gas for DC", "kind": "actor", "theme": "Data_Center_AI_Demand", "horizon": "near", "region": "AMER",
     "criticality": "high", "impact_weight": 0.65,
     "impact_rationale": "On-site gas turbines + GSUs to power data centers off-grid — pulls hard on GSU transformer supply.",
     "aliases": ["behind the meter", "gas turbine data center", "on-site generation", "GE Vernova gensets",
                 "data center power plant"]},
    {"name": "SMR Nuclear for DC", "kind": "actor", "theme": "Data_Center_AI_Demand", "horizon": "long", "region": "AMER",
     "criticality": "medium", "impact_weight": 0.5,
     "aliases": ["SMR", "small modular reactor", "NuScale", "Oklo", "nuclear data center", "Kairos"]},

    # ── US UTILITIES / GRID OPERATORS (theme: Grid_Replacement_Aging) ────────
    {"name": "Dominion Energy", "kind": "actor", "theme": "Grid_Replacement_Aging", "horizon": "near", "region": "AMER",
     "criticality": "high", "impact_weight": 0.7,
     "aliases": ["Dominion Energy", "Dominion Virginia", "Dominion"]},
    {"name": "American Electric Power", "kind": "actor", "theme": "Grid_Replacement_Aging", "horizon": "near", "region": "AMER",
     "criticality": "high", "impact_weight": 0.65, "aliases": ["AEP", "American Electric Power"]},
    {"name": "Duke Energy", "kind": "actor", "theme": "Grid_Replacement_Aging", "horizon": "near", "region": "AMER",
     "criticality": "high", "impact_weight": 0.65, "aliases": ["Duke Energy", "Duke"]},
    {"name": "NextEra Energy", "kind": "actor", "theme": "Renewable_Interconnection", "horizon": "near", "region": "AMER",
     "criticality": "high", "impact_weight": 0.65, "aliases": ["NextEra", "NextEra Energy", "Florida Power & Light", "FPL"]},
    {"name": "Southern Company", "kind": "actor", "theme": "Grid_Replacement_Aging", "horizon": "near", "region": "AMER",
     "criticality": "medium", "impact_weight": 0.6, "aliases": ["Southern Company", "Georgia Power"]},
    {"name": "PG&E", "kind": "actor", "theme": "Grid_Replacement_Aging", "horizon": "near", "region": "AMER",
     "criticality": "medium", "impact_weight": 0.55, "aliases": ["PG&E", "Pacific Gas and Electric"]},
    {"name": "PJM Interconnection", "kind": "actor", "theme": "Renewable_Interconnection", "horizon": "near", "region": "AMER",
     "criticality": "high", "impact_weight": 0.65, "aliases": ["PJM", "PJM Interconnection", "PJM queue"]},
    {"name": "ERCOT", "kind": "actor", "theme": "Electrification_Demand", "horizon": "near", "region": "AMER",
     "criticality": "high", "impact_weight": 0.6, "aliases": ["ERCOT", "Texas grid", "ERCOT interconnection"]},
    {"name": "TVA", "kind": "actor", "theme": "Grid_Replacement_Aging", "horizon": "near", "region": "AMER",
     "criticality": "medium", "impact_weight": 0.5, "aliases": ["TVA", "Tennessee Valley Authority"]},
    # ── EU TSOs (theme: Renewable_Interconnection / Grid_Replacement) ────────
    {"name": "National Grid UK", "kind": "actor", "theme": "Grid_Replacement_Aging", "horizon": "near", "region": "EU",
     "criticality": "high", "impact_weight": 0.6, "aliases": ["National Grid", "National Grid UK", "Great Grid Upgrade"]},
    {"name": "TenneT", "kind": "actor", "theme": "Renewable_Interconnection", "horizon": "near", "region": "EU",
     "criticality": "high", "impact_weight": 0.6, "aliases": ["TenneT", "TenneT TSO"]},
    {"name": "Amprion", "kind": "actor", "theme": "Renewable_Interconnection", "horizon": "near", "region": "EU",
     "criticality": "medium", "impact_weight": 0.55, "aliases": ["Amprion"]},
    {"name": "50Hertz", "kind": "actor", "theme": "Renewable_Interconnection", "horizon": "near", "region": "EU",
     "criticality": "medium", "impact_weight": 0.5, "aliases": ["50Hertz", "50 Hertz"]},
    {"name": "RTE France", "kind": "actor", "theme": "Grid_Replacement_Aging", "horizon": "near", "region": "EU",
     "criticality": "medium", "impact_weight": 0.5, "aliases": ["RTE", "RTE France", "Reseau de Transport"]},
    {"name": "Terna", "kind": "actor", "theme": "Grid_Replacement_Aging", "horizon": "near", "region": "EU",
     "criticality": "medium", "impact_weight": 0.5, "aliases": ["Terna", "Terna Italy"]},
    # ── RENEWABLE PROJECTS (theme: Renewable_Interconnection) ────────────────
    {"name": "Dogger Bank Wind Farm", "kind": "actor", "theme": "Renewable_Interconnection", "horizon": "near", "region": "EU",
     "criticality": "medium", "impact_weight": 0.5, "aliases": ["Dogger Bank", "Dogger Bank wind"]},
    {"name": "Hornsea Wind Farm", "kind": "actor", "theme": "Renewable_Interconnection", "horizon": "near", "region": "EU",
     "criticality": "medium", "impact_weight": 0.45, "aliases": ["Hornsea", "Hornsea wind"]},
    {"name": "Coastal Virginia Offshore Wind", "kind": "actor", "theme": "Renewable_Interconnection", "horizon": "near", "region": "AMER",
     "criticality": "medium", "impact_weight": 0.45, "aliases": ["CVOW", "Coastal Virginia Offshore Wind", "Dominion offshore wind"]},
    {"name": "Empire Wind", "kind": "actor", "theme": "Renewable_Interconnection", "horizon": "near", "region": "AMER",
     "criticality": "low", "impact_weight": 0.4, "aliases": ["Empire Wind", "Equinor Empire Wind"]},
    {"name": "SunZia Transmission", "kind": "actor", "theme": "Renewable_Interconnection", "horizon": "near", "region": "AMER",
     "criticality": "medium", "impact_weight": 0.45, "aliases": ["SunZia", "SunZia transmission", "Pattern Energy SunZia"]},
    # ── GOVERNMENT PROGRAMS (theme: Policy_Stimulus) ─────────────────────────
    {"name": "US IRA Grid Program", "kind": "actor", "theme": "Policy_Stimulus", "horizon": "medium", "region": "AMER",
     "criticality": "high", "impact_weight": 0.6, "aliases": ["IRA", "Inflation Reduction Act", "GRIP program", "DOE grid funding"]},
    {"name": "US IIJA Infrastructure", "kind": "actor", "theme": "Policy_Stimulus", "horizon": "medium", "region": "AMER",
     "criticality": "medium", "impact_weight": 0.55, "aliases": ["IIJA", "Bipartisan Infrastructure Law", "infrastructure bill"]},
    {"name": "REPowerEU", "kind": "actor", "theme": "Policy_Stimulus", "horizon": "medium", "region": "EU",
     "criticality": "high", "impact_weight": 0.6, "aliases": ["REPowerEU", "EU grid action plan", "EU Green Deal grid"]},
    {"name": "Saudi Vision 2030 NEOM", "kind": "actor", "theme": "Policy_Stimulus", "horizon": "medium", "region": "MENA",
     "criticality": "medium", "impact_weight": 0.5, "aliases": ["Vision 2030", "NEOM", "NEOM grid", "Saudi grid"]},
    {"name": "India Green Grid", "kind": "actor", "theme": "Policy_Stimulus", "horizon": "medium", "region": "APAC",
     "criticality": "medium", "impact_weight": 0.45, "aliases": ["Green Energy Corridor", "India grid", "Power Grid Corporation India"]},
    {"name": "Australia Rewiring the Nation", "kind": "actor", "theme": "Policy_Stimulus", "horizon": "medium", "region": "APAC",
     "criticality": "low", "impact_weight": 0.4, "aliases": ["Rewiring the Nation", "Australia grid", "AEMO ISP"]},
    # ── RESHORING (theme: Industrial_Reshoring) ──────────────────────────────
    {"name": "TSMC Arizona", "kind": "actor", "theme": "Industrial_Reshoring", "horizon": "near", "region": "AMER",
     "criticality": "medium", "impact_weight": 0.5, "aliases": ["TSMC", "TSMC Arizona", "TSMC fab", "Phoenix fab"]},
    {"name": "Intel Ohio", "kind": "actor", "theme": "Industrial_Reshoring", "horizon": "medium", "region": "AMER",
     "criticality": "low", "impact_weight": 0.4, "aliases": ["Intel Ohio", "Intel fab", "Ohio One"]},
    {"name": "Micron New York", "kind": "actor", "theme": "Industrial_Reshoring", "horizon": "medium", "region": "AMER",
     "criticality": "low", "impact_weight": 0.4, "aliases": ["Micron", "Micron New York", "Micron fab", "Clay NY"]},
]

# ═════════════════════════════════════════════════════════════════════════════
# EDGES — all relationships
# Format: (rel_type, start_label, start_name, end_label, end_name, props|None)
# A mix of auto-generated (from node properties) + explicit domain relationships.
# ═════════════════════════════════════════════════════════════════════════════

EDGES: list[tuple] = []

# Quick lookups
_COUNTRY_BY_ISO = {c["iso2"]: c["name"] for c in COUNTRIES}
_SUPPLIER_NAMES = {s["name"] for s in SUPPLIERS}
_SUPPLIER_BY_TYPE: dict[str, list[str]] = {}
for _s in SUPPLIERS:
    _SUPPLIER_BY_TYPE.setdefault(_s["type"], []).append(_s["name"])

# ── Plant → Supplier (OPERATED_BY) ───────────────────────────────────────────
for plant in PLANTS:
    EDGES.append(("OPERATED_BY", "Plant", plant["name"], "Supplier", plant["operator"],
                  {"criticality": plant.get("criticality", "medium")}))

# ── Plant → Country (LOCATED_IN) ──────────────────────────────────────────────
for plant in PLANTS:
    country_name = _COUNTRY_BY_ISO.get(plant["country"])
    if country_name:
        EDGES.append(("LOCATED_IN", "Plant", plant["name"], "Country", country_name, None))

# ── Material → Commodity (IS_FORM_OF) — only when the material has a commodity ─
for mat in MATERIALS:
    if mat.get("commodity"):
        EDGES.append(("IS_FORM_OF", "Material", mat["name"], "Commodity", mat["commodity"],
                      {"criticality": mat.get("criticality", "medium"),
                       "impact_weight": mat.get("impact_weight", 0.5)}))

# ── Plant → Material (USES_MATERIAL) — by plant specialty ─────────────────────
PLANT_MATERIAL_MAP: dict[str, list[str]] = {
    "large_power": ["GOES_HiB", "GOES_M3", "GOES_M4", "Cu_CTC", "Cu_PICC",
                    "Naphthenic_Oil_IEC60296", "Transformerboard", "Nomex_410_Aramid",
                    "OLTC_Assembly", "Bushing_RIP", "Tank_Structural_Steel", "Radiator_Cooling_Assembly"],
    "uhv": ["GOES_DomainRefined", "GOES_HiB", "Cu_CTC", "Naphthenic_Oil_IEC60296",
            "Transformerboard", "Nomex_410_Aramid", "OLTC_Assembly", "Bushing_RIS"],
    "hvdc": ["GOES_DomainRefined", "Cu_CTC", "Naphthenic_Oil_IEC60296", "Transformerboard",
             "Bushing_RIP", "Bushing_RIS", "OLTC_Assembly"],
    "gsu": ["GOES_HiB", "GOES_M3", "Cu_CTC", "Naphthenic_Oil_IEC60296", "Transformerboard",
            "OLTC_Assembly", "Bushing_RIP"],
    "data_center_class": ["GOES_M3", "GOES_M4", "Cu_PICC", "Cu_CTC", "Ester_KClass",
                          "Naphthenic_Oil_IEC60296", "Kraft_Insulation_Paper", "Bushing_OIP_Porcelain"],
    "mobile_substation": ["GOES_M4", "Cu_PICC", "Naphthenic_Oil_IEC60296", "Kraft_Insulation_Paper",
                          "OLTC_Assembly", "Bushing_OIP_Porcelain"],
    "distribution": ["NGOES_Reactor_Grade", "Al_Winding_Strip", "Cu_Bar_Bus",
                     "Naphthenic_Oil_IEC60296", "Kraft_Insulation_Paper"],
    # Upstream / component plants produce materials rather than consume the LPT BoM
    "goes_mill": [], "oltc": [], "bushings": [], "insulation": [],
    "winding_wire": [], "oil_refinery": [],
}
for plant in PLANTS:
    for m in PLANT_MATERIAL_MAP.get(plant.get("specialty", ""), []):
        EDGES.append(("USES_MATERIAL", "Plant", plant["name"], "Material", m, None))

# ── Plant → Port (SHIPS_VIA) — nearest heavy-lift port(s) by country ──────────
PLANT_PORT_MAP: dict[str, list[str]] = {
    "KR": ["Busan", "Ulsan", "Gwangyang", "Masan"],
    "JP": ["Kobe", "Yokohama", "Nagoya"],
    "CN": ["Shanghai", "Tianjin"],
    "IN": ["Mundra", "Nhava Sheva"],
    "DE": ["Hamburg", "Bremerhaven", "Antwerp"],
    "FR": ["Antwerp", "Genoa"],
    "PL": ["Hamburg", "Gothenburg"],
    "CH": ["Genoa", "Antwerp"],
    "SE": ["Gothenburg"],
    "FI": ["Gothenburg"],
    "AT": ["Genoa", "Hamburg"],
    "IT": ["Genoa"],
    "ES": ["Bilbao"],
    "NL": ["Rotterdam", "Antwerp"],
    "PT": ["Leixoes"],
    "GB": ["Rotterdam", "Antwerp"],
    "NO": ["Gothenburg"],
    "TR": ["Genoa"],
    "US": ["Houston", "Norfolk", "Savannah", "New Orleans"],
    "CA": ["Montreal"],
    "MX": ["Manzanillo", "Houston"],
    "BR": ["Itajai"],
    "RU": [],
}
# Only OEM / large-power plants ship finished transformers via port; upstream
# (mills, components) move by other modes and are excluded to keep edges meaningful.
_SHIPPING_SPECIALTIES = {"large_power", "uhv", "hvdc", "gsu", "data_center_class", "mobile_substation"}
for plant in PLANTS:
    if plant.get("specialty") in _SHIPPING_SPECIALTIES:
        for port in PLANT_PORT_MAP.get(plant["country"], []):
            EDGES.append(("SHIPS_VIA", "Plant", plant["name"], "Port", port, None))

# ── Port → Lane (ON_LANE) ─────────────────────────────────────────────────────
PORT_LANE_MAP: dict[str, list[str]] = {
    # Korea
    "Busan": ["Korea_USEC", "Korea_USWC", "Korea_USGulf", "Korea_EU"],
    "Ulsan": ["Korea_USEC", "Korea_USWC", "Korea_EU"],
    "Gwangyang": ["Korea_USWC", "Korea_EU"],
    "Masan": ["Korea_USWC"],
    # Japan
    "Kobe": ["Japan_USEC", "Japan_USWC"],
    "Yokohama": ["Japan_USWC"],
    "Nagoya": ["Japan_USWC", "Japan_USEC"],
    # China
    "Shanghai": ["China_USEC", "China_USWC", "China_EU"],
    "Tianjin": ["China_USWC", "China_EU"],
    # India
    "Mundra": ["India_EU", "India_USEC"],
    "Nhava Sheva": ["India_EU", "India_USEC"],
    # EU exports to US
    "Antwerp": ["EU_USEC", "EU_USGulf"],
    "Rotterdam": ["EU_USEC", "EU_USGulf"],
    "Hamburg": ["EU_USEC"],
    "Bremerhaven": ["EU_USEC"],
    "Genoa": ["EU_USEC"],
    "Bilbao": ["EU_USEC"],
    "Gothenburg": ["EU_USEC"],
    "Leixoes": ["EU_USEC"],
    # Latam / Mexico / Turkey
    "Itajai": ["Brazil_USEC"],
    "Manzanillo": ["Mexico_USGulf"],
}
for port, lanes in PORT_LANE_MAP.items():
    for lane in lanes:
        EDGES.append(("ON_LANE", "Port", port, "Lane", lane, None))

# ── Supplier → Supplier (SUB_TIER_OF) — upstream component dependency ─────────
# Each (component_type, impact_weight) feeds ALL large-power OEMs.
_LARGE_POWER_OEMS = [s["name"] for s in SUPPLIERS
                     if s["type"] in ("transformer_oem",) and s.get("criticality") in ("critical", "high")]
_COMPONENT_FEEDS = [
    ("goes_mill",        "GOES core steel",        0.95),
    ("tap_changer_oltc", "On-load tap changer",    0.8),
    ("bushings",         "HV bushings",            0.7),
    ("insulation",       "Pressboard / aramid",    0.65),
    ("winding_wire",     "CTC / magnet wire",      0.65),
    ("transformer_oil",  "Naphthenic oil",         0.6),
]
for sup_type, component, weight in _COMPONENT_FEEDS:
    for supplier in _SUPPLIER_BY_TYPE.get(sup_type, []):
        for oem in _LARGE_POWER_OEMS:
            EDGES.append(("SUB_TIER_OF", "Supplier", supplier, "Supplier", oem,
                          {"component": component, "impact_weight": weight}))

# ── Supplier ↔ Supplier (ALTERNATIVE_TO) — substitutable sources ─────────────
_ALTERNATIVE_GROUPS = [
    # GOES mills broadly substitutable (qualification permitting)
    ["Nippon Steel", "JFE Steel", "POSCO", "thyssenkrupp Electrical Steel", "Baowu Steel", "Cleveland-Cliffs", "Stalprodukt"],
    # OLTC makers
    ["Reinhausen", "Hitachi Energy OLTC", "Huaming Power Equipment"],
    # HV bushings
    ["Trench Group", "HSP Hochspannungsgeraete", "Hitachi Energy Bushings", "Pfisterer"],
    # Transformer oil
    ["Nynas", "Ergon", "Apar Industries"],
    # Insulation
    ["Weidmann Electrical Technology", "Krempel Group"],
    # Top-tier OEMs (broad substitution for large power orders)
    ["Hitachi Energy", "Siemens Energy", "GE Vernova", "Hyundai Electric", "Hyosung Heavy Industries"],
]
for group in _ALTERNATIVE_GROUPS:
    for i in range(len(group)):
        for j in range(i + 1, len(group)):
            EDGES.append(("ALTERNATIVE_TO", "Supplier", group[i], "Supplier", group[j], None))

# ── Supplier → Category (PRODUCES) — which OEM makes which product class ──────
PLANT_SPECIALTY_TO_CATEGORY = {
    "large_power": "Power_Transformer_Large",
    "uhv": "Power_Transformer_Large",
    "hvdc": "HVDC_Converter_Transformer",
    "gsu": "Generator_StepUp_GSU",
    "data_center_class": "Data_Center_Transformer",
    "mobile_substation": "Mobile_Substation",
    "distribution": "Medium_Power_Substation",
}
_seen_produces: set[tuple[str, str]] = set()
for plant in PLANTS:
    cat = PLANT_SPECIALTY_TO_CATEGORY.get(plant.get("specialty", ""))
    if cat and (plant["operator"], cat) not in _seen_produces:
        _seen_produces.add((plant["operator"], cat))
        EDGES.append(("PRODUCES", "Supplier", plant["operator"], "Category", cat, None))

# ── Commodity/Supplier → Category (CONSTRAINS) — explicit bottleneck edges ────
_CONSTRAINTS = [
    # (start_label, start_name, category, severity)
    ("Commodity", "GOES", "Power_Transformer_Large", "critical"),
    ("Commodity", "GOES", "Generator_StepUp_GSU", "critical"),
    ("Commodity", "GOES", "HVDC_Converter_Transformer", "critical"),
    ("Commodity", "GOES", "Data_Center_Transformer", "high"),
    ("Commodity", "Copper", "Power_Transformer_Large", "high"),
    ("Commodity", "Copper", "Data_Center_Transformer", "high"),
    ("Commodity", "Transformer_Oil_Naphthenic", "Power_Transformer_Large", "high"),
    ("Commodity", "Cellulose_Pressboard", "Power_Transformer_Large", "medium"),
    ("Commodity", "Aramid_Paper", "Data_Center_Transformer", "high"),
    ("Commodity", "Heavy_Lift_Freight", "Power_Transformer_Large", "high"),
    ("Commodity", "Heavy_Lift_Freight", "HVDC_Converter_Transformer", "high"),
    ("Supplier", "Reinhausen", "Power_Transformer_Large", "high"),
    ("Supplier", "Reinhausen", "Generator_StepUp_GSU", "high"),
    ("Supplier", "Trench Group", "Power_Transformer_Large", "high"),
    ("Supplier", "Weidmann Electrical Technology", "Power_Transformer_Large", "high"),
    ("Supplier", "Cleveland-Cliffs", "Power_Transformer_Large", "high"),  # US single-source GOES
    ("Supplier", "Essex Furukawa Magnet Wire", "Power_Transformer_Large", "medium"),
]
for start_label, start_name, cat, severity in _CONSTRAINTS:
    EDGES.append(("CONSTRAINS", start_label, start_name, "Category", cat, {"severity": severity}))

# ── DemandSource(actor) → DemandSource(theme) (BELONGS_TO_THEME) ──────────────
_THEME_NAMES = {d["name"] for d in DEMAND_SOURCES if d.get("kind") == "theme"}
for d in DEMAND_SOURCES:
    if d.get("kind") == "actor":
        theme = d.get("theme")
        if theme in _THEME_NAMES and theme != d["name"]:
            EDGES.append(("BELONGS_TO_THEME", "DemandSource", d["name"], "DemandSource", theme, None))

# ── DemandSource(theme) → Category (DRIVES_DEMAND_FOR), weighted ──────────────
_THEME_DRIVES = {
    "Data_Center_AI_Demand": [
        ("Data_Center_Transformer", 0.95), ("Power_Transformer_Large", 0.85),
        ("Generator_StepUp_GSU", 0.7), ("Medium_Power_Substation", 0.7),
    ],
    "Grid_Replacement_Aging": [
        ("Power_Transformer_Large", 0.85), ("Autotransformer", 0.7),
        ("Mobile_Substation", 0.5), ("Medium_Power_Substation", 0.6),
    ],
    "Renewable_Interconnection": [
        ("Generator_StepUp_GSU", 0.85), ("HVDC_Converter_Transformer", 0.7),
        ("Power_Transformer_Large", 0.7),
    ],
    "Electrification_Demand": [
        ("Medium_Power_Substation", 0.7), ("Power_Transformer_Large", 0.55),
    ],
    "Policy_Stimulus": [
        ("Power_Transformer_Large", 0.6), ("HVDC_Converter_Transformer", 0.55),
        ("Generator_StepUp_GSU", 0.5),
    ],
    "Industrial_Reshoring": [
        ("Medium_Power_Substation", 0.6), ("Power_Transformer_Large", 0.5),
    ],
}
for theme, targets in _THEME_DRIVES.items():
    theme_node = next((d for d in DEMAND_SOURCES if d["name"] == theme), None)
    horizon = theme_node.get("horizon", "medium") if theme_node else "medium"
    for cat, weight in targets:
        EDGES.append(("DRIVES_DEMAND_FOR", "DemandSource", theme, "Category", cat,
                      {"impact_weight": weight, "horizon": horizon}))

# ── DemandSource(theme) → Country (DEMAND_PULLS_ON) — regional capacity pressure
_THEME_REGION_PRESSURE = {
    "Data_Center_AI_Demand": [("United States", 0.95), ("South Korea", 0.6), ("Mexico", 0.6), ("Germany", 0.5)],
    "Grid_Replacement_Aging": [("United States", 0.8), ("Germany", 0.6), ("United Kingdom", 0.6)],
    "Renewable_Interconnection": [("United Kingdom", 0.7), ("Germany", 0.7), ("United States", 0.65), ("Netherlands", 0.6)],
    "Policy_Stimulus": [("United States", 0.65), ("Germany", 0.6), ("India", 0.5)],
    "Industrial_Reshoring": [("United States", 0.7)],
}
for theme, targets in _THEME_REGION_PRESSURE.items():
    for country, weight in targets:
        EDGES.append(("DEMAND_PULLS_ON", "DemandSource", theme, "Country", country,
                      {"impact_weight": weight}))
