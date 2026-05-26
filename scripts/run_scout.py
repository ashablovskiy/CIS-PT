#!/usr/bin/env python3
"""Manual runner for the Daily Scout Agent.

Usage:
    uv run python scripts/run_scout.py               # today's brief
    uv run python scripts/run_scout.py --date 2025-05-24   # specific date
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import date

sys.path.insert(0, ".")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Target date YYYY-MM-DD (default: today)")
    args = parser.parse_args()

    target = date.fromisoformat(args.date) if args.date else None

    from apps.api.scout.daily_scout import run_daily_scout

    brief = await run_daily_scout(target_date=target)
    print("\n" + "═" * 70)
    print(f"brief_date  : {brief.brief_date}")
    print(f"signal_count: {brief.signal_count}")
    print(f"themes      : {brief.themes}")
    print(f"flagged     : {len(brief.flagged_for_assessment or [])} signals")
    print()
    print(brief.body_markdown)


if __name__ == "__main__":
    asyncio.run(main())
