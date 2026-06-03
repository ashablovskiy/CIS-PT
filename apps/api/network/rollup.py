"""Layer 1 → Layer 2 rollup mapping.

Maps specific Layer-1 entity names (actor_name in signal_actor_link) and
signal impact_type tags to Layer-2 ANT actor IDs.

Two channels:
  ENTITY_TO_L2        — direct name match from signal_actor_link.actor_name
  IMPACT_TYPE_TO_L2   — secondary channel for actors with weak L1 entity backing
                         (Trade_Policy_Regime, Geographic_Concentration)

Design rules:
  - Every entry maps to one of the 8 MVP actor IDs in actor_map.py
  - Ambiguous signals (e.g. "Demand surge" — could be AI or Grid) default to
    AI_Datacenter_Demand since that's the larger and more active queue driver;
    refined later with more signal volume
  - Country-level entities map to Geographic_Concentration
  - Port / Lane entities map to Heavy_Lift_Logistics
"""

from __future__ import annotations

# ── Entity-name → L2 actor ────────────────────────────────────────────────────

ENTITY_TO_L2: dict[str, str] = {

    # ── OEM_Production_Capacity ────────────────────────────────────────────
    "Hitachi Energy":              "OEM_Production_Capacity",
    "Siemens Energy":              "OEM_Production_Capacity",
    "GE Vernova":                  "OEM_Production_Capacity",
    "Hyundai Electric":            "OEM_Production_Capacity",
    "Hyosung Heavy Industries":    "OEM_Production_Capacity",
    "Mitsubishi Electric":         "OEM_Production_Capacity",
    "WEG":                         "OEM_Production_Capacity",
    "TBEA":                        "OEM_Production_Capacity",
    "SGB-SMIT":                    "OEM_Production_Capacity",
    "CG Power":                    "OEM_Production_Capacity",
    "Toshiba Energy Systems":      "OEM_Production_Capacity",
    "ABB":                         "OEM_Production_Capacity",
    "Eaton":                       "OEM_Production_Capacity",
    "Hubbell":                     "OEM_Production_Capacity",
    "nVent Electric":              "OEM_Production_Capacity",
    "Vertiv":                      "OEM_Production_Capacity",
    "Quanta Services":             "OEM_Production_Capacity",
    # Categories (transformer types) also count as OEM capacity signals
    "Power_Transformer_Large":     "OEM_Production_Capacity",
    "Generator_StepUp_GSU":        "OEM_Production_Capacity",
    "HVDC_Converter_Transformer":  "OEM_Production_Capacity",
    "Data_Center_Transformer":     "OEM_Production_Capacity",
    "Autotransformer":             "OEM_Production_Capacity",

    # ── Critical_Components ───────────────────────────────────────────────
    "Reinhausen":                  "Critical_Components",
    "Maschinenfabrik Reinhausen":  "Critical_Components",
    "Trench Group":                "Critical_Components",
    "Trench":                      "Critical_Components",
    "HSP":                         "Critical_Components",
    "OLTC_Assembly":               "Critical_Components",
    "Bushing_RIP":                 "Critical_Components",
    "Bushing_RIS":                 "Critical_Components",
    "Bushing_OIP_Porcelain":       "Critical_Components",

    # ── Heavy_Lift_Logistics (ports) ──────────────────────────────────────
    "Busan":                       "Heavy_Lift_Logistics",
    "Ulsan":                       "Heavy_Lift_Logistics",
    "Gwangyang":                   "Heavy_Lift_Logistics",
    "Masan":                       "Heavy_Lift_Logistics",
    "Kobe":                        "Heavy_Lift_Logistics",
    "Yokohama":                    "Heavy_Lift_Logistics",
    "Nagoya":                      "Heavy_Lift_Logistics",
    "Shanghai":                    "Heavy_Lift_Logistics",
    "Tianjin":                     "Heavy_Lift_Logistics",
    "Mundra":                      "Heavy_Lift_Logistics",
    "Nhava Sheva":                 "Heavy_Lift_Logistics",
    "Hamburg":                     "Heavy_Lift_Logistics",
    "Bremerhaven":                 "Heavy_Lift_Logistics",
    "Antwerp":                     "Heavy_Lift_Logistics",
    "Rotterdam":                   "Heavy_Lift_Logistics",
    "Genoa":                       "Heavy_Lift_Logistics",
    "Gothenburg":                  "Heavy_Lift_Logistics",
    "Bilbao":                      "Heavy_Lift_Logistics",
    "Leixoes":                     "Heavy_Lift_Logistics",
    "Houston":                     "Heavy_Lift_Logistics",
    "Norfolk":                     "Heavy_Lift_Logistics",
    "Savannah":                    "Heavy_Lift_Logistics",
    "New Orleans":                 "Heavy_Lift_Logistics",
    "Montreal":                    "Heavy_Lift_Logistics",
    "Manzanillo":                  "Heavy_Lift_Logistics",
    "Itajai":                      "Heavy_Lift_Logistics",
    # Heavy_Lift_Logistics (lanes)
    "Korea_USEC":                  "Heavy_Lift_Logistics",
    "Korea_USWC":                  "Heavy_Lift_Logistics",
    "Korea_USGulf":                "Heavy_Lift_Logistics",
    "Korea_EU":                    "Heavy_Lift_Logistics",
    "Japan_USEC":                  "Heavy_Lift_Logistics",
    "Japan_USWC":                  "Heavy_Lift_Logistics",
    "China_USEC":                  "Heavy_Lift_Logistics",
    "China_EU":                    "Heavy_Lift_Logistics",
    "EU_USEC":                     "Heavy_Lift_Logistics",
    "EU_USGulf":                   "Heavy_Lift_Logistics",
    "India_USEC":                  "Heavy_Lift_Logistics",
    "LATAM_USEC":                  "Heavy_Lift_Logistics",
    "Mexico_USGulf":               "Heavy_Lift_Logistics",
    "Brazil_USEC":                 "Heavy_Lift_Logistics",
    "Russia_EU":                   "Heavy_Lift_Logistics",
    # Commodity proxy
    "Heavy_Lift_Freight":          "Heavy_Lift_Logistics",

    # ── Geographic_Concentration (oem_hub + goes_producer countries) ──────
    "South Korea":                 "Geographic_Concentration",
    "Japan":                       "Geographic_Concentration",
    "China":                       "Geographic_Concentration",
    "Germany":                     "Geographic_Concentration",
    "India":                       "Geographic_Concentration",
    "France":                      "Geographic_Concentration",
    "Poland":                      "Geographic_Concentration",
    "Sweden":                      "Geographic_Concentration",

    # ── AI_Datacenter_Demand (hyperscalers + DC builders) ─────────────────
    "Data_Center_AI_Demand":       "AI_Datacenter_Demand",
    "Microsoft":                   "AI_Datacenter_Demand",
    "Microsoft Datacenter Buildout": "AI_Datacenter_Demand",
    "Google":                      "AI_Datacenter_Demand",
    "Google Datacenter Buildout":  "AI_Datacenter_Demand",
    "Amazon":                      "AI_Datacenter_Demand",
    "Amazon Datacenter Buildout":  "AI_Datacenter_Demand",
    "Meta":                        "AI_Datacenter_Demand",
    "Meta Datacenter Buildout":    "AI_Datacenter_Demand",
    "OpenAI":                      "AI_Datacenter_Demand",
    "OpenAI / Stargate Buildout":  "AI_Datacenter_Demand",
    "Anthropic":                   "AI_Datacenter_Demand",
    "Anthropic Compute Buildout":  "AI_Datacenter_Demand",
    "Oracle":                      "AI_Datacenter_Demand",
    "Oracle / OCI Buildout":       "AI_Datacenter_Demand",
    "CoreWeave":                   "AI_Datacenter_Demand",
    "CoreWeave Buildout":          "AI_Datacenter_Demand",
    "Vantage":                     "AI_Datacenter_Demand",
    "Vantage Data Centers Buildout": "AI_Datacenter_Demand",
    "QTS":                         "AI_Datacenter_Demand",
    "QTS / Blackstone Buildout":   "AI_Datacenter_Demand",
    "Switch":                      "AI_Datacenter_Demand",
    "Switch Buildout":             "AI_Datacenter_Demand",
    "Crusoe":                      "AI_Datacenter_Demand",
    "Crusoe Energy Buildout":      "AI_Datacenter_Demand",
    "Digital Realty":              "AI_Datacenter_Demand",
    "Digital Realty Buildout":     "AI_Datacenter_Demand",
    "Equinix":                     "AI_Datacenter_Demand",
    "Equinix Buildout":            "AI_Datacenter_Demand",

    # ── Grid_Modernization_Demand ─────────────────────────────────────────
    "Grid_Replacement_Aging":          "Grid_Modernization_Demand",
    "Renewable_Interconnection":       "Grid_Modernization_Demand",
    "Electrification":                 "Grid_Modernization_Demand",
    "Offshore_Wind_Buildout":          "Grid_Modernization_Demand",
    "Solar_Farm_Interconnection":      "Grid_Modernization_Demand",
    "Utility_Grid_Modernization":      "Grid_Modernization_Demand",

    # ── Energy_Transition_Policy ──────────────────────────────────────────
    "IRA_Grid_Investment":         "Energy_Transition_Policy",
    "REPowerEU":                   "Energy_Transition_Policy",
    "Nuclear_Restart":             "Energy_Transition_Policy",
    "EU_Green_Deal":               "Energy_Transition_Policy",
    "Saudi_Vision_2030_Grid":      "Energy_Transition_Policy",
}

# ── Impact-type tag → L2 actor ────────────────────────────────────────────────
# Secondary channel — used when a signal has no direct L1 entity match.
# Also used to supplement entity-match pressure (additive, lower weight).

IMPACT_TYPE_TO_L2: dict[str, str] = {
    "OEM capacity":        "OEM_Production_Capacity",
    "OEM disruption":      "OEM_Production_Capacity",
    "Sub-tier supplier":   "Critical_Components",      # component supplier
    "Lane disruption":     "Heavy_Lift_Logistics",
    "Demand surge":        "AI_Datacenter_Demand",     # default; Grid added via entity match
    "Regulatory / trade":  "Trade_Policy_Regime",
    "Macro proxy":         None,                        # not mapped — too diffuse
    "GOES input cost":     "OEM_Production_Capacity",  # indirect cost pressure on OEM
    "Winding metal cost":  "OEM_Production_Capacity",  # copper cost → OEM margin/backlog
    "Insulation material": "OEM_Production_Capacity",  # similar
    "No TP impact":        None,                        # discarded
}

# Weight multiplier for the impact-type channel relative to entity-match pressure
IMPACT_TYPE_WEIGHT_FACTOR = 0.4


def entity_to_l2(entity_name: str) -> str | None:
    """Return the Layer-2 actor ID for a Layer-1 entity name, or None."""
    return ENTITY_TO_L2.get(entity_name)


def impact_type_to_l2(impact_type: str | None) -> str | None:
    """Return the Layer-2 actor ID for a signal impact_type, or None."""
    if not impact_type:
        return None
    return IMPACT_TYPE_TO_L2.get(impact_type)
