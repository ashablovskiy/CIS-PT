#!/usr/bin/env python3
"""Manual agent runner — for testing and ad-hoc backfills.

Usage:
    uv run python scripts/run_agents.py [--agent AGENT] [--hours N] [--all]

Examples:
    uv run python scripts/run_agents.py --agent prices --hours 24
    uv run python scripts/run_agents.py --all --hours 72
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import UTC, datetime

sys.path.insert(0, ".")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


AGENT_REGISTRY: dict[str, tuple[str, str]] = {
    "prices":    ("apps.api.ingest.sources.prices_agent",   "PricesAgent"),
    "gdelt":     ("apps.api.ingest.sources.gdelt_agent",    "GdeltAgent"),
    "logistics": ("apps.api.ingest.sources.logistics_agent","LogisticsAgent"),
    "press":     ("apps.api.ingest.sources.press_agent",    "PressAgent"),
    "demand":    ("apps.api.ingest.sources.demand_agent",   "DemandAgent"),
    "sec":       ("apps.api.ingest.sources.sec_agent",      "SecAgent"),
}


async def run_agent(name: str, hours: int) -> dict:
    import importlib

    module_path, class_name = AGENT_REGISTRY[name]
    module = importlib.import_module(module_path)
    AgentClass = getattr(module, class_name)

    logger.info("▶ Running %s | lookback=%dh", name, hours)
    t0 = datetime.now(UTC)
    agent = AgentClass()
    state = await agent.run(lookback_hours=hours)
    elapsed = (datetime.now(UTC) - t0).total_seconds()

    result = {
        "agent": name,
        "pulled": len(state.raw_items),
        "pre_filtered": len(state.pre_filtered),
        "llm_scored": len(state.llm_scored),
        "escalated": len(state.escalated),
        "errors": state.errors,
        "elapsed_s": round(elapsed, 1),
    }

    status = "✓" if not state.errors else "✗"
    logger.info(
        "%s %s: pulled=%d filtered=%d scored=%d escalated=%d errors=%d (%.1fs)",
        status, name,
        result["pulled"], result["pre_filtered"],
        result["llm_scored"], result["escalated"],
        len(result["errors"]), result["elapsed_s"],
    )
    if state.errors:
        for e in state.errors:
            logger.warning("  error: %s", e)
    for item in state.escalated[:3]:
        payload = item.item.raw_payload
        title = payload.get("title") or payload.get("ticker") or payload.get("gkg_record_id", "")
        logger.info("  ESCALATED [%.2f] %s", item.llm_score, str(title)[:70])

    return result


async def main():
    parser = argparse.ArgumentParser(description="Run CIS ingestion agents manually")
    parser.add_argument("--agent", choices=list(AGENT_REGISTRY.keys()), help="Agent to run")
    parser.add_argument("--all", action="store_true", help="Run all agents sequentially")
    parser.add_argument("--hours", type=int, default=None, help="Lookback hours (default: agent default)")
    args = parser.parse_args()

    if not args.agent and not args.all:
        parser.print_help()
        sys.exit(1)

    agents_to_run = list(AGENT_REGISTRY.keys()) if args.all else [args.agent]
    results = []

    for name in agents_to_run:
        hours = args.hours or {"prices": 2, "gdelt": 1, "logistics": 1, "press": 2, "demand": 4, "sec": 72}[name]
        try:
            result = await run_agent(name, hours)
            results.append(result)
        except Exception as exc:
            logger.exception("Agent %s failed: %s", name, exc)
            results.append({"agent": name, "error": str(exc)})

    print("\n=== Summary ===")
    for r in results:
        if "error" in r:
            print(f"  {r['agent']:15s} FAILED: {r['error'][:60]}")
        else:
            print(
                f"  {r['agent']:15s} "
                f"pulled={r['pulled']:4d} "
                f"filtered={r['pre_filtered']:3d} "
                f"scored={r['llm_scored']:3d} "
                f"escalated={r['escalated']:3d} "
                f"errors={len(r['errors'])} "
                f"({r['elapsed_s']}s)"
            )


if __name__ == "__main__":
    asyncio.run(main())
