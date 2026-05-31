#!/usr/bin/env python3
"""30-day backtest backfill — run every ingestion agent over a wide window.

Runs each agent with a 720h (30-day) lookback, isolating failures so one bad
source doesn't abort the rest. Each agent's full pipeline executes (pull →
rule filter → LLM relevance score → route → persist), so results land in the
signals / signal_relevance tables exactly as a live run would, and agent_runs
gets telemetry.

Reality of 30-day depth per source:
  gdelt   true historical (DOC API date-range, chunked)         → deep
  sec     EDGAR returns ~30d of filings                          → deep
  ir      Google News RSS (~weeks) + native RSS                  → partial
  press   trade RSS (feed depth, usually 1–3 weeks)              → partial
  demand  native RSS + Google News                               → partial
  prices  yfinance emits only the latest snapshot per ticker     → shallow (~3)
  logistics depends on source feed depth                         → partial

Usage:
  uv run python scripts/backtest_30d.py
  uv run python scripts/backtest_30d.py --hours 720 --only gdelt,sec,ir
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time

# Ensure the project root is importable when run as a script file
# (sys.path[0] is the scripts/ dir otherwise, so `import apps...` fails).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backtest")

AGENTS = {
    "prices":    ("apps.api.ingest.sources.prices_agent",    "PricesAgent"),
    "gdelt":     ("apps.api.ingest.sources.gdelt_agent",     "GdeltAgent"),
    "logistics": ("apps.api.ingest.sources.logistics_agent", "LogisticsAgent"),
    "press":     ("apps.api.ingest.sources.press_agent",     "PressAgent"),
    "demand":    ("apps.api.ingest.sources.demand_agent",    "DemandAgent"),
    "sec":       ("apps.api.ingest.sources.sec_agent",       "SecAgent"),
    "ir":        ("apps.api.ingest.sources.ir_agent",        "IrAgent"),
}


async def run_one(source: str, hours: int) -> dict:
    import importlib
    t0 = time.time()
    try:
        mod, cls = AGENTS[source]
        Agent = getattr(importlib.import_module(mod), cls)
        agent = Agent()
        state = await agent.run(lookback_hours=hours)
        return {
            "source": source,
            "pulled": len(state.raw_items),
            "pre_filtered": len(state.pre_filtered),
            "llm_scored": len(state.llm_scored),
            "escalated": len(state.escalated),
            "errors": state.errors,
            "secs": round(time.time() - t0, 1),
        }
    except Exception as exc:
        logger.exception("[%s] backtest run failed", source)
        return {"source": source, "error": str(exc), "secs": round(time.time() - t0, 1)}


async def main(hours: int, only: list[str]) -> None:
    sources = only or list(AGENTS.keys())
    logger.info("Backtest start | window=%dh | sources=%s", hours, sources)
    results = []
    for src in sources:
        logger.info("──── running %s ────", src)
        res = await run_one(src, hours)
        results.append(res)
        logger.info("[%s] %s", src, res)

    logger.info("════════ BACKTEST SUMMARY ════════")
    total_pulled = total_kept = 0
    for r in results:
        if "error" in r:
            logger.info("  %-10s ERROR: %s", r["source"], r["error"][:80])
            continue
        total_pulled += r["pulled"]
        total_kept += r["llm_scored"]
        logger.info(
            "  %-10s pulled=%-4d filtered=%-4d scored=%-4d escalated=%-3d (%.1fs)",
            r["source"], r["pulled"], r["pre_filtered"], r["llm_scored"],
            r["escalated"], r["secs"],
        )
    logger.info("  TOTAL pulled=%d  persisted/scored=%d", total_pulled, total_kept)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=720, help="lookback window (default 720 = 30 days)")
    ap.add_argument("--only", type=str, default="", help="comma-separated subset of sources")
    args = ap.parse_args()
    only = [s.strip() for s in args.only.split(",") if s.strip()]
    asyncio.run(main(args.hours, only))
