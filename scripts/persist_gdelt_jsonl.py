#!/usr/bin/env python3
"""Persist collected GDELT JSONL data directly into the signals table.

Reads the JSONL file written by collect_gdelt_30d.py and inserts records
into signals + signal_relevance using psycopg2 (sync, no asyncio).
Applies the same keyword rule-filter as the agent pipeline.
LLM scoring is skipped — all items get decision='review' with llm_score=0.4.
Safe to re-run: ON CONFLICT DO NOTHING on source_id.

Usage:
    uv run python scripts/persist_gdelt_jsonl.py
    uv run python scripts/persist_gdelt_jsonl.py --input data/gdelt_30d.jsonl
    uv run python scripts/persist_gdelt_jsonl.py --dry-run   # count only, no insert
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("persist_gdelt")

# ── Keyword rule filter (mirrors GdeltAgent.keyword_rules) ───────────────────

_KEYWORDS = [
    "transformer", "electrical steel", "goes", "siemens energy",
    "hitachi energy", "ge vernova", "hyundai", "posco", "nippon steel",
    "tap changer", "oltc", "bushing", "grid", "power", "substation",
    "grain oriented", "hyosung", "mitsubishi electric", "weg",
    "jfe steel", "cleveland-cliffs", "baosteel",
]


def _passes_rule_filter(payload: dict) -> bool:
    blob = json.dumps(payload, default=str).lower()
    return any(kw in blob for kw in _KEYWORDS)


def _content_hash(payload: dict) -> str:
    serialized = json.dumps(payload, sort_keys=True, default=str).encode()
    return hashlib.sha256(serialized).hexdigest()[:32]


# ── DB helpers (sync psycopg2) ────────────────────────────────────────────────

def _make_conn(database_sync_url: str):
    import psycopg2
    # Strip SQLAlchemy dialect prefix
    url = database_sync_url.replace("postgresql+psycopg2://", "postgresql://")
    return psycopg2.connect(url, connect_timeout=60)


def _upsert_signal(cur, item: dict) -> int | None:
    """Insert into signals, return signal_id (or None if duplicate)."""
    sql = """
    INSERT INTO signals (source, source_id, raw_payload, url, occurred_at, content_hash)
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT ON CONSTRAINT uq_signal_source_id DO NOTHING
    RETURNING id
    """
    occurred_at = item.get("occurred_at") or datetime.now(UTC).isoformat()
    cur.execute(sql, (
        "gdelt",
        item.get("source_id", f"gdelt:{abs(hash(item.get('url','')))}"),
        json.dumps(item, default=str),
        item.get("url", ""),
        occurred_at,
        _content_hash(item),
    ))
    row = cur.fetchone()
    if row:
        return row[0]
    # Conflict — fetch existing id
    cur.execute(
        "SELECT id FROM signals WHERE source_id = %s",
        (item.get("source_id"),),
    )
    existing = cur.fetchone()
    return existing[0] if existing else None


def _upsert_relevance(cur, signal_id: int) -> None:
    sql = """
    INSERT INTO signal_relevance (signal_id, rule_score, llm_score, decision, reasoning)
    VALUES (%s, %s, %s, %s, %s)
    ON CONFLICT (signal_id) DO UPDATE
        SET llm_score = EXCLUDED.llm_score,
            decision  = EXCLUDED.decision,
            reasoning = EXCLUDED.reasoning
    """
    cur.execute(sql, (signal_id, 1.0, 0.4, "review", "backfill_rule_scored"))


# ── Main ──────────────────────────────────────────────────────────────────────

def main(args: argparse.Namespace) -> None:
    from apps.api.settings import settings

    input_path = Path(args.input)
    if not input_path.exists():
        logger.error("Input file not found: %s", input_path)
        sys.exit(1)

    # Load items
    items: list[dict] = []
    with input_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    logger.info("Loaded %d items from %s", len(items), input_path)

    # Rule filter
    kept = [item for item in items if _passes_rule_filter(item)]
    logger.info("After rule filter: %d items (dropped %d)", len(kept), len(items) - len(kept))

    if args.dry_run:
        logger.info("Dry-run: would persist %d GDELT signals", len(kept))
        return

    # Persist
    conn = _make_conn(settings.database_sync_url)
    conn.autocommit = False
    inserted = 0
    skipped = 0
    try:
        with conn.cursor() as cur:
            for i, item in enumerate(kept):
                signal_id = _upsert_signal(cur, item)
                if signal_id:
                    _upsert_relevance(cur, signal_id)
                    inserted += 1
                else:
                    skipped += 1
                if (i + 1) % 50 == 0:
                    conn.commit()
                    logger.info("Progress: %d/%d inserted=%d skipped=%d",
                                i + 1, len(kept), inserted, skipped)
        conn.commit()
    except Exception as exc:
        conn.rollback()
        logger.error("Insert failed: %s", exc)
        raise
    finally:
        conn.close()

    logger.info("Done: inserted=%d skipped(dup)=%d", inserted, skipped)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="data/gdelt_30d.jsonl")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    main(args)
