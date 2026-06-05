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


def _get_conn():
    """psycopg2 sync connection — more resilient than asyncpg for cold Neon starts."""
    import psycopg2
    from apps.api.settings import settings
    url = settings.database_sync_url.replace("postgresql+psycopg2://", "postgresql://")
    return psycopg2.connect(url, connect_timeout=90)


def fetch_unscored_sync(limit: int | None) -> list[tuple]:
    """Return rows for all GDELT signals still carrying the backfill placeholder score."""
    sql = """
        SELECT s.id, s.source, s.source_id, s.url, s.occurred_at, s.raw_payload
        FROM signals s
        JOIN signal_relevance sr ON s.id = sr.signal_id
        WHERE s.source = 'gdelt'
          AND sr.reasoning = 'backfill_rule_scored'
        ORDER BY s.occurred_at DESC
    """
    if limit:
        sql += f" LIMIT {int(limit)}"

    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchall()
    finally:
        conn.close()


def update_batch_sync(updates: list[tuple]) -> None:
    """Bulk-update signal_relevance rows. Each tuple:
    (llm_score, decision, reasoning, impact_tier, impact_type,
     mechanism, signal_kind, what_changed, signal_id)
    """
    import psycopg2.extras
    sql = """
        UPDATE signal_relevance SET
            llm_score    = %s,
            decision     = %s,
            reasoning    = %s,
            impact_tier  = %s,
            impact_type  = %s,
            mechanism    = %s,
            signal_kind  = %s,
            what_changed = %s
        WHERE signal_id = %s
    """
    conn = _get_conn()
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, sql, updates, page_size=50)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


async def _score_batch_direct(items_payload: list[dict]) -> list[dict]:
    """Score a batch of raw_payloads using the relevance_scorer prompt directly.
    Bypasses the Neo4j entity-priors lookup so it works when Neo4j is offline."""
    import json

    import anthropic

    from apps.api.prompts.registry import registry as _prompt_registry

    client = anthropic.AsyncAnthropic()

    descriptions = []
    for idx, payload in enumerate(items_payload, 1):
        blob = json.dumps(payload, default=str)[:300]
        descriptions.append(f"{idx}. source=gdelt url={payload.get('url', 'n/a')}\n{blob}")

    user_msg = "Score each signal:\n\n" + "\n\n---\n\n".join(descriptions)

    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        system=await _prompt_registry.aget("relevance_scorer"),
        messages=[{"role": "user", "content": user_msg}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        return json.loads(raw)
    except Exception:
        bracket = raw.rfind("},")
        if bracket == -1:
            bracket = raw.rfind("}")
        partial = raw[: bracket + 1].rstrip().rstrip(",") + "]"
        if not partial.startswith("["):
            partial = "[" + partial
        try:
            return json.loads(partial)
        except Exception:
            return []


async def main(args: argparse.Namespace) -> None:

    # Use psycopg2 sync for the query — avoids asyncpg cold-start failures
    logger.info("Fetching un-scored GDELT signals from DB…")
    rows = fetch_unscored_sync(args.limit)

    logger.info("Found %d GDELT signals to re-score", len(rows))
    if args.dry_run or not rows:
        if not rows:
            logger.info("Nothing to do.")
        return

    ok = failed = 0
    t0_total = time.time()

    # Process in batches of 5 (matches runner's batch size for the scorer prompt)
    for batch_start in range(0, len(rows), _BATCH):
        batch_rows = rows[batch_start : batch_start + _BATCH]

        payloads = [r[5] or {} for r in batch_rows]
        try:
            score_objs = await _score_batch_direct(payloads)
        except Exception as exc:
            logger.warning("Batch %d–%d scoring failed: %s",
                           batch_start, batch_start + len(batch_rows), exc)
            failed += len(batch_rows)
            continue

        # Build update tuples
        updates = []
        for row, obj in zip(batch_rows, score_objs):
            score = float(obj.get("relevance", 0.0))
            decision = ("escalate" if score >= _ESCALATE_THRESHOLD
                        else "review" if score >= _REVIEW_THRESHOLD
                        else "discard")
            tier = obj.get("tier")
            try:
                tier = int(tier) if tier is not None else None
            except (TypeError, ValueError):
                tier = None
            updates.append((
                score,
                decision,
                obj.get("reasoning", ""),
                tier,
                obj.get("impact_type"),
                obj.get("mechanism"),
                obj.get("signal_kind"),
                obj.get("what_changed"),
                row[0],  # signal_id UUID
            ))
        # Pad with fallbacks if LLM returned fewer items than input
        for row in batch_rows[len(score_objs):]:
            updates.append((0.0, "discard", "scoring_truncated",
                            None, None, None, None, None, row[0]))

        try:
            update_batch_sync(updates)
            ok += len(updates)
        except Exception as exc:
            logger.warning("DB update for batch %d failed: %s", batch_start, exc)
            failed += len(batch_rows)
            continue

        pct = (batch_start + len(batch_rows)) / len(rows) * 100
        if score_objs:
            s = score_objs[0]
            logger.info(
                "Progress: %d/%d (%.0f%%) | sample: score=%.2f tier=%s type=%s",
                batch_start + len(batch_rows), len(rows), pct,
                float(s.get("relevance", 0)), s.get("tier"), s.get("impact_type"),
            )
        await asyncio.sleep(0.3)

    elapsed = time.time() - t0_total
    logger.info(
        "════ done: ok=%d  failed=%d  (%.0fs, %.1f/min) ════",
        ok, failed, elapsed, ok / elapsed * 60 if elapsed else 0,
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Re-score GDELT backfill signals with LLM")
    ap.add_argument("--dry-run", action="store_true",
                    help="count candidates without scoring or updating")
    ap.add_argument("--limit", type=int, default=None,
                    help="process only the first N signals (for testing)")
    asyncio.run(main(ap.parse_args()))
