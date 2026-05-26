# ADR-0002: XGBoost ML layer for scoring calibration and impact estimation

Date: 2026-05-26
Status: Planned — implement after Week 6 eval harness, requires ≥ 200 labeled signals

## Context

The current pipeline uses LLMs (Haiku, Opus) for every decision that requires judgment:
relevance scoring, triage classification, impact magnitude estimation, and clause trigger
detection. LLMs are accurate with small data but have two weaknesses at scale:

1. **Cost** — Haiku at $0.25/M tokens is cheap per call but adds up when processing
   thousands of signals per week across 6 sources.
2. **Calibration drift** — LLM confidence scores (e.g. "confidence: 0.7") are not
   statistically calibrated; they reflect the model's verbal habits, not empirical hit rates.
3. **Latency** — each Haiku call adds 1–3 s per batch; XGBoost inference is < 1 ms.

Three specific tasks in the pipeline are well-suited for gradient-boosted trees once
sufficient labeled data exists. This ADR records that decision, the data requirements,
and the integration points so the approach is not forgotten and can be revisited in Week 7+.

## Decision

Add an optional XGBoost layer at three points in the pipeline:

### Module 1 — Relevance Score Calibrator (`ml/relevance_calibrator.py`)
**Replaces:** post-Haiku threshold decision (escalate / classify / discard)
**Trains on:** `signal_relevance` rows joined to analyst `feedback` (accept/reject/edit)
**Features:** source, rule_score, llm_score, keyword_hit_count, title_token_count,
             has_url, signal_age_hours, source_day_of_week
**Label:** 1 if analyst accepted the escalation, 0 if rejected
**Trigger:** retrain weekly via Inngest cron once ≥ 200 feedback rows exist
**Benefit:** replaces hardcoded threshold (0.6) with a calibrated probability;
             reduces false escalations and API cost

### Module 2 — Price Impact Estimator (`ml/price_impact.py`)
**Replaces:** Opus's free-form `magnitude_pct` estimate in the synthesizer output
**Trains on:** commodity price delta → observed transformer cost change (bootstrapped
             from public data: LME copper, HRC futures, GOES steel indices vs. published
             transformer price indices from IEEE/CIGRE reports)
**Features:** commodity type, pct_change_1d, pct_change_30d, direction,
             volume_anomaly_flag, geo_region, season_quarter
**Label:** actual_cost_impact_pct (from historical records or analyst corrections)
**Trigger:** can be trained immediately with external data (no internal labels needed)
**Benefit:** replaces LLM guess with a model trained on actual commodity-price-to-cost
             pass-through relationships; critical for indexation clause trigger detection

### Module 3 — Clause Trigger Classifier (`ml/clause_trigger.py`)
**Replaces:** synthesizer's clause trigger inference (currently pure Opus reasoning)
**Trains on:** `assessments.affected_clauses` where `triggered=true/false` + signal features
**Features:** event_class, commodity, geo_tag_count, price_pct_change, supplier_count,
             clause_type, parsed_params thresholds (trigger_pct, review_cadence)
**Label:** triggered (bool)
**Trigger:** retrain monthly once ≥ 50 triggered-clause observations exist
**Benefit:** allows contract_scanner to pre-rank clauses by trigger probability before
             calling Opus, reducing synthesizer context and improving precision

## Data requirements before implementation

| Module | Min labeled examples | Current (2026-05-26) | Estimated reach |
|--------|---------------------|----------------------|-----------------|
| Relevance Calibrator | 200 feedback rows | 0 | ~6–8 weeks at current pace |
| Price Impact Estimator | 0 (external data) | n/a | **Can start now** |
| Clause Trigger Classifier | 50 triggered observations | ~0 | ~10–12 weeks |

The price impact estimator is the only module that can be implemented immediately,
bootstrapped from public commodity price history. The other two require the feedback
widget (built in Week 4) to accumulate analyst corrections.

## Integration architecture

```
Ingestion pipeline:
  rule_filter → Haiku scoring → [XGB Relevance Calibrator] → route/persist
                                 ↑ replaces hardcoded threshold

Assessment pipeline (node 5 — synthesizer):
  DSPy Predict (Opus) → output includes magnitude_pct
                              ↑
                    [XGB Price Impact Estimator] overrides/constrains
                    [XGB Clause Trigger Classifier] pre-scores clauses

Both XGB models run as pure Python functions (< 1 ms), not async.
Models are serialised as joblib files in ml/models/ (gitignored for large files,
but model metadata + training scripts are committed).
```

## Consequences

**Positive**
- Calibrated probabilities: XGBoost outputs are proper probabilities, unlike LLM confidence
- Cost reduction: Relevance Calibrator could cut Haiku calls by 30–40% once trained
- Speed: inline XGBoost inference doesn't add latency
- Explainability: SHAP values give per-prediction feature importance (auditable)
- DSPy synergy: XGBoost outputs can be used as DSPy metrics for MIPROv2 optimization

**Negative**
- Data dependency: Modules 1 and 3 are not useful until labeled data accumulates
- Model drift: commodity price pass-through relationships change with supply chain
  structure; needs periodic retraining and monitoring
- Maintenance: adds a second class of artifacts (model files) alongside LLM prompts

## Alternatives considered

- **Logistic regression.** Simpler but misses interaction effects (e.g. "press source AND
  low rule_score AND weekend" is a known-bad pattern). XGBoost handles these naturally.
- **Fine-tuned embedding classifier.** Higher accuracy ceiling but requires GPU, much more
  data, and loses the SHAP explainability that compliance/audit users expect.
- **Keep LLMs for everything.** Valid at current scale; revisit this ADR if weekly signal
  volume exceeds 2,000 or analyst correction rate stays above 25%.
- **LightGBM instead of XGBoost.** Equivalent accuracy; XGBoost chosen because it has
  better SHAP integration and is more commonly understood by data scientists inheriting
  this codebase.

## Files to create when implementing

```
ml/
├── __init__.py
├── relevance_calibrator.py     # Module 1: train + predict + SHAP explain
├── price_impact.py             # Module 2: bootstrap + train + predict
├── clause_trigger.py           # Module 3: train + predict
├── features.py                 # Shared feature extraction functions
├── training_data.py            # Pulls labeled rows from Neon for training
├── models/                     # Serialised .joblib files (gitignored)
│   └── .gitkeep
scripts/
├── train_relevance_calibrator.py
├── train_price_impact.py
├── train_clause_trigger.py
```

## Review trigger

Revisit this ADR when any of:
- Feedback table exceeds 200 rows
- Weekly signal volume exceeds 2,000
- Analyst correction rate (edit + reject) exceeds 25% of assessments
- LLM scoring costs exceed $50/month
