#!/usr/bin/env python3
"""Historical backfill — all ingestion sources through their full LLM pipeline.

Every source — including GDELT — runs through the standard ingestion pipeline:
  pull → rule filter → LLM relevance score → persist

GDELT notes:
  GdeltAgent.pull() auto-selects DOC API for windows > 6 h and chunks the
  window into ≤7-day slices with rate-limiting between each.  All articles
  are then LLM-scored via the relevance_scorer prompt — no more flat 0.4.
  For very deep windows (>21 d) the DOC API may return sparse results; use
  uv run python scripts/collect_gdelt_30d.py --days N  for a dedicated
  GDELT-only run, then uv run python scripts/rescore_gdelt.py to LLM-score.

Realistic depth per source (30 d window):
  gdelt     DOC API 7-day slices → deep (limited by API rate + results)
  sec       EDGAR returns ~30 d of filings → deep
  ir        Google News RSS (~weeks) + native RSS → partial
  press     trade RSS (feed depth 1–3 weeks) → partial
  demand    hyperscaler press rooms + Google News → partial
  prices    yfinance current snapshot per ticker → shallow (~3 signals)
  logistics Splash247 RSS + BDRY → partial

Usage:
    uv run python scripts/backfill_15d.py              # all sources, 15 days
    uv run python scripts/backfill_15d.py --days 30
    uv run python scripts/backfill_15d.py --only gdelt,sec,ir
    uv run python scripts/backfill_15d.py --only gdelt --days 15
"""
from __future__ import annotations

import argparse
import asyncio
import importlib
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill_15d")

_AGENTS = {
    "gdelt":     ("apps.api.ingest.sources.gdelt_agent",     "GdeltAgent"),
    "prices":    ("apps.api.ingest.sources.prices_agent",    "PricesAgent"),
    "logistics": ("apps.api.ingest.sources.logistics_agent", "LogisticsAgent"),
    "press":     ("apps.api.ingest.sources.press_agent",     "PressAgent"),
    "demand":    ("apps.api.ingest.sources.demand_agent",    "DemandAgent"),
    "sec":       ("apps.api.ingest.sources.sec_agent",       "SecAgent"),
    "ir":        ("apps.api.ingest.sources.ir_agent",        "IrAgent"),
}


async def _run_agent(source: str, hours: int) -> dict:
    t0 = time.time()
    try:
        mod_path, cls_name = _AGENTS[source]
        Agent = getattr(importlib.import_module(mod_path), cls_name)
        state = await Agent().run(lookback_hours=hours)
        return {
            "source":       source,
            "pulled":       len(state.raw_items),
            "pre_filtered": len(state.pre_filtered),
            "llm_scored":   len(state.llm_scored),
            "escalated":    len(state.escalated),
            "errors":       state.errors,
            "secs":         round(time.time() - t0, 1),
        }
    except Exception as exc:
        logger.exception("[%s] agent failed", source)
        return {"source": source, "error": str(exc), "secs": round(time.time() - t0, 1)}


async def main(args: argparse.Namespace) -> None:
    hours = args.days * 24
    only_set = {s.strip() for s in args.only.split(",") if s.strip()} if args.only else None
    sources = [s for s in _AGENTS if only_set is None or s in only_set]

    logger.info("════ backfill | %dd (%dh) | sources=%s ════", args.days, hours, sources)
    wall_t0 = time.time()
    results: list[dict] = []

    for source in sources:
        logger.info("════ %s ════", source)
        result = await _run_agent(source, hours)
        results.append(result)
        logger.info("[%s] %s", source, result)

    # ── Summary ────────────────────────────────────────────────────────────────
    logger.info("")
    logger.info("════════ BACKFILL SUMMARY (%dd) ════════", args.days)
    total_pulled = total_scored = 0
    for r in results:
        if "error" in r:
            logger.info("  %-10s ERROR: %s", r["source"], str(r["error"])[:80])
        else:
            total_pulled += r["pulled"]
            total_scored += r["llm_scored"]
            logger.info(
                "  %-10s pulled=%-4d  filtered=%-4d  scored=%-4d  escalated=%-3d  (%.0fs)",
                r["source"], r["pulled"], r["pre_filtered"],
                r["llm_scored"], r["escalated"], r["secs"],
            )
    logger.info("  ──────────────────────────────────────────────")
    logger.info("  TOTAL  pulled=%d  llm-scored=%d", total_pulled, total_scored)
    logger.info("  Wall time: %.0fs", time.time() - wall_t0)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Historical backfill — all sources, full LLM pipeline")
    ap.add_argument("--days", type=int, default=15,
                    help="lookback window in days (default: 15)")
    ap.add_argument("--only", type=str, default="",
                    help="comma-separated source subset, e.g. --only gdelt,sec,ir")
    asyncio.run(main(ap.parse_args()))
