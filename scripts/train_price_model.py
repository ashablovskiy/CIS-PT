#!/usr/bin/env python3
"""Train the XGBoost Price Impact Estimator from public commodity data.

Data pipeline:
  1. Pull 2 years of daily OHLCV from yfinance for 5 commodity tickers
  2. Build one training row per trading day:
     - Features: 1d/5d/30d % moves, volatility, day-of-week, month
     - Target magnitude: abs(30d forward return) for the primary commodity
     - Target direction: sign of 30d forward return (up/down/neutral ±2% band)
  3. Train XGBRegressor (magnitude) + XGBClassifier (direction)
  4. Evaluate on held-out last 6 months
  5. Persist to apps/api/ml/models/

No internal data needed. Runs in ~2 minutes on a laptop.

Usage:
    uv run python scripts/train_price_model.py
    uv run python scripts/train_price_model.py --lookback-years 3
"""

from __future__ import annotations

import argparse
import json
import logging
import pickle
import sys
from pathlib import Path

sys.path.insert(0, ".")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def build_dataset(lookback_years: int = 2):
    """Fetch commodity prices from yfinance and build feature/target arrays."""
    import pandas as pd
    import numpy as np
    import yfinance as yf

    from apps.api.ml.price_impact import COMMODITY_TICKERS, DIRECTION_LABEL_TO_INT

    logger.info("[train] Fetching %d years of commodity data from yfinance…", lookback_years)

    end = pd.Timestamp.now()
    start = end - pd.DateOffset(years=lookback_years + 1)  # +1 for forward-return label

    frames: dict[str, pd.DataFrame] = {}
    for ticker in COMMODITY_TICKERS:
        try:
            df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
            if df.empty:
                logger.warning("[train] No data for %s — skipping", ticker)
                continue
            frames[ticker] = df[["Close"]].rename(columns={"Close": ticker})
            logger.info("[train]   %s: %d rows", ticker, len(df))
        except Exception as exc:
            logger.warning("[train] Failed to fetch %s: %s", ticker, exc)

    if not frames:
        raise RuntimeError("No commodity data fetched — check internet connection")

    prices = pd.concat(frames.values(), axis=1).dropna()

    # Compute rolling returns and volatility for each ticker
    rows = []
    primary_ticker = "HG=F"  # Copper — best predictor of transformer prices
    if primary_ticker not in prices.columns:
        primary_ticker = list(prices.columns)[0]

    # We need 30 forward trading days for label
    for i in range(len(prices) - 30):
        row_date = prices.index[i]
        row: dict = {
            "date": row_date,
            "day_of_week": float(row_date.dayofweek),
            "month": float(row_date.month),
        }

        # Source / event class features: all zeros for price-series training
        # (these get populated with real values in pipeline inference)
        for ec in ["commodity_price_move", "supplier_capacity", "demand_surge",
                   "logistics_disruption", "regulatory_trade", "financial_disclosure",
                   "geopolitical_disruption", "natural_disaster", "other"]:
            row[f"ec_{ec}"] = 0.0
        row["ec_commodity_price_move"] = 1.0  # price series are commodity events

        for src in ("gdelt", "prices", "logistics", "press", "demand", "sec"):
            row[f"source_{src}"] = 0.0
        row["source_prices"] = 1.0

        # Payload price moves (all zeros for historical training rows)
        for period in ("1d", "5d", "30d"):
            row[f"move_{period}"] = 0.0

        # Commodity momentum features
        for ticker, meta in COMMODITY_TICKERS.items():
            name = meta["name"].lower()
            if ticker not in prices.columns:
                row[f"{name}_1d_pct"] = 0.0
                row[f"{name}_5d_pct"] = 0.0
                row[f"{name}_30d_pct"] = 0.0
                row[f"{name}_vol_30d"] = 0.0
                continue

            close = prices[ticker]
            c0 = float(close.iloc[i])
            if c0 == 0:
                continue

            c1 = float(close.iloc[max(0, i - 1)])
            c5 = float(close.iloc[max(0, i - 5)])
            c30 = float(close.iloc[max(0, i - 30)])

            row[f"{name}_1d_pct"]  = (c0 - c1)  / c1  * 100 if c1  else 0.0
            row[f"{name}_5d_pct"]  = (c0 - c5)  / c5  * 100 if c5  else 0.0
            row[f"{name}_30d_pct"] = (c0 - c30) / c30 * 100 if c30 else 0.0
            row[f"{name}_vol_30d"] = float(
                close.iloc[max(0, i - 30):i].pct_change().std() * 100
            ) if i >= 30 else 0.0

        # Labels: 30-day forward return of primary commodity
        c_now = float(prices[primary_ticker].iloc[i])
        c_fwd = float(prices[primary_ticker].iloc[i + 30])
        fwd_return_pct = (c_fwd - c_now) / c_now * 100 if c_now else 0.0

        row["target_magnitude"] = abs(fwd_return_pct)
        if fwd_return_pct > 2.0:
            row["target_direction"] = DIRECTION_LABEL_TO_INT["increase"]
        elif fwd_return_pct < -2.0:
            row["target_direction"] = DIRECTION_LABEL_TO_INT["decrease"]
        else:
            row["target_direction"] = DIRECTION_LABEL_TO_INT["neutral"]

        rows.append(row)

    df = pd.DataFrame(rows).set_index("date").dropna()
    logger.info("[train] Dataset: %d rows, %d features", len(df), len(df.columns) - 2)
    return df


def train_and_evaluate(df, test_months: int = 6):
    """Train XGBoost models on train split, evaluate on test split."""
    import numpy as np
    import pandas as pd
    import xgboost as xgb
    from sklearn.metrics import mean_absolute_error, accuracy_score

    feature_cols = [c for c in df.columns if c not in ("target_magnitude", "target_direction")]
    X = df[feature_cols].values
    y_magnitude = df["target_magnitude"].values
    y_direction = df["target_direction"].values.astype(int)

    # Temporal split — last N months as test
    split_idx = int(len(df) * (1 - test_months / 24))  # assume ~2yr dataset
    split_idx = max(split_idx, int(len(df) * 0.6))      # at least 60% train

    X_train, X_test = X[:split_idx], X[split_idx:]
    ym_train, ym_test = y_magnitude[:split_idx], y_magnitude[split_idx:]
    yd_train, yd_test = y_direction[:split_idx], y_direction[split_idx:]

    logger.info("[train] Train: %d rows  Test: %d rows", len(X_train), len(X_test))

    # ── Magnitude regressor ───────────────────────────────────────────────────
    mag_model = xgb.XGBRegressor(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        verbosity=0,
    )
    mag_model.fit(X_train, ym_train,
                  eval_set=[(X_test, ym_test)],
                  verbose=False)

    mag_preds = mag_model.predict(X_test)
    mae = mean_absolute_error(ym_test, mag_preds)
    logger.info("[train] Magnitude MAE: %.2f%%  (mean target: %.2f%%)",
                mae, ym_test.mean())

    # ── Direction classifier ──────────────────────────────────────────────────
    dir_model = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        use_label_encoder=False,
        eval_metric="mlogloss",
        random_state=42,
        verbosity=0,
    )
    dir_model.fit(X_train, yd_train,
                  eval_set=[(X_test, yd_test)],
                  verbose=False)

    dir_preds = dir_model.predict(X_test)
    acc = accuracy_score(yd_test, dir_preds)
    logger.info("[train] Direction accuracy: %.1f%%  (baseline: %.1f%%)",
                acc * 100,
                max(np.bincount(yd_test.astype(int))) / len(yd_test) * 100)

    return mag_model, dir_model, feature_cols, {"mae_pct": mae, "direction_acc": acc}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lookback-years", type=int, default=2,
                        help="Years of historical data to fetch (default: 2)")
    parser.add_argument("--test-months", type=int, default=6,
                        help="Months to hold out for evaluation (default: 6)")
    args = parser.parse_args()

    from apps.api.ml.price_impact import MODELS_DIR, MAGNITUDE_MODEL_PATH, \
        DIRECTION_MODEL_PATH, FEATURE_NAMES_PATH

    print(f"\n{'═' * 60}")
    print("XGBoost Price Impact Estimator — Training")
    print(f"{'═' * 60}\n")

    df = build_dataset(lookback_years=args.lookback_years)
    mag_model, dir_model, feature_cols, metrics = train_and_evaluate(df, args.test_months)

    # Persist
    with open(MAGNITUDE_MODEL_PATH, "wb") as f:
        pickle.dump(mag_model, f)
    with open(DIRECTION_MODEL_PATH, "wb") as f:
        pickle.dump(dir_model, f)
    FEATURE_NAMES_PATH.write_text(json.dumps(feature_cols, indent=2))

    print(f"\n{'═' * 60}")
    print("Results")
    print(f"{'═' * 60}")
    print(f"  Magnitude MAE    : {metrics['mae_pct']:.2f}%")
    print(f"  Direction accuracy: {metrics['direction_acc'] * 100:.1f}%")
    print(f"  Models saved to  : {MODELS_DIR}")
    print(f"\n  ✓ Reload the API to pick up new models (or restart uvicorn)")


if __name__ == "__main__":
    main()
