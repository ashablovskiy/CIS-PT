"""Unit tests for assessment_quality_metric.

Tests each scoring dimension independently, then end-to-end.
No DB or API calls — pure function tests.
"""

from __future__ import annotations

import json
import pytest
import dspy

from apps.api.dspy_lab.metrics import assessment_quality_metric
from tests.conftest import MockPrediction


# ── End-to-end quality bounds ─────────────────────────────────────────────────

def test_high_quality_scores_above_threshold(high_quality_prediction):
    score = assessment_quality_metric(dspy.Example(), high_quality_prediction)
    assert score >= 0.75, f"High-quality prediction scored only {score:.4f}"


def test_low_quality_scores_below_threshold(low_quality_prediction):
    score = assessment_quality_metric(dspy.Example(), low_quality_prediction)
    assert score <= 0.40, f"Low-quality prediction scored {score:.4f} (expected ≤ 0.40)"


def test_high_scores_above_low(high_quality_prediction, low_quality_prediction):
    high = assessment_quality_metric(dspy.Example(), high_quality_prediction)
    low = assessment_quality_metric(dspy.Example(), low_quality_prediction)
    assert high > low + 0.30, f"Gap too small: high={high:.4f} low={low:.4f}"


def test_score_in_unit_range(high_quality_prediction):
    score = assessment_quality_metric(dspy.Example(), high_quality_prediction)
    assert 0.0 <= score <= 1.0


# ── Entity specificity dimension ──────────────────────────────────────────────

def test_entity_score_zero_with_no_suppliers():
    pred = MockPrediction(suppliers=[], plants=[], commodities=[])
    score = assessment_quality_metric(dspy.Example(), pred)
    # entity contributes 0.25 * 0 = 0 of 0.25 max
    assert score <= 0.65  # remaining dimensions can still score


def test_entity_score_improves_with_named_suppliers():
    pred_none = MockPrediction(suppliers=[])
    pred_one  = MockPrediction(suppliers=["Siemens Energy"])
    pred_three = MockPrediction(suppliers=["Siemens Energy", "Hitachi Energy", "GE Vernova"])

    s_none  = assessment_quality_metric(dspy.Example(), pred_none)
    s_one   = assessment_quality_metric(dspy.Example(), pred_one)
    s_three = assessment_quality_metric(dspy.Example(), pred_three)

    assert s_one > s_none
    assert s_three >= s_one


# ── Clause coverage dimension ─────────────────────────────────────────────────

def test_clause_score_zero_with_empty_clauses():
    pred = MockPrediction(
        summary="Some assessment with Siemens Energy and Hitachi Energy named clearly.",
        suppliers=["Siemens Energy", "Hitachi Energy"],
        clauses=[],
    )
    score = assessment_quality_metric(dspy.Example(), pred)
    # clause contributes 0/0.25
    assert score <= 0.80


def test_clause_score_requires_type_detail_triggered():
    good_clause = {
        "clause_type": "indexation",
        "triggered": True,
        "detail": "GOES price exceeded 5% threshold per parsed_params.trigger_threshold_pct",
    }
    bad_clause = {"clause_type": "indexation"}  # missing triggered + detail

    pred_good = MockPrediction(clauses=[good_clause])
    pred_bad  = MockPrediction(clauses=[bad_clause])

    s_good = assessment_quality_metric(dspy.Example(), pred_good)
    s_bad  = assessment_quality_metric(dspy.Example(), pred_bad)
    assert s_good > s_bad


# ── Reasoning quality dimension ───────────────────────────────────────────────

def test_reasoning_score_improves_with_grounded_steps():
    def make_step(grounded: bool, with_inference: bool) -> dict:
        return {
            "step": 1,
            "claim": "Some claim",
            "grounded_in": {"source": "contract_clauses: CIS-2026-001 parsed_params"} if grounded else {},
            "inference": "Therefore something important follows from this finding." if with_inference else "",
        }

    pred_no_steps  = MockPrediction(chain=[])
    pred_ungrounded = MockPrediction(chain=[make_step(False, False)] * 4)
    pred_grounded  = MockPrediction(chain=[make_step(True, True)] * 4)

    s_none    = assessment_quality_metric(dspy.Example(), pred_no_steps)
    s_unground = assessment_quality_metric(dspy.Example(), pred_ungrounded)
    s_ground  = assessment_quality_metric(dspy.Example(), pred_grounded)

    assert s_ground > s_unground
    assert s_unground > s_none  # step count still helps


# ── Confidence calibration dimension ─────────────────────────────────────────

def test_confidence_exactly_half_penalised():
    pred = MockPrediction(
        suppliers=["Siemens Energy", "Hitachi Energy", "GE Vernova"],
        confidence=0.5,
    )
    pred_calibrated = MockPrediction(
        suppliers=["Siemens Energy", "Hitachi Energy", "GE Vernova"],
        confidence=0.82,
    )
    s_lazy = assessment_quality_metric(dspy.Example(), pred)
    s_cal  = assessment_quality_metric(dspy.Example(), pred_calibrated)
    assert s_cal > s_lazy


def test_overconfident_without_entities_penalised():
    pred_overconfident = MockPrediction(suppliers=[], confidence=0.95)
    pred_calibrated    = MockPrediction(suppliers=["Siemens Energy", "Hitachi Energy"], confidence=0.82)

    s_over = assessment_quality_metric(dspy.Example(), pred_overconfident)
    s_cal  = assessment_quality_metric(dspy.Example(), pred_calibrated)
    assert s_cal > s_over


# ── Summary quality dimension ─────────────────────────────────────────────────

def test_short_summary_penalised():
    pred_short = MockPrediction(summary="Impact is significant.")
    pred_long  = MockPrediction(
        summary=(
            "Siemens Energy and Hitachi Energy face indexation clause triggers due to "
            "GOES price increases. The force majeure clause applies under export controls, "
            "providing schedule relief for transformer delivery obligations. "
            "Procurement team should act immediately to secure alternative GOES sourcing."
        )
    )
    s_short = assessment_quality_metric(dspy.Example(), pred_short)
    s_long  = assessment_quality_metric(dspy.Example(), pred_long)
    assert s_long > s_short


def test_domain_terms_boost_summary_score():
    generic = MockPrediction(
        summary="There are procurement impacts affecting the supply chain in this market."
                " Multiple entities face challenges related to their operations."
    )
    domain = MockPrediction(
        summary="Siemens Energy faces indexation clause triggers as GOES winding strip "
                "prices breach the 5% threshold. The force majeure clause in the transformer "
                "contract covers export controls per the parsed_params specification."
    )
    s_generic = assessment_quality_metric(dspy.Example(), generic)
    s_domain  = assessment_quality_metric(dspy.Example(), domain)
    assert s_domain > s_generic


# ── Gold-standard bonus ───────────────────────────────────────────────────────

def test_gold_standard_bonus_when_suppliers_match():
    example_with_gold = dspy.Example(
        summary="reference summary",
        affected_entities_json=json.dumps({
            "suppliers": ["Siemens Energy", "Hitachi Energy"]
        }),
    )
    pred = MockPrediction(
        summary="Siemens Energy and Hitachi Energy are affected by the supply disruption.",
        suppliers=["Siemens Energy", "Hitachi Energy"],
    )
    score_with_gold = assessment_quality_metric(example_with_gold, pred)
    score_no_gold   = assessment_quality_metric(dspy.Example(), pred)
    assert score_with_gold >= score_no_gold  # gold bonus never hurts
