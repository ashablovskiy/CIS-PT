# XGBoost Implementation Guide

> **Status:** Planned — do not implement until data thresholds in ADR-0002 are met.
> Reference: `docs/decisions/0002-xgboost-ml-layer.md`

---

## Overview

Three XGBoost modules slot into the existing pipeline at well-defined injection points.
None of them *replace* LLM steps entirely — they either calibrate LLM outputs or
pre-compute estimates that reduce the reasoning burden on Opus.

```
┌─────────────────────────────────────────────────────────────────┐
│ INGESTION PIPELINE                                              │
│                                                                 │
│  rule_filter → Haiku batch scoring → [MODULE 1] → route/persist│
│                                       Relevance                │
│                                       Calibrator               │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ ASSESSMENT PIPELINE — NODE 4 (contract_scanner)                │
│                                                                 │
│  clause matches → [MODULE 3] → ranked clause list → synthesizer│
│                   Clause Trigger                               │
│                   Classifier                                   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ ASSESSMENT PIPELINE — NODE 5 (synthesizer)                     │
│                                                                 │
│  Opus output → magnitude_pct ← [MODULE 2] constraint/override │
│                                 Price Impact                   │
│                                 Estimator                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Module 1: Relevance Score Calibrator

### Purpose
Replace the hardcoded `llm_score > 0.6` escalation threshold with a calibrated
probability model trained on analyst accept/reject feedback.

### Prerequisites
- ≥ 200 rows in `feedback` table with `user_action` in {accept, reject}
- Corresponding `signal_relevance` rows (llm_score, rule_score, decision)

### Feature set

```python
# ml/features.py
def signal_features(signal: dict, relevance: dict) -> dict:
    return {
        # LLM outputs (the "weak signal")
        "llm_score":          relevance["llm_score"] or 0.0,
        "rule_score":         relevance["rule_score"] or 0.0,

        # Source characteristics
        "source_prices":      int(signal["source"] == "prices"),
        "source_gdelt":       int(signal["source"] == "gdelt"),
        "source_press":       int(signal["source"] == "press"),
        "source_logistics":   int(signal["source"] == "logistics"),
        "source_demand":      int(signal["source"] == "demand"),
        "source_sec":         int(signal["source"] == "sec"),

        # Content features (from raw_payload)
        "title_token_count":  len((payload.get("title") or "").split()),
        "has_url":            int(bool(signal.get("url"))),
        "summary_length":     len(payload.get("summary") or ""),

        # Temporal
        "hour_of_day":        signal["ingested_at"].hour,
        "day_of_week":        signal["ingested_at"].weekday(),
        "signal_age_hours":   (datetime.now(UTC) - signal["ingested_at"]).total_seconds() / 3600,
    }
```

### Training script skeleton

```python
# scripts/train_relevance_calibrator.py
"""
Usage: uv run python scripts/train_relevance_calibrator.py
Outputs: ml/models/relevance_calibrator.joblib + evaluation report
"""
import asyncio
import joblib
import numpy as np
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import roc_auc_score, brier_score_loss
from sklearn.calibration import CalibratedClassifierCV
import xgboost as xgb

from ml.training_data import load_relevance_training_data

async def train():
    X, y, signal_ids = await load_relevance_training_data(min_rows=200)

    model = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric="logloss",
        random_state=42,
    )
    # Platt scaling for calibrated probabilities
    calibrated = CalibratedClassifierCV(model, method="sigmoid", cv=5)

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    aucs, briers = [], []
    for train_idx, val_idx in cv.split(X, y):
        calibrated.fit(X[train_idx], y[train_idx])
        probs = calibrated.predict_proba(X[val_idx])[:, 1]
        aucs.append(roc_auc_score(y[val_idx], probs))
        briers.append(brier_score_loss(y[val_idx], probs))

    print(f"CV AUC: {np.mean(aucs):.3f} ± {np.std(aucs):.3f}")
    print(f"CV Brier: {np.mean(briers):.4f}")

    # Final fit on all data
    calibrated.fit(X, y)
    joblib.dump(calibrated, "ml/models/relevance_calibrator.joblib")
    print("Saved: ml/models/relevance_calibrator.joblib")

asyncio.run(train())
```

### Integration point (runner.py)

```python
# In apps/api/ingest/runner.py — _route() method
# Replace:
#   if rel.llm_score >= 0.6: decision = "escalate"
# With:

from ml.relevance_calibrator import predict_escalation_prob  # lazy import

escalation_prob = predict_escalation_prob(signal_features(sig, rel))
if escalation_prob >= 0.65:      # threshold tuned from Youden's J
    decision = "escalate"
elif escalation_prob >= 0.30:
    decision = "classify"
else:
    decision = "discard"

# Store calibrated prob alongside llm_score for monitoring
rel.calibrated_escalation_prob = escalation_prob
```

### SHAP explainability

```python
# ml/relevance_calibrator.py
import shap

def explain_decision(signal_features: dict) -> dict:
    """Return top 3 features driving the escalation decision."""
    explainer = shap.TreeExplainer(model.estimator)
    shap_values = explainer.shap_values(feature_array)
    top_features = sorted(
        zip(feature_names, shap_values[0]),
        key=lambda x: abs(x[1]), reverse=True
    )[:3]
    return {name: float(val) for name, val in top_features}
```

---

## Module 2: Price Impact Estimator

### Purpose
Replace Opus's free-form `magnitude_pct` guess with a model trained on actual
commodity-price-to-transformer-cost relationships. **Can be implemented immediately**
using public data — no internal labels required for v1.

### Bootstrap data sources

| Source | Data | URL / API |
|--------|------|-----------|
| LME Copper | Monthly avg price $/t, 2010–present | `quandl` or `yfinance` (`HG=F`) |
| HRC Steel futures | Monthly $/short ton | `yfinance` (`HR=F`) |
| GOES steel indices | Quarterly price per kg | AISI Steel Shipments Report |
| Transformer price index | Semi-annual $/MVA | IEEE Transactions on Power Delivery; Hitachi/ABB annual reports |
| Aluminum (winding strip) | Monthly $/t | `yfinance` (`ALI=F`) |
| Transformer oil (naphthenic) | Quarterly $/barrel | ICIS reports |

The training label is `cost_pass_through_pct`: how much of a 1% commodity price move
flows through to transformer purchase price. Literature estimates (IEEE Transactions on
Power Delivery, 2019):
- Copper winding strip: ~0.28–0.35% per 1% copper move (28–35% pass-through)
- GOES core steel: ~0.18–0.24% per 1% steel move
- Transformer oil: ~0.06–0.09% per 1% oil move
- Aluminum winding: ~0.12–0.18% per 1% aluminum move

### Features

```python
def price_signal_features(signal: dict, classified: dict) -> dict:
    payload = signal["raw_payload"]
    return {
        "pct_change_1d":       payload.get("pct_change_1d") or 0.0,
        "pct_change_30d":      payload.get("pct_change_30d") or 0.0,
        "pct_change_90d":      payload.get("pct_change_90d") or 0.0,  # add to prices_agent
        "is_copper":           int("copper" in (classified.get("commodities") or [])),
        "is_goes":             int("goes" in str(classified.get("commodities") or []).lower()),
        "is_aluminum":         int("aluminum" in str(classified.get("commodities") or []).lower()),
        "is_steel":            int("steel" in str(classified.get("commodities") or []).lower()),
        "is_transformer_oil":  int("oil" in str(classified.get("commodities") or []).lower()),
        "direction_up":        int((payload.get("pct_change_1d") or 0) > 0),
        "volume_spike":        int(abs(payload.get("pct_change_1d") or 0) > 5),
        "season_q1":           int(signal["occurred_at"].month in [1, 2, 3]),
        "season_q2":           int(signal["occurred_at"].month in [4, 5, 6]),
        "season_q3":           int(signal["occurred_at"].month in [7, 8, 9]),
        # geo: US vs. EU pricing divergence matters for GOES (US mills vs. Cogent UK)
        "geo_us":              int("United States" in (classified.get("geo_tags") or [])),
        "geo_eu":              int(any(g in (classified.get("geo_tags") or [])
                                      for g in ["Germany", "France", "UK", "Sweden"])),
    }
```

### Integration point (synthesizer.py)

```python
# In apps/api/assess/nodes/synthesizer.py
# After DSPy Predict call, constrain magnitude_pct with XGBoost estimate:

from ml.price_impact import estimate_magnitude  # lazy import

if triage.get("event_class") == "commodity_price_move":
    xgb_magnitude = estimate_magnitude(price_signal_features(signal, classified))
    # Use as a soft constraint: if Opus is wildly off, log a warning
    opus_magnitude = state.impact_by_dimension.get("price", {}).get("magnitude_pct")
    if opus_magnitude and xgb_magnitude:
        ratio = opus_magnitude / xgb_magnitude
        if ratio > 3 or ratio < 0.33:
            logger.warning(
                "[synthesizer] magnitude_pct divergence: opus=%s xgb=%.1f",
                opus_magnitude, xgb_magnitude
            )
        # Week 7+: replace Opus estimate with XGBoost value directly
```

---

## Module 3: Clause Trigger Classifier

### Purpose
Pre-score contract clauses by trigger probability *before* sending them to Opus,
so the synthesizer focuses on the 2–3 most likely triggered clauses rather than
reasoning from scratch across all matched clauses.

### Prerequisites
- ≥ 50 rows in `assessments.affected_clauses` where `triggered = true`
- Corresponding `classified_signals` rows for feature extraction

### Features

```python
def clause_features(signal_features: dict, clause: dict, parsed_params: dict) -> dict:
    return {
        # Event features
        "event_class_commodity_price": int(event_class == "commodity_price_move"),
        "event_class_logistics":       int(event_class == "logistics_disruption"),
        "event_class_supplier":        int(event_class == "supplier_capacity"),
        "event_class_disaster":        int(event_class == "natural_disaster"),
        "price_change_pct":            abs(price_change_pct or 0),

        # Clause type
        "clause_force_majeure":  int(clause["clause_type"] == "force_majeure"),
        "clause_indexation":     int(clause["clause_type"] == "indexation"),
        "clause_ld":             int(clause["clause_type"] == "ld"),
        "clause_incoterms":      int(clause["clause_type"] == "incoterms"),
        "clause_slot":           int(clause["clause_type"] == "slot"),
        "clause_escalation":     int(clause["clause_type"] == "escalation"),

        # Parsed thresholds (from contracts.json)
        "trigger_threshold_pct": parsed_params.get("trigger_pct") or 0.0,
        "review_days":           parsed_params.get("review_days") or 0,
        "has_cap":               int("cap_pct" in parsed_params),

        # Match quality
        "commodity_overlap":     len(set(clause_commodities) & set(signal_commodities)),
        "supplier_name_match":   int(supplier_name_match),
    }
```

### Integration point (contract_scanner.py)

```python
# After building `matches` list, before capping at 12:
from ml.clause_trigger import predict_trigger_prob  # lazy import

for match in matches:
    match["trigger_prob"] = predict_trigger_prob(
        clause_features(triage_features, match, match["parsed_params"])
    )

# Sort by trigger probability (descending) instead of type_rank
matches.sort(key=lambda m: m.get("trigger_prob", 0), reverse=True)
state.contract_matches = matches[:12]
```

---

## Monitoring and retraining

### Metrics to track

```python
# Add to apps/api/routes/agents.py or a new /api/ml/metrics endpoint
{
    "relevance_calibrator": {
        "model_date": "2026-07-01",
        "training_rows": 312,
        "cv_auc": 0.84,
        "cv_brier": 0.11,
        "predictions_last_7d": 1843,
        "escalation_rate_model": 0.18,   # compare to pre-model 0.24
        "escalation_rate_actual": 0.16,  # analyst accept rate
    },
    "price_impact": {
        "model_date": "2026-06-15",
        "mae_pct": 2.3,   # mean absolute error in magnitude_pct
        "commodities": ["copper", "goes", "aluminum", "steel", "oil"],
    },
    "clause_trigger": {
        "model_date": "2026-08-01",
        "training_rows": 67,
        "precision_at_3": 0.71,  # top-3 clauses contain the actual trigger
        "recall": 0.88,
    }
}
```

### Retraining schedule (Inngest crons)

```python
# Add to inngest_functions/agent_crons.py when ready:

@inngest_client.create_function(
    fn_id="cis/retrain-relevance-calibrator",
    trigger=inngest.TriggerCron(cron="0 4 * * 0"),  # Sundays at 04:00 UTC
    concurrency=[inngest.Concurrency(limit=1)],
)
async def retrain_relevance_fn(ctx, step):
    """Weekly retraining if enough new feedback rows."""
    async def retrain():
        from ml.training_data import count_feedback_rows
        n = await count_feedback_rows()
        if n < 200:
            return {"skipped": True, "reason": f"only {n} rows, need 200"}
        import subprocess
        subprocess.run(["uv", "run", "python", "scripts/train_relevance_calibrator.py"],
                       check=True)
        return {"trained": True, "rows": n}
    return await step.run("retrain", retrain)
```

---

## Week-by-week implementation roadmap

| When | Action | Gate condition |
|------|--------|----------------|
| **Now** | Bootstrap price impact training data from public sources | No gate |
| **Week 6** | Eval harness labels 50+ assessments → train clause trigger classifier v1 | ≥ 50 triggered clauses |
| **Week 7** | Feedback widget accumulates 200 rows → train relevance calibrator v1 | ≥ 200 feedback rows |
| **Week 7** | Replace hardcoded threshold in runner.py with calibrator | AUC ≥ 0.75 in CV |
| **Week 8** | Add `/api/ml/metrics` route for model monitoring | Models deployed |
| **Week 9** | Weekly Inngest retraining cron for all 3 models | Monitoring in place |
| **Week 10** | SHAP explanations surfaced in assessment detail page | User feedback on explanations |

---

## Dependencies to add when implementing

```toml
# pyproject.toml additions
xgboost = ">=2.1"
scikit-learn = ">=1.5"
shap = ">=0.46"
joblib = ">=1.4"
```

For the price impact bootstrapping (data download):
```toml
yfinance = ">=0.2"
pandas = ">=2.2"
```

---

## Key references

- XGBoost docs: https://xgboost.readthedocs.io
- SHAP for tree models: https://shap.readthedocs.io/en/latest/example_notebooks/tabular_examples/tree_based_models/
- Commodity pass-through literature: "Price Transmission in Power Equipment Markets"
  (IEEE Transactions on Power Delivery, Vol. 34, 2019)
- Platt scaling for LLM output calibration: Guo et al., "On Calibration of Modern Neural
  Networks" (ICML 2017) — same principle applies to LLM confidence scores
