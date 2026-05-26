"""Unit tests for XGBoost Price Impact Estimator — rule-based path only.

These tests run without internet access or trained models.
They verify feature engineering, commodity inference, and fallback behaviour.
"""

from __future__ import annotations

import pytest

from apps.api.ml.price_impact import (
    PriceImpactEstimator,
    PriceImpactEstimate,
    extract_features,
    _infer_commodities,
    COMMODITY_TICKERS,
    EVENT_CLASS_PRIORS,
    DIRECTION_LABELS,
)


# ── Commodity inference ───────────────────────────────────────────────────────

def test_infer_commodities_detects_copper():
    payload = {"title": "Copper prices surge", "summary": "HG=F up 5%"}
    result = _infer_commodities(payload)
    assert "Copper" in result


def test_infer_commodities_detects_goes():
    payload = {"summary": "grain-oriented electrical steel shortage at Nippon Steel"}
    result = _infer_commodities(payload)
    assert "GOES" in result


def test_infer_commodities_detects_aluminum():
    payload = {"summary": "ALI=F aluminum winding strip price decline"}
    result = _infer_commodities(payload)
    assert "Aluminum" in result


def test_infer_commodities_defaults_to_copper_when_unknown():
    payload = {"summary": "general market update with no specific materials mentioned"}
    result = _infer_commodities(payload)
    assert result == ["Copper"]


def test_infer_commodities_can_return_multiple():
    payload = {"summary": "copper and GOES grain-oriented steel both affected"}
    result = _infer_commodities(payload)
    assert len(result) >= 2


# ── Feature engineering ───────────────────────────────────────────────────────

def test_extract_features_returns_dict():
    features = extract_features({}, "other")
    assert isinstance(features, dict)
    assert len(features) > 10


def test_extract_features_event_class_one_hot():
    features = extract_features({}, "demand_surge")
    assert features["ec_demand_surge"] == 1.0
    # All other event classes should be 0
    for ec in EVENT_CLASS_PRIORS:
        if ec != "demand_surge":
            assert features[f"ec_{ec}"] == 0.0


def test_extract_features_source_encoding():
    payload = {"source": "sec"}
    features = extract_features(payload, "financial_disclosure")
    assert features["source_sec"] == 1.0
    assert features["source_gdelt"] == 0.0


def test_extract_features_price_moves_parsed():
    payload = {"moves_pct": {"1d": "+2.1%", "5d": "-0.5%", "30d": "+12.3%"}}
    features = extract_features(payload, "commodity_price_move")
    assert abs(features["move_1d"] - 2.1) < 0.01
    assert abs(features["move_5d"] - (-0.5)) < 0.01
    assert abs(features["move_30d"] - 12.3) < 0.01


def test_extract_features_handles_missing_moves():
    features = extract_features({}, "other")
    assert features["move_1d"] == 0.0
    assert features["move_5d"] == 0.0
    assert features["move_30d"] == 0.0


def test_extract_features_has_all_commodity_fields():
    features = extract_features({}, "other")
    for meta in COMMODITY_TICKERS.values():
        name = meta["name"].lower()
        for suffix in ("1d_pct", "5d_pct", "30d_pct", "vol_30d"):
            assert f"{name}_{suffix}" in features, f"Missing feature: {name}_{suffix}"


def test_extract_features_temporal():
    features = extract_features({}, "other")
    assert 0 <= features["day_of_week"] <= 6
    assert 1 <= features["month"] <= 12


# ── Rule-based fallback ───────────────────────────────────────────────────────

def test_rule_based_predict_returns_estimate():
    estimator = PriceImpactEstimator()
    # Force fallback (no models loaded in unit test environment)
    estimator._loaded = False
    result = estimator.predict({"source": "gdelt"}, "demand_surge")
    assert isinstance(result, PriceImpactEstimate)


def test_rule_based_direction_for_demand_surge():
    estimator = PriceImpactEstimator()
    estimator._loaded = False
    result = estimator.predict({}, "demand_surge")
    assert result.direction == "increase"


def test_rule_based_commodity_price_move_uses_payload():
    """If the payload has a price move, rule-based should use it."""
    estimator = PriceImpactEstimator()
    estimator._loaded = False
    payload = {"moves_pct": {"30d": "+15.0%"}, "source": "prices"}
    result = estimator.predict(payload, "commodity_price_move")
    assert result.magnitude_pct >= 15.0 or result.magnitude_pct == pytest.approx(15.0, abs=0.1)


def test_rule_based_magnitude_capped_at_30():
    estimator = PriceImpactEstimator()
    estimator._loaded = False
    payload = {"moves_pct": {"30d": "+99%"}}
    result = estimator.predict(payload, "commodity_price_move")
    assert result.magnitude_pct <= 30.0


def test_rule_based_confidence_is_low():
    """Rule-based should signal low confidence so callers know to treat it as prior."""
    estimator = PriceImpactEstimator()
    estimator._loaded = False
    result = estimator.predict({}, "other")
    assert result.confidence < 0.6


def test_rule_based_model_version_is_fallback():
    estimator = PriceImpactEstimator()
    estimator._loaded = False
    result = estimator.predict({}, "other")
    assert "fallback" in result.model_version
    assert result.used_ml is False


def test_direction_labels_are_complete():
    assert set(DIRECTION_LABELS.values()) == {"increase", "decrease", "neutral"}


def test_all_event_classes_have_priors():
    for ec in ("commodity_price_move", "supplier_capacity", "demand_surge",
               "logistics_disruption", "regulatory_trade", "other"):
        assert ec in EVENT_CLASS_PRIORS
        prior = EVENT_CLASS_PRIORS[ec]
        assert "magnitude" in prior
        assert "direction_bias" in prior
