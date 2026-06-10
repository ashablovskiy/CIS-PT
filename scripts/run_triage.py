#!/usr/bin/env python3
"""Run the triage classifier on signals that have no classified_signals row yet.

Cheaper than the full 7-node assessment pipeline — only calls the triage node
(1 × Haiku call per signal) and writes directly to classified_signals.
Does NOT create an assessments row (that requires the full pipeline).

Usage:
    # triage all un-classified demand signals in the last 30 days
    uv run python scripts/run_triage.py --source demand

    # triage all un-classified signals across all sources (30-day window)
    uv run python scripts/run_triage.py

    # triage a specific time window
    uv run python scripts/run_triage.py --source demand --hours 720

    # dry-run: show what would be triaged without calling the LLM
    uv run python scripts/run_triage.py --source demand --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("run_triage")


async def _fetch_untriaged(
    source: str | None,
    hours: int,
    session,
) -> list[tuple[UUID, dict, str]]:
    """Return (signal_id, raw_payload, source) for signals missing classified_signals."""
    from sqlalchemy import select

    from apps.api.db.models import ClassifiedSignal, Signal, SignalRelevance

    cutoff = datetime.now(UTC) - timedelta(hours=hours)

    stmt = (
        select(Signal.id, Signal.raw_payload, Signal.source)
        .join(SignalRelevance, Signal.id == SignalRelevance.signal_id)
        .outerjoin(ClassifiedSignal, Signal.id == ClassifiedSignal.signal_id)
        .where(
            Signal.ingested_at >= cutoff,
            ClassifiedSignal.signal_id.is_(None),            # no triage row yet
            SignalRelevance.decision.in_(["review", "escalate"]),
        )
        .order_by(Signal.ingested_at.desc())
    )
    if source:
        stmt = stmt.where(Signal.source == source)

    rows = await session.execute(stmt)
    return rows.fetchall()


async def _write_classified_signal(signal_id: UUID, triage: dict, session) -> None:
    """Upsert a classified_signals row from triage output."""
    from sqlalchemy.dialects.postgresql import insert

    from apps.api.classify.schemas import EventClass
    from apps.api.db.models import ClassifiedSignal

    cs_values = {
        "signal_id": signal_id,
        "event_class":             triage.get("event_class", EventClass.OTHER),
        "secondary_event_classes": triage.get("secondary_event_classes", []),
        "geo_tags":                triage.get("geo_tags", []),
        "graph_entities":          triage.get("graph_entities", {}),
        "commodities":             triage.get("commodities", []),
        "impact_dimensions":       triage.get("impact_dimensions", []),
        "state_change":            triage.get("state_change"),
        "confidence":              triage.get("confidence", 0.0),
        "triage_reasoning":        triage.get("reasoning"),
        "classifier_version":      "triage_script_v1",
    }
    stmt = (
        insert(ClassifiedSignal)
        .values(**cs_values)
        .on_conflict_do_update(
            index_elements=["signal_id"],
            set_={k: v for k, v in cs_values.items() if k != "signal_id"},
        )
    )
    await session.execute(stmt)


async def main(args: argparse.Namespace) -> None:
    from apps.api.agents.state import AssessmentState
    from apps.api.assess.nodes.triage import triage_node
    from apps.api.db.session import async_session_factory

    label = f"source={args.source or 'ALL'}  window={args.hours}h"
    logger.info("════ run_triage | %s ════", label)

    # ── Fetch candidates ──────────────────────────────────────────────────────
    async with async_session_factory() as session:
        candidates = await _fetch_untriaged(args.source, args.hours, session)

    logger.info("Found %d un-triaged signals to classify", len(candidates))

    if args.dry_run:
        for sig_id, payload, src in candidates:
            title = (payload.get("title") or payload.get("label") or "")[:80]
            logger.info("  [dry-run] %s  %-10s  %s", sig_id, src, title)
        return

    # ── Run triage + persist ──────────────────────────────────────────────────
    ok = failed = skipped = 0
    t0_total = time.time()

    for i, (signal_id, raw_payload, source) in enumerate(candidates, 1):
        t0 = time.time()
        title = (raw_payload.get("title") or raw_payload.get("label") or "")[:60]
        logger.info("[%d/%d] %s  %s  '%s'", i, len(candidates), signal_id, source, title)

        try:
            # Build minimal AssessmentState and run only the triage node
            state = AssessmentState(
                signal_id=signal_id,
                signal_payload=raw_payload,
                trace_id=str(uuid4()),
            )
            state = await triage_node(state)

            if not state.triage_passed:
                logger.info("  → triage gate failed (event_class=other, low confidence) — skipping")
                skipped += 1
                continue

            # Extract triage dict from graph_context
            triage_data: dict = {}
            for item in state.graph_context:
                if "_triage" in item:
                    triage_data = item["_triage"]
                    break

            # Persist to classified_signals
            async with async_session_factory() as session:
                async with session.begin():
                    await _write_classified_signal(signal_id, triage_data, session)

            ec  = triage_data.get("event_class", "?")
            ent = {k: len(v) for k, v in triage_data.get("graph_entities", {}).items() if v}
            logger.info("  ✓ class=%-20s entities=%s conf=%.2f (%.1fs)",
                        ec, ent, triage_data.get("confidence", 0), time.time() - t0)
            ok += 1

        except Exception as exc:
            logger.exception("  ✗ failed: %s", exc)
            failed += 1

        # Brief pause between LLM calls to stay well within rate limits
        if i < len(candidates):
            await asyncio.sleep(0.5)

    logger.info(
        "════ done: ok=%d  skipped=%d  failed=%d  (%.0fs total) ════",
        ok, skipped, failed, time.time() - t0_total,
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Triage-classify signals missing classified_signals rows")
    ap.add_argument("--source", default=None,
                    help="filter by source name, e.g. demand, ir, press (default: all sources)")
    ap.add_argument("--hours", type=int, default=720,
                    help="look-back window in hours (default: 720 = 30 days)")
    ap.add_argument("--dry-run", action="store_true",
                    help="list candidates without calling LLM or writing to DB")
    asyncio.run(main(ap.parse_args()))
