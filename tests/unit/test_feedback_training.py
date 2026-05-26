"""Unit tests for feedback route helpers — training example construction."""

from __future__ import annotations

import json
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from apps.api.routes.feedback import _build_training_example, _extract_event_class, _extract_impact_dims


def _make_assessment(
    summary="Test summary.",
    confidence=0.78,
    affected_entities=None,
    affected_clauses=None,
    impact=None,
    reasoning_chain=None,
) -> MagicMock:
    a = MagicMock()
    a.id = uuid4()
    a.summary = summary
    a.confidence = confidence
    a.affected_entities = affected_entities or {
        "suppliers": ["Siemens Energy", "Hitachi Energy"],
        "plants": ["Siemens Nuremberg"],
        "commodities": ["GOES"],
    }
    a.affected_clauses = affected_clauses or [
        {"clause_type": "indexation", "triggered": True,
         "detail": "GOES threshold exceeded per parsed_params.trigger_threshold_pct=5"},
    ]
    a.impact = impact or {
        "price": {"direction": "increase", "magnitude_pct": 12, "confidence": 0.80},
        "availability": {"direction": "decrease", "magnitude_pct": 20, "confidence": 0.70},
    }
    a.reasoning_chain = reasoning_chain or [
        {"step": 1, "claim": "Test claim",
         "grounded_in": {"source": "signal summary"}, "inference": "Test inference"},
    ]
    return a


def _make_signal(source="gdelt", title="Test Signal Title") -> MagicMock:
    sig = MagicMock()
    sig.id = uuid4()
    sig.source = source
    sig.raw_payload = {
        "source": source,
        "title": title,
        "summary": "Test signal summary for unit testing purposes.",
    }
    return sig


# ── _build_training_example ───────────────────────────────────────────────────

def test_build_training_example_returns_object():
    fb_id = uuid4()
    a = _make_assessment()
    sig = _make_signal()

    te = _build_training_example(fb_id, a, sig, corrected={}, action="accept")
    assert te is not None
    assert te.feedback_id == fb_id


def test_build_training_example_inputs_have_required_keys():
    te = _build_training_example(uuid4(), _make_assessment(), _make_signal(), {}, "accept")
    inputs = te.inputs
    for key in ("signal_summary", "graph_context", "similar_past",
                "contract_clauses", "event_class", "impact_dimensions"):
        assert key in inputs, f"Missing input key: {key}"


def test_build_training_example_outputs_have_required_keys():
    te = _build_training_example(uuid4(), _make_assessment(), _make_signal(), {}, "accept")
    outputs = te.expected_outputs
    for key in ("summary", "affected_entities_json", "affected_clauses_json",
                "impact_json", "reasoning_chain_json", "confidence"):
        assert key in outputs, f"Missing output key: {key}"


def test_build_training_example_uses_corrected_summary_for_edit():
    a = _make_assessment(summary="Original summary")
    corrected = {"summary": "Corrected analyst summary that is better"}

    te = _build_training_example(uuid4(), a, _make_signal(), corrected, "edit")
    assert te.expected_outputs["summary"] == "Corrected analyst summary that is better"


def test_build_training_example_uses_original_when_no_correction():
    a = _make_assessment(summary="Original pipeline summary")
    te = _build_training_example(uuid4(), a, _make_signal(), {}, "accept")
    assert te.expected_outputs["summary"] == "Original pipeline summary"


def test_build_training_example_higher_weight_for_edit_with_correction():
    a = _make_assessment()
    te_accept = _build_training_example(uuid4(), a, _make_signal(), {}, "accept")
    te_edit   = _build_training_example(uuid4(), a, _make_signal(),
                                        {"summary": "Corrected"}, "edit")
    assert te_edit.weight > te_accept.weight


def test_build_training_example_signal_summary_contains_source():
    te = _build_training_example(uuid4(), _make_assessment(), _make_signal(source="gdelt"), {}, "accept")
    assert "source=gdelt" in te.inputs["signal_summary"]


def test_build_training_example_handles_none_signal():
    """Should not crash when signal is None (assessment without signal)."""
    te = _build_training_example(uuid4(), _make_assessment(), None, {}, "accept")
    assert te is not None
    assert "source=unknown" in te.inputs["signal_summary"]


def test_build_training_example_outputs_are_valid_json():
    te = _build_training_example(uuid4(), _make_assessment(), _make_signal(), {}, "accept")
    outputs = te.expected_outputs
    for key in ("affected_entities_json", "affected_clauses_json",
                "impact_json", "reasoning_chain_json"):
        try:
            json.loads(outputs[key])
        except json.JSONDecodeError:
            pytest.fail(f"Output '{key}' is not valid JSON: {outputs[key]!r}")


# ── _extract_impact_dims ──────────────────────────────────────────────────────

def test_extract_impact_dims_returns_populated_dimensions():
    a = _make_assessment(impact={
        "price": {"direction": "up", "confidence": 0.8},
        "logistics": {"direction": "disrupted", "confidence": 0.9},
    })
    dims = _extract_impact_dims(a)
    assert "price" in dims
    assert "logistics" in dims


def test_extract_impact_dims_fallback_when_empty():
    a = _make_assessment(impact={})
    dims = _extract_impact_dims(a)
    assert dims == "price, availability"
