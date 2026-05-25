"""Prices ingestion agent — yfinance commodity price moves.

Tickers watched:
  HG=F  COMEX Copper (LME-correlated proxy)
  ALI=F Aluminum
  HRC=F US Midwest hot-rolled coil (GOES / steel proxy)
  CL=F  WTI Crude (freight fuel proxy)
  ^BDI  Baltic Dry Index (bulk shipping tightness)

Flags signals where single-day move ≥ 2%, 5-day ≥ 5%, or 30-day ≥ 10%.
Cadence: every 15 minutes.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import yfinance as yf

from apps.api.ingest.base import RawItem
from apps.api.ingest.runner import BaseIngestionAgent

logger = logging.getLogger(__name__)

TICKERS: dict[str, dict[str, Any]] = {
    "HG=F":  {"commodity": "Copper",   "label": "COMEX Copper Futures",           "category": "non_ferrous"},
    "ALI=F": {"commodity": "Aluminum",  "label": "CME Aluminum Futures",            "category": "non_ferrous"},
    "HRC=F": {"commodity": "GOES",      "label": "US Midwest HRC (GOES steel proxy)", "category": "ferrous"},
    "CL=F":  {"commodity": "Crude_Oil", "label": "WTI Crude Oil Futures",          "category": "freight_proxy"},
    "^BDI":  {"commodity": "BDI",       "label": "Baltic Dry Index",               "category": "logistics"},
}

# Threshold: |move| must exceed this to be flagged as a signal.
THRESHOLDS = {"1d": 0.02, "5d": 0.05, "30d": 0.10}


def _pct_change(current: float, reference: float) -> float | None:
    if reference and reference != 0:
        return (current - reference) / abs(reference)
    return None


class PricesAgent(BaseIngestionAgent):
    agent_name = "prices_agent"

    def default_lookback_hours(self) -> int:
        return 1  # Pull recent; 30-day window is computed internally from yfinance.

    def keyword_rules(self) -> list[str]:
        # Price moves are always relevant to our categories — pass all through.
        return ["copper", "aluminum", "steel", "goes", "hrc", "bdi", "crude", "freight"]

    async def pull(self, window: tuple[datetime, datetime]) -> list[RawItem]:
        items: list[RawItem] = []
        now = window[1]

        for ticker, meta in TICKERS.items():
            try:
                hist = yf.Ticker(ticker).history(period="35d", interval="1d")
                if hist.empty or len(hist) < 2:
                    logger.warning("[prices] No data for %s", ticker)
                    continue

                close_today = float(hist["Close"].iloc[-1])
                close_1d_ago = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else None
                close_5d_ago = float(hist["Close"].iloc[-6]) if len(hist) >= 6 else None
                close_30d_ago = float(hist["Close"].iloc[0]) if len(hist) >= 30 else None

                moves: dict[str, float | None] = {
                    "1d": _pct_change(close_today, close_1d_ago) if close_1d_ago else None,
                    "5d": _pct_change(close_today, close_5d_ago) if close_5d_ago else None,
                    "30d": _pct_change(close_today, close_30d_ago) if close_30d_ago else None,
                }

                # Only emit a signal if at least one threshold is crossed.
                triggered = {
                    window_label: move
                    for window_label, move in moves.items()
                    if move is not None and abs(move) >= THRESHOLDS[window_label]
                }
                if not triggered:
                    logger.debug("[prices] %s: no threshold crossed (1d=%.2f%%)", ticker, (moves["1d"] or 0) * 100)
                    continue

                payload: dict[str, Any] = {
                    "ticker": ticker,
                    "commodity": meta["commodity"],
                    "label": meta["label"],
                    "category": meta["category"],
                    "close": close_today,
                    "moves_pct": {k: round(v * 100, 3) for k, v in moves.items() if v is not None},
                    "triggered_thresholds": list(triggered.keys()),
                    "direction": "up" if sum(triggered.values()) > 0 else "down",
                    "date": hist.index[-1].strftime("%Y-%m-%d"),
                }

                items.append(
                    RawItem(
                        source="prices",
                        source_id=f"{ticker}:{hist.index[-1].strftime('%Y-%m-%d')}",
                        url=f"https://finance.yahoo.com/quote/{ticker}",
                        occurred_at=now,
                        raw_payload=payload,
                    )
                )
                logger.info(
                    "[prices] %s flagged: %s | close=%.2f",
                    ticker,
                    {k: f"{v*100:+.1f}%" for k, v in triggered.items()},
                    close_today,
                )

            except Exception as exc:
                logger.error("[prices] Error pulling %s: %s", ticker, exc)

        return items
