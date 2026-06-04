#!/usr/bin/env python3
"""15-day historical backfill — all ingestion sources.

GDELT strategy (can't query 15 days at once):
  1. DOC API  — 3 × 7-day slices (rate-limited 1 req/5 s, ~60 s total)
  2. GKG CSV  — fallback if DOC API returns < 50 articles per slice;
                downloads sampled 15-min GKG files (4/day × 15 days = 60 files)
  Collected to data/gdelt_15d.jsonl first (checkpoint), then persisted
  without LLM scoring (rule-scored at 'review' tier to avoid API cost).

Other agents (prices, logistics, press, demand, sec, ir):
  Full pipeline — pull → rule filter → LLM relevance score → persist.
  Actual depth limited by each source's feed (RSS feeds: 1–3 weeks;
  SEC EDGAR: ~30 days; prices: current snapshot only).

Usage:
    uv run python scripts/backfill_15d.py              # all sources, 15 days
    uv run python scripts/backfill_15d.py --days 15
    uv run python scripts/backfill_15d.py --skip-gdelt
    uv run python scripts/backfill_15d.py --gdelt-only
    uv run python scripts/backfill_15d.py --gdelt-gkg-only  # bypass DOC API
    uv run python scripts/backfill_15d.py --only sec,ir,press
"""
from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import logging
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))           # project root (apps.api.*)
sys.path.insert(0, str(_ROOT / "scripts"))  # sibling scripts (collect_gdelt_30d, persist_gdelt_jsonl)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill_15d")

_LIVE_AGENTS = {
    "prices":    ("apps.api.ingest.sources.prices_agent",    "PricesAgent"),
    "logistics": ("apps.api.ingest.sources.logistics_agent", "LogisticsAgent"),
    "press":     ("apps.api.ingest.sources.press_agent",     "PressAgent"),
    "demand":    ("apps.api.ingest.sources.demand_agent",    "DemandAgent"),
    "sec":       ("apps.api.ingest.sources.sec_agent",       "SecAgent"),
    "ir":        ("apps.api.ingest.sources.ir_agent",        "IrAgent"),
}


# ── GDELT ─────────────────────────────────────────────────────────────────────

async def _run_gdelt(days: int, gkg_only: bool, output_path: Path) -> int:
    """Collect GDELT for `days` days, persist to DB. Returns inserted count."""
    from collect_gdelt_30d import collect_via_docapi, collect_via_gkg
    from persist_gdelt_jsonl import (
        _passes_rule_filter, _make_conn, _upsert_signal, _upsert_relevance,
    )
    from apps.api.settings import settings

    now = datetime.now(UTC)
    start = now - timedelta(days=days)
    end = now
    logger.info("[gdelt] window: %s → %s (%d days)", start.date(), end.date(), days)

    all_items: list[dict] = []
    seen_urls: set[str] = set()

    if not gkg_only:
        logger.info("[gdelt] DOC API — %d slices of 7 days (rate-limited, ~60 s)…",
                    -(-days // 7))   # ceiling division
        doc_items, seen_urls = await collect_via_docapi(start, end)
        all_items.extend(doc_items)
        logger.info("[gdelt] DOC API → %d articles", len(doc_items))

        if len(doc_items) < 50:
            logger.info("[gdelt] DOC API returned < 50 articles — running GKG CSV fallback…")
            gkg_items = await collect_via_gkg(start, end, seen_urls)
            all_items.extend(gkg_items)
            logger.info("[gdelt] GKG CSV → %d additional articles", len(gkg_items))
        else:
            logger.info("[gdelt] DOC API sufficient — skipping GKG CSV")
    else:
        logger.info("[gdelt] GKG CSV only (--gdelt-gkg-only) — downloading 4 files/day…")
        gkg_items = await collect_via_gkg(start, end, seen_urls)
        all_items.extend(gkg_items)
        logger.info("[gdelt] GKG CSV → %d articles", len(gkg_items))

    # Checkpoint: save raw JSONL before persisting (safe to re-persist from this file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as fh:
        for item in all_items:
            fh.write(json.dumps(item, default=str) + "\n")
    logger.info("[gdelt] checkpoint saved → %s (%d raw articles)", output_path, len(all_items))

    # Rule filter
    kept = [item for item in all_items if _passes_rule_filter(item)]
    logger.info("[gdelt] after rule filter: %d / %d", len(kept), len(all_items))

    # Persist (sync psycopg2, idempotent ON CONFLICT DO NOTHING)
    conn = _make_conn(settings.database_sync_url)
    conn.autocommit = False
    inserted = skipped = 0
    try:
        with conn.cursor() as cur:
            for i, item in enumerate(kept):
                sig_id = _upsert_signal(cur, item)
                if sig_id:
                    _upsert_relevance(cur, sig_id)
                    inserted += 1
                else:
                    skipped += 1
                if (i + 1) % 100 == 0:
                    conn.commit()
                    logger.info("[gdelt] %d / %d — inserted=%d  skipped=%d",
                                i + 1, len(kept), inserted, skipped)
        conn.commit()
    except Exception as exc:
        conn.rollback()
        logger.error("[gdelt] persist error: %s", exc)
        raise
    finally:
        conn.close()

    logger.info("[gdelt] persist done: inserted=%d  skipped(dup)=%d", inserted, skipped)
    return inserted


# ── Live agents ───────────────────────────────────────────────────────────────

async def _run_agent(source: str, hours: int) -> dict:
    t0 = time.time()
    try:
        mod_path, cls_name = _LIVE_AGENTS[source]
        Agent = getattr(importlib.import_module(mod_path), cls_name)
        state = await Agent().run(lookback_hours=hours)
        return {
            "source": source,
            "pulled": len(state.raw_items),
            "pre_filtered": len(state.pre_filtered),
            "llm_scored": len(state.llm_scored),
            "escalated": len(state.escalated),
            "errors": state.errors,
            "secs": round(time.time() - t0, 1),
        }
    except Exception as exc:
        logger.exception("[%s] agent failed", source)
        return {"source": source, "error": str(exc), "secs": round(time.time() - t0, 1)}


# ── Main ──────────────────────────────────────────────────────────────────────

async def main(args: argparse.Namespace) -> None:
    hours = args.days * 24
    only_set = {s.strip() for s in args.only.split(",") if s.strip()} if args.only else None

    logger.info("════ backfill_15d | %dd (%dh) | %s ════",
                args.days, hours,
                "gdelt-only" if args.gdelt_only else
                "skip-gdelt" if args.skip_gdelt else "all sources")

    wall_t0 = time.time()
    gdelt_inserted = 0
    agent_results: list[dict] = []

    # ── GDELT ──────────────────────────────────────────────────────────────
    run_gdelt = (not args.skip_gdelt) and (only_set is None or "gdelt" in only_set)
    if run_gdelt:
        output_path = Path(f"data/gdelt_{args.days}d.jsonl")
        t0 = time.time()
        logger.info("════ GDELT ════")
        try:
            gdelt_inserted = await _run_gdelt(
                days=args.days,
                gkg_only=args.gdelt_gkg_only,
                output_path=output_path,
            )
        except Exception as exc:
            logger.error("[gdelt] fatal error — continuing with other agents: %s", exc)
        logger.info("════ GDELT done (%.0fs) ════", time.time() - t0)

    if args.gdelt_only:
        logger.info("════ done: gdelt inserted=%d (%.0fs total) ════",
                    gdelt_inserted, time.time() - wall_t0)
        return

    # ── Live agents ────────────────────────────────────────────────────────
    sources = [s for s in _LIVE_AGENTS if only_set is None or s in only_set]
    for source in sources:
        logger.info("════ %s ════", source)
        result = await _run_agent(source, hours)
        agent_results.append(result)
        logger.info("[%s] %s", source, result)

    # ── Summary ────────────────────────────────────────────────────────────
    logger.info("")
    logger.info("════════════ BACKFILL SUMMARY (%dd) ════════════", args.days)
    if run_gdelt:
        logger.info("  %-10s inserted=%-4d  (rule-scored, no LLM cost)", "gdelt", gdelt_inserted)
    total_pulled = total_scored = 0
    for r in agent_results:
        if "error" in r:
            logger.info("  %-10s ERROR: %s", r["source"], str(r["error"])[:80])
        else:
            total_pulled += r["pulled"]
            total_scored += r["llm_scored"]
            logger.info(
                "  %-10s pulled=%-4d  filtered=%-4d  scored=%-4d  escalated=%-3d  (%.0fs)",
                r["source"], r["pulled"], r["pre_filtered"],
                r["llm_scored"], r["escalated"], r["secs"],
            )
    logger.info("  ─────────────────────────────────────────────────")
    logger.info("  TOTAL  pulled=%d  llm-scored=%d  gdelt-inserted=%d",
                total_pulled, total_scored, gdelt_inserted)
    logger.info("  Wall time: %.0fs", time.time() - wall_t0)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="15-day historical backfill for all sources")
    ap.add_argument("--days", type=int, default=15,
                    help="lookback window in days (default: 15)")
    ap.add_argument("--skip-gdelt", action="store_true",
                    help="skip GDELT, run live agents only")
    ap.add_argument("--gdelt-only", action="store_true",
                    help="run GDELT only, skip live agents")
    ap.add_argument("--gdelt-gkg-only", action="store_true",
                    help="force GDELT to use GKG CSV instead of DOC API")
    ap.add_argument("--only", type=str, default="",
                    help="comma-separated source subset, e.g. --only gdelt,sec,ir")
    asyncio.run(main(ap.parse_args()))
