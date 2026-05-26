"""Power-transformer supply graph seed data — v2 (expanded).

v1 (~107 nodes): minimum-viable hand-curated set from PROJECT_SPEC §4.
v2 (~620 nodes): deep expansion covering the real industry surface area.

Rationale: the `aliases` lists on each node are the SEARCH KEYWORDS used by
KeywordRegistry to filter incoming GDELT/press/SEC/demand signals.
More realistic entities + richer aliases = better recall on actual incidents.

Every name and alias here is grounded in a real industry participant — no
synthetic filler. Where mergers/rebrands have occurred (e.g. Hitachi Energy
ex-ABB Power Grids, Cleveland-Cliffs ex-AK Steel) we keep the legacy name
as an alias because older articles and SEC filings still use them.

NOTE: Keep this file as plain data — no Neo4j imports here. The loader script
(scripts/seed_graph.py) is responsible for translation to Cypher MERGE.
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# COMMODITIES — raw materials at the commodity-market level
# ─────────────────────────────────────────────────────────────────────────────

COMMODITIES: list[dict] = [
    # ── Core transformer commodities ─────────────────────────────────────
    {"name": "GOES", "full_name": "Grain-Oriented Electrical Steel", "ticker_proxy": "HRC=F", "category": "ferrous",
     "aliases": ["grain-oriented electrical steel", "grain oriented steel", "electrical steel", "GOES strip",
                 "transformer steel", "silicon steel", "M3 steel", "M4 steel", "M5 steel", "M6 steel",
                 "oriented electrical steel", "CRGO", "cold-rolled grain-oriented", "Hi-B steel", "HiB",
                 "23P090", "27P090", "27ZH100", "30P110", "P-grade steel"]},
    {"name": "Silicon_Steel_NGOES", "full_name": "Non-Grain-Oriented Electrical Steel (smaller units)", "ticker_proxy": "HRC=F", "category": "ferrous",
     "aliases": ["NGOES", "non-oriented electrical steel", "NOES", "silicon steel non-oriented",
                 "CRNGO", "cold-rolled non-grain-oriented", "M-19", "M19", "M-22", "M-43", "M-45",
                 "fully processed electrical steel", "semi-processed electrical steel"]},
    {"name": "Copper", "full_name": "Copper", "ticker_proxy": "HG=F", "category": "non_ferrous",
     "aliases": ["copper cathode", "copper rod", "copper wire", "CTC conductor", "copper winding",
                 "HG=F", "copper futures", "electrolytic copper", "LME copper", "cathode copper",
                 "Grade A copper", "Cu cathode", "London copper", "Comex copper", "copper concentrate"]},
    {"name": "Aluminum", "full_name": "Aluminum", "ticker_proxy": "ALI=F", "category": "non_ferrous",
     "aliases": ["aluminium", "aluminum strip", "aluminum winding", "ALI=F", "aluminum futures",
                 "EC-grade aluminum", "1350 aluminum", "1350-H19", "LME aluminum", "primary aluminum",
                 "AA1350", "high-purity aluminum", "aluminum ingot", "alumina"]},
    {"name": "Mineral_Oil", "full_name": "Transformer Mineral Oil", "ticker_proxy": "CL=F", "category": "petrochemical",
     "aliases": ["transformer oil", "insulating oil", "dielectric oil", "naphthenic oil",
                 "Nynas oil", "Nytro", "Diala", "Shell Diala", "uninhibited mineral oil",
                 "inhibited mineral oil", "IEC 60296", "Group I oil", "naphthenic base oil"]},
    {"name": "Ester_Fluid", "full_name": "Natural/Synthetic Ester Insulating Fluid", "ticker_proxy": None, "category": "biofluid",
     "aliases": ["ester oil", "natural ester", "synthetic ester", "FR3", "Midel", "Midel 7131",
                 "fire-safe fluid", "biodegradable transformer fluid", "K-class fluid",
                 "BIOTEMP", "Envirotemp", "ester insulating fluid"]},
    # ── Insulating materials ─────────────────────────────────────────────
    {"name": "Porcelain", "full_name": "High-Voltage Porcelain (Bushings)", "ticker_proxy": None, "category": "ceramic",
     "aliases": ["ceramic bushing", "porcelain bushing", "HV bushing", "high voltage bushing",
                 "ceramic insulator", "alumina porcelain", "C-130 porcelain"]},
    {"name": "Composite_Bushing_Polymer", "full_name": "Silicone Composite (Bushings)", "ticker_proxy": None, "category": "polymer",
     "aliases": ["silicone bushing", "composite bushing", "polymer bushing", "RIP bushing",
                 "resin impregnated paper", "RIS bushing", "resin impregnated synthetic",
                 "silicone rubber housing", "HTV silicone", "LSR silicone"]},
    {"name": "Pressboard", "full_name": "Cellulose Pressboard (Transformer Insulation)", "ticker_proxy": None, "category": "cellulosic",
     "aliases": ["transformer pressboard", "cellulose pressboard", "Weidmann pressboard",
                 "kraft paper", "transformer paper", "Nomex paper", "aramid paper", "Nomex 410",
                 "calendered pressboard", "moulded pressboard"]},
    {"name": "Amorphous_Metal", "full_name": "Amorphous Metal Alloy (Distribution Transformers)", "ticker_proxy": None, "category": "alloy",
     "aliases": ["amorphous alloy", "amorphous core", "metglas", "Metglas 2605",
                 "amorphous distribution transformer", "AMDT", "AMT core", "iron-boron-silicon alloy"]},
    # ── Logistics / freight inputs ───────────────────────────────────────
    {"name": "Crude_Oil_Freight", "full_name": "Bunker Fuel Proxy", "ticker_proxy": "CL=F", "category": "freight_input",
     "aliases": ["bunker fuel", "VLSFO", "marine fuel", "shipping fuel", "CL=F",
                 "low-sulfur fuel oil", "IFO 380", "MGO", "marine gasoil"]},
    {"name": "Container_Freight", "full_name": "Container Freight Rate Index", "ticker_proxy": None, "category": "freight_input",
     "aliases": ["SCFI", "Shanghai Containerized Freight Index", "WCI", "Drewry index",
                 "container freight rate", "ocean freight rate", "FEU rate", "TEU rate",
                 "Baltic Dry Index", "BDI"]},
    {"name": "Heavy_Lift_Freight", "full_name": "Heavy-Lift / Breakbulk Freight Rates", "ticker_proxy": None, "category": "freight_input",
     "aliases": ["heavy lift shipping", "breakbulk shipping", "project cargo",
                 "BBC Chartering", "AAL Shipping", "SAL Heavy Lift", "Jumbo Shipping",
                 "Cosco Heavy Transport"]},
    {"name": "Lumber_Crating", "full_name": "Heavy-Lift Crating Lumber", "ticker_proxy": None, "category": "logistics_input",
     "aliases": ["timber", "heavy lift crating", "breakbulk crating", "wooden crating",
                 "ISPM 15", "treated lumber", "transformer crate"]},
    # ── Steel feedstocks (upstream of GOES mills) ────────────────────────
    {"name": "Iron_Ore", "full_name": "Iron Ore (Steel Feedstock)", "ticker_proxy": "TIO=F", "category": "ferrous_feedstock",
     "aliases": ["iron ore fines", "iron ore pellets", "Pilbara fines", "Carajas ore",
                 "62% Fe", "65% Fe", "Platts IODEX", "TIO=F", "SGX iron ore"]},
    {"name": "Coking_Coal", "full_name": "Metallurgical Coking Coal", "ticker_proxy": None, "category": "ferrous_feedstock",
     "aliases": ["met coal", "metallurgical coal", "coking coal", "hard coking coal", "HCC",
                 "semi-soft coking coal", "PCI coal", "premium hard coking coal"]},
    {"name": "Natural_Gas", "full_name": "Natural Gas (Steel Process / Transformer Drying)", "ticker_proxy": "NG=F", "category": "energy",
     "aliases": ["natgas", "natural gas", "NG=F", "Henry Hub gas", "TTF gas", "Dutch TTF",
                 "JKM LNG", "JKM", "European gas", "Asian LNG"]},
    {"name": "Electricity", "full_name": "Electricity Prices (Manufacturing Input)", "ticker_proxy": None, "category": "energy",
     "aliases": ["power prices", "wholesale electricity", "spot electricity", "PJM power",
                 "ERCOT power", "Nordpool", "EPEX power", "industrial power tariff"]},
    # ── Specialty / contact materials ────────────────────────────────────
    {"name": "Nickel", "full_name": "Nickel (Catalyst / Contact)", "ticker_proxy": None, "category": "non_ferrous_minor",
     "aliases": ["nickel cathode", "LME nickel", "Class 1 nickel", "nickel sulfate",
                 "nickel briquette"]},
    {"name": "Silver", "full_name": "Silver (Contact Materials)", "ticker_proxy": "SI=F", "category": "precious",
     "aliases": ["silver futures", "SI=F", "Comex silver", "London silver", "AgCu contact",
                 "silver tungsten contact"]},
    {"name": "Tin", "full_name": "Tin (Solder)", "ticker_proxy": None, "category": "non_ferrous_minor",
     "aliases": ["LME tin", "tin solder", "Sn solder", "lead-free solder"]},
    {"name": "Rare_Earths", "full_name": "Rare Earth Elements", "ticker_proxy": None, "category": "specialty",
     "aliases": ["NdFeB", "neodymium", "praseodymium", "dysprosium", "rare earth magnets",
                 "China rare earth", "REE", "MP Materials"]},
]

# ─────────────────────────────────────────────────────────────────────────────
# MATERIALS — specific engineered forms used in plants
# ─────────────────────────────────────────────────────────────────────────────

MATERIALS: list[dict] = [
    # Core steel grades
    {"name": "GOES_M3_Grade", "commodity": "GOES", "spec": "0.23mm, B800 ≥ 1.88T"},
    {"name": "GOES_M4_Grade", "commodity": "GOES", "spec": "0.27mm, B800 ≥ 1.85T"},
    {"name": "GOES_M5_Grade", "commodity": "GOES", "spec": "0.30mm, B800 ≥ 1.82T"},
    {"name": "GOES_HiB_Grade", "commodity": "GOES", "spec": "0.23mm Hi-B / 23ZH090"},
    {"name": "GOES_Domain_Refined", "commodity": "GOES", "spec": "Laser-scribed / 27ZDKH85"},
    {"name": "NGOES_Grade50", "commodity": "Silicon_Steel_NGOES", "spec": "M-19 / 0.5mm"},
    {"name": "NGOES_Grade35", "commodity": "Silicon_Steel_NGOES", "spec": "0.35mm semi-processed"},
    {"name": "Amorphous_Core_Strip", "commodity": "Amorphous_Metal", "spec": "Metglas 2605HB1M ribbon"},
    # Copper forms
    {"name": "Cu_Winding_Strip", "commodity": "Copper", "spec": "Continuously Transposed Conductor (CTC)"},
    {"name": "Cu_Bar_Bus", "commodity": "Copper", "spec": "Electrolytic-grade busbar"},
    {"name": "Cu_Round_Wire", "commodity": "Copper", "spec": "Enameled round wire"},
    {"name": "Cu_Flat_Wire", "commodity": "Copper", "spec": "Paper-insulated rectangular"},
    {"name": "Cu_Foil", "commodity": "Copper", "spec": "Foil winding for distribution"},
    # Aluminum forms
    {"name": "Al_Winding_Strip", "commodity": "Aluminum", "spec": "EC-grade strip"},
    {"name": "Al_Bar_Bus", "commodity": "Aluminum", "spec": "1350-H19 busbar"},
    {"name": "Al_Foil", "commodity": "Aluminum", "spec": "Foil winding for distribution"},
    # Fluids
    {"name": "Mineral_Oil_IEC60296", "commodity": "Mineral_Oil", "spec": "IEC 60296 standard"},
    {"name": "Mineral_Oil_Inhibited", "commodity": "Mineral_Oil", "spec": "Inhibited / IEC 60296-T"},
    {"name": "Ester_K_Class", "commodity": "Ester_Fluid", "spec": "K-class fire-safe ester"},
    {"name": "Ester_Synthetic_Midel", "commodity": "Ester_Fluid", "spec": "Midel 7131 synthetic"},
    {"name": "Ester_Natural_FR3", "commodity": "Ester_Fluid", "spec": "FR3 natural ester"},
    # Bushings
    {"name": "Bushing_HV_Porcelain", "commodity": "Porcelain", "spec": "≥ 220 kV porcelain"},
    {"name": "Bushing_HV_Composite", "commodity": "Composite_Bushing_Polymer", "spec": "Silicone composite, ≥ 220 kV"},
    {"name": "Bushing_RIP", "commodity": "Composite_Bushing_Polymer", "spec": "Resin-impregnated paper bushing"},
    {"name": "Bushing_RIS", "commodity": "Composite_Bushing_Polymer", "spec": "Resin-impregnated synthetic bushing"},
    # Cellulosic insulation
    {"name": "Insulation_Pressboard", "commodity": "Pressboard", "spec": "Weidmann calendered pressboard"},
    {"name": "Insulation_Kraft_Paper", "commodity": "Pressboard", "spec": "Standard kraft paper"},
    {"name": "Insulation_Nomex", "commodity": "Pressboard", "spec": "Nomex 410 aramid paper"},
    # Logistics / structural
    {"name": "Heavy_Lift_Cratepack", "commodity": "Lumber_Crating", "spec": "Bespoke per unit"},
    {"name": "Structural_Steel_Tank", "commodity": "Iron_Ore", "spec": "Tank/yoke structural steel"},
    {"name": "Cooling_Radiator_Al", "commodity": "Aluminum", "spec": "Pressed aluminum radiator"},
    {"name": "Tap_Changer_Contacts_AgCu", "commodity": "Silver", "spec": "Ag-Cu contact tips"},
]

# ─────────────────────────────────────────────────────────────────────────────
# COUNTRIES — production origins + key destinations for transformer trade
# ─────────────────────────────────────────────────────────────────────────────

COUNTRIES: list[dict] = [
    # EU
    {"name": "Germany",        "iso2": "DE", "region": "EU"},
    {"name": "Switzerland",    "iso2": "CH", "region": "EU"},
    {"name": "Sweden",         "iso2": "SE", "region": "EU"},
    {"name": "Finland",        "iso2": "FI", "region": "EU"},
    {"name": "Austria",        "iso2": "AT", "region": "EU"},
    {"name": "Poland",         "iso2": "PL", "region": "EU"},
    {"name": "Italy",          "iso2": "IT", "region": "EU"},
    {"name": "France",         "iso2": "FR", "region": "EU"},
    {"name": "Spain",          "iso2": "ES", "region": "EU"},
    {"name": "Netherlands",    "iso2": "NL", "region": "EU"},
    {"name": "Belgium",        "iso2": "BE", "region": "EU"},
    {"name": "Norway",         "iso2": "NO", "region": "EU"},
    {"name": "United Kingdom", "iso2": "GB", "region": "EU"},
    {"name": "Czech Republic", "iso2": "CZ", "region": "EU"},
    {"name": "Romania",        "iso2": "RO", "region": "EU"},
    {"name": "Hungary",        "iso2": "HU", "region": "EU"},
    {"name": "Portugal",       "iso2": "PT", "region": "EU"},
    {"name": "Denmark",        "iso2": "DK", "region": "EU"},
    # APAC
    {"name": "South Korea",    "iso2": "KR", "region": "APAC"},
    {"name": "Japan",          "iso2": "JP", "region": "APAC"},
    {"name": "China",          "iso2": "CN", "region": "APAC"},
    {"name": "India",          "iso2": "IN", "region": "APAC"},
    {"name": "Vietnam",        "iso2": "VN", "region": "APAC"},
    {"name": "Thailand",       "iso2": "TH", "region": "APAC"},
    {"name": "Indonesia",      "iso2": "ID", "region": "APAC"},
    {"name": "Australia",      "iso2": "AU", "region": "APAC"},
    # AMER
    {"name": "United States",  "iso2": "US", "region": "AMER"},
    {"name": "Canada",         "iso2": "CA", "region": "AMER"},
    {"name": "Mexico",         "iso2": "MX", "region": "AMER"},
    # LATAM
    {"name": "Brazil",         "iso2": "BR", "region": "LATAM"},
    {"name": "Argentina",      "iso2": "AR", "region": "LATAM"},
    {"name": "Colombia",       "iso2": "CO", "region": "LATAM"},
    # MENA / Other
    {"name": "Turkey",         "iso2": "TR", "region": "MENA"},
    {"name": "United Arab Emirates", "iso2": "AE", "region": "MENA"},
    {"name": "Saudi Arabia",   "iso2": "SA", "region": "MENA"},
    {"name": "South Africa",   "iso2": "ZA", "region": "AFRICA"},
    {"name": "Russia",         "iso2": "RU", "region": "EUROPE_NON_EU"},
]

# ─────────────────────────────────────────────────────────────────────────────
# SUPPLIERS — tier-1 transformer OEMs + tier-2 GOES mills + sub-component
# specialists + adjacent power-equipment & feedstock players
# ─────────────────────────────────────────────────────────────────────────────

SUPPLIERS: list[dict] = [
    # ═══ TIER-1 LARGE-POWER TRANSFORMER OEMs ═══════════════════════════
    # ── European big-three ───────────────────────────────────────────────
    {"name": "Siemens Energy", "tier": 1, "type": "transformer_oem", "hq_country": "DE", "sec_cik": None,
     "aliases": ["Siemens-Energy", "Siemens Energy AG", "siemens energy", "ENR.DE", "SMNEY"]},
    {"name": "Hitachi Energy", "tier": 1, "type": "transformer_oem", "hq_country": "CH", "sec_cik": None,
     "aliases": ["Hitachi ABB Power Grids", "ABB Power Grids", "Hitachi-ABB", "日立エナジー",
                 "Hitachi Energy Ltd", "Hitachi T&D"]},
    {"name": "GE Vernova", "tier": 1, "type": "transformer_oem", "hq_country": "US", "sec_cik": "1993009",
     "aliases": ["GE Grid Solutions", "General Electric Grid", "GEV", "GE Power", "GE T&D",
                 "GE Renewable Energy"]},
    {"name": "SGB-SMIT", "tier": 1, "type": "transformer_oem", "hq_country": "DE", "sec_cik": None,
     "aliases": ["SGB SMIT", "Starkstrom-Gerätebau", "SMIT Transformatoren", "SGB Group",
                 "SGB Regensburg"]},
    {"name": "Schneider Electric T&D", "tier": 1, "type": "transformer_oem", "hq_country": "FR", "sec_cik": None,
     "aliases": ["Schneider Electric", "Schneider T&D", "Schneider Transformers", "SU.PA",
                 "Schneider Energy Management"]},
    {"name": "Royal SMIT Transformers", "tier": 1, "type": "transformer_oem", "hq_country": "NL", "sec_cik": None,
     "aliases": ["Royal SMIT", "SMIT Nijmegen", "Koninklijke SMIT", "SMIT Transformatoren BV"]},
    {"name": "Wilson Power Solutions", "tier": 1, "type": "transformer_oem", "hq_country": "GB", "sec_cik": None,
     "aliases": ["Wilson Power", "Wilson Transformers", "Wilson Leeds"]},
    {"name": "Brush Group", "tier": 1, "type": "transformer_oem", "hq_country": "GB", "sec_cik": None,
     "aliases": ["Brush Electrical Machines", "Brush Turbogenerators", "Brush Loughborough"]},
    {"name": "Tamini", "tier": 1, "type": "transformer_oem", "hq_country": "IT", "sec_cik": None,
     "aliases": ["Tamini Trasformatori", "Tamini Group", "Terna Tamini"]},
    {"name": "Tesar", "tier": 1, "type": "transformer_oem", "hq_country": "IT", "sec_cik": None,
     "aliases": ["Tesar S.p.A.", "Tesar Trasformatori"]},
    {"name": "Trafomec", "tier": 1, "type": "transformer_oem", "hq_country": "IT", "sec_cik": None,
     "aliases": ["Trafomec S.p.A.", "Trafomec Group"]},
    {"name": "GBE", "tier": 1, "type": "transformer_oem", "hq_country": "IT", "sec_cik": None,
     "aliases": ["Green Building Energy", "GBE Italia", "GBE Power"]},
    {"name": "Imefy", "tier": 1, "type": "transformer_oem", "hq_country": "ES", "sec_cik": None,
     "aliases": ["Imefy Group", "Imefy SA"]},
    {"name": "Ormazabal", "tier": 1, "type": "transformer_oem", "hq_country": "ES", "sec_cik": None,
     "aliases": ["Ormazabal Velatia", "Velatia Group", "Cotradis"]},
    {"name": "Power Machines", "tier": 1, "type": "transformer_oem", "hq_country": "RU", "sec_cik": None,
     "aliases": ["Силовые машины", "Silovye Mashiny", "Power Machines OJSC", "Power Machines SCC"]},
    # ── Asian tier-1 (Korea, Japan, China, India) ────────────────────────
    {"name": "Hyundai Electric", "tier": 1, "type": "transformer_oem", "hq_country": "KR", "sec_cik": None,
     "aliases": ["Hyundai Electric & Energy", "현대일렉트릭", "Hyundai Heavy Industries Electric",
                 "Hyundai Power Transformers USA", "HEES"]},
    {"name": "Hyosung Heavy Industries", "tier": 1, "type": "transformer_oem", "hq_country": "KR", "sec_cik": None,
     "aliases": ["Hyosung", "Hyosung HS", "효성중공업", "효성", "HSHI", "Hyosung HICO",
                 "Hico America", "Hyosung HICO Memphis"]},
    {"name": "LS Electric", "tier": 1, "type": "transformer_oem", "hq_country": "KR", "sec_cik": None,
     "aliases": ["LS Industrial Systems", "LSIS", "LS산전", "LG Industrial Systems"]},
    {"name": "Iljin Electric", "tier": 1, "type": "transformer_oem", "hq_country": "KR", "sec_cik": None,
     "aliases": ["Iljin", "일진전기", "Iljin Group"]},
    {"name": "Mitsubishi Electric", "tier": 1, "type": "transformer_oem", "hq_country": "JP", "sec_cik": None,
     "aliases": ["MELCO", "三菱電機", "Mitsubishi Electric Power Products", "MEPPI"]},
    {"name": "Toshiba Energy Systems", "tier": 1, "type": "transformer_oem", "hq_country": "JP", "sec_cik": None,
     "aliases": ["Toshiba", "東芝", "Toshiba Energy Systems & Solutions", "Toshiba ESS",
                 "Toshiba T&D Systems", "Toshiba International"]},
    {"name": "Fuji Electric", "tier": 1, "type": "transformer_oem", "hq_country": "JP", "sec_cik": None,
     "aliases": ["富士電機", "Fuji Electric Co", "Fuji Electric Power Semiconductor"]},
    {"name": "Daihen", "tier": 1, "type": "transformer_oem", "hq_country": "JP", "sec_cik": None,
     "aliases": ["Daihen Corporation", "ダイヘン"]},
    {"name": "TBEA", "tier": 1, "type": "transformer_oem", "hq_country": "CN", "sec_cik": None,
     "aliases": ["特变电工", "TBEA Co Ltd", "Tebian Electric", "TBEA Shenyang", "Special Transformer Works"]},
    {"name": "CHINT", "tier": 1, "type": "transformer_oem", "hq_country": "CN", "sec_cik": None,
     "aliases": ["正泰", "CHINT Group", "CHINT Electric", "Zhejiang Chint"]},
    {"name": "Pinggao Group", "tier": 1, "type": "transformer_oem", "hq_country": "CN", "sec_cik": None,
     "aliases": ["Pinggao Electric", "平高电气", "Pinggao Hennan"]},
    {"name": "XJ Group", "tier": 1, "type": "transformer_oem", "hq_country": "CN", "sec_cik": None,
     "aliases": ["许继电气", "XJ Electric", "XJ Power", "Xuji Group"]},
    {"name": "Shandong Electrical Engineering", "tier": 1, "type": "transformer_oem", "hq_country": "CN", "sec_cik": None,
     "aliases": ["山东电工", "Shandong Power Equipment", "SDEE"]},
    {"name": "Shenyang Transformer Group", "tier": 1, "type": "transformer_oem", "hq_country": "CN", "sec_cik": None,
     "aliases": ["沈变", "Shenyang Transformer", "STG Group"]},
    {"name": "Wuhan Transformer", "tier": 1, "type": "transformer_oem", "hq_country": "CN", "sec_cik": None,
     "aliases": ["武汉变压器", "Wuhan Power Transformer", "WHTC"]},
    {"name": "WEG", "tier": 1, "type": "transformer_oem", "hq_country": "BR", "sec_cik": None,
     "aliases": ["WEG S.A.", "WEG Industries", "WEG Electric", "WEGE3"]},
    {"name": "Prolec GE", "tier": 1, "type": "transformer_oem", "hq_country": "MX", "sec_cik": None,
     "aliases": ["Prolec-GE", "Prolec Mexico", "Prolec Apodaca", "Prolec Monterrey"]},
    {"name": "CG Power", "tier": 1, "type": "transformer_oem", "hq_country": "IN", "sec_cik": None,
     "aliases": ["CG Power and Industrial Solutions", "Crompton Greaves", "CG Industrial",
                 "Murugappa Group CG"]},
    {"name": "BHEL", "tier": 1, "type": "transformer_oem", "hq_country": "IN", "sec_cik": None,
     "aliases": ["Bharat Heavy Electricals", "Bharat Heavy Electricals Limited", "भेल"]},
    {"name": "Voltamp Transformers", "tier": 1, "type": "transformer_oem", "hq_country": "IN", "sec_cik": None,
     "aliases": ["Voltamp", "Voltamp Vadodara"]},
    {"name": "Transformers and Rectifiers India", "tier": 1, "type": "transformer_oem", "hq_country": "IN", "sec_cik": None,
     "aliases": ["TRIL", "TRIL India", "T&R India"]},
    {"name": "Vijai Electricals", "tier": 1, "type": "transformer_oem", "hq_country": "IN", "sec_cik": None,
     "aliases": ["Vijai", "Vijai Electric Hyderabad"]},
    {"name": "Indo Tech Transformers", "tier": 1, "type": "transformer_oem", "hq_country": "IN", "sec_cik": None,
     "aliases": ["Indo-Tech Transformers", "Indo Tech Chennai"]},
    {"name": "BEST Transformer", "tier": 1, "type": "transformer_oem", "hq_country": "TR", "sec_cik": None,
     "aliases": ["BEST Trafo", "Balikesir Elektromekanik", "BEST AS"]},
    {"name": "ABB India", "tier": 1, "type": "transformer_oem", "hq_country": "IN", "sec_cik": None,
     "aliases": ["ABB Limited India", "ABB Ltd India", "ABB Power India"]},
    # ── US tier-1 + adjacent ─────────────────────────────────────────────
    {"name": "Eaton", "tier": 1, "type": "power_equipment_adjacent", "hq_country": "US", "sec_cik": "31277",
     "aliases": ["Eaton Corporation", "Eaton Electrical", "Eaton Waukesha", "ETN"]},
    {"name": "Hubbell", "tier": 1, "type": "power_equipment_adjacent", "hq_country": "US", "sec_cik": "48898",
     "aliases": ["Hubbell Incorporated", "Hubbell Power Systems", "HUBB"]},
    {"name": "Pennsylvania Transformer Tech", "tier": 1, "type": "transformer_oem", "hq_country": "US", "sec_cik": None,
     "aliases": ["PTTI", "PA Transformer", "Penn Transformer", "Pennsylvania Transformer Canonsburg"]},
    {"name": "Virginia Transformer", "tier": 1, "type": "transformer_oem", "hq_country": "US", "sec_cik": None,
     "aliases": ["VTC", "Virginia Transformer Corp", "Roanoke transformer"]},
    {"name": "Howard Industries", "tier": 1, "type": "transformer_oem", "hq_country": "US", "sec_cik": None,
     "aliases": ["Howard", "Howard Power Solutions", "Howard Laurel"]},
    {"name": "ERMCO", "tier": 1, "type": "transformer_oem", "hq_country": "US", "sec_cik": None,
     "aliases": ["Electric Research and Manufacturing", "ERMCO Dyersburg"]},
    {"name": "Maddox Industrial Transformer", "tier": 1, "type": "transformer_oem", "hq_country": "US", "sec_cik": None,
     "aliases": ["Maddox Transformer", "Maddox South Bend", "Maddox Idaho"]},
    {"name": "Niagara Transformer", "tier": 1, "type": "transformer_oem", "hq_country": "US", "sec_cik": None,
     "aliases": ["Niagara Buffalo", "Niagara Transformer Corp"]},
    {"name": "SPX Transformer Solutions", "tier": 1, "type": "transformer_oem", "hq_country": "US", "sec_cik": None,
     "aliases": ["SPX Transformer", "SPX Waukesha", "Waukesha Electric Systems", "SPX Technologies"]},
    {"name": "Delta Star", "tier": 1, "type": "transformer_oem", "hq_country": "US", "sec_cik": None,
     "aliases": ["Delta Star Inc", "Delta Star Lynchburg", "Delta Star San Carlos"]},
    {"name": "Federal Pacific", "tier": 1, "type": "transformer_oem", "hq_country": "US", "sec_cik": None,
     "aliases": ["FedPac", "Federal Pacific Transformer", "Federal Pacific Bristol"]},
    {"name": "Pacific Crest Transformers", "tier": 1, "type": "transformer_oem", "hq_country": "US", "sec_cik": None,
     "aliases": ["Pacific Crest", "PCT Medford"]},

    # ═══ TIER-2 GOES MILLS (the binding constraint of the industry) ═════
    {"name": "Nippon Steel", "tier": 2, "type": "goes_mill", "hq_country": "JP", "sec_cik": None,
     "aliases": ["NSSMC", "Nippon Steel Corporation", "新日鐵住金", "NSC", "Nippon Steel & Sumitomo Metal",
                 "Nippon Steel Engineering"]},
    {"name": "JFE Steel", "tier": 2, "type": "goes_mill", "hq_country": "JP", "sec_cik": None,
     "aliases": ["JFE", "Kawasaki Steel", "NKK", "Japan Fe Steel", "JFEスチール", "JFE Holdings"]},
    {"name": "POSCO", "tier": 2, "type": "goes_mill", "hq_country": "KR", "sec_cik": None,
     "aliases": ["POSCO Holdings", "포스코", "Pohang Iron and Steel", "POSCO International",
                 "POSCO Future M"]},
    {"name": "Baosteel", "tier": 2, "type": "goes_mill", "hq_country": "CN", "sec_cik": None,
     "aliases": ["Baoshan Iron & Steel", "China Baowu", "宝钢", "Baowu Steel", "Bao Steel",
                 "Baowu Group"]},
    {"name": "WISCO", "tier": 2, "type": "goes_mill", "hq_country": "CN", "sec_cik": None,
     "aliases": ["Wuhan Iron and Steel", "武钢", "Wuhan Steel"]},
    {"name": "TISCO", "tier": 2, "type": "goes_mill", "hq_country": "CN", "sec_cik": None,
     "aliases": ["Taiyuan Iron and Steel", "太原钢铁", "Taigang"]},
    {"name": "Stalprodukt", "tier": 2, "type": "goes_mill", "hq_country": "PL", "sec_cik": None,
     "aliases": ["Stalprodukt Bochnia", "SPE", "Stalprodukt S.A."]},
    {"name": "Cleveland-Cliffs", "tier": 2, "type": "goes_mill", "hq_country": "US", "sec_cik": "764065",
     "aliases": ["Cliffs", "AK Steel", "Cleveland Cliffs", "CLF", "Cliffs Natural Resources"]},
    {"name": "Big River Steel", "tier": 2, "type": "goes_mill", "hq_country": "US", "sec_cik": None,
     "aliases": ["Big River Steel Works", "BRS Osceola", "US Steel Arkansas"]},
    {"name": "ThyssenKrupp Electrical Steel", "tier": 2, "type": "goes_mill", "hq_country": "DE", "sec_cik": None,
     "aliases": ["ThyssenKrupp", "TKES", "TK Electrical Steel", "TKSE", "ThyssenKrupp Steel Europe",
                 "TK Bochum"]},
    {"name": "Aperam", "tier": 2, "type": "goes_mill", "hq_country": "FR", "sec_cik": None,
     "aliases": ["Aperam Imphy", "Aperam Stainless", "ArcelorMittal Stainless"]},
    {"name": "NLMK", "tier": 2, "type": "goes_mill", "hq_country": "RU", "sec_cik": None,
     "aliases": ["Novolipetsk Steel", "НЛМК", "NLMK Lipetsk", "NLMK Group"]},
    {"name": "Severstal", "tier": 2, "type": "goes_mill", "hq_country": "RU", "sec_cik": None,
     "aliases": ["Северсталь", "Severstal Cherepovets", "PAO Severstal"]},
    {"name": "Erdemir", "tier": 2, "type": "goes_mill", "hq_country": "TR", "sec_cik": None,
     "aliases": ["Eregli Iron and Steel", "ERDEMIR", "OYAK Erdemir", "Eregli Demir"]},
    {"name": "Tata Steel BSL", "tier": 2, "type": "goes_mill", "hq_country": "IN", "sec_cik": None,
     "aliases": ["Tata Steel", "Bhushan Steel", "Tata Steel Long Products"]},

    # ═══ TIER-2 SUB-COMPONENTS ══════════════════════════════════════════
    # ── Tap changers (oligopoly: Reinhausen + Hitachi) ──────────────────
    {"name": "Reinhausen", "tier": 2, "type": "tap_changer_oltc", "hq_country": "DE", "sec_cik": None,
     "aliases": ["MR Reinhausen", "Maschinenfabrik Reinhausen", "MR Group", "Reinhausen Regensburg"]},
    {"name": "Huaming Power Equipment", "tier": 2, "type": "tap_changer_oltc", "hq_country": "CN", "sec_cik": None,
     "aliases": ["华明电力", "Huaming Tap Changer", "Huaming Shanghai"]},
    # ── Bushings ─────────────────────────────────────────────────────────
    {"name": "ABB Bushings", "tier": 2, "type": "bushings", "hq_country": "SE", "sec_cik": None,
     "aliases": ["ABB High Voltage Cables", "ABB Components", "Hitachi Energy Bushings"]},
    {"name": "Trench Group", "tier": 2, "type": "bushings", "hq_country": "DE", "sec_cik": None,
     "aliases": ["Trench Bushings", "Trench Italia", "Trench Limited", "Trench Austria",
                 "Trench France", "Trench Bayreuth"]},
    {"name": "Pfisterer", "tier": 2, "type": "bushings", "hq_country": "DE", "sec_cik": None,
     "aliases": ["Pfisterer Holding", "Pfisterer SEFAG", "Pfisterer Connectors"]},
    {"name": "Yangzhou Saiyi", "tier": 2, "type": "bushings", "hq_country": "CN", "sec_cik": None,
     "aliases": ["Saiyi Electric", "扬州赛义"]},
    {"name": "Modern Insulators", "tier": 2, "type": "bushings", "hq_country": "IN", "sec_cik": None,
     "aliases": ["Modern Insulators Ltd"]},
    {"name": "Bharat Bijlee", "tier": 2, "type": "bushings", "hq_country": "IN", "sec_cik": None,
     "aliases": ["Bharat Bijlee Ltd", "BBL Mumbai"]},
    # ── Insulation (pressboard / paper) ──────────────────────────────────
    {"name": "Weidmann Electrical Technology", "tier": 2, "type": "insulation", "hq_country": "CH", "sec_cik": None,
     "aliases": ["Weidmann", "Weidmann Rapperswil", "WICOR", "Wicor Holding"]},
    {"name": "Krempel Group", "tier": 2, "type": "insulation", "hq_country": "DE", "sec_cik": None,
     "aliases": ["Krempel", "Krempel Vaihingen", "August Krempel Söhne"]},
    {"name": "Felten Guilleaume", "tier": 2, "type": "insulation", "hq_country": "DE", "sec_cik": None,
     "aliases": ["Felten & Guilleaume", "F&G Electric", "F+G"]},
    {"name": "DuPont Nomex", "tier": 2, "type": "insulation", "hq_country": "US", "sec_cik": "1666700",
     "aliases": ["DuPont", "Nomex", "DD", "DuPont de Nemours", "Nomex paper"]},
    # ── Winding wire ─────────────────────────────────────────────────────
    {"name": "Essex Furukawa Magnet Wire", "tier": 2, "type": "winding_wire", "hq_country": "US", "sec_cik": None,
     "aliases": ["Essex Furukawa", "Essex Magnet Wire", "Furukawa Electric Magnet", "EFMW"]},
    {"name": "Superior Essex", "tier": 2, "type": "winding_wire", "hq_country": "US", "sec_cik": None,
     "aliases": ["Superior Essex Communications", "Essex Group"]},
    {"name": "Elektrisola", "tier": 2, "type": "winding_wire", "hq_country": "DE", "sec_cik": None,
     "aliases": ["Elektrisola GmbH", "Elektrisola Reichshof"]},
    # ── Cable (HV cable, often bundled with transformer projects) ────────
    {"name": "Prysmian", "tier": 2, "type": "hv_cable", "hq_country": "IT", "sec_cik": None,
     "aliases": ["Prysmian Group", "Pirelli Cavi", "Prysmian Cables", "PRY"]},
    {"name": "Nexans", "tier": 2, "type": "hv_cable", "hq_country": "FR", "sec_cik": None,
     "aliases": ["Nexans SA", "Nexans HV", "NEX.PA", "Nexans Lyon"]},
    {"name": "NKT", "tier": 2, "type": "hv_cable", "hq_country": "DK", "sec_cik": None,
     "aliases": ["NKT Cables", "NKT A/S", "NKT Karlskrona"]},
    {"name": "LS Cable", "tier": 2, "type": "hv_cable", "hq_country": "KR", "sec_cik": None,
     "aliases": ["LS Cable & System", "LS C&S", "엘에스전선"]},
    {"name": "Sumitomo Electric", "tier": 2, "type": "hv_cable", "hq_country": "JP", "sec_cik": None,
     "aliases": ["Sumitomo Electric Industries", "住友電気工業", "SEI", "Sumitomo Cable"]},
    # ── Switchgear / GIS (frequently bundled with transformer orders) ────
    {"name": "Hitachi Energy GIS", "tier": 2, "type": "switchgear", "hq_country": "CH", "sec_cik": None,
     "aliases": ["Hitachi GIS", "Hitachi Energy switchgear", "ABB GIS legacy"]},
    {"name": "Siemens Energy GIS", "tier": 2, "type": "switchgear", "hq_country": "DE", "sec_cik": None,
     "aliases": ["Siemens GIS", "Siemens 8DN8", "Siemens switchgear"]},
    {"name": "Mitsubishi Electric Power Products", "tier": 2, "type": "switchgear", "hq_country": "US", "sec_cik": None,
     "aliases": ["MEPPI", "Mitsubishi Power Products", "Mitsubishi Electric Warrendale"]},
    # ── Feedstock / raw-material giants (upstream of GOES mills) ─────────
    {"name": "Vale", "tier": 3, "type": "iron_ore_miner", "hq_country": "BR", "sec_cik": "917851",
     "aliases": ["Vale SA", "Companhia Vale do Rio Doce", "VALE", "Carajas mine"]},
    {"name": "BHP", "tier": 3, "type": "iron_ore_miner", "hq_country": "AU", "sec_cik": "811809",
     "aliases": ["BHP Group", "BHP Billiton", "BHP Iron Ore", "Pilbara operations"]},
    {"name": "Rio Tinto", "tier": 3, "type": "iron_ore_miner", "hq_country": "AU", "sec_cik": "863064",
     "aliases": ["Rio Tinto Group", "RIO", "Rio Tinto Iron Ore", "Pilbara Rio"]},
    {"name": "Fortescue Metals", "tier": 3, "type": "iron_ore_miner", "hq_country": "AU", "sec_cik": None,
     "aliases": ["Fortescue", "FMG", "Fortescue Metals Group"]},
    # ── Insulation oil refiners ──────────────────────────────────────────
    {"name": "Nynas", "tier": 2, "type": "transformer_oil", "hq_country": "SE", "sec_cik": None,
     "aliases": ["Nynas AB", "Nytro", "Nynas Naphthenics", "Nynas Nynäshamn"]},
    {"name": "Ergon", "tier": 2, "type": "transformer_oil", "hq_country": "US", "sec_cik": None,
     "aliases": ["Ergon Inc", "Ergon Refining", "Ergon Vicksburg"]},
    {"name": "Apar Industries", "tier": 2, "type": "transformer_oil", "hq_country": "IN", "sec_cik": None,
     "aliases": ["APAR", "Apar Mumbai", "Apar Oil"]},
    # ── Ester fluid specialists ──────────────────────────────────────────
    {"name": "Cargill BIOTEMP", "tier": 2, "type": "ester_fluid", "hq_country": "US", "sec_cik": None,
     "aliases": ["Cargill", "Envirotemp FR3", "FR3 dielectric", "Cargill Industrial"]},
    {"name": "MIDEL", "tier": 2, "type": "ester_fluid", "hq_country": "GB", "sec_cik": None,
     "aliases": ["Midel 7131", "Midel eN", "MIDEL ester", "M&I Materials"]},
]

# ─────────────────────────────────────────────────────────────────────────────
# PLANTS — named factory sites for the major suppliers above
# ─────────────────────────────────────────────────────────────────────────────

PLANTS: list[dict] = [
    # ── Siemens Energy ───────────────────────────────────────────────────
    {"name": "Siemens Nuremberg",      "operator": "Siemens Energy", "country": "DE", "lat": 49.45, "lon": 11.08, "specialty": "large_power"},
    {"name": "Siemens Weiz",           "operator": "Siemens Energy", "country": "AT", "lat": 47.22, "lon": 15.62, "specialty": "large_power"},
    {"name": "Siemens Linz",           "operator": "Siemens Energy", "country": "AT", "lat": 48.31, "lon": 14.29, "specialty": "distribution"},
    {"name": "Siemens Charlotte",      "operator": "Siemens Energy", "country": "US", "lat": 35.23, "lon": -80.84, "specialty": "large_power"},
    {"name": "Siemens Cordoba",        "operator": "Siemens Energy", "country": "ES", "lat": 37.89, "lon":  -4.78, "specialty": "large_power"},
    {"name": "Siemens Drammen",        "operator": "Siemens Energy", "country": "NO", "lat": 59.74, "lon":  10.20, "specialty": "large_power"},
    {"name": "Siemens Mumbai",         "operator": "Siemens Energy", "country": "IN", "lat": 19.08, "lon":  72.88, "specialty": "large_power"},
    {"name": "Siemens Goa",            "operator": "Siemens Energy", "country": "IN", "lat": 15.50, "lon":  73.83, "specialty": "distribution"},
    {"name": "Siemens Krzewina",       "operator": "Siemens Energy", "country": "PL", "lat": 51.10, "lon":  17.05, "specialty": "distribution"},
    {"name": "Siemens Belo Horizonte", "operator": "Siemens Energy", "country": "BR", "lat":-19.92, "lon": -43.94, "specialty": "large_power"},
    {"name": "Siemens Wendell",        "operator": "Siemens Energy", "country": "US", "lat": 35.78, "lon": -78.37, "specialty": "large_power"},
    # ── Hitachi Energy ───────────────────────────────────────────────────
    {"name": "Hitachi Bad Honnef",     "operator": "Hitachi Energy", "country": "DE", "lat": 50.65, "lon":   7.22, "specialty": "large_power"},
    {"name": "Hitachi Ludvika",        "operator": "Hitachi Energy", "country": "SE", "lat": 60.15, "lon":  15.18, "specialty": "hvdc"},
    {"name": "Hitachi Vaasa",          "operator": "Hitachi Energy", "country": "FI", "lat": 63.10, "lon":  21.62, "specialty": "large_power"},
    {"name": "Hitachi South Boston",   "operator": "Hitachi Energy", "country": "US", "lat": 36.70, "lon": -78.90, "specialty": "large_power"},
    {"name": "Hitachi Cordoba",        "operator": "Hitachi Energy", "country": "ES", "lat": 37.89, "lon":  -4.78, "specialty": "large_power"},
    {"name": "Hitachi Mont Royal",     "operator": "Hitachi Energy", "country": "CA", "lat": 45.52, "lon": -73.65, "specialty": "large_power"},
    {"name": "Hitachi Pinetops",       "operator": "Hitachi Energy", "country": "US", "lat": 35.79, "lon": -77.64, "specialty": "distribution"},
    {"name": "Hitachi Pinhao",         "operator": "Hitachi Energy", "country": "BR", "lat":-25.20, "lon": -49.18, "specialty": "large_power"},
    {"name": "Hitachi Vadodara",       "operator": "Hitachi Energy", "country": "IN", "lat": 22.31, "lon":  73.18, "specialty": "large_power"},
    {"name": "Hitachi Helsinki",       "operator": "Hitachi Energy", "country": "FI", "lat": 60.17, "lon":  24.94, "specialty": "distribution"},
    {"name": "Hitachi Lodz",           "operator": "Hitachi Energy", "country": "PL", "lat": 51.76, "lon":  19.46, "specialty": "distribution"},
    {"name": "Hitachi Jefferson City", "operator": "Hitachi Energy", "country": "US", "lat": 38.58, "lon": -92.17, "specialty": "large_power"},
    {"name": "Hitachi Crystal Springs","operator": "Hitachi Energy", "country": "US", "lat": 31.99, "lon": -90.36, "specialty": "distribution"},
    # ── GE Vernova ───────────────────────────────────────────────────────
    {"name": "GE Vernova Pittsburgh",  "operator": "GE Vernova", "country": "US", "lat": 40.44, "lon": -79.99, "specialty": "large_power"},
    {"name": "GE Vernova Memphis",     "operator": "GE Vernova", "country": "US", "lat": 35.15, "lon": -90.05, "specialty": "large_power"},
    {"name": "GE Vernova Charleroi",   "operator": "GE Vernova", "country": "US", "lat": 40.14, "lon": -79.90, "specialty": "large_power"},
    {"name": "GE Vernova Stafford",    "operator": "GE Vernova", "country": "GB", "lat": 52.81, "lon":  -2.12, "specialty": "large_power"},
    {"name": "GE Vernova Villeurbanne","operator": "GE Vernova", "country": "FR", "lat": 45.77, "lon":   4.88, "specialty": "hvdc"},
    {"name": "GE Vernova Mohammedia",  "operator": "GE Vernova", "country": "MX", "lat": 19.43, "lon": -99.13, "specialty": "distribution"},
    # ── Prolec GE (Mexico) ───────────────────────────────────────────────
    {"name": "Prolec Apodaca",         "operator": "Prolec GE", "country": "MX", "lat": 25.78, "lon": -100.19, "specialty": "large_power"},
    {"name": "Prolec Monterrey",       "operator": "Prolec GE", "country": "MX", "lat": 25.67, "lon": -100.31, "specialty": "distribution"},
    {"name": "Prolec Shreveport",      "operator": "Prolec GE", "country": "US", "lat": 32.52, "lon":  -93.75, "specialty": "distribution"},
    # ── SGB-SMIT ─────────────────────────────────────────────────────────
    {"name": "SGB Regensburg",         "operator": "SGB-SMIT", "country": "DE", "lat": 49.01, "lon":  12.10, "specialty": "large_power"},
    {"name": "SGB Neumark",            "operator": "SGB-SMIT", "country": "DE", "lat": 50.66, "lon":  12.34, "specialty": "distribution"},
    {"name": "SGB Nijmegen",           "operator": "SGB-SMIT", "country": "NL", "lat": 51.81, "lon":   5.84, "specialty": "large_power"},
    {"name": "SGB Lugoj",              "operator": "SGB-SMIT", "country": "RO", "lat": 45.69, "lon":  21.90, "specialty": "distribution"},
    {"name": "SGB Louisville",         "operator": "SGB-SMIT", "country": "US", "lat": 38.25, "lon":  -85.76, "specialty": "large_power"},
    # ── Schneider Electric T&D ───────────────────────────────────────────
    {"name": "Schneider Grenoble",     "operator": "Schneider Electric T&D", "country": "FR", "lat": 45.19, "lon":   5.72, "specialty": "distribution"},
    {"name": "Schneider Saint Louis",  "operator": "Schneider Electric T&D", "country": "FR", "lat": 47.59, "lon":   7.56, "specialty": "distribution"},
    {"name": "Schneider Smyrna",       "operator": "Schneider Electric T&D", "country": "US", "lat": 35.98, "lon":  -86.52, "specialty": "distribution"},
    {"name": "Schneider Suzhou",       "operator": "Schneider Electric T&D", "country": "CN", "lat": 31.30, "lon": 120.59, "specialty": "distribution"},
    # ── Royal SMIT / Wilson / Brush / Tamini / Tesar / Trafomec / GBE ────
    {"name": "Royal SMIT Nijmegen",    "operator": "Royal SMIT Transformers", "country": "NL", "lat": 51.81, "lon":   5.84, "specialty": "large_power"},
    {"name": "Wilson Power Leeds",     "operator": "Wilson Power Solutions", "country": "GB", "lat": 53.80, "lon":  -1.55, "specialty": "distribution"},
    {"name": "Brush Loughborough",     "operator": "Brush Group", "country": "GB", "lat": 52.77, "lon":  -1.21, "specialty": "large_power"},
    {"name": "Tamini Legnano",         "operator": "Tamini", "country": "IT", "lat": 45.59, "lon":   8.92, "specialty": "large_power"},
    {"name": "Tamini Melegnano",       "operator": "Tamini", "country": "IT", "lat": 45.36, "lon":   9.32, "specialty": "large_power"},
    {"name": "Tesar Colle Umberto",    "operator": "Tesar", "country": "IT", "lat": 45.94, "lon":  12.40, "specialty": "large_power"},
    {"name": "Trafomec Tavernelle",    "operator": "Trafomec", "country": "IT", "lat": 43.00, "lon":  12.16, "specialty": "distribution"},
    {"name": "GBE Padova",             "operator": "GBE", "country": "IT", "lat": 45.41, "lon":  11.88, "specialty": "distribution"},
    # ── Imefy / Ormazabal / Power Machines ───────────────────────────────
    {"name": "Imefy Yecla",            "operator": "Imefy", "country": "ES", "lat": 38.61, "lon":  -1.11, "specialty": "distribution"},
    {"name": "Ormazabal Bilbao",       "operator": "Ormazabal", "country": "ES", "lat": 43.26, "lon":  -2.93, "specialty": "distribution"},
    {"name": "Ormazabal Cordoba",      "operator": "Ormazabal", "country": "ES", "lat": 37.89, "lon":  -4.78, "specialty": "distribution"},
    {"name": "Power Machines SPb",     "operator": "Power Machines", "country": "RU", "lat": 59.94, "lon":  30.31, "specialty": "large_power"},
    # ── Hyundai Electric ─────────────────────────────────────────────────
    {"name": "Hyundai Ulsan",          "operator": "Hyundai Electric", "country": "KR", "lat": 35.55, "lon": 129.32, "specialty": "large_power"},
    {"name": "Hyundai Alabama",        "operator": "Hyundai Electric", "country": "US", "lat": 33.41, "lon":  -86.61, "specialty": "large_power"},
    {"name": "Hyundai Sofia",          "operator": "Hyundai Electric", "country": "RO", "lat": 42.70, "lon":  23.32, "specialty": "distribution"},
    # ── Hyosung Heavy Industries ─────────────────────────────────────────
    {"name": "Hyosung Changwon",       "operator": "Hyosung Heavy Industries", "country": "KR", "lat": 35.23, "lon": 128.68, "specialty": "ultra_high_voltage"},
    {"name": "Hyosung Yangsan",        "operator": "Hyosung Heavy Industries", "country": "KR", "lat": 35.34, "lon": 129.04, "specialty": "distribution"},
    {"name": "Hyosung HICO Memphis",   "operator": "Hyosung Heavy Industries", "country": "US", "lat": 35.15, "lon":  -90.05, "specialty": "large_power"},
    # ── LS Electric / Iljin ──────────────────────────────────────────────
    {"name": "LS Electric Cheongju",   "operator": "LS Electric", "country": "KR", "lat": 36.64, "lon": 127.49, "specialty": "distribution"},
    {"name": "LS Electric Busan",      "operator": "LS Electric", "country": "KR", "lat": 35.10, "lon": 129.04, "specialty": "distribution"},
    {"name": "Iljin Hwaseong",         "operator": "Iljin Electric", "country": "KR", "lat": 37.21, "lon": 126.83, "specialty": "distribution"},
    # ── Mitsubishi Electric / Toshiba / Fuji / Daihen ────────────────────
    {"name": "Mitsubishi Ako",         "operator": "Mitsubishi Electric", "country": "JP", "lat": 34.74, "lon": 134.39, "specialty": "large_power"},
    {"name": "Mitsubishi Kobe",        "operator": "Mitsubishi Electric", "country": "JP", "lat": 34.69, "lon": 135.20, "specialty": "distribution"},
    {"name": "Mitsubishi Warrendale",  "operator": "Mitsubishi Electric", "country": "US", "lat": 40.63, "lon": -80.04, "specialty": "switchgear"},
    {"name": "Toshiba Hamakawasaki",   "operator": "Toshiba Energy Systems", "country": "JP", "lat": 35.53, "lon": 139.71, "specialty": "large_power"},
    {"name": "Toshiba Mie",            "operator": "Toshiba Energy Systems", "country": "JP", "lat": 34.49, "lon": 136.71, "specialty": "large_power"},
    {"name": "Toshiba Houston",        "operator": "Toshiba Energy Systems", "country": "US", "lat": 29.76, "lon":  -95.37, "specialty": "large_power"},
    {"name": "Fuji Electric Tokyo",    "operator": "Fuji Electric", "country": "JP", "lat": 35.68, "lon": 139.69, "specialty": "distribution"},
    {"name": "Daihen Osaka",           "operator": "Daihen", "country": "JP", "lat": 34.69, "lon": 135.50, "specialty": "distribution"},
    # ── Chinese OEMs ─────────────────────────────────────────────────────
    {"name": "TBEA Shenyang",          "operator": "TBEA", "country": "CN", "lat": 41.81, "lon": 123.43, "specialty": "ultra_high_voltage"},
    {"name": "TBEA Hengyang",          "operator": "TBEA", "country": "CN", "lat": 26.89, "lon": 112.57, "specialty": "large_power"},
    {"name": "TBEA Tianjin",           "operator": "TBEA", "country": "CN", "lat": 39.13, "lon": 117.20, "specialty": "large_power"},
    {"name": "TBEA Shandong",          "operator": "TBEA", "country": "CN", "lat": 36.65, "lon": 117.02, "specialty": "distribution"},
    {"name": "CHINT Hangzhou",         "operator": "CHINT", "country": "CN", "lat": 30.27, "lon": 120.15, "specialty": "distribution"},
    {"name": "CHINT Wenzhou",          "operator": "CHINT", "country": "CN", "lat": 27.99, "lon": 120.69, "specialty": "distribution"},
    {"name": "Pinggao Pingdingshan",   "operator": "Pinggao Group", "country": "CN", "lat": 33.74, "lon": 113.30, "specialty": "switchgear"},
    {"name": "XJ Xuchang",             "operator": "XJ Group", "country": "CN", "lat": 34.04, "lon": 113.85, "specialty": "switchgear"},
    {"name": "Shandong Jinan",         "operator": "Shandong Electrical Engineering", "country": "CN", "lat": 36.65, "lon": 117.02, "specialty": "distribution"},
    {"name": "Shenyang Transformer",   "operator": "Shenyang Transformer Group", "country": "CN", "lat": 41.81, "lon": 123.43, "specialty": "large_power"},
    {"name": "Wuhan Transformer Plant","operator": "Wuhan Transformer", "country": "CN", "lat": 30.59, "lon": 114.31, "specialty": "large_power"},
    # ── WEG / BR / Latam ─────────────────────────────────────────────────
    {"name": "WEG Blumenau",           "operator": "WEG", "country": "BR", "lat":-26.91, "lon": -49.07, "specialty": "large_power"},
    {"name": "WEG Manaus",             "operator": "WEG", "country": "BR", "lat": -3.12, "lon": -60.02, "specialty": "distribution"},
    {"name": "WEG Sao Paulo",          "operator": "WEG", "country": "BR", "lat":-23.55, "lon": -46.63, "specialty": "distribution"},
    # ── Indian OEMs ──────────────────────────────────────────────────────
    {"name": "CG Power Bhopal",        "operator": "CG Power", "country": "IN", "lat": 23.26, "lon":  77.41, "specialty": "large_power"},
    {"name": "CG Power Nashik",        "operator": "CG Power", "country": "IN", "lat": 19.99, "lon":  73.79, "specialty": "distribution"},
    {"name": "BHEL Bhopal",            "operator": "BHEL", "country": "IN", "lat": 23.26, "lon":  77.41, "specialty": "large_power"},
    {"name": "BHEL Jhansi",            "operator": "BHEL", "country": "IN", "lat": 25.45, "lon":  78.57, "specialty": "distribution"},
    {"name": "BHEL Hardwar",           "operator": "BHEL", "country": "IN", "lat": 29.96, "lon":  78.16, "specialty": "ultra_high_voltage"},
    {"name": "Voltamp Vadodara",       "operator": "Voltamp Transformers", "country": "IN", "lat": 22.31, "lon":  73.18, "specialty": "distribution"},
    {"name": "TRIL Moraiya",           "operator": "Transformers and Rectifiers India", "country": "IN", "lat": 22.93, "lon":  72.45, "specialty": "distribution"},
    {"name": "Vijai Hyderabad",        "operator": "Vijai Electricals", "country": "IN", "lat": 17.39, "lon":  78.49, "specialty": "distribution"},
    {"name": "Indo Tech Chennai",      "operator": "Indo Tech Transformers", "country": "IN", "lat": 13.08, "lon":  80.27, "specialty": "distribution"},
    {"name": "ABB Vadodara",           "operator": "ABB India", "country": "IN", "lat": 22.31, "lon":  73.18, "specialty": "large_power"},
    # ── Turkey ───────────────────────────────────────────────────────────
    {"name": "BEST Trafo Sakarya",     "operator": "BEST Transformer", "country": "TR", "lat": 40.78, "lon":  30.40, "specialty": "large_power"},
    {"name": "BEST Trafo Balikesir",   "operator": "BEST Transformer", "country": "TR", "lat": 39.65, "lon":  27.89, "specialty": "distribution"},
    # ── US adjacent + tier-1 ─────────────────────────────────────────────
    {"name": "Eaton Waukesha",         "operator": "Eaton", "country": "US", "lat": 43.01, "lon":  -88.23, "specialty": "distribution"},
    {"name": "Eaton Nacogdoches",      "operator": "Eaton", "country": "US", "lat": 31.60, "lon":  -94.66, "specialty": "distribution"},
    {"name": "Hubbell Centralia",      "operator": "Hubbell", "country": "US", "lat": 38.52, "lon":  -89.13, "specialty": "distribution"},
    {"name": "Hubbell Aiken",          "operator": "Hubbell", "country": "US", "lat": 33.56, "lon":  -81.72, "specialty": "distribution"},
    {"name": "PTTI Canonsburg",        "operator": "Pennsylvania Transformer Tech", "country": "US", "lat": 40.26, "lon":  -80.19, "specialty": "large_power"},
    {"name": "Virginia Transformer Roanoke", "operator": "Virginia Transformer", "country": "US", "lat": 37.27, "lon": -79.94, "specialty": "large_power"},
    {"name": "Howard Laurel",          "operator": "Howard Industries", "country": "US", "lat": 31.69, "lon":  -89.13, "specialty": "distribution"},
    {"name": "ERMCO Dyersburg",        "operator": "ERMCO", "country": "US", "lat": 36.03, "lon":  -89.39, "specialty": "distribution"},
    {"name": "Maddox South Bend",      "operator": "Maddox Industrial Transformer", "country": "US", "lat": 41.68, "lon":  -86.25, "specialty": "distribution"},
    {"name": "Maddox Idaho Falls",     "operator": "Maddox Industrial Transformer", "country": "US", "lat": 43.49, "lon": -112.04, "specialty": "distribution"},
    {"name": "Niagara Buffalo",        "operator": "Niagara Transformer", "country": "US", "lat": 42.89, "lon":  -78.88, "specialty": "distribution"},
    {"name": "SPX Waukesha",           "operator": "SPX Transformer Solutions", "country": "US", "lat": 43.01, "lon":  -88.23, "specialty": "large_power"},
    {"name": "Delta Star Lynchburg",   "operator": "Delta Star", "country": "US", "lat": 37.41, "lon":  -79.14, "specialty": "large_power"},
    {"name": "Delta Star San Carlos",  "operator": "Delta Star", "country": "US", "lat": 37.51, "lon": -122.26, "specialty": "mobile_substation"},
    {"name": "Federal Pacific Bristol","operator": "Federal Pacific", "country": "US", "lat": 36.59, "lon":  -82.16, "specialty": "distribution"},
    {"name": "Pacific Crest Medford",  "operator": "Pacific Crest Transformers", "country": "US", "lat": 42.33, "lon": -122.87, "specialty": "distribution"},

    # ═══ GOES MILLS ═════════════════════════════════════════════════════
    {"name": "Nippon Steel Hirohata",      "operator": "Nippon Steel", "country": "JP", "lat": 34.79, "lon": 134.65, "specialty": "goes_mill"},
    {"name": "Nippon Steel Kashima",       "operator": "Nippon Steel", "country": "JP", "lat": 35.92, "lon": 140.71, "specialty": "goes_mill"},
    {"name": "Nippon Steel Yawata",        "operator": "Nippon Steel", "country": "JP", "lat": 33.86, "lon": 130.81, "specialty": "goes_mill"},
    {"name": "JFE Kurashiki",              "operator": "JFE Steel", "country": "JP", "lat": 34.59, "lon": 133.77, "specialty": "goes_mill"},
    {"name": "JFE Chiba",                  "operator": "JFE Steel", "country": "JP", "lat": 35.61, "lon": 140.10, "specialty": "goes_mill"},
    {"name": "JFE Fukuyama",               "operator": "JFE Steel", "country": "JP", "lat": 34.49, "lon": 133.36, "specialty": "goes_mill"},
    {"name": "POSCO Pohang",               "operator": "POSCO", "country": "KR", "lat": 36.04, "lon": 129.36, "specialty": "goes_mill"},
    {"name": "POSCO Gwangyang",            "operator": "POSCO", "country": "KR", "lat": 34.94, "lon": 127.69, "specialty": "goes_mill"},
    {"name": "Baosteel Shanghai",          "operator": "Baosteel", "country": "CN", "lat": 31.40, "lon": 121.49, "specialty": "goes_mill"},
    {"name": "Baosteel Wuhan",             "operator": "Baosteel", "country": "CN", "lat": 30.59, "lon": 114.31, "specialty": "goes_mill"},
    {"name": "Baosteel Zhanjiang",         "operator": "Baosteel", "country": "CN", "lat": 21.27, "lon": 110.36, "specialty": "goes_mill"},
    {"name": "WISCO Wuhan",                "operator": "WISCO", "country": "CN", "lat": 30.59, "lon": 114.31, "specialty": "goes_mill"},
    {"name": "TISCO Taiyuan",              "operator": "TISCO", "country": "CN", "lat": 37.87, "lon": 112.55, "specialty": "goes_mill"},
    {"name": "Stalprodukt Bochnia",        "operator": "Stalprodukt", "country": "PL", "lat": 49.97, "lon":  20.43, "specialty": "goes_mill"},
    {"name": "Cleveland-Cliffs Butler",    "operator": "Cleveland-Cliffs", "country": "US", "lat": 40.86, "lon": -79.90, "specialty": "goes_mill"},
    {"name": "Cleveland-Cliffs Zanesville","operator": "Cleveland-Cliffs", "country": "US", "lat": 39.94, "lon": -82.01, "specialty": "goes_mill"},
    {"name": "Big River Steel Osceola",    "operator": "Big River Steel", "country": "US", "lat": 35.71, "lon": -89.97, "specialty": "goes_mill"},
    {"name": "TKES Bochum",                "operator": "ThyssenKrupp Electrical Steel", "country": "DE", "lat": 51.48, "lon":   7.22, "specialty": "goes_mill"},
    {"name": "TKES Gelsenkirchen",         "operator": "ThyssenKrupp Electrical Steel", "country": "DE", "lat": 51.51, "lon":   7.10, "specialty": "goes_mill"},
    {"name": "Aperam Imphy",               "operator": "Aperam", "country": "FR", "lat": 46.94, "lon":   3.27, "specialty": "goes_mill"},
    {"name": "NLMK Lipetsk",               "operator": "NLMK", "country": "RU", "lat": 52.61, "lon":  39.60, "specialty": "goes_mill"},
    {"name": "Severstal Cherepovets",      "operator": "Severstal", "country": "RU", "lat": 59.13, "lon":  37.91, "specialty": "goes_mill"},
    {"name": "Erdemir Eregli",             "operator": "Erdemir", "country": "TR", "lat": 41.28, "lon":  31.42, "specialty": "goes_mill"},
    {"name": "Tata Steel Angul",           "operator": "Tata Steel BSL", "country": "IN", "lat": 20.84, "lon":  85.10, "specialty": "goes_mill"},

    # ═══ SUB-COMPONENTS ═════════════════════════════════════════════════
    # Tap changers
    {"name": "Reinhausen Regensburg",      "operator": "Reinhausen", "country": "DE", "lat": 49.01, "lon":  12.10, "specialty": "tap_changer"},
    {"name": "Reinhausen Humboldt",        "operator": "Reinhausen", "country": "US", "lat": 35.82, "lon": -88.91, "specialty": "tap_changer"},
    {"name": "Huaming Shanghai",           "operator": "Huaming Power Equipment", "country": "CN", "lat": 31.23, "lon": 121.47, "specialty": "tap_changer"},
    # Bushings
    {"name": "ABB Bushings Ludvika",       "operator": "ABB Bushings", "country": "SE", "lat": 60.15, "lon":  15.18, "specialty": "bushings"},
    {"name": "Trench Bayreuth",            "operator": "Trench Group", "country": "DE", "lat": 49.95, "lon":  11.58, "specialty": "bushings"},
    {"name": "Trench Vienna",              "operator": "Trench Group", "country": "AT", "lat": 48.21, "lon":  16.37, "specialty": "bushings"},
    {"name": "Trench Hannover",            "operator": "Trench Group", "country": "DE", "lat": 52.37, "lon":   9.74, "specialty": "bushings"},
    {"name": "Trench St-Louis-du-Parc",    "operator": "Trench Group", "country": "CA", "lat": 46.59, "lon": -72.91, "specialty": "bushings"},
    {"name": "Pfisterer Winterbach",       "operator": "Pfisterer", "country": "DE", "lat": 48.81, "lon":   9.55, "specialty": "bushings"},
    {"name": "Saiyi Yangzhou",             "operator": "Yangzhou Saiyi", "country": "CN", "lat": 32.39, "lon": 119.42, "specialty": "bushings"},
    {"name": "Modern Insulators Abu Road", "operator": "Modern Insulators", "country": "IN", "lat": 24.49, "lon":  72.78, "specialty": "bushings"},
    {"name": "BBL Mumbai",                 "operator": "Bharat Bijlee", "country": "IN", "lat": 19.07, "lon":  72.88, "specialty": "bushings"},
    # Insulation (pressboard)
    {"name": "Weidmann Rapperswil",        "operator": "Weidmann Electrical Technology", "country": "CH", "lat": 47.23, "lon":   8.82, "specialty": "insulation"},
    {"name": "Weidmann Saint Johnsbury",   "operator": "Weidmann Electrical Technology", "country": "US", "lat": 44.42, "lon": -72.02, "specialty": "insulation"},
    {"name": "Weidmann Hammond",           "operator": "Weidmann Electrical Technology", "country": "US", "lat": 41.59, "lon": -87.50, "specialty": "insulation"},
    {"name": "Krempel Vaihingen",          "operator": "Krempel Group", "country": "DE", "lat": 48.93, "lon":   8.97, "specialty": "insulation"},
    {"name": "F&G Cologne",                "operator": "Felten Guilleaume", "country": "DE", "lat": 50.94, "lon":   6.96, "specialty": "insulation"},
    {"name": "DuPont Richmond",            "operator": "DuPont Nomex", "country": "US", "lat": 37.54, "lon": -77.43, "specialty": "insulation"},
    # Winding wire
    {"name": "Essex Furukawa Fort Wayne",  "operator": "Essex Furukawa Magnet Wire", "country": "US", "lat": 41.08, "lon": -85.14, "specialty": "winding_wire"},
    {"name": "Essex Furukawa Vincennes",   "operator": "Essex Furukawa Magnet Wire", "country": "US", "lat": 38.68, "lon": -87.53, "specialty": "winding_wire"},
    {"name": "Superior Essex Hoisington",  "operator": "Superior Essex", "country": "US", "lat": 38.52, "lon": -98.78, "specialty": "winding_wire"},
    {"name": "Elektrisola Reichshof",      "operator": "Elektrisola", "country": "DE", "lat": 50.96, "lon":   7.69, "specialty": "winding_wire"},
    # Cable HV
    {"name": "Prysmian Pikkala",           "operator": "Prysmian", "country": "FI", "lat": 60.13, "lon":  24.40, "specialty": "hv_cable"},
    {"name": "Prysmian Arco Felice",       "operator": "Prysmian", "country": "IT", "lat": 40.83, "lon":  14.07, "specialty": "hv_cable"},
    {"name": "Prysmian Charleston",        "operator": "Prysmian", "country": "US", "lat": 32.78, "lon": -79.93, "specialty": "hv_cable"},
    {"name": "Nexans Halden",              "operator": "Nexans", "country": "NO", "lat": 59.13, "lon":  11.38, "specialty": "hv_cable"},
    {"name": "Nexans Charleston",          "operator": "Nexans", "country": "US", "lat": 32.78, "lon": -79.93, "specialty": "hv_cable"},
    {"name": "NKT Karlskrona",             "operator": "NKT", "country": "SE", "lat": 56.16, "lon":  15.59, "specialty": "hv_cable"},
    {"name": "NKT Cologne",                "operator": "NKT", "country": "DE", "lat": 50.94, "lon":   6.96, "specialty": "hv_cable"},
    {"name": "LS Cable Donghae",           "operator": "LS Cable", "country": "KR", "lat": 37.52, "lon": 129.11, "specialty": "hv_cable"},
    {"name": "Sumitomo Osaka",             "operator": "Sumitomo Electric", "country": "JP", "lat": 34.69, "lon": 135.50, "specialty": "hv_cable"},
    # Switchgear
    {"name": "Hitachi GIS Zurich",         "operator": "Hitachi Energy GIS", "country": "CH", "lat": 47.38, "lon":   8.55, "specialty": "switchgear"},
    {"name": "Siemens GIS Berlin",         "operator": "Siemens Energy GIS", "country": "DE", "lat": 52.52, "lon":  13.40, "specialty": "switchgear"},
    {"name": "MEPPI Warrendale",           "operator": "Mitsubishi Electric Power Products", "country": "US", "lat": 40.63, "lon": -80.04, "specialty": "switchgear"},
    # Feedstock miners
    {"name": "Vale Carajas Mine",          "operator": "Vale", "country": "BR", "lat":  -6.05, "lon": -50.16, "specialty": "iron_ore_mine"},
    {"name": "BHP Pilbara",                "operator": "BHP", "country": "AU", "lat": -22.50, "lon": 119.00, "specialty": "iron_ore_mine"},
    {"name": "Rio Tinto Pilbara",          "operator": "Rio Tinto", "country": "AU", "lat": -22.40, "lon": 118.50, "specialty": "iron_ore_mine"},
    {"name": "Fortescue Solomon",          "operator": "Fortescue Metals", "country": "AU", "lat": -22.30, "lon": 117.80, "specialty": "iron_ore_mine"},
    # Oil refiners (transformer-grade naphthenic)
    {"name": "Nynas Nynashamn",            "operator": "Nynas", "country": "SE", "lat": 58.90, "lon":  17.95, "specialty": "transformer_oil_refinery"},
    {"name": "Ergon Vicksburg",            "operator": "Ergon", "country": "US", "lat": 32.35, "lon": -90.87, "specialty": "transformer_oil_refinery"},
    {"name": "Apar Rabale",                "operator": "Apar Industries", "country": "IN", "lat": 19.16, "lon":  73.00, "specialty": "transformer_oil_refinery"},
    # Ester fluid producers
    {"name": "Cargill Liverpool",          "operator": "Cargill BIOTEMP", "country": "GB", "lat": 53.40, "lon":  -2.99, "specialty": "ester_plant"},
    {"name": "Midel Manchester",           "operator": "MIDEL", "country": "GB", "lat": 53.48, "lon":  -2.24, "specialty": "ester_plant"},
]

# ─────────────────────────────────────────────────────────────────────────────
# PORTS — heavy-lift / breakbulk capable, plus container hubs
# ─────────────────────────────────────────────────────────────────────────────

PORTS: list[dict] = [
    # APAC
    {"name": "Busan",            "locode": "KRPUS", "country": "KR", "type": "container_breakbulk",
     "aliases": ["Pusan", "Port of Busan", "부산항", "KRPUS"]},
    {"name": "Incheon",          "locode": "KRINC", "country": "KR", "type": "container",
     "aliases": ["Port of Incheon", "인천항", "KRINC"]},
    {"name": "Gwangyang",        "locode": "KRKAN", "country": "KR", "type": "heavy_lift_breakbulk",
     "aliases": ["Kwangyang", "광양항", "KRKAN"]},
    {"name": "Ulsan",            "locode": "KRUSN", "country": "KR", "type": "heavy_lift_breakbulk",
     "aliases": ["Port of Ulsan", "울산항", "KRUSN"]},
    {"name": "Yokohama",         "locode": "JPYOK", "country": "JP", "type": "container_breakbulk",
     "aliases": ["Port of Yokohama", "横浜港", "JPYOK"]},
    {"name": "Tokyo",            "locode": "JPTYO", "country": "JP", "type": "container",
     "aliases": ["Port of Tokyo", "東京港", "JPTYO"]},
    {"name": "Nagoya",           "locode": "JPNGO", "country": "JP", "type": "container_breakbulk",
     "aliases": ["Port of Nagoya", "名古屋港", "JPNGO"]},
    {"name": "Kobe",             "locode": "JPUKB", "country": "JP", "type": "container_breakbulk",
     "aliases": ["Port of Kobe", "神戸港", "JPUKB"]},
    {"name": "Shanghai",         "locode": "CNSHA", "country": "CN", "type": "container_breakbulk",
     "aliases": ["Port of Shanghai", "上海港", "Yangshan", "CNSHA"]},
    {"name": "Ningbo-Zhoushan",  "locode": "CNNGB", "country": "CN", "type": "container_breakbulk",
     "aliases": ["Ningbo", "Zhoushan", "宁波舟山", "CNNGB"]},
    {"name": "Shenzhen",         "locode": "CNSZN", "country": "CN", "type": "container",
     "aliases": ["Yantian", "Shekou", "Chiwan", "深圳港", "CNSZN", "CNYTN"]},
    {"name": "Qingdao",          "locode": "CNTAO", "country": "CN", "type": "container_breakbulk",
     "aliases": ["Port of Qingdao", "青岛港", "CNTAO"]},
    {"name": "Tianjin",          "locode": "CNTXG", "country": "CN", "type": "container_breakbulk",
     "aliases": ["Port of Tianjin", "Xingang", "天津港", "CNTXG"]},
    {"name": "Hong Kong",        "locode": "HKHKG", "country": "CN", "type": "container",
     "aliases": ["Port of Hong Kong", "Kwai Tsing", "HKHKG"]},
    {"name": "Guangzhou",        "locode": "CNGZG", "country": "CN", "type": "container",
     "aliases": ["Nansha", "广州港", "CNGZG"]},
    {"name": "Singapore",        "locode": "SGSIN", "country": "SG", "type": "container_breakbulk",
     "aliases": ["Port of Singapore", "PSA Singapore", "SGSIN"]},
    {"name": "Jebel Ali",        "locode": "AEJEA", "country": "AE", "type": "heavy_lift_breakbulk",
     "aliases": ["Port of Jebel Ali", "DP World Jebel Ali", "AEJEA"]},
    {"name": "Mundra",           "locode": "INMUN", "country": "IN", "type": "container_breakbulk",
     "aliases": ["Adani Mundra", "Port of Mundra", "INMUN"]},
    {"name": "Nhava Sheva",      "locode": "INNSA", "country": "IN", "type": "container",
     "aliases": ["JNPT", "Jawaharlal Nehru", "Nhava Sheva Port", "INNSA"]},
    {"name": "Chennai",          "locode": "INMAA", "country": "IN", "type": "container_breakbulk",
     "aliases": ["Port of Chennai", "Madras Port", "INMAA"]},
    # EU
    {"name": "Antwerp",          "locode": "BEANR", "country": "BE", "type": "heavy_lift_breakbulk",
     "aliases": ["Port of Antwerp", "Antwerpen", "Antwerp-Bruges", "BEANR"]},
    {"name": "Rotterdam",        "locode": "NLRTM", "country": "NL", "type": "heavy_lift_breakbulk",
     "aliases": ["Port of Rotterdam", "Maasvlakte", "NLRTM"]},
    {"name": "Bremerhaven",      "locode": "DEBRV", "country": "DE", "type": "heavy_lift_breakbulk",
     "aliases": ["Port of Bremerhaven", "DEBRV"]},
    {"name": "Hamburg",          "locode": "DEHAM", "country": "DE", "type": "container_breakbulk",
     "aliases": ["Port of Hamburg", "Hamburg Hafen", "DEHAM"]},
    {"name": "Felixstowe",       "locode": "GBFXT", "country": "GB", "type": "container",
     "aliases": ["Port of Felixstowe", "GBFXT"]},
    {"name": "London Gateway",   "locode": "GBLGP", "country": "GB", "type": "container_breakbulk",
     "aliases": ["DP World London Gateway", "Port of London", "GBLGP"]},
    {"name": "Le Havre",         "locode": "FRLEH", "country": "FR", "type": "container_breakbulk",
     "aliases": ["Port of Le Havre", "Haropa", "FRLEH"]},
    {"name": "Marseille-Fos",    "locode": "FRFOS", "country": "FR", "type": "container_breakbulk",
     "aliases": ["Marseille", "Fos-sur-Mer", "Port of Marseille", "FRFOS"]},
    {"name": "Genoa",            "locode": "ITGOA", "country": "IT", "type": "container_breakbulk",
     "aliases": ["Genova", "Port of Genoa", "ITGOA"]},
    {"name": "Trieste",          "locode": "ITTRS", "country": "IT", "type": "heavy_lift_breakbulk",
     "aliases": ["Port of Trieste", "ITTRS"]},
    {"name": "Gdansk",           "locode": "PLGDN", "country": "PL", "type": "container_breakbulk",
     "aliases": ["Port of Gdansk", "DCT Gdansk", "Baltic Hub", "PLGDN"]},
    {"name": "Gdynia",           "locode": "PLGDY", "country": "PL", "type": "container",
     "aliases": ["Port of Gdynia", "PLGDY"]},
    {"name": "Constanta",        "locode": "ROCND", "country": "RO", "type": "container_breakbulk",
     "aliases": ["Port of Constanta", "ROCND"]},
    {"name": "Algeciras",        "locode": "ESALG", "country": "ES", "type": "container",
     "aliases": ["Port of Algeciras", "ESALG"]},
    {"name": "Valencia",         "locode": "ESVLC", "country": "ES", "type": "container_breakbulk",
     "aliases": ["Port of Valencia", "ESVLC"]},
    {"name": "Piraeus",          "locode": "GRPIR", "country": "GR", "type": "container",
     "aliases": ["Port of Piraeus", "Cosco Piraeus", "GRPIR"]},
    # US
    {"name": "Savannah",         "locode": "USSAV", "country": "US", "type": "container_breakbulk",
     "aliases": ["Port of Savannah", "Garden City Terminal", "USSAV"]},
    {"name": "Norfolk",          "locode": "USORF", "country": "US", "type": "heavy_lift_breakbulk",
     "aliases": ["Port of Virginia", "Hampton Roads", "Portsmouth", "USORF"]},
    {"name": "Houston",          "locode": "USHOU", "country": "US", "type": "heavy_lift_breakbulk",
     "aliases": ["Port of Houston", "Bayport", "Barbours Cut", "USHOU"]},
    {"name": "Long Beach",       "locode": "USLGB", "country": "US", "type": "container_breakbulk",
     "aliases": ["Port of Long Beach", "POLB", "USLGB"]},
    {"name": "Los Angeles",      "locode": "USLAX", "country": "US", "type": "container",
     "aliases": ["Port of Los Angeles", "POLA", "San Pedro Bay", "USLAX"]},
    {"name": "Oakland",          "locode": "USOAK", "country": "US", "type": "container",
     "aliases": ["Port of Oakland", "USOAK"]},
    {"name": "Seattle-Tacoma",   "locode": "USSEA", "country": "US", "type": "container_breakbulk",
     "aliases": ["Seattle", "Tacoma", "Northwest Seaport Alliance", "NWSA", "USSEA", "USTAC"]},
    {"name": "Charleston",       "locode": "USCHS", "country": "US", "type": "container_breakbulk",
     "aliases": ["Port of Charleston", "SC Ports", "USCHS"]},
    {"name": "Mobile",           "locode": "USMOB", "country": "US", "type": "heavy_lift_breakbulk",
     "aliases": ["Port of Mobile", "APM Mobile", "USMOB"]},
    {"name": "Jacksonville",     "locode": "USJAX", "country": "US", "type": "container_breakbulk",
     "aliases": ["JAXPORT", "Port of Jacksonville", "USJAX"]},
    {"name": "New Orleans",      "locode": "USMSY", "country": "US", "type": "heavy_lift_breakbulk",
     "aliases": ["Port of New Orleans", "Port NOLA", "USMSY"]},
    {"name": "Beaumont",         "locode": "USBPT", "country": "US", "type": "heavy_lift_breakbulk",
     "aliases": ["Port of Beaumont", "USBPT"]},
    {"name": "Galveston",        "locode": "USGLS", "country": "US", "type": "heavy_lift_breakbulk",
     "aliases": ["Port of Galveston", "USGLS"]},
    {"name": "Baltimore",        "locode": "USBAL", "country": "US", "type": "heavy_lift_breakbulk",
     "aliases": ["Port of Baltimore", "Helen Delich Bentley", "USBAL"]},
    {"name": "New York-New Jersey", "locode": "USNYC", "country": "US", "type": "container_breakbulk",
     "aliases": ["Port of New York", "PANYNJ", "Port Newark", "USNYC", "USEWR"]},
    # Canada / LATAM / MENA
    {"name": "Halifax",          "locode": "CAHAL", "country": "CA", "type": "container_breakbulk",
     "aliases": ["Port of Halifax", "CAHAL"]},
    {"name": "Vancouver",        "locode": "CAVAN", "country": "CA", "type": "container_breakbulk",
     "aliases": ["Port of Vancouver", "Port Metro Vancouver", "CAVAN"]},
    {"name": "Manzanillo",       "locode": "MXZLO", "country": "MX", "type": "container_breakbulk",
     "aliases": ["Manzanillo Mexico", "Port of Manzanillo", "MXZLO"]},
    {"name": "Veracruz",         "locode": "MXVER", "country": "MX", "type": "heavy_lift_breakbulk",
     "aliases": ["Port of Veracruz", "MXVER"]},
    {"name": "Santos",           "locode": "BRSSZ", "country": "BR", "type": "container_breakbulk",
     "aliases": ["Port of Santos", "Porto de Santos", "BRSSZ"]},
    {"name": "Itajai",           "locode": "BRITJ", "country": "BR", "type": "container",
     "aliases": ["Port of Itajai", "BRITJ"]},
    {"name": "Cartagena Colombia", "locode": "COCTG", "country": "CO", "type": "container_breakbulk",
     "aliases": ["Port of Cartagena", "Cartagena de Indias", "COCTG"]},
    {"name": "Buenos Aires",     "locode": "ARBUE", "country": "AR", "type": "container_breakbulk",
     "aliases": ["Port of Buenos Aires", "Puerto Nuevo", "ARBUE"]},
    {"name": "Durban",           "locode": "ZADUR", "country": "ZA", "type": "heavy_lift_breakbulk",
     "aliases": ["Port of Durban", "ZADUR"]},
]

# ─────────────────────────────────────────────────────────────────────────────
# LANES — shipping corridors
# ─────────────────────────────────────────────────────────────────────────────

LANES: list[dict] = [
    {"name": "Korea_USEC",         "origin_region": "APAC",  "destination_region": "AMER", "transit_days": 30},
    {"name": "Korea_USWC",         "origin_region": "APAC",  "destination_region": "AMER", "transit_days": 14},
    {"name": "Korea_USGulf",       "origin_region": "APAC",  "destination_region": "AMER", "transit_days": 35},
    {"name": "Korea_EU_NorthSea",  "origin_region": "APAC",  "destination_region": "EU",   "transit_days": 38},
    {"name": "Korea_EU_Med",       "origin_region": "APAC",  "destination_region": "EU",   "transit_days": 32},
    {"name": "Japan_USEC",         "origin_region": "APAC",  "destination_region": "AMER", "transit_days": 28},
    {"name": "Japan_USWC",         "origin_region": "APAC",  "destination_region": "AMER", "transit_days": 12},
    {"name": "Japan_EU_NorthSea",  "origin_region": "APAC",  "destination_region": "EU",   "transit_days": 36},
    {"name": "China_USEC",         "origin_region": "APAC",  "destination_region": "AMER", "transit_days": 32},
    {"name": "China_USWC",         "origin_region": "APAC",  "destination_region": "AMER", "transit_days": 16},
    {"name": "China_EU_NorthSea",  "origin_region": "APAC",  "destination_region": "EU",   "transit_days": 40},
    {"name": "China_EU_Med",       "origin_region": "APAC",  "destination_region": "EU",   "transit_days": 30},
    {"name": "India_EU",           "origin_region": "APAC",  "destination_region": "EU",   "transit_days": 22},
    {"name": "India_USEC",         "origin_region": "APAC",  "destination_region": "AMER", "transit_days": 32},
    {"name": "India_MENA",         "origin_region": "APAC",  "destination_region": "MENA", "transit_days":  8},
    {"name": "Brazil_USEC",        "origin_region": "LATAM", "destination_region": "AMER", "transit_days": 18},
    {"name": "Brazil_EU",          "origin_region": "LATAM", "destination_region": "EU",   "transit_days": 21},
    {"name": "Mexico_USGulf",      "origin_region": "AMER",  "destination_region": "AMER", "transit_days":  4},
    {"name": "EU_USEC",            "origin_region": "EU",    "destination_region": "AMER", "transit_days": 14},
    {"name": "EU_USGulf",          "origin_region": "EU",    "destination_region": "AMER", "transit_days": 18},
    {"name": "Turkey_EU",          "origin_region": "MENA",  "destination_region": "EU",   "transit_days":  6},
    {"name": "Australia_APAC",     "origin_region": "APAC",  "destination_region": "APAC", "transit_days":  9},
]

# ─────────────────────────────────────────────────────────────────────────────
# CATEGORIES — procurement categorization
# ─────────────────────────────────────────────────────────────────────────────

CATEGORIES: list[dict] = [
    {"name": "Power_Transformer_Large",            "description": "Large power transformers ≥ 100 MVA"},
    {"name": "Power_Transformer_GSU",              "description": "Generator step-up transformers"},
    {"name": "Power_Transformer_HVDC_Converter",   "description": "HVDC converter transformers"},
    {"name": "Power_Transformer_Distribution",     "description": "Substation / distribution transformers"},
    {"name": "Power_Transformer_Spot_OneOff",      "description": "Single-unit spot purchases"},
    {"name": "Shunt_Reactor",                      "description": "Shunt reactors for reactive power compensation"},
    {"name": "Series_Reactor",                     "description": "Series reactors for current limiting"},
    {"name": "Phase_Shifting_Transformer",         "description": "Phase-shifting transformers for power flow control"},
    {"name": "Autotransformer",                    "description": "Autotransformers for inter-system coupling"},
    {"name": "Mobile_Substation",                  "description": "Trailer-mounted mobile substations for emergency"},
    {"name": "Distribution_Transformer_PadMount",  "description": "Pad-mounted distribution transformers"},
    {"name": "Transformer_Repair_Refurb",          "description": "Repair, refurbishment, lifetime extension services"},
]

# ─────────────────────────────────────────────────────────────────────────────
# DEMAND SOURCES — who is driving transformer demand globally
# ─────────────────────────────────────────────────────────────────────────────

DEMAND_SOURCES: list[dict] = [
    # ── Hyperscaler datacenters (AI buildout, single biggest demand driver) ──
    {"name": "Microsoft Datacenter Buildout",  "type": "hyperscaler", "country": "US"},
    {"name": "Google Datacenter Buildout",     "type": "hyperscaler", "country": "US"},
    {"name": "Amazon Datacenter Buildout",     "type": "hyperscaler", "country": "US"},
    {"name": "Meta Datacenter Buildout",       "type": "hyperscaler", "country": "US"},
    {"name": "Oracle Cloud Buildout",          "type": "hyperscaler", "country": "US"},
    {"name": "Apple Datacenter Buildout",      "type": "hyperscaler", "country": "US"},
    {"name": "X AI Memphis Buildout",          "type": "hyperscaler", "country": "US"},
    {"name": "CoreWeave Buildout",             "type": "hyperscaler", "country": "US"},
    {"name": "Crusoe AI Buildout",             "type": "hyperscaler", "country": "US"},
    {"name": "ByteDance Datacenter Buildout",  "type": "hyperscaler", "country": "CN"},
    {"name": "Tencent Datacenter Buildout",    "type": "hyperscaler", "country": "CN"},
    {"name": "Alibaba Cloud Buildout",         "type": "hyperscaler", "country": "CN"},
    # ── Colocation operators ─────────────────────────────────────────────
    {"name": "Equinix Buildout",               "type": "colocation", "country": "US"},
    {"name": "Digital Realty Buildout",        "type": "colocation", "country": "US"},
    {"name": "QTS Realty Buildout",            "type": "colocation", "country": "US"},
    {"name": "CyrusOne Buildout",              "type": "colocation", "country": "US"},
    {"name": "Iron Mountain Datacenter",       "type": "colocation", "country": "US"},
    {"name": "Vantage Data Centers",           "type": "colocation", "country": "US"},
    {"name": "Aligned Data Centers",           "type": "colocation", "country": "US"},
    {"name": "NTT Data Centers",               "type": "colocation", "country": "JP"},
    # ── US investor-owned utilities ──────────────────────────────────────
    {"name": "Dominion Energy",                "type": "utility_us", "country": "US"},
    {"name": "Duke Energy",                    "type": "utility_us", "country": "US"},
    {"name": "Southern Company",               "type": "utility_us", "country": "US"},
    {"name": "NextEra Energy",                 "type": "utility_us", "country": "US"},
    {"name": "American Electric Power",        "type": "utility_us", "country": "US"},
    {"name": "Exelon",                         "type": "utility_us", "country": "US"},
    {"name": "FirstEnergy",                    "type": "utility_us", "country": "US"},
    {"name": "Xcel Energy",                    "type": "utility_us", "country": "US"},
    {"name": "PG&E",                           "type": "utility_us", "country": "US"},
    {"name": "Sempra",                         "type": "utility_us", "country": "US"},
    {"name": "Vistra Energy",                  "type": "utility_us", "country": "US"},
    {"name": "Constellation Energy",           "type": "utility_us", "country": "US"},
    {"name": "TVA",                            "type": "utility_us", "country": "US"},
    {"name": "Bonneville Power Administration","type": "utility_us", "country": "US"},
    # ── EU TSOs ──────────────────────────────────────────────────────────
    {"name": "TenneT",                         "type": "tso_eu", "country": "NL"},
    {"name": "Amprion",                        "type": "tso_eu", "country": "DE"},
    {"name": "50Hertz",                        "type": "tso_eu", "country": "DE"},
    {"name": "TransnetBW",                     "type": "tso_eu", "country": "DE"},
    {"name": "Terna",                          "type": "tso_eu", "country": "IT"},
    {"name": "Red Electrica",                  "type": "tso_eu", "country": "ES"},
    {"name": "RTE France",                     "type": "tso_eu", "country": "FR"},
    {"name": "National Grid UK",               "type": "tso_eu", "country": "GB"},
    {"name": "Elia",                           "type": "tso_eu", "country": "BE"},
    {"name": "Energinet",                      "type": "tso_eu", "country": "DK"},
    {"name": "Fingrid",                        "type": "tso_eu", "country": "FI"},
    {"name": "Statnett",                       "type": "tso_eu", "country": "NO"},
    {"name": "Svenska Kraftnat",               "type": "tso_eu", "country": "SE"},
    {"name": "PSE Polska",                     "type": "tso_eu", "country": "PL"},
    # ── Government / capex programs ──────────────────────────────────────
    {"name": "IRA Grid Modernization Program", "type": "government_grid", "country": "US"},
    {"name": "IIJA Infrastructure Bill",       "type": "government_grid", "country": "US"},
    {"name": "REPowerEU Grid Upgrade",         "type": "government_grid", "country": "EU"},
    {"name": "Great Grid Upgrade UK",          "type": "government_grid", "country": "GB"},
    {"name": "India Green Grid Initiative",    "type": "government_grid", "country": "IN"},
    {"name": "Saudi Vision 2030 NEOM Grid",    "type": "government_grid", "country": "SA"},
    {"name": "Australia Rewiring the Nation",  "type": "government_grid", "country": "AU"},
    # ── Major offshore-wind / renewable projects ─────────────────────────
    {"name": "Dogger Bank Wind Farm",          "type": "renewable_project", "country": "GB"},
    {"name": "Hornsea Wind Farm",              "type": "renewable_project", "country": "GB"},
    {"name": "ScotWind Offshore Leasing",      "type": "renewable_project", "country": "GB"},
    {"name": "Empire Wind",                    "type": "renewable_project", "country": "US"},
    {"name": "Coastal Virginia Offshore Wind", "type": "renewable_project", "country": "US"},
    {"name": "Vineyard Wind",                  "type": "renewable_project", "country": "US"},
    {"name": "Revolution Wind",                "type": "renewable_project", "country": "US"},
    {"name": "DolWin BorWin German Offshore",  "type": "renewable_project", "country": "DE"},
    {"name": "North Sea Wind Power Hub",       "type": "renewable_project", "country": "NL"},
    # ── EV charging networks (smaller but real distribution demand) ──────
    {"name": "Tesla Supercharger Network",     "type": "ev_charging", "country": "US"},
    {"name": "Electrify America Buildout",     "type": "ev_charging", "country": "US"},
    {"name": "ChargePoint Network",            "type": "ev_charging", "country": "US"},
    {"name": "Ionity Network",                 "type": "ev_charging", "country": "EU"},
]

# ─────────────────────────────────────────────────────────────────────────────
# EDGES — all relationships
# Format: (relationship_type, start_label, start_name, end_label, end_name, props_or_None)
# ─────────────────────────────────────────────────────────────────────────────

EDGES: list[tuple] = []

# Plant → Supplier (OPERATED_BY) — auto-generated from each plant's `operator`
for plant in PLANTS:
    EDGES.append(("OPERATED_BY", "Plant", plant["name"], "Supplier", plant["operator"], None))

# Plant → Country (LOCATED_IN) — auto-generated
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

# Plant → Material (USES_MATERIAL) — by specialty
_transformer_plant_materials = [
    "GOES_M3_Grade", "Cu_Winding_Strip", "Al_Winding_Strip",
    "Mineral_Oil_IEC60296", "Bushing_HV_Porcelain", "Insulation_Pressboard",
    "Heavy_Lift_Cratepack",
]
_distribution_plant_materials = [
    "NGOES_Grade50", "Cu_Winding_Strip", "Al_Winding_Strip",
    "Mineral_Oil_IEC60296", "Insulation_Kraft_Paper",
]
_hvdc_plant_materials = [
    "GOES_M3_Grade", "GOES_M4_Grade", "GOES_HiB_Grade",
    "Cu_Winding_Strip", "Mineral_Oil_IEC60296", "Ester_K_Class",
    "Bushing_HV_Composite", "Insulation_Pressboard", "Heavy_Lift_Cratepack",
]
_uhv_plant_materials = [
    "GOES_HiB_Grade", "GOES_Domain_Refined", "Cu_Winding_Strip",
    "Mineral_Oil_Inhibited", "Bushing_HV_Composite",
    "Insulation_Pressboard", "Insulation_Nomex", "Heavy_Lift_Cratepack",
]
for plant in PLANTS:
    specialty = plant["specialty"]
    if specialty in (
        "goes_mill", "tap_changer", "bushings", "insulation", "winding_wire",
        "hv_cable", "switchgear", "iron_ore_mine",
        "transformer_oil_refinery", "ester_plant", "mobile_substation",
    ):
        continue  # these plants are themselves component suppliers, not transformer assembly
    if specialty == "hvdc":
        mats = _hvdc_plant_materials
    elif specialty == "ultra_high_voltage":
        mats = _uhv_plant_materials
    elif specialty == "distribution":
        mats = _distribution_plant_materials
    else:
        mats = _transformer_plant_materials
    for m in mats:
        EDGES.append(("USES_MATERIAL", "Plant", plant["name"], "Material", m, None))

# ── Plant → Port (SHIPS_VIA) ─────────────────────────────────────────────
# Explicit overrides (legacy + curated) preferred; otherwise default by country.
_plant_to_ports: dict[str, list[str]] = {
    # Legacy / curated explicit mappings
    "Siemens Nuremberg": ["Hamburg", "Bremerhaven"],
    "Siemens Weiz": ["Hamburg"],
    "Siemens Linz": ["Hamburg"],
    "Siemens Charlotte": ["Savannah", "Norfolk"],
    "Siemens Cordoba": ["Algeciras", "Valencia"],
    "Siemens Drammen": ["Bremerhaven"],
    "Siemens Mumbai": ["Nhava Sheva", "Mundra"],
    "Siemens Goa": ["Mundra"],
    "Siemens Krzewina": ["Gdansk"],
    "Siemens Belo Horizonte": ["Santos"],
    "Siemens Wendell": ["Norfolk", "Savannah"],

    "Hitachi Bad Honnef": ["Rotterdam", "Antwerp"],
    "Hitachi Ludvika": ["Hamburg", "Gdansk"],
    "Hitachi Vaasa": ["Hamburg"],
    "Hitachi South Boston": ["Norfolk"],
    "Hitachi Cordoba": ["Algeciras"],
    "Hitachi Mont Royal": ["Halifax"],
    "Hitachi Pinetops": ["Norfolk"],
    "Hitachi Pinhao": ["Santos", "Itajai"],
    "Hitachi Vadodara": ["Mundra"],
    "Hitachi Helsinki": ["Hamburg"],
    "Hitachi Lodz": ["Gdansk"],
    "Hitachi Jefferson City": ["New Orleans"],
    "Hitachi Crystal Springs": ["New Orleans"],

    "GE Vernova Pittsburgh": ["Norfolk", "Baltimore"],
    "GE Vernova Memphis": ["New Orleans", "Houston"],
    "GE Vernova Charleroi": ["Norfolk"],
    "GE Vernova Stafford": ["London Gateway", "Felixstowe"],
    "GE Vernova Villeurbanne": ["Marseille-Fos"],
    "GE Vernova Mohammedia": ["Veracruz"],

    "Prolec Apodaca": ["Houston", "Manzanillo"],
    "Prolec Monterrey": ["Houston"],
    "Prolec Shreveport": ["New Orleans"],

    "Hyundai Ulsan": ["Ulsan", "Busan"],
    "Hyundai Alabama": ["Mobile", "Savannah"],
    "Hyosung Changwon": ["Busan"],
    "Hyosung Yangsan": ["Busan"],
    "Hyosung HICO Memphis": ["New Orleans"],

    "Mitsubishi Ako": ["Kobe", "Yokohama"],
    "Mitsubishi Kobe": ["Kobe"],
    "Mitsubishi Warrendale": ["Baltimore"],
    "Toshiba Hamakawasaki": ["Yokohama", "Tokyo"],
    "Toshiba Mie": ["Nagoya"],
    "Toshiba Houston": ["Houston"],

    "TBEA Shenyang": ["Tianjin"],
    "TBEA Hengyang": ["Shanghai"],
    "TBEA Tianjin": ["Tianjin"],
    "TBEA Shandong": ["Qingdao"],
    "CHINT Hangzhou": ["Ningbo-Zhoushan"],
    "CHINT Wenzhou": ["Ningbo-Zhoushan"],
    "Pinggao Pingdingshan": ["Tianjin"],
    "XJ Xuchang": ["Tianjin"],
    "Shenyang Transformer": ["Tianjin"],
    "Wuhan Transformer Plant": ["Shanghai"],
    "Shandong Jinan": ["Qingdao"],

    "WEG Blumenau": ["Santos", "Itajai"],
    "WEG Manaus": ["Santos"],
    "WEG Sao Paulo": ["Santos"],

    "CG Power Bhopal": ["Mundra", "Nhava Sheva"],
    "CG Power Nashik": ["Nhava Sheva"],
    "BHEL Bhopal": ["Mundra"],
    "BHEL Jhansi": ["Mundra"],
    "BHEL Hardwar": ["Nhava Sheva"],
    "Voltamp Vadodara": ["Mundra"],
    "TRIL Moraiya": ["Mundra"],
    "Vijai Hyderabad": ["Chennai"],
    "Indo Tech Chennai": ["Chennai"],
    "ABB Vadodara": ["Mundra"],

    "BEST Trafo Sakarya": ["Constanta", "Piraeus"],
    "BEST Trafo Balikesir": ["Piraeus"],

    "Eaton Waukesha": ["Houston"],
    "Eaton Nacogdoches": ["Houston", "Beaumont"],
    "Hubbell Centralia": ["New Orleans"],
    "Hubbell Aiken": ["Charleston", "Savannah"],
    "PTTI Canonsburg": ["Baltimore", "Norfolk"],
    "Virginia Transformer Roanoke": ["Norfolk"],
    "Howard Laurel": ["Mobile"],
    "ERMCO Dyersburg": ["New Orleans"],
    "Maddox South Bend": ["Baltimore"],
    "Maddox Idaho Falls": ["Long Beach", "Seattle-Tacoma"],
    "Niagara Buffalo": ["New York-New Jersey"],
    "SPX Waukesha": ["Houston"],
    "Delta Star Lynchburg": ["Norfolk"],
    "Delta Star San Carlos": ["Oakland", "Long Beach"],
    "Federal Pacific Bristol": ["Norfolk"],
    "Pacific Crest Medford": ["Oakland"],

    # GOES mills
    "Nippon Steel Hirohata": ["Kobe", "Yokohama"],
    "Nippon Steel Kashima": ["Yokohama", "Tokyo"],
    "Nippon Steel Yawata": ["Kobe"],
    "JFE Kurashiki": ["Kobe"],
    "JFE Chiba": ["Tokyo"],
    "JFE Fukuyama": ["Kobe"],
    "POSCO Pohang": ["Busan", "Gwangyang"],
    "POSCO Gwangyang": ["Gwangyang"],
    "Baosteel Shanghai": ["Shanghai", "Ningbo-Zhoushan"],
    "Baosteel Wuhan": ["Shanghai"],
    "Baosteel Zhanjiang": ["Hong Kong"],
    "WISCO Wuhan": ["Shanghai"],
    "TISCO Taiyuan": ["Tianjin"],
    "Stalprodukt Bochnia": ["Gdansk", "Hamburg"],
    "Cleveland-Cliffs Butler": ["Baltimore", "Norfolk"],
    "Cleveland-Cliffs Zanesville": ["Baltimore"],
    "Big River Steel Osceola": ["New Orleans"],
    "TKES Bochum": ["Hamburg", "Rotterdam"],
    "TKES Gelsenkirchen": ["Rotterdam"],
    "Aperam Imphy": ["Le Havre", "Marseille-Fos"],
    "NLMK Lipetsk": ["Constanta"],
    "Severstal Cherepovets": ["Hamburg"],
    "Erdemir Eregli": ["Constanta", "Piraeus"],
    "Tata Steel Angul": ["Chennai"],

    # Sub-components
    "Reinhausen Regensburg": ["Hamburg"],
    "Reinhausen Humboldt": ["New Orleans"],
    "Huaming Shanghai": ["Shanghai"],
    "ABB Bushings Ludvika": ["Hamburg"],
    "Trench Bayreuth": ["Hamburg"],
    "Trench Vienna": ["Trieste"],
    "Trench Hannover": ["Hamburg"],
    "Trench St-Louis-du-Parc": ["Halifax"],
    "Pfisterer Winterbach": ["Hamburg"],
    "Saiyi Yangzhou": ["Shanghai"],
    "Modern Insulators Abu Road": ["Mundra"],
    "BBL Mumbai": ["Nhava Sheva"],
    "Weidmann Rapperswil": ["Hamburg", "Rotterdam"],
    "Weidmann Saint Johnsbury": ["New York-New Jersey"],
    "Weidmann Hammond": ["New Orleans"],
    "Krempel Vaihingen": ["Hamburg"],
    "F&G Cologne": ["Rotterdam"],
    "DuPont Richmond": ["Norfolk"],
    "Essex Furukawa Fort Wayne": ["Baltimore"],
    "Essex Furukawa Vincennes": ["New Orleans"],
    "Superior Essex Hoisington": ["Houston"],
    "Elektrisola Reichshof": ["Hamburg"],

    "Prysmian Pikkala": ["Hamburg"],
    "Prysmian Arco Felice": ["Genoa"],
    "Prysmian Charleston": ["Charleston"],
    "Nexans Halden": ["Hamburg"],
    "Nexans Charleston": ["Charleston"],
    "NKT Karlskrona": ["Hamburg"],
    "NKT Cologne": ["Rotterdam"],
    "LS Cable Donghae": ["Busan"],
    "Sumitomo Osaka": ["Kobe"],
    "Hitachi GIS Zurich": ["Genoa"],
    "Siemens GIS Berlin": ["Hamburg"],
    "MEPPI Warrendale": ["Baltimore"],
    "Vale Carajas Mine": ["Itajai"],
    "BHP Pilbara": ["Singapore"],
    "Rio Tinto Pilbara": ["Singapore"],
    "Fortescue Solomon": ["Singapore"],
    "Nynas Nynashamn": ["Hamburg"],
    "Ergon Vicksburg": ["New Orleans"],
    "Apar Rabale": ["Nhava Sheva"],
    "Cargill Liverpool": ["London Gateway"],
    "Midel Manchester": ["London Gateway"],

    # Other Siemens/Hitachi plants
    "SGB Regensburg": ["Hamburg"],
    "SGB Neumark": ["Hamburg"],
    "SGB Nijmegen": ["Rotterdam"],
    "SGB Lugoj": ["Constanta"],
    "SGB Louisville": ["New Orleans"],
    "Schneider Grenoble": ["Marseille-Fos"],
    "Schneider Saint Louis": ["Le Havre"],
    "Schneider Smyrna": ["Mobile", "Savannah"],
    "Schneider Suzhou": ["Shanghai"],
    "Royal SMIT Nijmegen": ["Rotterdam"],
    "Wilson Power Leeds": ["Felixstowe"],
    "Brush Loughborough": ["Felixstowe"],
    "Tamini Legnano": ["Genoa"],
    "Tamini Melegnano": ["Genoa"],
    "Tesar Colle Umberto": ["Genoa", "Trieste"],
    "Trafomec Tavernelle": ["Genoa"],
    "GBE Padova": ["Genoa"],
    "Imefy Yecla": ["Valencia"],
    "Ormazabal Bilbao": ["Valencia"],
    "Ormazabal Cordoba": ["Algeciras"],
    "Power Machines SPb": ["Hamburg"],
    "LS Electric Cheongju": ["Busan"],
    "LS Electric Busan": ["Busan"],
    "Iljin Hwaseong": ["Incheon"],
    "Fuji Electric Tokyo": ["Tokyo"],
    "Daihen Osaka": ["Kobe"],
    "Hyundai Sofia": ["Constanta"],
}
for plant_name, ports in _plant_to_ports.items():
    for p in ports:
        EDGES.append(("SHIPS_VIA", "Plant", plant_name, "Port", p, None))

# Port → Lane (ON_LANE)
_port_to_lanes: dict[str, list[str]] = {
    # APAC
    "Busan":            ["Korea_USEC", "Korea_USWC", "Korea_USGulf", "Korea_EU_NorthSea", "Korea_EU_Med"],
    "Incheon":          ["Korea_USWC", "Korea_EU_NorthSea"],
    "Gwangyang":        ["Korea_USEC", "Korea_EU_NorthSea"],
    "Ulsan":            ["Korea_USEC", "Korea_USWC"],
    "Yokohama":         ["Japan_USEC", "Japan_USWC", "Japan_EU_NorthSea"],
    "Tokyo":            ["Japan_USEC", "Japan_EU_NorthSea"],
    "Nagoya":           ["Japan_USEC", "Japan_USWC"],
    "Kobe":             ["Japan_USEC", "Japan_EU_NorthSea"],
    "Shanghai":         ["China_USEC", "China_USWC", "China_EU_NorthSea", "China_EU_Med"],
    "Ningbo-Zhoushan":  ["China_USEC", "China_USWC", "China_EU_NorthSea"],
    "Shenzhen":         ["China_USWC", "China_EU_Med"],
    "Qingdao":          ["China_USEC", "China_EU_NorthSea"],
    "Tianjin":          ["China_USEC", "China_EU_NorthSea"],
    "Hong Kong":        ["China_USWC", "China_EU_Med"],
    "Guangzhou":        ["China_USWC", "China_EU_Med"],
    "Singapore":        ["Australia_APAC", "India_EU", "China_EU_Med"],
    "Jebel Ali":        ["India_MENA", "India_EU"],
    "Mundra":           ["India_EU", "India_USEC", "India_MENA"],
    "Nhava Sheva":      ["India_EU", "India_USEC", "India_MENA"],
    "Chennai":          ["India_EU", "India_USEC"],
    # EU
    "Antwerp":          ["EU_USEC", "EU_USGulf"],
    "Rotterdam":        ["EU_USEC", "EU_USGulf"],
    "Bremerhaven":      ["EU_USEC"],
    "Hamburg":          ["EU_USEC", "EU_USGulf"],
    "Felixstowe":       ["EU_USEC"],
    "London Gateway":   ["EU_USEC"],
    "Le Havre":         ["EU_USEC"],
    "Marseille-Fos":    ["EU_USGulf"],
    "Genoa":            ["EU_USEC"],
    "Trieste":          ["EU_USEC"],
    "Gdansk":           ["EU_USEC"],
    "Gdynia":           ["EU_USEC"],
    "Constanta":        ["Turkey_EU"],
    "Algeciras":        ["EU_USEC", "EU_USGulf"],
    "Valencia":         ["EU_USEC"],
    "Piraeus":          ["Turkey_EU", "EU_USGulf"],
    # AMER
    "Houston":          ["Korea_USGulf", "Japan_USEC", "Brazil_USEC", "China_USEC", "Mexico_USGulf", "EU_USGulf"],
    "Norfolk":          ["Korea_USEC", "Japan_USEC", "EU_USEC", "China_USEC", "India_USEC", "Brazil_USEC"],
    "Savannah":         ["Korea_USEC", "EU_USEC", "China_USEC"],
    "Long Beach":       ["Korea_USWC", "Japan_USWC", "China_USWC"],
    "Los Angeles":      ["Korea_USWC", "Japan_USWC", "China_USWC"],
    "Oakland":          ["Japan_USWC", "China_USWC"],
    "Seattle-Tacoma":   ["Korea_USWC", "Japan_USWC", "China_USWC"],
    "Charleston":       ["EU_USEC", "Korea_USEC"],
    "Mobile":           ["Korea_USGulf", "EU_USGulf"],
    "Jacksonville":     ["EU_USEC", "Brazil_USEC"],
    "New Orleans":      ["Korea_USGulf", "Japan_USEC", "Brazil_USEC", "EU_USGulf"],
    "Beaumont":         ["Korea_USGulf", "Mexico_USGulf"],
    "Galveston":        ["Mexico_USGulf"],
    "Baltimore":        ["EU_USEC", "Korea_USEC"],
    "New York-New Jersey": ["EU_USEC", "China_USEC"],
    "Halifax":          ["EU_USEC"],
    "Vancouver":        ["Korea_USWC", "Japan_USWC", "China_USWC"],
    "Manzanillo":       ["Korea_USWC", "Japan_USWC", "Mexico_USGulf"],
    "Veracruz":         ["EU_USGulf", "Mexico_USGulf"],
    "Santos":           ["Brazil_USEC", "Brazil_EU"],
    "Itajai":           ["Brazil_USEC", "Brazil_EU"],
    "Cartagena Colombia": ["Brazil_USEC"],
    "Buenos Aires":     ["Brazil_USEC", "Brazil_EU"],
    "Durban":           ["India_MENA"],
}
for port_name, lanes in _port_to_lanes.items():
    for lane in lanes:
        EDGES.append(("ON_LANE", "Port", port_name, "Lane", lane, None))

# Supplier → Supplier (SUB_TIER_OF) — feedstock + sub-component dependencies
_subtier_relationships: list[tuple[str, str]] = [
    # GOES mills → transformer OEMs
    ("Nippon Steel", "Mitsubishi Electric"),
    ("Nippon Steel", "Hyundai Electric"),
    ("Nippon Steel", "Hyosung Heavy Industries"),
    ("Nippon Steel", "Toshiba Energy Systems"),
    ("JFE Steel", "Mitsubishi Electric"),
    ("JFE Steel", "Hyundai Electric"),
    ("JFE Steel", "Toshiba Energy Systems"),
    ("POSCO", "Hyundai Electric"),
    ("POSCO", "Hyosung Heavy Industries"),
    ("POSCO", "LS Electric"),
    ("Baosteel", "TBEA"),
    ("Baosteel", "CHINT"),
    ("Baosteel", "Pinggao Group"),
    ("Baosteel", "CG Power"),
    ("Baosteel", "BHEL"),
    ("WISCO", "TBEA"),
    ("WISCO", "Shenyang Transformer Group"),
    ("TISCO", "Pinggao Group"),
    ("Stalprodukt", "Siemens Energy"),
    ("Stalprodukt", "Hitachi Energy"),
    ("Stalprodukt", "SGB-SMIT"),
    ("Cleveland-Cliffs", "GE Vernova"),
    ("Cleveland-Cliffs", "Eaton"),
    ("Cleveland-Cliffs", "Pennsylvania Transformer Tech"),
    ("Big River Steel", "GE Vernova"),
    ("Big River Steel", "Howard Industries"),
    ("ThyssenKrupp Electrical Steel", "Siemens Energy"),
    ("ThyssenKrupp Electrical Steel", "Hitachi Energy"),
    ("ThyssenKrupp Electrical Steel", "SGB-SMIT"),
    ("Aperam", "Schneider Electric T&D"),
    ("NLMK", "Power Machines"),
    ("Severstal", "Power Machines"),
    ("Erdemir", "BEST Transformer"),
    ("Tata Steel BSL", "BHEL"),
    ("Tata Steel BSL", "CG Power"),
    # Tap-changers → OEMs
    ("Reinhausen", "Siemens Energy"),
    ("Reinhausen", "Hitachi Energy"),
    ("Reinhausen", "GE Vernova"),
    ("Reinhausen", "SGB-SMIT"),
    ("Reinhausen", "Mitsubishi Electric"),
    ("Reinhausen", "Hyundai Electric"),
    ("Reinhausen", "Hyosung Heavy Industries"),
    ("Reinhausen", "BHEL"),
    ("Huaming Power Equipment", "TBEA"),
    ("Huaming Power Equipment", "CHINT"),
    # Bushings → OEMs
    ("ABB Bushings", "Hitachi Energy"),
    ("ABB Bushings", "Siemens Energy"),
    ("Trench Group", "Siemens Energy"),
    ("Trench Group", "GE Vernova"),
    ("Pfisterer", "Siemens Energy"),
    ("Pfisterer", "SGB-SMIT"),
    ("Yangzhou Saiyi", "TBEA"),
    ("Yangzhou Saiyi", "CHINT"),
    ("Modern Insulators", "BHEL"),
    ("Bharat Bijlee", "CG Power"),
    # Insulation → OEMs
    ("Weidmann Electrical Technology", "Siemens Energy"),
    ("Weidmann Electrical Technology", "Hitachi Energy"),
    ("Weidmann Electrical Technology", "GE Vernova"),
    ("Krempel Group", "Siemens Energy"),
    ("Felten Guilleaume", "Siemens Energy"),
    ("DuPont Nomex", "GE Vernova"),
    # Winding wire → OEMs
    ("Essex Furukawa Magnet Wire", "GE Vernova"),
    ("Essex Furukawa Magnet Wire", "Eaton"),
    ("Superior Essex", "GE Vernova"),
    ("Elektrisola", "Siemens Energy"),
    # Cable
    ("Prysmian", "Siemens Energy"),
    ("Nexans", "GE Vernova"),
    ("NKT", "Hitachi Energy"),
    ("LS Cable", "LS Electric"),
    # Oil
    ("Nynas", "Siemens Energy"),
    ("Nynas", "Hitachi Energy"),
    ("Ergon", "GE Vernova"),
    ("Apar Industries", "BHEL"),
    ("Cargill BIOTEMP", "GE Vernova"),
    ("MIDEL", "Siemens Energy"),
    # Iron ore upstream of GOES mills
    ("Vale", "Nippon Steel"),
    ("Vale", "POSCO"),
    ("BHP", "Nippon Steel"),
    ("BHP", "POSCO"),
    ("Rio Tinto", "Nippon Steel"),
    ("Rio Tinto", "JFE Steel"),
    ("Fortescue Metals", "Baosteel"),
]
for sub, tier1 in _subtier_relationships:
    EDGES.append(("SUB_TIER_OF", "Supplier", sub, "Supplier", tier1, None))

# Supplier → Supplier (ALTERNATIVE_TO) — peer manufacturers
_alternative_pairs: list[tuple[str, str]] = [
    # Big-three large-power EU/US
    ("Siemens Energy", "Hitachi Energy"),
    ("Hitachi Energy", "GE Vernova"),
    ("GE Vernova", "Siemens Energy"),
    # Tier-1 EU mid-size
    ("SGB-SMIT", "Royal SMIT Transformers"),
    ("SGB-SMIT", "Tamini"),
    ("Tamini", "Tesar"),
    ("Tesar", "Trafomec"),
    ("Schneider Electric T&D", "Ormazabal"),
    ("Imefy", "Ormazabal"),
    ("Brush Group", "Wilson Power Solutions"),
    # Korean tier-1
    ("Hyundai Electric", "Hyosung Heavy Industries"),
    ("Hyundai Electric", "Mitsubishi Electric"),
    ("Hyosung Heavy Industries", "Mitsubishi Electric"),
    ("LS Electric", "Iljin Electric"),
    ("LS Electric", "Hyundai Electric"),
    # Japanese tier-1
    ("Mitsubishi Electric", "Toshiba Energy Systems"),
    ("Toshiba Energy Systems", "Fuji Electric"),
    ("Fuji Electric", "Daihen"),
    # Chinese tier-1
    ("TBEA", "CHINT"),
    ("CHINT", "Pinggao Group"),
    ("Pinggao Group", "XJ Group"),
    ("Shenyang Transformer Group", "Wuhan Transformer"),
    ("TBEA", "Shandong Electrical Engineering"),
    # Indian tier-1
    ("CG Power", "BHEL"),
    ("BHEL", "Voltamp Transformers"),
    ("Voltamp Transformers", "Transformers and Rectifiers India"),
    ("Vijai Electricals", "Indo Tech Transformers"),
    # US tier-1
    ("Eaton", "Hubbell"),
    ("Howard Industries", "ERMCO"),
    ("Pennsylvania Transformer Tech", "Virginia Transformer"),
    ("SPX Transformer Solutions", "Delta Star"),
    ("Federal Pacific", "Pacific Crest Transformers"),
    ("Maddox Industrial Transformer", "Niagara Transformer"),
    # GOES mills
    ("Nippon Steel", "JFE Steel"),
    ("JFE Steel", "POSCO"),
    ("POSCO", "Baosteel"),
    ("Baosteel", "WISCO"),
    ("Cleveland-Cliffs", "Big River Steel"),
    ("ThyssenKrupp Electrical Steel", "Stalprodukt"),
    ("Stalprodukt", "Aperam"),
    ("NLMK", "Severstal"),
    # Bushings
    ("ABB Bushings", "Trench Group"),
    ("Trench Group", "Pfisterer"),
    # Oil
    ("Nynas", "Ergon"),
    ("Ergon", "Apar Industries"),
    ("Cargill BIOTEMP", "MIDEL"),
    # Cable
    ("Prysmian", "Nexans"),
    ("Nexans", "NKT"),
    ("LS Cable", "Sumitomo Electric"),
]
for a, b in _alternative_pairs:
    EDGES.append(("ALTERNATIVE_TO", "Supplier", a, "Supplier", b, None))
    EDGES.append(("ALTERNATIVE_TO", "Supplier", b, "Supplier", a, None))

# DemandSource → Category (DRIVES_DEMAND_FOR)
_demand_targets: dict[str, list[str]] = {
    # Hyperscalers → large + GSU
    "Microsoft Datacenter Buildout": ["Power_Transformer_Large", "Power_Transformer_GSU"],
    "Google Datacenter Buildout":    ["Power_Transformer_Large", "Power_Transformer_GSU"],
    "Amazon Datacenter Buildout":    ["Power_Transformer_Large", "Power_Transformer_GSU"],
    "Meta Datacenter Buildout":      ["Power_Transformer_Large"],
    "Oracle Cloud Buildout":         ["Power_Transformer_Large"],
    "Apple Datacenter Buildout":     ["Power_Transformer_Large"],
    "X AI Memphis Buildout":         ["Power_Transformer_Large", "Power_Transformer_GSU"],
    "CoreWeave Buildout":            ["Power_Transformer_Large"],
    "Crusoe AI Buildout":            ["Power_Transformer_Large"],
    "ByteDance Datacenter Buildout": ["Power_Transformer_Large"],
    "Tencent Datacenter Buildout":   ["Power_Transformer_Large"],
    "Alibaba Cloud Buildout":        ["Power_Transformer_Large"],
    # Colocation → large + distribution
    "Equinix Buildout":              ["Power_Transformer_Large", "Power_Transformer_Distribution"],
    "Digital Realty Buildout":       ["Power_Transformer_Large", "Power_Transformer_Distribution"],
    "QTS Realty Buildout":           ["Power_Transformer_Large"],
    "CyrusOne Buildout":             ["Power_Transformer_Large"],
    "Iron Mountain Datacenter":      ["Power_Transformer_Distribution"],
    "Vantage Data Centers":          ["Power_Transformer_Large"],
    "Aligned Data Centers":          ["Power_Transformer_Large"],
    "NTT Data Centers":              ["Power_Transformer_Large"],
    # US utilities — broad mix
    "Dominion Energy":                ["Power_Transformer_Large", "Power_Transformer_Distribution"],
    "Duke Energy":                    ["Power_Transformer_Large", "Power_Transformer_Distribution"],
    "Southern Company":               ["Power_Transformer_Large", "Power_Transformer_Distribution"],
    "NextEra Energy":                 ["Power_Transformer_Large", "Power_Transformer_GSU", "Shunt_Reactor"],
    "American Electric Power":        ["Power_Transformer_Large", "Power_Transformer_HVDC_Converter"],
    "Exelon":                         ["Power_Transformer_Distribution"],
    "FirstEnergy":                    ["Power_Transformer_Distribution"],
    "Xcel Energy":                    ["Power_Transformer_Large", "Power_Transformer_Distribution"],
    "PG&E":                           ["Power_Transformer_Distribution", "Mobile_Substation"],
    "Sempra":                         ["Power_Transformer_Distribution"],
    "Vistra Energy":                  ["Power_Transformer_GSU"],
    "Constellation Energy":           ["Power_Transformer_GSU"],
    "TVA":                            ["Power_Transformer_Large", "Power_Transformer_GSU"],
    "Bonneville Power Administration":["Power_Transformer_Large", "Shunt_Reactor"],
    # EU TSOs
    "TenneT":                        ["Power_Transformer_Large", "Power_Transformer_HVDC_Converter", "Phase_Shifting_Transformer"],
    "Amprion":                       ["Power_Transformer_Large", "Power_Transformer_HVDC_Converter"],
    "50Hertz":                       ["Power_Transformer_Large", "Power_Transformer_HVDC_Converter"],
    "TransnetBW":                    ["Power_Transformer_Large"],
    "Terna":                         ["Power_Transformer_Large", "Phase_Shifting_Transformer"],
    "Red Electrica":                 ["Power_Transformer_Large", "Shunt_Reactor"],
    "RTE France":                    ["Power_Transformer_Large", "Power_Transformer_HVDC_Converter"],
    "National Grid UK":              ["Power_Transformer_Large", "Power_Transformer_HVDC_Converter"],
    "Elia":                          ["Power_Transformer_Large"],
    "Energinet":                     ["Power_Transformer_Large", "Power_Transformer_HVDC_Converter"],
    "Fingrid":                       ["Power_Transformer_Large"],
    "Statnett":                      ["Power_Transformer_Large", "Power_Transformer_HVDC_Converter"],
    "Svenska Kraftnat":              ["Power_Transformer_Large", "Power_Transformer_HVDC_Converter"],
    "PSE Polska":                    ["Power_Transformer_Large", "Phase_Shifting_Transformer"],
    # Government programs
    "IRA Grid Modernization Program": ["Power_Transformer_Large", "Power_Transformer_HVDC_Converter", "Power_Transformer_Distribution"],
    "IIJA Infrastructure Bill":       ["Power_Transformer_Large", "Power_Transformer_Distribution", "Transformer_Repair_Refurb"],
    "REPowerEU Grid Upgrade":         ["Power_Transformer_Large", "Power_Transformer_HVDC_Converter"],
    "Great Grid Upgrade UK":          ["Power_Transformer_Large", "Power_Transformer_HVDC_Converter"],
    "India Green Grid Initiative":    ["Power_Transformer_Large", "Power_Transformer_Distribution"],
    "Saudi Vision 2030 NEOM Grid":    ["Power_Transformer_Large", "Power_Transformer_HVDC_Converter"],
    "Australia Rewiring the Nation":  ["Power_Transformer_Large"],
    # Offshore wind / renewable projects
    "Dogger Bank Wind Farm":          ["Power_Transformer_HVDC_Converter", "Power_Transformer_GSU"],
    "Hornsea Wind Farm":              ["Power_Transformer_HVDC_Converter", "Power_Transformer_GSU"],
    "ScotWind Offshore Leasing":      ["Power_Transformer_HVDC_Converter"],
    "Empire Wind":                    ["Power_Transformer_HVDC_Converter", "Power_Transformer_GSU"],
    "Coastal Virginia Offshore Wind": ["Power_Transformer_HVDC_Converter"],
    "Vineyard Wind":                  ["Power_Transformer_GSU"],
    "Revolution Wind":                ["Power_Transformer_GSU"],
    "DolWin BorWin German Offshore":  ["Power_Transformer_HVDC_Converter"],
    "North Sea Wind Power Hub":       ["Power_Transformer_HVDC_Converter"],
    # EV charging — distribution + pad-mount
    "Tesla Supercharger Network":     ["Power_Transformer_Distribution", "Distribution_Transformer_PadMount"],
    "Electrify America Buildout":     ["Distribution_Transformer_PadMount"],
    "ChargePoint Network":            ["Distribution_Transformer_PadMount"],
    "Ionity Network":                 ["Distribution_Transformer_PadMount"],
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
    from collections import Counter
    types = Counter(e[0] for e in EDGES)
    for t, n in sorted(types.items(), key=lambda x: -x[1]):
        print(f"  {t:<22} {n}")

    # Alias coverage stats
    aliased = [n for n in COMMODITIES + SUPPLIERS + PORTS if n.get("aliases")]
    total_aliases = sum(len(n["aliases"]) for n in aliased)
    print(f"\nAliases on commodities+suppliers+ports: {total_aliases}")
    print(f"Approx total searchable keyword terms: {total_aliases + NODE_COUNT}")
