"""Power-transformer supply graph seed data.

Hand-curated against PROJECT_SPEC §4 (domain primer).
~93 nodes, ~200 edges. Loaded by scripts/seed_graph.py.

NOTE: Keep this file as plain data — no Neo4j imports here.
The loader script is responsible for translation to Cypher MERGE statements.
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# COMMODITIES (raw materials at the commodity-market level)
# ─────────────────────────────────────────────────────────────────────────────

COMMODITIES: list[dict] = [
    {"name": "GOES", "full_name": "Grain-Oriented Electrical Steel", "ticker_proxy": "HRC=F", "category": "ferrous"},
    {"name": "Copper", "full_name": "Copper", "ticker_proxy": "HG=F", "category": "non_ferrous"},
    {"name": "Aluminum", "full_name": "Aluminum", "ticker_proxy": "ALI=F", "category": "non_ferrous"},
    {"name": "Mineral_Oil", "full_name": "Transformer Mineral Oil", "ticker_proxy": "CL=F", "category": "petrochemical"},
    {"name": "Ester_Fluid", "full_name": "Natural/Synthetic Ester Insulating Fluid", "ticker_proxy": None, "category": "biofluid"},
    {"name": "Porcelain", "full_name": "High-Voltage Porcelain (Bushings)", "ticker_proxy": None, "category": "ceramic"},
    {"name": "Composite_Bushing_Polymer", "full_name": "Silicone Composite (Bushings)", "ticker_proxy": None, "category": "polymer"},
    {"name": "Crude_Oil_Freight", "full_name": "Bunker Fuel Proxy", "ticker_proxy": "CL=F", "category": "freight_input"},
    {"name": "Lumber_Crating", "full_name": "Heavy-Lift Crating Lumber", "ticker_proxy": None, "category": "logistics_input"},
    {"name": "Silicon_Steel_NGOES", "full_name": "Non-Grain-Oriented Electrical Steel (smaller units)", "ticker_proxy": "HRC=F", "category": "ferrous"},
]

# ─────────────────────────────────────────────────────────────────────────────
# MATERIALS (specific engineered forms of the commodities used in plants)
# ─────────────────────────────────────────────────────────────────────────────

MATERIALS: list[dict] = [
    {"name": "GOES_M3_Grade", "commodity": "GOES", "spec": "0.23mm, B800 ≥ 1.88T"},
    {"name": "GOES_M4_Grade", "commodity": "GOES", "spec": "0.27mm, B800 ≥ 1.85T"},
    {"name": "Cu_Winding_Strip", "commodity": "Copper", "spec": "Continuously Transposed Conductor (CTC)"},
    {"name": "Cu_Bar_Bus", "commodity": "Copper", "spec": "Electrolytic-grade busbar"},
    {"name": "Al_Winding_Strip", "commodity": "Aluminum", "spec": "EC-grade strip"},
    {"name": "Al_Bar_Bus", "commodity": "Aluminum", "spec": "1350-H19 busbar"},
    {"name": "Mineral_Oil_IEC60296", "commodity": "Mineral_Oil", "spec": "IEC 60296 standard"},
    {"name": "Ester_K_Class", "commodity": "Ester_Fluid", "spec": "K-class fire-safe ester"},
    {"name": "Bushing_HV_Porcelain", "commodity": "Porcelain", "spec": "≥ 220 kV porcelain"},
    {"name": "Bushing_HV_Composite", "commodity": "Composite_Bushing_Polymer", "spec": "Silicone composite, ≥ 220 kV"},
    {"name": "NGOES_Grade50", "commodity": "Silicon_Steel_NGOES", "spec": "M-19 / 0.5mm"},
    {"name": "Heavy_Lift_Cratepack", "commodity": "Lumber_Crating", "spec": "Bespoke per unit"},
]

# ─────────────────────────────────────────────────────────────────────────────
# COUNTRIES
# ─────────────────────────────────────────────────────────────────────────────

COUNTRIES: list[dict] = [
    {"name": "Germany", "iso2": "DE", "region": "EU"},
    {"name": "Switzerland", "iso2": "CH", "region": "EU"},
    {"name": "Sweden", "iso2": "SE", "region": "EU"},
    {"name": "Finland", "iso2": "FI", "region": "EU"},
    {"name": "Austria", "iso2": "AT", "region": "EU"},
    {"name": "Poland", "iso2": "PL", "region": "EU"},
    {"name": "Italy", "iso2": "IT", "region": "EU"},
    {"name": "South Korea", "iso2": "KR", "region": "APAC"},
    {"name": "Japan", "iso2": "JP", "region": "APAC"},
    {"name": "China", "iso2": "CN", "region": "APAC"},
    {"name": "India", "iso2": "IN", "region": "APAC"},
    {"name": "Brazil", "iso2": "BR", "region": "LATAM"},
    {"name": "United States", "iso2": "US", "region": "AMER"},
]

# ─────────────────────────────────────────────────────────────────────────────
# SUPPLIERS (tier-1 transformer makers + tier-2 GOES mills + adjacent)
# ─────────────────────────────────────────────────────────────────────────────

SUPPLIERS: list[dict] = [
    # Tier-1 large-power transformer manufacturers
    {"name": "Siemens Energy", "tier": 1, "type": "transformer_oem", "hq_country": "DE", "sec_cik": None},
    {"name": "Hitachi Energy", "tier": 1, "type": "transformer_oem", "hq_country": "CH", "sec_cik": None},
    {"name": "GE Vernova", "tier": 1, "type": "transformer_oem", "hq_country": "US", "sec_cik": "1993009"},
    {"name": "Hyundai Electric", "tier": 1, "type": "transformer_oem", "hq_country": "KR", "sec_cik": None},
    {"name": "Hyosung Heavy Industries", "tier": 1, "type": "transformer_oem", "hq_country": "KR", "sec_cik": None},
    {"name": "Mitsubishi Electric", "tier": 1, "type": "transformer_oem", "hq_country": "JP", "sec_cik": None},
    {"name": "WEG", "tier": 1, "type": "transformer_oem", "hq_country": "BR", "sec_cik": None},
    {"name": "CG Power", "tier": 1, "type": "transformer_oem", "hq_country": "IN", "sec_cik": None},
    {"name": "BHEL", "tier": 1, "type": "transformer_oem", "hq_country": "IN", "sec_cik": None},
    # Adjacent power-equipment SEC filers
    {"name": "Eaton", "tier": 1, "type": "power_equipment_adjacent", "hq_country": "US", "sec_cik": "31277"},
    {"name": "Hubbell", "tier": 1, "type": "power_equipment_adjacent", "hq_country": "US", "sec_cik": "48898"},
    # Tier-2 GOES mills
    {"name": "Nippon Steel", "tier": 2, "type": "goes_mill", "hq_country": "JP", "sec_cik": None},
    {"name": "JFE Steel", "tier": 2, "type": "goes_mill", "hq_country": "JP", "sec_cik": None},
    {"name": "POSCO", "tier": 2, "type": "goes_mill", "hq_country": "KR", "sec_cik": None},
    {"name": "Baosteel", "tier": 2, "type": "goes_mill", "hq_country": "CN", "sec_cik": None},
    {"name": "Stalprodukt", "tier": 2, "type": "goes_mill", "hq_country": "PL", "sec_cik": None},
    {"name": "Cleveland-Cliffs", "tier": 2, "type": "goes_mill", "hq_country": "US", "sec_cik": "764065"},
    # Tier-2 sub-components
    {"name": "Reinhausen", "tier": 2, "type": "tap_changer_oltc", "hq_country": "DE", "sec_cik": None},
    {"name": "ABB Bushings", "tier": 2, "type": "bushings", "hq_country": "SE", "sec_cik": None},
]

# ─────────────────────────────────────────────────────────────────────────────
# PLANTS
# ─────────────────────────────────────────────────────────────────────────────

PLANTS: list[dict] = [
    # Siemens Energy
    {"name": "Siemens Nuremberg", "operator": "Siemens Energy", "country": "DE", "lat": 49.45, "lon": 11.08, "specialty": "large_power"},
    {"name": "Siemens Weiz", "operator": "Siemens Energy", "country": "AT", "lat": 47.22, "lon": 15.62, "specialty": "large_power"},
    {"name": "Siemens Linz", "operator": "Siemens Energy", "country": "AT", "lat": 48.31, "lon": 14.29, "specialty": "distribution"},
    {"name": "Siemens Charlotte", "operator": "Siemens Energy", "country": "US", "lat": 35.23, "lon": -80.84, "specialty": "large_power"},
    # Hitachi Energy
    {"name": "Hitachi Bad Honnef", "operator": "Hitachi Energy", "country": "DE", "lat": 50.65, "lon": 7.22, "specialty": "large_power"},
    {"name": "Hitachi Ludvika", "operator": "Hitachi Energy", "country": "SE", "lat": 60.15, "lon": 15.18, "specialty": "hvdc"},
    {"name": "Hitachi Vaasa", "operator": "Hitachi Energy", "country": "FI", "lat": 63.10, "lon": 21.62, "specialty": "large_power"},
    {"name": "Hitachi South Boston", "operator": "Hitachi Energy", "country": "US", "lat": 36.70, "lon": -78.90, "specialty": "large_power"},
    # GE Vernova
    {"name": "GE Vernova Pittsburgh", "operator": "GE Vernova", "country": "US", "lat": 40.44, "lon": -79.99, "specialty": "large_power"},
    {"name": "GE Vernova Memphis", "operator": "GE Vernova", "country": "US", "lat": 35.15, "lon": -90.05, "specialty": "large_power"},
    # Hyundai Electric
    {"name": "Hyundai Ulsan", "operator": "Hyundai Electric", "country": "KR", "lat": 35.55, "lon": 129.32, "specialty": "large_power"},
    # Hyosung
    {"name": "Hyosung Changwon", "operator": "Hyosung Heavy Industries", "country": "KR", "lat": 35.23, "lon": 128.68, "specialty": "ultra_high_voltage"},
    # Mitsubishi Electric
    {"name": "Mitsubishi Ako", "operator": "Mitsubishi Electric", "country": "JP", "lat": 34.74, "lon": 134.39, "specialty": "large_power"},
    # WEG
    {"name": "WEG Blumenau", "operator": "WEG", "country": "BR", "lat": -26.91, "lon": -49.07, "specialty": "large_power"},
    # CG / BHEL
    {"name": "CG Power Bhopal", "operator": "CG Power", "country": "IN", "lat": 23.26, "lon": 77.41, "specialty": "large_power"},
    {"name": "BHEL Bhopal", "operator": "BHEL", "country": "IN", "lat": 23.26, "lon": 77.41, "specialty": "large_power"},
    # Adjacent (US distribution)
    {"name": "Eaton Waukesha", "operator": "Eaton", "country": "US", "lat": 43.01, "lon": -88.23, "specialty": "distribution"},
    {"name": "Hubbell Centralia", "operator": "Hubbell", "country": "US", "lat": 38.52, "lon": -89.13, "specialty": "distribution"},
    # GOES mills
    {"name": "Nippon Steel Hirohata", "operator": "Nippon Steel", "country": "JP", "lat": 34.79, "lon": 134.65, "specialty": "goes_mill"},
    {"name": "JFE Kurashiki", "operator": "JFE Steel", "country": "JP", "lat": 34.59, "lon": 133.77, "specialty": "goes_mill"},
    {"name": "POSCO Pohang", "operator": "POSCO", "country": "KR", "lat": 36.04, "lon": 129.36, "specialty": "goes_mill"},
    {"name": "Baosteel Shanghai", "operator": "Baosteel", "country": "CN", "lat": 31.40, "lon": 121.49, "specialty": "goes_mill"},
    {"name": "Stalprodukt Bochnia", "operator": "Stalprodukt", "country": "PL", "lat": 49.97, "lon": 20.43, "specialty": "goes_mill"},
    {"name": "Cleveland-Cliffs Butler", "operator": "Cleveland-Cliffs", "country": "US", "lat": 40.86, "lon": -79.90, "specialty": "goes_mill"},
    # Sub-components
    {"name": "Reinhausen Regensburg", "operator": "Reinhausen", "country": "DE", "lat": 49.01, "lon": 12.10, "specialty": "tap_changer"},
    {"name": "ABB Bushings Ludvika", "operator": "ABB Bushings", "country": "SE", "lat": 60.15, "lon": 15.18, "specialty": "bushings"},
]

# ─────────────────────────────────────────────────────────────────────────────
# PORTS
# ─────────────────────────────────────────────────────────────────────────────

PORTS: list[dict] = [
    {"name": "Busan", "locode": "KRPUS", "country": "KR", "type": "container_breakbulk"},
    {"name": "Antwerp", "locode": "BEANR", "country": "BE", "type": "heavy_lift_breakbulk"},
    {"name": "Rotterdam", "locode": "NLRTM", "country": "NL", "type": "heavy_lift_breakbulk"},
    {"name": "Bremerhaven", "locode": "DEBRV", "country": "DE", "type": "heavy_lift_breakbulk"},
    {"name": "Hamburg", "locode": "DEHAM", "country": "DE", "type": "container_breakbulk"},
    {"name": "Savannah", "locode": "USSAV", "country": "US", "type": "container_breakbulk"},
    {"name": "Norfolk", "locode": "USORF", "country": "US", "type": "heavy_lift_breakbulk"},
    {"name": "Houston", "locode": "USHOU", "country": "US", "type": "heavy_lift_breakbulk"},
    {"name": "Yokohama", "locode": "JPYOK", "country": "JP", "type": "container_breakbulk"},
    {"name": "Santos", "locode": "BRSSZ", "country": "BR", "type": "container_breakbulk"},
]

# ─────────────────────────────────────────────────────────────────────────────
# LANES (shipping corridors)
# ─────────────────────────────────────────────────────────────────────────────

LANES: list[dict] = [
    {"name": "Korea_USEC", "origin_region": "APAC", "destination_region": "AMER", "transit_days": 30},
    {"name": "Korea_EU_NorthSea", "origin_region": "APAC", "destination_region": "EU", "transit_days": 38},
    {"name": "Japan_USEC", "origin_region": "APAC", "destination_region": "AMER", "transit_days": 28},
    {"name": "Japan_EU_NorthSea", "origin_region": "APAC", "destination_region": "EU", "transit_days": 36},
    {"name": "Brazil_USEC", "origin_region": "LATAM", "destination_region": "AMER", "transit_days": 18},
    {"name": "EU_USEC", "origin_region": "EU", "destination_region": "AMER", "transit_days": 14},
]

# ─────────────────────────────────────────────────────────────────────────────
# CATEGORIES (procurement categorization)
# ─────────────────────────────────────────────────────────────────────────────

CATEGORIES: list[dict] = [
    {"name": "Power_Transformer_Large", "description": "Large power transformers ≥ 100 MVA"},
    {"name": "Power_Transformer_GSU", "description": "Generator step-up transformers"},
    {"name": "Power_Transformer_HVDC_Converter", "description": "HVDC converter transformers"},
    {"name": "Power_Transformer_Distribution", "description": "Substation / distribution transformers"},
    {"name": "Power_Transformer_Spot_OneOff", "description": "Single-unit spot purchases"},
]

# ─────────────────────────────────────────────────────────────────────────────
# DEMAND SOURCES (entities driving demand for the category)
# ─────────────────────────────────────────────────────────────────────────────

DEMAND_SOURCES: list[dict] = [
    {"name": "Microsoft Datacenter Buildout", "type": "hyperscaler", "country": "US"},
    {"name": "Google Datacenter Buildout", "type": "hyperscaler", "country": "US"},
    {"name": "Amazon Datacenter Buildout", "type": "hyperscaler", "country": "US"},
    {"name": "Meta Datacenter Buildout", "type": "hyperscaler", "country": "US"},
    {"name": "IRA Grid Modernization Program", "type": "government_grid", "country": "US"},
    {"name": "REPowerEU Grid Upgrade", "type": "government_grid", "country": "EU"},
]

# ─────────────────────────────────────────────────────────────────────────────
# EDGES — all relationships
# Format: (relationship_type, start_label, start_name, end_label, end_name, props_or_None)
# ─────────────────────────────────────────────────────────────────────────────

EDGES: list[tuple] = []

# Plant → Supplier (OPERATED_BY)
for plant in PLANTS:
    EDGES.append(("OPERATED_BY", "Plant", plant["name"], "Supplier", plant["operator"], None))

# Plant → Country (LOCATED_IN)
_country_name_by_iso = {c["iso2"]: c["name"] for c in COUNTRIES}
for plant in PLANTS:
    EDGES.append((
        "LOCATED_IN", "Plant", plant["name"], "Country",
        _country_name_by_iso.get(plant["country"], plant["country"]),
        None,
    ))

# Material → Commodity (IS_FORM_OF)
for mat in MATERIALS:
    EDGES.append(("IS_FORM_OF", "Material", mat["name"], "Commodity", mat["commodity"], None))

# Plant → Material (USES_MATERIAL).
# Most transformer plants use: GOES + Cu strip + Al strip + Mineral Oil + Bushings
# GOES mills use nothing (they ARE the mill); distribution plants use NGOES instead.
_transformer_plant_materials = [
    "GOES_M3_Grade",
    "Cu_Winding_Strip",
    "Al_Winding_Strip",
    "Mineral_Oil_IEC60296",
    "Bushing_HV_Porcelain",
    "Heavy_Lift_Cratepack",
]
_distribution_plant_materials = [
    "NGOES_Grade50",
    "Cu_Winding_Strip",
    "Al_Winding_Strip",
    "Mineral_Oil_IEC60296",
]
_hvdc_plant_materials = [
    "GOES_M3_Grade",
    "GOES_M4_Grade",
    "Cu_Winding_Strip",
    "Mineral_Oil_IEC60296",
    "Ester_K_Class",
    "Bushing_HV_Composite",
    "Heavy_Lift_Cratepack",
]
for plant in PLANTS:
    specialty = plant["specialty"]
    if specialty == "goes_mill":
        continue
    if specialty == "hvdc":
        mats = _hvdc_plant_materials
    elif specialty == "distribution":
        mats = _distribution_plant_materials
    else:
        mats = _transformer_plant_materials
    for m in mats:
        EDGES.append(("USES_MATERIAL", "Plant", plant["name"], "Material", m, None))

# Plant → Port (SHIPS_VIA)
_plant_to_ports: dict[str, list[str]] = {
    # Siemens
    "Siemens Nuremberg": ["Hamburg", "Bremerhaven"],
    "Siemens Weiz": ["Hamburg"],
    "Siemens Linz": ["Hamburg"],
    "Siemens Charlotte": ["Savannah", "Norfolk"],
    # Hitachi
    "Hitachi Bad Honnef": ["Rotterdam", "Antwerp"],
    "Hitachi Ludvika": ["Hamburg"],
    "Hitachi Vaasa": ["Hamburg"],
    "Hitachi South Boston": ["Norfolk"],
    # GE
    "GE Vernova Pittsburgh": ["Norfolk"],
    "GE Vernova Memphis": ["Houston"],
    # Korean
    "Hyundai Ulsan": ["Busan"],
    "Hyosung Changwon": ["Busan"],
    # JP
    "Mitsubishi Ako": ["Yokohama"],
    # WEG
    "WEG Blumenau": ["Santos"],
    # India
    "CG Power Bhopal": ["Houston"],
    "BHEL Bhopal": ["Houston"],
    # Adjacent
    "Eaton Waukesha": ["Houston"],
    "Hubbell Centralia": ["Houston"],
    # GOES mills
    "Nippon Steel Hirohata": ["Yokohama"],
    "JFE Kurashiki": ["Yokohama"],
    "POSCO Pohang": ["Busan"],
    "Baosteel Shanghai": ["Yokohama"],
    "Stalprodukt Bochnia": ["Hamburg"],
    "Cleveland-Cliffs Butler": ["Norfolk"],
    # Sub-components
    "Reinhausen Regensburg": ["Hamburg"],
    "ABB Bushings Ludvika": ["Hamburg"],
}
for plant_name, ports in _plant_to_ports.items():
    for p in ports:
        EDGES.append(("SHIPS_VIA", "Plant", plant_name, "Port", p, None))

# Port → Lane (ON_LANE)
_port_to_lanes: dict[str, list[str]] = {
    "Busan": ["Korea_USEC", "Korea_EU_NorthSea"],
    "Yokohama": ["Japan_USEC", "Japan_EU_NorthSea"],
    "Santos": ["Brazil_USEC"],
    "Antwerp": ["EU_USEC"],
    "Rotterdam": ["EU_USEC"],
    "Bremerhaven": ["EU_USEC"],
    "Hamburg": ["EU_USEC"],
    "Houston": ["Korea_USEC", "Japan_USEC", "Brazil_USEC"],
    "Norfolk": ["Korea_USEC", "Japan_USEC", "EU_USEC"],
    "Savannah": ["Korea_USEC", "EU_USEC"],
}
for port_name, lanes in _port_to_lanes.items():
    for lane in lanes:
        EDGES.append(("ON_LANE", "Port", port_name, "Lane", lane, None))

# Supplier → Supplier (SUB_TIER_OF) — GOES mills supply transformer OEMs
_subtier_relationships: list[tuple[str, str]] = [
    # Nippon Steel sub-tier of Japanese + Korean OEMs
    ("Nippon Steel", "Mitsubishi Electric"),
    ("Nippon Steel", "Hyundai Electric"),
    ("Nippon Steel", "Hyosung Heavy Industries"),
    # JFE
    ("JFE Steel", "Mitsubishi Electric"),
    ("JFE Steel", "Hyundai Electric"),
    # POSCO sub-tier of Korean OEMs
    ("POSCO", "Hyundai Electric"),
    ("POSCO", "Hyosung Heavy Industries"),
    # Baosteel → CN/IN
    ("Baosteel", "CG Power"),
    ("Baosteel", "BHEL"),
    # Stalprodukt → EU OEMs
    ("Stalprodukt", "Siemens Energy"),
    ("Stalprodukt", "Hitachi Energy"),
    # Cleveland-Cliffs → US OEMs (limited US supply)
    ("Cleveland-Cliffs", "GE Vernova"),
    ("Cleveland-Cliffs", "Eaton"),
    # Reinhausen tap-changers to nearly all EU/US OEMs
    ("Reinhausen", "Siemens Energy"),
    ("Reinhausen", "Hitachi Energy"),
    ("Reinhausen", "GE Vernova"),
    # ABB Bushings
    ("ABB Bushings", "Hitachi Energy"),
    ("ABB Bushings", "Siemens Energy"),
]
for sub, tier1 in _subtier_relationships:
    EDGES.append(("SUB_TIER_OF", "Supplier", sub, "Supplier", tier1, None))

# Supplier → Supplier (ALTERNATIVE_TO) — peer manufacturers in similar segments
_alternative_pairs: list[tuple[str, str]] = [
    ("Siemens Energy", "Hitachi Energy"),
    ("Hitachi Energy", "GE Vernova"),
    ("GE Vernova", "Siemens Energy"),
    ("Hyundai Electric", "Hyosung Heavy Industries"),
    ("Hyundai Electric", "Mitsubishi Electric"),
    ("Hyosung Heavy Industries", "Mitsubishi Electric"),
    ("CG Power", "BHEL"),
    ("Eaton", "Hubbell"),
]
for a, b in _alternative_pairs:
    EDGES.append(("ALTERNATIVE_TO", "Supplier", a, "Supplier", b, None))
    EDGES.append(("ALTERNATIVE_TO", "Supplier", b, "Supplier", a, None))

# DemandSource → Category (DRIVES_DEMAND_FOR)
_demand_targets: dict[str, list[str]] = {
    "Microsoft Datacenter Buildout": ["Power_Transformer_Large", "Power_Transformer_GSU"],
    "Google Datacenter Buildout": ["Power_Transformer_Large", "Power_Transformer_GSU"],
    "Amazon Datacenter Buildout": ["Power_Transformer_Large", "Power_Transformer_GSU"],
    "Meta Datacenter Buildout": ["Power_Transformer_Large"],
    "IRA Grid Modernization Program": ["Power_Transformer_Large", "Power_Transformer_HVDC_Converter", "Power_Transformer_Distribution"],
    "REPowerEU Grid Upgrade": ["Power_Transformer_Large", "Power_Transformer_HVDC_Converter"],
}
for src, cats in _demand_targets.items():
    for c in cats:
        EDGES.append(("DRIVES_DEMAND_FOR", "DemandSource", src, "Category", c, None))


# ─────────────────────────────────────────────────────────────────────────────
# Summary (computed at import-time for quick sanity checking)
# ─────────────────────────────────────────────────────────────────────────────

NODE_COUNT = (
    len(COMMODITIES)
    + len(MATERIALS)
    + len(COUNTRIES)
    + len(SUPPLIERS)
    + len(PLANTS)
    + len(PORTS)
    + len(LANES)
    + len(CATEGORIES)
    + len(DEMAND_SOURCES)
)
EDGE_COUNT = len(EDGES)


if __name__ == "__main__":
    print(f"Nodes: {NODE_COUNT}")
    print(f"  Commodities:    {len(COMMODITIES)}")
    print(f"  Materials:      {len(MATERIALS)}")
    print(f"  Countries:      {len(COUNTRIES)}")
    print(f"  Suppliers:      {len(SUPPLIERS)}")
    print(f"  Plants:         {len(PLANTS)}")
    print(f"  Ports:          {len(PORTS)}")
    print(f"  Lanes:          {len(LANES)}")
    print(f"  Categories:     {len(CATEGORIES)}")
    print(f"  DemandSources:  {len(DEMAND_SOURCES)}")
    print(f"Edges: {EDGE_COUNT}")
    # Edge type breakdown
    from collections import Counter
    types = Counter(e[0] for e in EDGES)
    for t, n in sorted(types.items(), key=lambda x: -x[1]):
        print(f"  {t:<22} {n}")
