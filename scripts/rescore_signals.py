#!/usr/bin/env python3
"""Re-score signals that were saved with rule-based fallback scores (llm_unavailable_rule_fallback).

Runs the same relevance_scorer prompt used during live ingestion and updates
signal_relevance with proper scores, tiers, impact_type, mechanism, and
what_changed fields.

Works across all sources (press, demand, logistics, prices, gdelt, …).

Usage:
    uv run python scripts/rescore_signals.py               # all fallback signals
    uv run python scripts/rescore_signals.py --dry-run     # count only
    uv run python scripts/rescore_signals.py --limit 50    # first 50
    uv run python scripts/rescore_signals.py --source press
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("rescore_signals")

_BATCH = 5
_REVIEW_THRESHOLD   = 0.3
_ESCALATE_THRESHOLD = 0.6
_FALLBACK_REASONING = "llm_unavailable_rule_fallback"


def _get_conn():
    import psycopg2
    from apps.api.settings import settings
    url = settings.database_sync_url.replace("postgresql+psycopg2://", "postgresql://")
    return psycopg2.connect(url, connect_timeout=90)


def fetch_fallback_signals(limit: int | None, source: str | None) -> list[tuple]:
    """Return (id, source, source_id, url, occurred_at, raw_payload) for fallback-scored signals."""
    sql = """
        SELECT s.id, s.source, s.source_id, s.url, s.occurred_at, s.raw_payload
        FROM signals s
        JOIN signal_relevance sr ON s.id = sr.signal_id
        WHERE sr.reasoning = %s
    """
    params: list = [_FALLBACK_REASONING]
    if source:
        sql += " AND s.source = %s"
        params.append(source)
    sql += " ORDER BY s.occurred_at DESC"
    if limit:
        sql += f" LIMIT {int(limit)}"

    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        conn.close()


def update_batch_sync(updates: list[tuple]) -> None:
    """Bulk-update signal_relevance rows.
    Each tuple: (llm_score, decision, reasoning, impact_tier, impact_type,
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


async def _score_batch_direct(rows: list[tuple]) -> list[dict]:
    """Score a batch via the relevance_scorer prompt. Rows are DB tuples."""
    import anthropic
    from apps.api.prompts.registry import registry as _prompt_registry
    from apps.api.settings import settings

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    descriptions = []
    for idx, row in enumerate(rows, 1):
        sig_id, source, source_id, url, occurred_at, payload = row
        blob = json.dumps(payload or {}, default=str)[:300]
        descriptions.append(f"{idx}. source={source} url={url or 'n/a'}\n{blob}")

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
    logger.info("Fetching fallback-scored signals (reasoning=%s)…", _FALLBACK_REASONING)
    rows = fetch_fallback_signals(args.limit, args.source)

    label = f"source={args.source or 'ALL'}"
    logger.info("Found %d signals to re-score (%s)", len(rows), label)
    if args.dry_run or not rows:
        if not rows:
            logger.info("Nothing to do.")
        # Show breakdown by source even in dry-run
        from collections import Counter
        counts = Counter(r[1] for r in rows)
        for src, cnt in sorted(counts.items()):
            logger.info("  %s: %d", src, cnt)
        return

    ok = failed = 0
    t0_total = time.time()

    for batch_start in range(0, len(rows), _BATCH):
        batch_rows = rows[batch_start : batch_start + _BATCH]

        try:
            score_objs = await _score_batch_direct(batch_rows)
        except Exception as exc:
            logger.warning("Batch %d–%d scoring failed: %s",
                           batch_start, batch_start + len(batch_rows), exc)
            failed += len(batch_rows)
            await asyncio.sleep(2)
            continue

        updates = []
        for row, obj in zip(batch_rows, score_objs):
            score = float(obj.get("relevance", 0.0))
            decision = (
                "escalate" if score >= _ESCALATE_THRESHOLD
                else "review" if score >= _REVIEW_THRESHOLD
                else "discard"
            )
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
        # Pad with fallbacks for any items the LLM truncated
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

        done = batch_start + len(batch_rows)
        pct = done / len(rows) * 100
        sample = score_objs[0] if score_objs else {}
        logger.info(
            "[%.0f%%] %d/%d done | sample: score=%.2f tier=%s type=%s",
            pct, done, len(rows),
            float(sample.get("relevance", 0)), sample.get("tier"), sample.get("impact_type"),
        )
        await asyncio.sleep(0.3)

    elapsed = time.time() - t0_total
    logger.info(
        "════ done: ok=%d  failed=%d  (%.0fs, %.1f signals/min) ════",
        ok, failed, elapsed, ok / elapsed * 60 if elapsed else 0,
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Re-score fallback-scored signals with LLM")
    ap.add_argument("--dry-run", action="store_true",
                    help="count candidates without scoring or updating")
    ap.add_argument("--limit", type=int, default=None,
                    help="process only the first N signals")
    ap.add_argument("--source", default=None,
                    help="filter by source, e.g. press, demand, gdelt")
    asyncio.run(main(ap.parse_args()))
