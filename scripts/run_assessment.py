#!/usr/bin/env python3
"""Manual assessment runner — test the 7-node pipeline end-to-end.

Usage:
    uv run python scripts/run_assessment.py               # all unassessed escalated signals
    uv run python scripts/run_assessment.py --signal-id <uuid>   # specific signal
    uv run python scripts/run_assessment.py --hours 24    # look back 24h for unassessed
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from uuid import UUID

sys.path.insert(0, ".")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


async def run_single(signal_id: UUID) -> None:
    from sqlalchemy import select
    from apps.api.db.models import Signal
    from apps.api.db.session import async_session_factory
    from apps.api.assess.pipeline import run_assessment

    async with async_session_factory() as session:
        row = await session.execute(select(Signal).where(Signal.id == signal_id))
        signal = row.scalar_one_or_none()
        if not signal:
            logger.error("Signal %s not found", signal_id)
            return

    state = await run_assessment(signal_id, signal.raw_payload)
    _print_result(state)


async def run_batch(hours: int) -> None:
    from apps.api.assess.pipeline import run_assessments_for_escalated
    states = await run_assessments_for_escalated(lookback_hours=hours)
    if not states:
        print("No unassessed escalated signals found.")
        return
    for state in states:
        _print_result(state)


def _print_result(state) -> None:
    print("\n" + "═" * 70)
    print(f"signal_id : {state.signal_id}")
    print(f"triage    : {'PASSED' if state.triage_passed else 'SKIPPED'}")
    if not state.triage_passed:
        return
    print(f"critic    : {'PASSED' if state.critic_passed else 'NEEDS REVIEW'}")
    print(f"confidence: {state.confidence:.2f}")
    print(f"errors    : {state.errors or 'none'}")
    print()
    print("SUMMARY:")
    print(f"  {state.summary}")
    if state.affected_entities:
        print("\nAFFECTED ENTITIES:")
        for k, v in state.affected_entities.items():
            if v:
                print(f"  {k}: {v}")
    if state.affected_clauses:
        print("\nCLAUSE IMPACTS:")
        for c in state.affected_clauses[:3]:
            triggered = "⚠ TRIGGERED" if c.get("triggered") else "  ok"
            print(f"  {triggered}  [{c.get('clause_type')}] {c.get('detail','')[:80]}")
    if state.impact_by_dimension:
        print("\nIMPACT BY DIMENSION:")
        for dim, detail in state.impact_by_dimension.items():
            if isinstance(detail, dict):
                print(f"  {dim}: {detail.get('direction','')} {detail.get('magnitude_pct','?')}%  "
                      f"confidence={detail.get('confidence','?')}")
    if state.reasoning_chain:
        print("\nREASONING CHAIN:")
        for step in state.reasoning_chain[:3]:
            print(f"  {step.step}. {step.claim}")
            print(f"     → {step.inference}")
    if state.critic_notes and state.critic_notes != "none":
        print(f"\nCRITIC NOTES: {state.critic_notes}")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--signal-id", help="Specific signal UUID to assess")
    parser.add_argument("--hours", type=int, default=48,
                        help="Hours lookback for unassessed escalated signals")
    args = parser.parse_args()

    if args.signal_id:
        await run_single(UUID(args.signal_id))
    else:
        await run_batch(args.hours)


if __name__ == "__main__":
    asyncio.run(main())
