"""Training data extraction for DSPy MIPROv2 optimization.

Two data sources (merged at compile time):
  1. Feedback-accepted assessments — strongest signal (analyst confirmed correct)
  2. Bootstrap examples — hand-crafted golden scenarios covering all 5 event classes
     Used when feedback table is sparse (< 10 accepted rows).

Each DSPy Example contains the synthesizer's input fields + expected outputs,
mirroring the ImpactAssessment Signature exactly.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import dspy
from sqlalchemy import select

from apps.api.db.models import Assessment, Signal
from apps.api.db.session import async_session_factory

logger = logging.getLogger(__name__)


# ── Bootstrap examples (hand-crafted, event-class coverage) ──────────────────
# These ensure MIPROv2 always has something to work with, even before analyst
# feedback accumulates. Quality bar: specific entities, concrete clause analysis.

BOOTSTRAP_EXAMPLES: list[dspy.Example] = [

    # 1. Commodity price move — aluminum decline, indexation trigger
    dspy.Example(
        signal_summary=(
            "source=prices | ticker=ALI=F | price_moves={'1d': '-7.4%', '5d': '-4.7%'} | "
            "label=Aluminum futures decline — Al_Winding_Strip input cost reduction"
        ),
        graph_context=json.dumps([{
            "commodity": "Aluminum",
            "affected_suppliers": ["Siemens Energy", "Hitachi Energy", "GE Vernova", "Eaton"],
            "affected_plants": ["Siemens Nuremberg", "Siemens Weiz", "Hitachi Bad Honnef",
                                "Hitachi Vaasa", "GE Vernova Pittsburgh"],
            "affected_lanes": ["EU_USEC", "Korea_USEC"],
        }]),
        similar_past=json.dumps([]),
        contract_clauses=json.dumps([
            {"contract_id": "CIS-2026-006", "clause_type": "indexation",
             "parsed_params": {"trigger_threshold_pct": 0, "weights": {"Aluminum": 0.35}},
             "text": "Price adjustments quarterly; aluminum weighted 35% of basket."},
            {"contract_id": "CIS-2026-001", "clause_type": "indexation",
             "parsed_params": {"trigger_threshold_pct": 3, "weights": {"Aluminum": 0.20}},
             "text": "Indexation triggered when any basket component moves >3%."},
        ]),
        event_class="commodity_price_move",
        impact_dimensions="price, availability",
        # ── Expected outputs ──
        summary=(
            "CME Aluminum futures declined 7.4% (1-day) and 4.7% (5-day), "
            "triggering quarterly price-adjustment clauses in the Eaton CIS-2026-006 "
            "contract (35% aluminum weight, no threshold) and GE Vernova CIS-2026-001 "
            "(20% aluminum weight, 3% threshold now crossed). Expected procurement cost "
            "reduction of 1.5–2.6% on aluminum-indexed contract lines across Siemens Energy, "
            "Hitachi Energy, GE Vernova, and Eaton supply agreements."
        ),
        affected_entities_json=json.dumps({
            "suppliers": ["Siemens Energy", "Hitachi Energy", "GE Vernova", "Eaton"],
            "plants": ["Siemens Nuremberg", "Siemens Weiz", "Hitachi Bad Honnef",
                       "Hitachi Vaasa", "GE Vernova Pittsburgh"],
            "ports": ["Hamburg", "Bremerhaven", "Antwerp"],
            "commodities": ["Aluminum", "Al_Winding_Strip"],
        }),
        affected_clauses_json=json.dumps([
            {"contract_id": "CIS-2026-006", "clause_type": "indexation",
             "triggered": True,
             "detail": "0% threshold — all movements pass through at 35% weight. "
                       "Quarterly recalculation due; estimated -2.6% on aluminum line."},
            {"contract_id": "CIS-2026-001", "clause_type": "indexation",
             "triggered": True,
             "detail": "7.4% > 3% trigger threshold. Aluminum weighted 20%. "
                       "Estimated -1.5% on aluminum line at next review."},
        ]),
        impact_json=json.dumps({
            "price": {"direction": "decrease", "magnitude_pct": "1.5-2.6",
                      "confidence": 0.82,
                      "detail": "Eaton: 35% × 7.4% = -2.6%. GE Vernova: 20% × 7.4% = -1.5%."},
            "availability": {"direction": "neutral", "magnitude_pct": 0, "confidence": 0.9},
            "lead_time":    {"direction": "neutral", "magnitude_pct": 0, "confidence": 0.9},
            "logistics":    {"direction": "neutral", "magnitude_pct": 0, "confidence": 0.9},
            "regulatory":   {"direction": "neutral", "magnitude_pct": 0, "confidence": 0.9},
            "demand":       {"direction": "neutral", "magnitude_pct": 0, "confidence": 0.9},
        }),
        reasoning_chain_json=json.dumps([
            {"step": 1, "claim": "ALI=F declined 7.4% in 1 day and 4.7% over 5 days",
             "grounded_in": {"source": "prices signal: moves_pct={'1d':'-7.4%','5d':'-4.7%'}"},
             "inference": "Significant short-term aluminum price decline confirmed by futures data"},
            {"step": 2, "claim": "Eaton CIS-2026-006 has zero trigger threshold at 35% aluminum weight",
             "grounded_in": {"source": "contract_clauses: CIS-2026-006 parsed_params.trigger_threshold_pct=0"},
             "inference": "All price movements pass through immediately; quarterly recalculation triggered"},
            {"step": 3, "claim": "GE Vernova CIS-2026-001 threshold (3%) exceeded by 7.4% move",
             "grounded_in": {"source": "contract_clauses: CIS-2026-001 parsed_params.trigger_threshold_pct=3"},
             "inference": "Indexation clause activated; 20% aluminum weight yields ~-1.5% cost reduction"},
            {"step": 4, "claim": "Five plants across four suppliers use Al_Winding_Strip",
             "grounded_in": {"source": "graph_context: affected_plants and affected_suppliers"},
             "inference": "Cost reduction flows to procurement for all active transformer orders at these plants"},
        ]),
        confidence=0.82,
    ).with_inputs("signal_summary", "graph_context", "similar_past",
                  "contract_clauses", "event_class", "impact_dimensions"),

    # 2. Supplier capacity — copper constraint, multiple OEMs
    dspy.Example(
        signal_summary=(
            "source=gdelt | signal_type=supplier_capacity | "
            "summary=Major copper refinery curtailment affects transformer winding strip supply; "
            "Siemens Energy and Hitachi Energy issue allocation notices | "
            "commodities=['Copper', 'Cu_Winding_Strip']"
        ),
        graph_context=json.dumps([{
            "commodity": "Copper",
            "affected_suppliers": ["Siemens Energy", "Hitachi Energy", "GE Vernova"],
            "affected_plants": ["Siemens Nuremberg", "Siemens Charlotte",
                                "Hitachi Bad Honnef", "Hitachi Ludvika", "GE Vernova Pittsburgh"],
            "alternative_suppliers": ["ABB", "Transformers & Rectifiers India"],
            "sub_tier_at_risk": ["Codelco", "Aurubis", "Freeport-McMoRan"],
        }]),
        similar_past=json.dumps([]),
        contract_clauses=json.dumps([
            {"contract_id": "CIS-2026-002", "clause_type": "slot",
             "parsed_params": {"slots_per_quarter": 3, "notice_days": 60},
             "text": "Supplier shall reserve 3 delivery slots per quarter with 60 days notice."},
            {"contract_id": "CIS-2026-003", "clause_type": "force_majeure",
             "parsed_params": {"force_majeure_events": ["commodity shortage", "supplier insolvency"]},
             "text": "Force majeure includes commodity shortage affecting production capacity."},
        ]),
        event_class="supplier_capacity",
        impact_dimensions="availability, lead_time, price",
        summary=(
            "A copper refinery curtailment is constraining Cu_Winding_Strip supply to three major "
            "power transformer OEMs — Siemens Energy, Hitachi Energy, and GE Vernova — across five "
            "manufacturing plants in Germany, Sweden, and the US. Allocation notices signal a 10–25% "
            "reduction in available winding strip. The CIS-2026-002 slot clause is at risk of "
            "breach if Siemens cannot fulfill quarterly reservation commitments; the CIS-2026-003 "
            "force majeure clause may provide relief if curtailment is certified as a commodity shortage."
        ),
        affected_entities_json=json.dumps({
            "suppliers": ["Siemens Energy", "Hitachi Energy", "GE Vernova"],
            "plants": ["Siemens Nuremberg", "Siemens Charlotte",
                       "Hitachi Bad Honnef", "Hitachi Ludvika", "GE Vernova Pittsburgh"],
            "ports": ["Hamburg", "Bremerhaven", "Savannah"],
            "commodities": ["Copper", "Cu_Winding_Strip"],
        }),
        affected_clauses_json=json.dumps([
            {"contract_id": "CIS-2026-002", "clause_type": "slot",
             "triggered": True,
             "detail": "3 slots/quarter commitment at 60-day notice. Allocation constraints "
                       "may prevent Siemens from honoring slot reservations; breach risk rising."},
            {"contract_id": "CIS-2026-003", "clause_type": "force_majeure",
             "triggered": False,
             "detail": "'Commodity shortage' is listed as force majeure event. Not yet triggered — "
                       "requires formal certification of shortage; monitor for official curtailment notice."},
        ]),
        impact_json=json.dumps({
            "price":        {"direction": "increase", "magnitude_pct": "5-15", "confidence": 0.65,
                             "detail": "Copper supply tightening typically adds 5-15% to Cu_Winding_Strip cost"},
            "availability": {"direction": "decrease",  "magnitude_pct": "10-25", "confidence": 0.75,
                             "detail": "Allocation notices suggest 10-25% reduction at affected plants"},
            "lead_time":    {"direction": "increase",  "magnitude_pct": None,   "confidence": 0.70,
                             "detail": "Estimated +4-10 weeks on new copper-wound transformer orders"},
            "logistics":    {"direction": "neutral",   "magnitude_pct": 0,      "confidence": 0.80},
            "regulatory":   {"direction": "neutral",   "magnitude_pct": 0,      "confidence": 0.85},
            "demand":       {"direction": "neutral",   "magnitude_pct": 0,      "confidence": 0.80},
        }),
        reasoning_chain_json=json.dumps([
            {"step": 1,
             "claim": "Copper refinery curtailment confirmed with allocation notices from Siemens Energy and Hitachi Energy",
             "grounded_in": {"source": "signal summary: allocation notices issued by two major OEMs"},
             "inference": "Supply disruption is material and multi-supplier, not isolated"},
            {"step": 2,
             "claim": "Five plants across three OEMs depend on Cu_Winding_Strip from affected sub-tier suppliers",
             "grounded_in": {"source": "graph_context: sub_tier_at_risk=[Codelco, Aurubis, Freeport-McMoRan]"},
             "inference": "Geographic spread of plants indicates systemic constraint, not regional"},
            {"step": 3,
             "claim": "CIS-2026-002 slot clause requires 3 deliveries/quarter with 60-day notice",
             "grounded_in": {"source": "contract_clauses: CIS-2026-002 parsed_params.slots_per_quarter=3"},
             "inference": "Allocation constraints may prevent Siemens from meeting slot commitments; breach risk escalating"},
            {"step": 4,
             "claim": "'Commodity shortage' is enumerated as force majeure in CIS-2026-003",
             "grounded_in": {"source": "contract_clauses: CIS-2026-003 parsed_params.force_majeure_events"},
             "inference": "Force majeure relief possible but requires formal certification — not yet triggered"},
        ]),
        confidence=0.72,
    ).with_inputs("signal_summary", "graph_context", "similar_past",
                  "contract_clauses", "event_class", "impact_dimensions"),

    # 3. Demand surge — hyperscaler datacenter buildout
    dspy.Example(
        signal_summary=(
            "source=demand | signal_type=demand_surge | "
            "company=Microsoft | title=Microsoft announces 2 GW datacenter campus in Virginia | "
            "summary=Microsoft breaks ground on 2 GW AI datacenter campus requiring 15+ GSU "
            "transformers and 40+ medium power transformers; RFQ process launching Q3"
        ),
        graph_context=json.dumps([{
            "demand_source": "Microsoft",
            "category": "Hyperscaler",
            "transformer_types_needed": ["Power_Transformer_Large", "GSU"],
            "competing_demand": ["Google", "Amazon", "Meta"],
            "affected_suppliers": ["Siemens Energy", "Hitachi Energy", "GE Vernova"],
        }]),
        similar_past=json.dumps([]),
        contract_clauses=json.dumps([
            {"contract_id": "CIS-2026-001", "clause_type": "slot",
             "parsed_params": {"slots_per_quarter": 4, "notice_days": 90},
             "text": "GE Vernova reserves 4 delivery slots per quarter. 90-day advance notice required."},
            {"contract_id": "CIS-2026-004", "clause_type": "delivery_obligation",
             "parsed_params": {"lead_time_weeks": 52, "penalty_per_week_usd": 50000},
             "text": "Delivery obligations: 52-week lead time. Delay penalty $50K/week."},
        ]),
        event_class="demand_surge",
        impact_dimensions="availability, lead_time, demand",
        summary=(
            "Microsoft's 2 GW Virginia datacenter campus creates immediate demand for 15+ GSU and "
            "40+ medium power transformers, compounding existing hyperscaler backlog from Google, "
            "Amazon, and Meta. Siemens Energy, Hitachi Energy, and GE Vernova manufacturing slots "
            "are likely to be fully committed 18–24 months forward. The GE Vernova CIS-2026-001 "
            "slot clause (4 slots/quarter, 90-day notice) and delivery obligation clause "
            "(52-week lead time, $50K/week penalty) require immediate review to protect allocation priority."
        ),
        affected_entities_json=json.dumps({
            "suppliers": ["Siemens Energy", "Hitachi Energy", "GE Vernova"],
            "plants": ["GE Vernova Pittsburgh", "GE Vernova Memphis",
                       "Siemens Charlotte", "Hitachi South Boston"],
            "ports": ["Norfolk", "Savannah", "Houston"],
            "commodities": ["Power_Transformer_Large", "GSU"],
        }),
        affected_clauses_json=json.dumps([
            {"contract_id": "CIS-2026-001", "clause_type": "slot",
             "triggered": True,
             "detail": "Demand surge may exhaust available slots within current 90-day notice window. "
                       "4 slots/quarter is insufficient for 40+ transformer RFQ. Escalate to supplier."},
            {"contract_id": "CIS-2026-004", "clause_type": "delivery_obligation",
             "triggered": False,
             "detail": "52-week lead time not yet breached, but backlog pressure makes on-time "
                       "delivery at risk within 2 quarters. $50K/week penalty clause creates urgency."},
        ]),
        impact_json=json.dumps({
            "price":        {"direction": "increase",  "magnitude_pct": "3-8",  "confidence": 0.60,
                             "detail": "Tight capacity allows suppliers to push spot prices up 3-8%"},
            "availability": {"direction": "decrease",  "magnitude_pct": "20-40", "confidence": 0.75,
                             "detail": "Slot availability likely to drop 20-40% within 6 months"},
            "lead_time":    {"direction": "increase",  "magnitude_pct": None,   "confidence": 0.80,
                             "detail": "Current 52-week standard lead time likely to extend 18-24 months"},
            "logistics":    {"direction": "neutral",   "magnitude_pct": 0,      "confidence": 0.70},
            "regulatory":   {"direction": "neutral",   "magnitude_pct": 0,      "confidence": 0.85},
            "demand":       {"direction": "increase",  "magnitude_pct": "15-25", "confidence": 0.85,
                             "detail": "2 GW campus is incremental to existing 12 GW hyperscaler pipeline"},
        }),
        reasoning_chain_json=json.dumps([
            {"step": 1,
             "claim": "Microsoft 2 GW campus requires 15+ GSU and 40+ medium transformers",
             "grounded_in": {"source": "demand signal: title and summary with specific MW and unit counts"},
             "inference": "Concrete procurement requirement, not speculative; RFQ launching Q3 confirms urgency"},
            {"step": 2,
             "claim": "Google, Amazon, Meta represent competing hyperscaler demand drawing on same OEM capacity",
             "grounded_in": {"source": "graph_context: competing_demand=[Google, Amazon, Meta]"},
             "inference": "Market-wide slot shortage rather than isolated Microsoft impact"},
            {"step": 3,
             "claim": "GE Vernova CIS-2026-001 allows only 4 slots/quarter with 90-day advance notice",
             "grounded_in": {"source": "contract_clauses: CIS-2026-001 parsed_params.slots_per_quarter=4"},
             "inference": "Existing slot allocation insufficient for 40+ unit RFQ; immediate notice required"},
            {"step": 4,
             "claim": "CIS-2026-004 imposes $50K/week delivery delay penalty on 52-week lead time",
             "grounded_in": {"source": "contract_clauses: CIS-2026-004 parsed_params.penalty_per_week_usd=50000"},
             "inference": "Backlog pressure materially increases delivery risk; financial exposure rising"},
        ]),
        confidence=0.75,
    ).with_inputs("signal_summary", "graph_context", "similar_past",
                  "contract_clauses", "event_class", "impact_dimensions"),

    # 4. Logistics disruption — Busan port congestion
    dspy.Example(
        signal_summary=(
            "source=logistics | signal_type=logistics_disruption | "
            "title=Busan port congestion: 8-day vessel queues amid Korean labor action | "
            "summary=Korea's largest port reports 8-day waiting times for bulk cargo vessels "
            "following dock worker strike. Transformer shipments from Korean OEMs affected."
        ),
        graph_context=json.dumps([{
            "port": "Busan",
            "affected_lanes": ["Korea_USEC", "Korea_USGC"],
            "affected_suppliers": ["Hyundai Heavy Industries", "LS Electric"],
            "alternative_ports": ["Incheon", "Gwangyang"],
            "typical_transit_days": 28,
        }]),
        similar_past=json.dumps([]),
        contract_clauses=json.dumps([
            {"contract_id": "CIS-2026-005", "clause_type": "incoterms",
             "parsed_params": {"incoterm": "CIF", "port_of_loading": "Busan"},
             "text": "Delivery CIF Busan. Risk transfers at port of loading."},
            {"contract_id": "CIS-2026-007", "clause_type": "ld",
             "parsed_params": {"delay_threshold_days": 14, "ld_rate_pct_per_week": 0.5},
             "text": "Liquidated damages of 0.5% per week for delays exceeding 14 days."},
            {"contract_id": "CIS-2026-007", "clause_type": "force_majeure",
             "parsed_params": {"force_majeure_events": ["port closure", "labor strike"]},
             "text": "Labor strikes at named port of loading constitute force majeure."},
        ]),
        event_class="logistics_disruption",
        impact_dimensions="lead_time, logistics, availability",
        summary=(
            "An 8-day vessel queue at Busan port from a Korean dock worker strike is disrupting "
            "transformer shipments on the Korea_USEC and Korea_USGC lanes. CIF contracts "
            "(CIS-2026-005) transfer risk at loading — buyer bears congestion delay costs. "
            "The 14-day LD threshold in CIS-2026-007 is at risk of breach within one week "
            "if congestion persists, though the force majeure clause ('labor strike') should "
            "provide relief. Alternative routing via Incheon or Gwangyang is possible but "
            "adds 3–5 transit days and additional cost."
        ),
        affected_entities_json=json.dumps({
            "suppliers": ["Hyundai Heavy Industries", "LS Electric"],
            "plants": [],
            "ports": ["Busan", "Incheon", "Gwangyang"],
            "commodities": ["Power_Transformer_Large", "Power_Transformer_Medium"],
        }),
        affected_clauses_json=json.dumps([
            {"contract_id": "CIS-2026-005", "clause_type": "incoterms",
             "triggered": True,
             "detail": "CIF Busan: buyer bears risk from port of loading. 8-day delay costs "
                       "fall on buyer. Consider renegotiating to CIP with alternative loading port."},
            {"contract_id": "CIS-2026-007", "clause_type": "ld",
             "triggered": False,
             "detail": "14-day threshold not yet breached (8 days elapsed). Breach imminent "
                       "if congestion extends past day 14. LD rate: 0.5%/week of contract value."},
            {"contract_id": "CIS-2026-007", "clause_type": "force_majeure",
             "triggered": True,
             "detail": "'Labor strike' explicitly listed as force majeure event. Supplier "
                       "should issue FM notice to suspend LD clock. Obtain port authority certification."},
        ]),
        impact_json=json.dumps({
            "price":        {"direction": "neutral",   "magnitude_pct": 0,     "confidence": 0.85},
            "availability": {"direction": "decrease",  "magnitude_pct": None,  "confidence": 0.70,
                             "detail": "Korea-origin transformers delayed; limited spot availability"},
            "lead_time":    {"direction": "increase",  "magnitude_pct": None,  "confidence": 0.90,
                             "detail": "+8 days minimum; +11-13 days via alternate port routing"},
            "logistics":    {"direction": "disrupted", "magnitude_pct": None,  "confidence": 0.92,
                             "detail": "Korea_USEC and Korea_USGC lanes impacted; Busan is primary hub"},
            "regulatory":   {"direction": "neutral",   "magnitude_pct": 0,     "confidence": 0.85},
            "demand":       {"direction": "neutral",   "magnitude_pct": 0,     "confidence": 0.85},
        }),
        reasoning_chain_json=json.dumps([
            {"step": 1,
             "claim": "8-day vessel queue at Busan due to dock worker strike",
             "grounded_in": {"source": "logistics signal: title and summary — 8-day waiting times"},
             "inference": "Material disruption to Korea-origin shipments; not a minor delay"},
            {"step": 2,
             "claim": "CIS-2026-005 is CIF Busan — risk transfers at loading, buyer bears congestion costs",
             "grounded_in": {"source": "contract_clauses: CIS-2026-005 parsed_params.incoterm=CIF"},
             "inference": "Buyer absorbs 8+ days of demurrage and storage costs at Busan"},
            {"step": 3,
             "claim": "CIS-2026-007 LD clause triggers at 14-day delay threshold",
             "grounded_in": {"source": "contract_clauses: CIS-2026-007 parsed_params.delay_threshold_days=14"},
             "inference": "6 days remaining before LD clock activates at 0.5%/week — imminent breach risk"},
            {"step": 4,
             "claim": "'Labor strike' is explicitly listed as force majeure in CIS-2026-007",
             "grounded_in": {"source": "contract_clauses: CIS-2026-007 parsed_params.force_majeure_events"},
             "inference": "FM notice suspends LD clock; supplier must obtain port authority certification urgently"},
        ]),
        confidence=0.85,
    ).with_inputs("signal_summary", "graph_context", "similar_past",
                  "contract_clauses", "event_class", "impact_dimensions"),

    # 5. Regulatory / trade — GOES export control
    dspy.Example(
        signal_summary=(
            "source=gdelt | signal_type=regulatory_trade | "
            "title=US Commerce Dept expands GOES export restrictions to additional countries | "
            "summary=New EAR controls on grain-oriented electrical steel require export license "
            "for shipments to 12 additional countries. Effective 60 days from publication."
        ),
        graph_context=json.dumps([{
            "commodity": "GOES",
            "affected_countries": ["India", "Vietnam", "Thailand", "Malaysia"],
            "affected_suppliers": ["Cogent Power", "Nippon Steel", "JFE Steel", "POSCO"],
            "affected_plants": ["Siemens Nuremberg", "Hitachi Bad Honnef"],
            "us_producers": ["AK Steel (Cleveland-Cliffs)", "ATI Metals"],
        }]),
        similar_past=json.dumps([]),
        contract_clauses=json.dumps([
            {"contract_id": "CIS-2026-008", "clause_type": "indexation",
             "parsed_params": {"trigger_threshold_pct": 5, "weights": {"GOES": 0.40}},
             "text": "GOES steel weighted 40% in price adjustment formula. Trigger: 5% move."},
            {"contract_id": "CIS-2026-003", "clause_type": "force_majeure",
             "parsed_params": {"force_majeure_events": ["government regulation", "export control"]},
             "text": "Force majeure includes new government export controls affecting supply."},
        ]),
        event_class="regulatory_trade",
        impact_dimensions="price, availability, regulatory",
        summary=(
            "New US Commerce Dept GOES export controls (EAR) covering 12 countries will restrict "
            "supply from Cogent Power, Nippon Steel, JFE Steel, and POSCO to EU/US transformer "
            "plants within 60 days. The 40% GOES weighting in CIS-2026-008 indexation clause "
            "creates a trigger risk if supply restriction drives >5% price increase. Force majeure "
            "clause (CIS-2026-003) covers 'export controls' — both parties may invoke it to "
            "renegotiate delivery schedules. Immediate action: identify US domestic GOES sources "
            "(Cleveland-Cliffs, ATI Metals) as substitutes."
        ),
        affected_entities_json=json.dumps({
            "suppliers": ["Cogent Power", "Nippon Steel", "JFE Steel", "POSCO"],
            "plants": ["Siemens Nuremberg", "Hitachi Bad Honnef"],
            "ports": ["Rotterdam", "Antwerp", "Hamburg"],
            "commodities": ["GOES", "GOES_M3_Grade"],
        }),
        affected_clauses_json=json.dumps([
            {"contract_id": "CIS-2026-008", "clause_type": "indexation",
             "triggered": False,
             "detail": "5% trigger not yet breached — export controls announced but not effective for 60 days. "
                       "Monitor GOES spot price; 40% weight means a 12.5% price rise hits the trigger. "
                       "Historical supply restrictions have caused 10-20% GOES price spikes."},
            {"contract_id": "CIS-2026-003", "clause_type": "force_majeure",
             "triggered": True,
             "detail": "'Export control' explicitly listed. Either party may invoke FM to extend "
                       "delivery schedules by the period of supply disruption (typically 90-day cap)."},
        ]),
        impact_json=json.dumps({
            "price":        {"direction": "increase",  "magnitude_pct": "5-20", "confidence": 0.70,
                             "detail": "Supply restriction to OECD markets historically drives 5-20% GOES premium"},
            "availability": {"direction": "decrease",  "magnitude_pct": "15-30", "confidence": 0.75,
                             "detail": "Restricted-country GOES suppliers represent ~30% of EU transformer input"},
            "lead_time":    {"direction": "increase",  "magnitude_pct": None,   "confidence": 0.65,
                             "detail": "License processing 30-60 days adds to lead time if licenses pursued"},
            "logistics":    {"direction": "neutral",   "magnitude_pct": 0,      "confidence": 0.75},
            "regulatory":   {"direction": "restricted", "magnitude_pct": None,  "confidence": 0.92,
                             "detail": "New EAR controls effective in 60 days; compliance review required"},
            "demand":       {"direction": "neutral",   "magnitude_pct": 0,      "confidence": 0.80},
        }),
        reasoning_chain_json=json.dumps([
            {"step": 1,
             "claim": "US Commerce Dept EAR controls on GOES effective 60 days from publication for 12 countries",
             "grounded_in": {"source": "regulatory signal: title and summary — specific timeline and scope"},
             "inference": "Hard deadline creates procurement urgency; pre-control inventory build possible"},
            {"step": 2,
             "claim": "Cogent Power, Nippon Steel, JFE Steel, POSCO are primary GOES suppliers to EU transformer plants",
             "grounded_in": {"source": "graph_context: affected_suppliers list"},
             "inference": "Export restriction directly impacts ~40% of EU transformer core steel supply"},
            {"step": 3,
             "claim": "CIS-2026-008 GOES indexation trigger is 5% with 40% basket weight",
             "grounded_in": {"source": "contract_clauses: CIS-2026-008 parsed_params.trigger_threshold_pct=5, weights.GOES=0.40"},
             "inference": "A 12.5% GOES price increase (plausible under supply restriction) hits the indexation trigger"},
            {"step": 4,
             "claim": "'Export control' is listed as force majeure in CIS-2026-003",
             "grounded_in": {"source": "contract_clauses: CIS-2026-003 parsed_params.force_majeure_events"},
             "inference": "FM clause provides schedule relief; both parties may renegotiate delivery terms"},
            {"step": 5,
             "claim": "US domestic GOES producers (Cleveland-Cliffs, ATI Metals) are available as alternatives",
             "grounded_in": {"source": "graph_context: us_producers list"},
             "inference": "Domestic sourcing eliminates export control exposure but may carry 5-10% price premium"},
        ]),
        confidence=0.78,
    ).with_inputs("signal_summary", "graph_context", "similar_past",
                  "contract_clauses", "event_class", "impact_dimensions"),
]


async def load_feedback_examples(min_accepted: int = 5) -> list[dspy.Example]:
    """Pull pre-built DspyTrainingExample rows written by the feedback route.

    These are created automatically when an analyst accepts or edits an assessment
    via POST /api/feedback. Each row has serialised inputs + expected_outputs that
    mirror the ImpactAssessment Signature exactly, so we just deserialise them.

    Returns [] if fewer than min_accepted rows exist (optimizer uses bootstrap only).
    """
    from apps.api.db.models import DspyTrainingExample

    examples: list[dspy.Example] = []

    async with async_session_factory() as session:
        rows = await session.execute(
            select(DspyTrainingExample)
            .order_by(DspyTrainingExample.created_at.desc())
            .limit(100)
        )
        te_rows = rows.scalars().all()

    if len(te_rows) < min_accepted:
        logger.info(
            "[training_data] Only %d training examples in DB (need %d) — using bootstrap only",
            len(te_rows), min_accepted,
        )
        return []

    for te in te_rows:
        try:
            inputs = te.inputs or {}
            outputs = te.expected_outputs or {}

            ex = dspy.Example(
                # Inputs
                signal_summary=inputs.get("signal_summary", ""),
                graph_context=inputs.get("graph_context", "{}"),
                similar_past=inputs.get("similar_past", "[]"),
                contract_clauses=inputs.get("contract_clauses", "[]"),
                event_class=inputs.get("event_class", "other"),
                impact_dimensions=inputs.get("impact_dimensions", "price, availability"),
                # Expected outputs
                summary=outputs.get("summary", ""),
                affected_entities_json=outputs.get("affected_entities_json", "{}"),
                affected_clauses_json=outputs.get("affected_clauses_json", "[]"),
                impact_json=outputs.get("impact_json", "{}"),
                reasoning_chain_json=outputs.get("reasoning_chain_json", "[]"),
                confidence=float(outputs.get("confidence", 0.5)),
            ).with_inputs("signal_summary", "graph_context", "similar_past",
                          "contract_clauses", "event_class", "impact_dimensions")

            examples.append(ex)
        except Exception as exc:
            logger.warning("[training_data] Skipping malformed training example %s: %s", te.id, exc)

    logger.info("[training_data] Loaded %d training examples from analyst feedback", len(examples))
    return examples


def get_trainset(max_bootstrap: int = 5) -> list[dspy.Example]:
    """Return the combined training set for MIPROv2.

    Always includes bootstrap examples. Adds feedback examples if available.
    In async context, call load_feedback_examples() separately and pass them in.
    """
    return BOOTSTRAP_EXAMPLES[:max_bootstrap]


def _payload_to_summary(payload: dict, source: str) -> str:
    parts = [f"source={source}"]
    for key in ("title", "label", "alert_type", "ticker", "summary"):
        val = payload.get(key)
        if val and isinstance(val, str):
            parts.append(f"{key}={val[:200]}")
    return " | ".join(parts)
