#!/usr/bin/env python3
"""Backfill embeddings and event_id clustering for signals that have neither.

Signals ingested when Voyage API was down have embedding=NULL and event_id=NULL.
Without an embedding they can't be deduplicated in ANT Layer 2, so the same
real-world event (e.g. 3 outlets covering Camlin acquisition) adds 3× pressure
instead of 1×.

This script:
  1. Fetches signals with NULL embedding (in batches of 50)
  2. Embeds them via Voyage AI (batch API call)
  3. Stores the embedding on the signal row
  4. Runs event clustering (cosine similarity > 0.85 within 24h, different source)
     and sets event_id = canonical_signal_id
  5. Reports how many clusters were found

Safe to re-run (idempotent — skips already-embedded signals).

Free-tier mode (default, --free-tier):
    Voyage AI free tier = 3 RPM / 10K TPM.
    Batch size 10 (~3K tokens) + 21s sleep between batches.
    ~244 remaining signals ≈ 25 batches ≈ 9 minutes.

Paid-tier mode (--no-free-tier):
    Batch size 50, 0.2s sleep — for when a payment method is added.

Usage:
    uv run python scripts/recluster_events.py               # free tier (default)
    uv run python scripts/recluster_events.py --no-free-tier
    uv run python scripts/recluster_events.py --limit 50    # test first 50
    uv run python scripts/recluster_events.py --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("recluster")

_BATCH_FREE = 10    # free tier:  3 RPM / 10K TPM → ~3K tokens per request
_BATCH_PAID = 50    # paid tier:  higher limits → 50 signals per request
_SLEEP_FREE = 21.0  # seconds between batches on free tier (safely ≤ 3 RPM)
_SLEEP_PAID =  0.2


async def main(args: argparse.Namespace) -> None:
    from sqlalchemy import select, update
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from apps.api.assess.embeddings import embed_texts
    from apps.api.db.models import Signal
    from apps.api.db.session import async_session_factory
    from apps.api.network.event_cluster import (
        CLUSTER_THRESHOLD, CLUSTER_WINDOW_HOURS,
        find_event_cluster, payload_to_cluster_text,
    )

    # ── 1. Fetch un-embedded signals ─────────────────────────────────────────
    async with async_session_factory() as s:
        stmt = (
            select(Signal.id, Signal.source, Signal.source_id, Signal.raw_payload, Signal.occurred_at)
            .where(Signal.embedding.is_(None))
            .order_by(Signal.occurred_at.desc())
        )
        if args.limit:
            stmt = stmt.limit(args.limit)
        rows = (await s.execute(stmt)).all()

    batch_size = _BATCH_FREE if args.free_tier else _BATCH_PAID
    sleep_secs = _SLEEP_FREE if args.free_tier else _SLEEP_PAID
    n_batches  = -(-len(rows) // batch_size)   # ceiling division
    eta_min    = n_batches * sleep_secs / 60

    logger.info(
        "Found %d signals with NULL embedding | batch=%d sleep=%.0fs "
        "→ %d batches ≈ %.0f min (%s tier)",
        len(rows), batch_size, sleep_secs, n_batches, eta_min,
        "FREE" if args.free_tier else "PAID",
    )

    if args.dry_run:
        logger.info("[dry-run] would process %d signals — exiting", len(rows))
        return

    # ── 2. Embed + cluster in batches ─────────────────────────────────────────
    embedded = clustered = errors = 0

    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        texts = [payload_to_cluster_text(r.raw_payload or {}) for r in batch]

        try:
            vecs = await embed_texts(texts)
        except Exception as exc:
            logger.warning("Voyage batch %d–%d failed: %s", i, i + len(batch), exc)
            errors += len(batch)
            continue

        async with async_session_factory() as s:
            async with s.begin():
                for row, vec in zip(batch, vecs):
                    if vec is None:
                        continue
                    # Store embedding
                    await s.execute(
                        update(Signal)
                        .where(Signal.id == row.id)
                        .values(embedding=vec)
                    )
                    embedded += 1

                # Flush so find_event_cluster can see new embeddings
                await s.flush()

                # Run clustering for each signal in this batch
                for row, vec in zip(batch, vecs):
                    if vec is None:
                        continue
                    canonical = await find_event_cluster(
                        s,
                        signal_id=row.id,
                        embedding=vec,
                        occurred_at=row.occurred_at or datetime.now(UTC),
                        source=row.source,
                        source_id=row.source_id,
                        threshold=CLUSTER_THRESHOLD,
                        window_hours=CLUSTER_WINDOW_HOURS,
                    )
                    if str(canonical) != str(row.id):
                        # This signal is a duplicate — point to the canonical
                        await s.execute(
                            update(Signal)
                            .where(Signal.id == row.id)
                            .values(event_id=canonical)
                        )
                        clustered += 1
                    else:
                        # This signal IS canonical — set event_id = self
                        await s.execute(
                            update(Signal)
                            .where(Signal.id == row.id)
                            .values(event_id=row.id)
                        )

        done  = i + len(batch)
        pct   = done / len(rows) * 100
        remaining_batches = (len(rows) - done + batch_size - 1) // batch_size
        eta_s = remaining_batches * sleep_secs
        logger.info(
            "[%d%%] embedded=%d  clustered(dedup)=%d  errors=%d  ETA≈%dm%02ds",
            int(pct), embedded, clustered, errors,
            int(eta_s // 60), int(eta_s % 60),
        )
        if done < len(rows):
            await asyncio.sleep(sleep_secs)

    logger.info(
        "════ done ════  embedded=%d  clusters_found=%d  errors=%d",
        embedded, clustered, errors,
    )
    if clustered:
        logger.info(
            "%d signals now point to a canonical event_id — "
            "ANT Layer 2 will no longer double-count those events.",
            clustered,
        )


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Backfill embeddings and event clustering")
    ap.add_argument("--limit",      type=int, default=0,
                    help="max signals to process (default: all)")
    ap.add_argument("--dry-run",   action="store_true",
                    help="count candidates without writing to DB")
    ap.add_argument("--no-free-tier", dest="free_tier", action="store_false",
                    help="use paid-tier batch/sleep settings (batch=50, sleep=0.2s)")
    ap.set_defaults(free_tier=True)
    asyncio.run(main(ap.parse_args()))
