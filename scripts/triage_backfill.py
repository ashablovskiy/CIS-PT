#!/usr/bin/env python3
"""Run the triage classifier on all signals that have no classified_signals row.

The ingestion pipeline (runner.py) only populates signals + signal_relevance.
The triage classifier (assess/nodes/triage.py) populates classified_signals with
entity extraction, event_class, geo_tags, state_change, etc. — those are the
columns shown in the Signals table UI under "III · TRIAGE CLASSIFIER".

This script bridges the gap: it fetches every unclassified signal and runs
just the triage node (one Haiku call each), then persists to classified_signals.

Usage:
    uv run python scripts/triage_backfill.py
    uv run python scripts/triage_backfill.py --limit 50        # first N signals
    uv run python scripts/triage_backfill.py --concurrency 5   # parallel workers
    uv run python scripts/triage_backfill.py --dry-run         # count only
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("triage_backfill")


async def fetch_unclassified(session, limit: int | None) -> list[tuple[uuid.UUID, dict]]:
    """Return (signal_id, raw_payload) for signals with no classified_signals row."""
    from sqlalchemy import select, text
    from apps.api.db.models import Signal, ClassifiedSignal, SignalRelevance

    stmt = (
        select(Signal.id, Signal.raw_payload)
        .outerjoin(ClassifiedSignal, Signal.id == ClassifiedSignal.signal_id)
        .join(SignalRelevance, Signal.id == SignalRelevance.signal_id)
        .where(ClassifiedSignal.signal_id.is_(None))
        .where(SignalRelevance.decision.in_(["review", "escalate"]))
        .order_by(Signal.occurred_at.desc())
    )
    if limit:
        stmt = stmt.limit(limit)

    rows = (await session.execute(stmt)).all()
    return [(row.id, row.raw_payload) for row in rows]


async def persist_classification(session, signal_id: uuid.UUID, triage: dict) -> None:
    """Upsert a classified_signals row from triage output."""
    from sqlalchemy.dialects.postgresql import insert
    from apps.api.db.models import ClassifiedSignal

    stmt = insert(ClassifiedSignal).values(
        id=uuid.uuid4(),
        signal_id=signal_id,
        event_class=triage.get("event_class"),
        secondary_event_classes=triage.get("secondary_event_classes", []),
        geo_tags=triage.get("geo_tags", []),
        graph_entities=triage.get("graph_entities", {}),
        commodities=triage.get("commodities", []),
        impact_dimensions=triage.get("impact_dimensions", []),
        state_change=triage.get("state_change"),
        confidence=triage.get("confidence", 0.0),
        triage_reasoning=triage.get("reasoning"),
        classifier_version="backfill-v1",
    ).on_conflict_do_update(
        index_elements=["signal_id"],
        set_={
            "event_class": triage.get("event_class"),
            "secondary_event_classes": triage.get("secondary_event_classes", []),
            "geo_tags": triage.get("geo_tags", []),
            "graph_entities": triage.get("graph_entities", {}),
            "commodities": triage.get("commodities", []),
            "impact_dimensions": triage.get("impact_dimensions", []),
            "state_change": triage.get("state_change"),
            "confidence": triage.get("confidence", 0.0),
            "triage_reasoning": triage.get("reasoning"),
            "classifier_version": "backfill-v1",
        },
    )
    await session.execute(stmt)


async def classify_one(
    signal_id: uuid.UUID,
    payload: dict,
    sem: asyncio.Semaphore,
) -> tuple[uuid.UUID, dict | None, str]:
    """Run triage_node on a single signal. Returns (id, triage_dict_or_None, status)."""
    from apps.api.agents.state import AssessmentState
    from apps.api.assess.nodes.triage import triage_node

    async with sem:
        state = AssessmentState(
            signal_id=signal_id,
            signal_payload=payload,
        )
        try:
            state = await triage_node(state)
        except Exception as exc:
            return signal_id, None, f"error: {exc}"

        if not state.triage_passed:
            return signal_id, None, "skipped (OTHER/low-confidence)"

        triage = state.graph_context[0]["_triage"]
        return signal_id, triage, f"ok:{triage.get('event_class','?')}"


async def main(args: argparse.Namespace) -> None:
    from apps.api.db.session import async_session_factory

    async with async_session_factory() as session:
        logger.info("Fetching unclassified signals…")
        signals = await fetch_unclassified(session, args.limit)

    logger.info("Found %d unclassified signals to triage", len(signals))
    if args.dry_run:
        logger.info("Dry-run — exiting (would classify %d signals)", len(signals))
        return
    if not signals:
        logger.info("Nothing to do.")
        return

    sem = asyncio.Semaphore(args.concurrency)
    tasks = [classify_one(sid, payload, sem) for sid, payload in signals]

    ok = skipped = errors = 0
    async with async_session_factory() as session:
        for coro in asyncio.as_completed(tasks):
            signal_id, triage, status = await coro
            if triage is not None:
                await persist_classification(session, signal_id, triage)
                await session.commit()
                ok += 1
            elif status.startswith("skipped"):
                skipped += 1
            else:
                errors += 1
            total = ok + skipped + errors
            if total % 10 == 0 or total == len(signals):
                logger.info(
                    "[%d/%d] classified=%d  skipped=%d  errors=%d",
                    total, len(signals), ok, skipped, errors,
                )

    logger.info("Done — classified=%d  skipped=%d  errors=%d", ok, skipped, errors)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="max signals to process")
    ap.add_argument("--concurrency", type=int, default=5, help="parallel Haiku calls (default 5)")
    ap.add_argument("--dry-run", action="store_true")
    asyncio.run(main(ap.parse_args()))
