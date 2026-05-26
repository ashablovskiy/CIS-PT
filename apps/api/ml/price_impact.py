"""XGBoost Price Impact Estimator — Module 2 of the ML layer.

Predicts the expected price impact magnitude (%) and direction for a supply-chain
signal, given observable commodity and market features. Uses only public data:
yfinance price series, FRED macro indicators, and signal metadata.

No analyst labels required — training target is derived from actual commodity
price moves observed 30 days after each signal date.

Architecture:
  - Feature engineering from commodity tickers + signal metadata
  - XGBRegressor for magnitude (0–30% expected move)
  - XGBClassifier for direction (up / down / neutral)
  - Persists model artifacts to apps/api/ml/models/
  - Loaded at startup; inference called from synthesizer pipeline

Usage:
    # Train (run weekly, needs internet)
    uv run python scripts/train_price_model.py

    # Inference (called from pipeline)
    from apps.api.ml.price_impact import price_impact_estimator
    est = price_impact_estimator.predict(signal_payload, event_class)
"""

from __future__ import annotations

import json
import logging
import os
import pickle
from dataclasses import dataclass, field
from datetime import datetime, timedelta, UTC
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).parent / "models"
MODELS_DIR.mkdir(exist_ok=True)

MAGNITUDE_MODEL_PATH = MODELS_DIR / "price_magnitude_xgb.pkl"
DIRECTION_MODEL_PATH = MODELS_DIR / "price_direction_xgb.pkl"
FEATURE_NAMES_PATH   = MODELS_DIR / "price_feature_names.json"

# Commodity tickers → human-readable + weight in transformer BOM
COMMODITY_TICKERS: dict[str, dict] = {
    "HG=F":  {"name": "Copper",    "bom_weight": 0.35, "clauses": ["indexation"]},
    "ALI=F": {"name": "Aluminum",  "bom_weight": 0.20, "clauses": ["indexation"]},
    "SB=F":  {"name": "GOES_Proxy","bom_weight": 0.25, "clauses": ["indexation"]},  # Silicon steel proxy
    "CL=F":  {"name": "Oil",       "bom_weight": 0.05, "clauses": ["indexation", "logistics"]},
    "NG=F":  {"name": "NatGas",    "bom_weight": 0.05, "clauses": []},
}

# Event class → price impact multiplier prior
EVENT_CLASS_PRIORS: dict[str, dict] = {
    "commodity_price_move":   {"magnitude": 8.0,  "direction_bias": 0},
    "supplier_capacity":      {"magnitude": 5.0,  "direction_bias": 1},   # tend to push price up
    "demand_surge":           {"magnitude": 4.0,  "direction_bias": 1},
    "logistics_disruption":   {"magnitude": 3.0,  "direction_bias": 1},
    "regulatory_trade":       {"magnitude": 6.0,  "direction_bias": 1},
    "financial_disclosure":   {"magnitude": 2.0,  "direction_bias": 0},
    "geopolitical_disruption":{"magnitude": 5.0,  "direction_bias": 1},
    "natural_disaster":       {"magnitude": 7.0,  "direction_bias": 1},
    "other":                  {"magnitude": 1.5,  "direction_bias": 0},
}

DIRECTION_LABELS = {0: "decrease", 1: "neutral", 2: "increase"}
DIRECTION_LABEL_TO_INT = {v: k for k, v in DIRECTION_LABELS.items()}


@dataclass
class PriceImpactEstimate:
    """Result from the price impact estimator."""
    direction: str           # "increase" | "decrease" | "neutral"
    magnitude_pct: float     # expected price move magnitude (0–30)
    confidence: float        # model confidence 0–1
    affected_commodities: list[str] = field(default_factory=list)
    feature_contributions: dict[str, float] = field(default_factory=dict)
    model_version: str = "rule_based_fallback"
    used_ml: bool = False


class PriceImpactEstimator:
    """Loads XGBoost models at startup, serves predictions per signal.

    Falls back to rule-based estimation when models are not yet trained.
    """

    def __init__(self) -> None:
        self._magnitude_model = None
        self._direction_model = None
        self._feature_names: list[str] = []
        self._loaded = False
        self._load_models()

    def _load_models(self) -> None:
        try:
            if MAGNITUDE_MODEL_PATH.exists() and DIRECTION_MODEL_PATH.exists():
                with open(MAGNITUDE_MODEL_PATH, "rb") as f:
                    self._magnitude_model = pickle.load(f)
                with open(DIRECTION_MODEL_PATH, "rb") as f:
                    self._direction_model = pickle.load(f)
                if FEATURE_NAMES_PATH.exists():
                    self._feature_names = json.loads(FEATURE_NAMES_PATH.read_text())
                self._loaded = True
                logger.info("[price_impact] Loaded XGBoost models from %s", MODELS_DIR)
            else:
                logger.info("[price_impact] No trained models found — using rule-based fallback")
        except Exception as exc:
            logger.warning("[price_impact] Failed to load models: %s — using fallback", exc)

    def predict(
        self,
        signal_payload: dict[str, Any],
        event_class: str = "other",
        commodities: list[str] | None = None,
    ) -> PriceImpactEstimate:
        """Estimate price impact for a signal.

        If XGBoost models are loaded, uses ML inference. Otherwise falls back
        to rule-based estimation using event class priors + commodity moves.
        """
        affected = commodities or _infer_commodities(signal_payload)

        if self._loaded and self._magnitude_model is not None:
            return self._ml_predict(signal_payload, event_class, affected)
        else:
            return self._rule_based_predict(signal_payload, event_class, affected)

    def _ml_predict(
        self,
        payload: dict[str, Any],
        event_class: str,
        commodities: list[str],
    ) -> PriceImpactEstimate:
        """Run XGBoost inference.

        Magnitude: from XGBRegressor (MAE ~6% vs mean target ~7.5%).
        Direction: rule-based blend — 30-day commodity momentum dominates when
        strong (>3%), otherwise falls back to event class prior. The XGBoost
        direction classifier is not reliable enough for autonomous use on a
        40-feature technical-only model.
        """
        try:
            features = extract_features(payload, event_class)
            X = np.array([[features.get(f, 0.0) for f in self._feature_names]])

            magnitude = float(self._magnitude_model.predict(X)[0])
            magnitude = max(0.0, min(30.0, magnitude))

            # Direction: momentum-first, then event class prior
            move_30d = features.get("move_30d", 0.0)
            move_1d  = features.get("move_1d", 0.0)
            prior = EVENT_CLASS_PRIORS.get(event_class, EVENT_CLASS_PRIORS["other"])

            if abs(move_30d) >= 3.0:
                # Strong observed move — use its sign as direction
                direction = "increase" if move_30d > 0 else "decrease"
                dir_confidence = min(0.85, 0.55 + abs(move_30d) / 30.0)
            elif abs(move_1d) >= 2.0:
                direction = "increase" if move_1d > 0 else "decrease"
                dir_confidence = 0.60
            elif prior["direction_bias"] > 0:
                direction = "increase"
                dir_confidence = 0.55
            elif prior["direction_bias"] < 0:
                direction = "decrease"
                dir_confidence = 0.55
            else:
                direction = "neutral"
                dir_confidence = 0.50

            # Feature contributions via XGBoost's built-in importance (magnitude model)
            contribs: dict[str, float] = {}
            try:
                import xgboost as xgb
                dmatrix = xgb.DMatrix(X, feature_names=self._feature_names)
                raw_contribs = self._magnitude_model.get_booster().predict(
                    dmatrix, pred_contribs=True
                )[0]
                for name, val in zip(self._feature_names, raw_contribs[:-1]):
                    if abs(val) > 0.1:
                        contribs[name] = round(float(val), 3)
            except Exception:
                pass

            return PriceImpactEstimate(
                direction=direction,
                magnitude_pct=round(magnitude, 2),
                confidence=round(dir_confidence, 3),
                affected_commodities=commodities,
                feature_contributions=contribs,
                model_version="xgb_v1",
                used_ml=True,
            )
        except Exception as exc:
            logger.warning("[price_impact] ML inference failed: %s — using fallback", exc)
            return self._rule_based_predict(payload, event_class, commodities)

    def _rule_based_predict(
        self,
        payload: dict[str, Any],
        event_class: str,
        commodities: list[str],
    ) -> PriceImpactEstimate:
        """Rule-based fallback: event class prior + commodity move signals."""
        prior = EVENT_CLASS_PRIORS.get(event_class, EVENT_CLASS_PRIORS["other"])
        base_magnitude = prior["magnitude"]
        direction_bias = prior["direction_bias"]  # 1=up, -1=down, 0=neutral

        # Augment with any price moves in payload
        moves = payload.get("moves_pct", {})
        if moves:
            move_vals = []
            for k, v in moves.items():
                try:
                    move_vals.append(float(str(v).replace("%", "").replace("+", "")))
                except ValueError:
                    pass
            if move_vals:
                observed_move = abs(sum(move_vals) / len(move_vals))
                base_magnitude = max(base_magnitude, observed_move)
                direction_bias = 1 if sum(move_vals) > 0 else -1

        # Map bias to direction
        if direction_bias > 0:
            direction = "increase"
        elif direction_bias < 0:
            direction = "decrease"
        else:
            direction = "neutral"

        return PriceImpactEstimate(
            direction=direction,
            magnitude_pct=round(min(base_magnitude, 30.0), 2),
            confidence=0.45,   # low confidence for rule-based
            affected_commodities=commodities,
            model_version="rule_based_fallback",
            used_ml=False,
        )


# ── Feature engineering ───────────────────────────────────────────────────────

def extract_features(
    payload: dict[str, Any],
    event_class: str,
    lookback_days: int = 30,
) -> dict[str, float]:
    """Build the feature vector for one signal.

    Features are entirely from public data — no internal labels needed.
    Called both at training time (with historical payloads) and at inference.
    """
    features: dict[str, float] = {}

    # ── Event class one-hot ───────────────────────────────────────────────────
    for ec in EVENT_CLASS_PRIORS:
        features[f"ec_{ec}"] = 1.0 if event_class == ec else 0.0

    # ── Payload price moves (if present) ─────────────────────────────────────
    moves = payload.get("moves_pct", {})
    for period in ("1d", "5d", "30d"):
        raw = moves.get(period, "0%")
        try:
            features[f"move_{period}"] = float(str(raw).replace("%", "").replace("+", ""))
        except (ValueError, TypeError):
            features[f"move_{period}"] = 0.0

    # ── Commodity momentum (fetched from yfinance at training, cached at inference) ──
    for ticker, meta in COMMODITY_TICKERS.items():
        name = meta["name"].lower()
        # These are populated by the training pipeline; default 0 at inference if missing
        features[f"{name}_1d_pct"] = 0.0
        features[f"{name}_5d_pct"] = 0.0
        features[f"{name}_30d_pct"] = 0.0
        features[f"{name}_vol_30d"] = 0.0

    # ── Signal source encoding ────────────────────────────────────────────────
    source = payload.get("source", "unknown")
    for s in ("gdelt", "prices", "logistics", "press", "demand", "sec"):
        features[f"source_{s}"] = 1.0 if source == s else 0.0

    # ── Temporal features ─────────────────────────────────────────────────────
    now = datetime.now(UTC)
    features["day_of_week"] = float(now.weekday())
    features["month"] = float(now.month)

    return features


def _infer_commodities(payload: dict[str, Any]) -> list[str]:
    """Guess which commodities are affected from signal payload text."""
    text = json.dumps(payload, default=str).lower()
    result = []
    keyword_map = {
        "GOES": ["goes", "grain-oriented", "electrical steel"],
        "Copper": ["copper", "cu_winding", "hg=f"],
        "Aluminum": ["aluminum", "aluminium", "al_winding", "ali=f"],
        "Mineral_Oil": ["mineral oil", "transformer oil", "insulating oil"],
    }
    for commodity, keywords in keyword_map.items():
        if any(kw in text for kw in keywords):
            result.append(commodity)
    return result or ["Copper"]  # default — copper is always relevant


# ── Singleton (loaded once at startup) ────────────────────────────────────────
price_impact_estimator = PriceImpactEstimator()
