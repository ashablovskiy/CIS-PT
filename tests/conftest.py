"""Shared pytest fixtures and configuration."""

from __future__ import annotations

import json
import pytest


# ── Minimal mock prediction for metric tests ──────────────────────────────────

class MockPrediction:
    """Simulates a DSPy prediction object with all ImpactAssessment output fields."""

    def __init__(
        self,
        summary: str = "",
        suppliers: list[str] | None = None,
        plants: list[str] | None = None,
        commodities: list[str] | None = None,
        clauses: list[dict] | None = None,
        chain: list[dict] | None = None,
        confidence: float = 0.75,
    ):
        entities = {
            "suppliers": suppliers or [],
            "plants": plants or [],
            "commodities": commodities or [],
        }
        self.summary = summary
        self.affected_entities_json = json.dumps(entities)
        self.affected_clauses_json = json.dumps(clauses or [])
        self.impact_json = json.dumps({})
        self.reasoning_chain_json = json.dumps(chain or [])
        self.confidence = confidence


@pytest.fixture
def high_quality_prediction() -> MockPrediction:
    """A well-structured prediction that should score ~0.90+."""
    return MockPrediction(
        summary=(
            "Siemens Energy and Hitachi Energy face supply constraints on GOES winding strip "
            "following new EAR export controls. The indexation clause in CIS-2026-008 is at "
            "risk of triggering if GOES prices rise above the 5% threshold. Force majeure "
            "under CIS-2026-003 may apply — export controls are an enumerated FM event."
        ),
        suppliers=["Siemens Energy", "Hitachi Energy", "GE Vernova"],
        plants=["Siemens Nuremberg", "Hitachi Bad Honnef"],
        commodities=["GOES", "GOES_M3_Grade"],
        clauses=[
            {
                "clause_type": "indexation",
                "triggered": False,
                "detail": "GOES price up 8% — below the 5% basket threshold due to 40% weighting: "
                          "effective basket move is 3.2%. Monitor for further GOES appreciation.",
            },
            {
                "clause_type": "force_majeure",
                "triggered": True,
                "detail": "Export controls explicitly listed as FM event in parsed_params. "
                          "Supplier should issue FM notice within 7 days per clause 12.2.",
            },
        ],
        chain=[
            {
                "step": 1,
                "claim": "US EAR controls effective in 60 days for 12 countries",
                "grounded_in": {"source": "regulatory signal: Federal Register notice, 60-day effective date"},
                "inference": "Hard deadline creates pre-control inventory window",
            },
            {
                "step": 2,
                "claim": "Siemens Energy and Hitachi Energy source GOES from restricted-country mills",
                "grounded_in": {"source": "graph_context: affected_suppliers=[Cogent Power, Nippon Steel, JFE Steel]"},
                "inference": "~40% of EU transformer GOES supply affected",
            },
            {
                "step": 3,
                "claim": "Indexation trigger at 5% with 40% GOES basket weight requires 12.5% GOES price rise",
                "grounded_in": {"source": "contract_clauses: CIS-2026-008 parsed_params.trigger_threshold_pct=5"},
                "inference": "Current 8% GOES move insufficient to trigger; watch for sustained appreciation",
            },
            {
                "step": 4,
                "claim": "Force majeure covers export controls per CIS-2026-003",
                "grounded_in": {"source": "contract_clauses: CIS-2026-003 parsed_params.force_majeure_events"},
                "inference": "FM notice suspends delivery obligations; obtain regulatory certification",
            },
        ],
        confidence=0.82,
    )


@pytest.fixture
def low_quality_prediction() -> MockPrediction:
    """A thin, vague prediction that should score low."""
    return MockPrediction(
        summary="There may be some supply chain impacts.",
        suppliers=[],
        plants=[],
        commodities=[],
        clauses=[],
        chain=[],
        confidence=0.5,
    )
