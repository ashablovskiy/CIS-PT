#!/usr/bin/env python3
"""Backfill signal_actor_link for all existing signals.

Re-runs the Phase-1 grounding over every persisted signal using the same
entity-prior matching the scorer uses. Idempotent (upsert on (signal_id, actor)).

Usage:
    uv run python scripts/backfill_actor_links.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    from sqlalchemy import select

    from apps.api.db.models import Signal, SignalRelevance
    from apps.api.db.session import async_session_factory
    from apps.api.network.grounding import links_from_payload, persist_links

    written = 0
    signals_with_links = 0

    async with async_session_factory() as session:
        rows = (await session.execute(
            select(Signal, SignalRelevance)
            .outerjoin(SignalRelevance, Signal.id == SignalRelevance.signal_id)
        )).all()

        logger.info("Backfilling actor links for %d signals…", len(rows))

        for sig, rel in rows:
            score = None
            tier = None
            if rel is not None:
                score = rel.analyst_score if rel.analyst_score is not None else rel.llm_score
                tier = rel.impact_tier
            links = links_from_payload(sig.raw_payload or {}, score, tier)
            if links:
                n = await persist_links(session, sig.id, links)
                written += n
                signals_with_links += 1

        await session.commit()

    logger.info(
        "Done. %d links written across %d signals (%d had no actor match).",
        written, signals_with_links, len(rows) - signals_with_links,
    )


if __name__ == "__main__":
    asyncio.run(main())
