#!/usr/bin/env python3
"""Retroactively LLM-score GDELT signals that were persisted with the flat
backfill score (llm_score=0.4, reasoning='backfill_rule_scored').

Runs the same relevance_scorer prompt used during live ingestion and updates
signal_relevance with proper scores, tiers, impact_type, mechanism, and
what_changed fields.

Usage:
    uv run python scripts/rescore_gdelt.py
    uv run python scripts/rescore_gdelt.py --dry-run   # show count only
    uv run python scripts/rescore_gdelt.py --limit 50  # process first N signals
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("rescore_gdelt")

_BATCH = 5          # match runner's batch size for the relevance_scorer prompt
_REVIEW_THRESHOLD  = 0.3
_ESCALATE_THRESHOLD = 0.6


async def fetch_unscored(session, limit: int | None) -> list[tuple]:
    """Return (signal_id, source, source_id, url, occurred_at, raw_payload)
    for all GDELT signals that still carry the backfill placeholder score."""
    from sqlalchemy import select, text

    from apps.api.db.models import Signal, SignalRelevance

    stmt = (
        select(
            Signal.id,
            Signal.source,
            Signal.source_id,
            Signal.url,
            Signal.occurred_at,
            Signal.raw_payload,
        )
        .join(SignalRelevance, Signal.id == SignalRelevance.signal_id)
        .where(
            Signal.source == "gdelt",
            SignalRelevance.reasoning == "backfill_rule_scored",
        )
        .order_by(Signal.occurred_at.desc())
    )
    if limit:
        stmt = stmt.limit(limit)

    rows = await session.execute(stmt)
    return rows.fetchall()


async def update_relevance(session, signal_id, scored) -> None:
    """Write the LLM-scored fields back to signal_relevance."""
    from sqlalchemy import update

    from apps.api.db.models import SignalRelevance

    score = scored.llm_score or 0.0
    if score >= _ESCALATE_THRESHOLD:
        decision = "escalate"
    elif score >= _REVIEW_THRESHOLD:
        decision = "review"
    else:
        decision = "discard"

    await session.execute(
        update(SignalRelevance)
        .where(SignalRelevance.signal_id == signal_id)
        .values(
            llm_score=score,
            decision=decision,
            reasoning=scored.llm_reasoning or "",
            impact_tier=scored.impact_tier,
            impact_type=scored.impact_type,
            mechanism=scored.mechanism,
            signal_kind=scored.signal_kind,
            what_changed=scored.what_changed,
        )
    )


async def main(args: argparse.Namespace) -> None:
    from apps.api.db.session import async_session_factory
    from apps.api.ingest.base import RawItem
    from apps.api.ingest.sources.gdelt_agent import GdeltAgent

    agent = GdeltAgent()   # inherits _score_batch from BaseIngestionAgent

    async with async_session_factory() as session:
        rows = await fetch_unscored(session, args.limit)

    logger.info("Found %d GDELT signals to re-score", len(rows))
    if args.dry_run or not rows:
        if not rows:
            logger.info("Nothing to do.")
        return

    ok = failed = 0
    t0_total = time.time()

    # Process in batches of 5 (matches runner's batch size)
    for batch_start in range(0, len(rows), _BATCH):
        batch_rows = rows[batch_start : batch_start + _BATCH]

        # Build RawItem objects from DB rows
        items = [
            RawItem(
                source=r.source,
                source_id=r.source_id,
                url=r.url,
                occurred_at=r.occurred_at.replace(tzinfo=UTC)
                if r.occurred_at.tzinfo is None else r.occurred_at,
                raw_payload=r.raw_payload or {},
            )
            for r in batch_rows
        ]

        try:
            scored_items = await agent._score_batch(items)
        except Exception as exc:
            logger.warning("Batch %d-%d scoring failed: %s",
                           batch_start, batch_start + len(batch_rows), exc)
            failed += len(batch_rows)
            continue

        async with async_session_factory() as session:
            async with session.begin():
                for row, scored in zip(batch_rows, scored_items):
                    try:
                        await update_relevance(session, row.id, scored)
                        ok += 1
                    except Exception as exc:
                        logger.warning("Update failed for %s: %s", row.id, exc)
                        failed += 1

        pct = (batch_start + len(batch_rows)) / len(rows) * 100
        logger.info(
            "Progress: %d/%d (%.0f%%) — ok=%d failed=%d",
            batch_start + len(batch_rows), len(rows), pct, ok, failed,
        )
        # Brief pause to stay within rate limits
        await asyncio.sleep(0.3)

    elapsed = time.time() - t0_total
    logger.info(
        "════ done: ok=%d  failed=%d  (%.0fs, %.1f signals/min) ════",
        ok, failed, elapsed, ok / elapsed * 60 if elapsed else 0,
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Re-score GDELT backfill signals with LLM")
    ap.add_argument("--dry-run", action="store_true",
                    help="count candidates without scoring or updating")
    ap.add_argument("--limit", type=int, default=None,
                    help="process only the first N signals (for testing)")
    asyncio.run(main(ap.parse_args()))
