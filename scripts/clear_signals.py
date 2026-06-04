#!/usr/bin/env python3
"""Delete all signals and related data from the database.

Run this before a full backfill to start with a clean slate.
TRUNCATE ... CASCADE handles signal_relevance, event cluster links,
and any other FK dependents automatically.

Usage:
    uv run python scripts/clear_signals.py
    uv run python scripts/clear_signals.py --yes   # skip confirmation
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("clear_signals")


def main(yes: bool) -> None:
    from apps.api.settings import settings
    import psycopg2

    url = settings.database_sync_url.replace("postgresql+psycopg2://", "postgresql://")

    conn = psycopg2.connect(url, connect_timeout=30)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM signals")
            count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM signal_relevance")
            rel_count = cur.fetchone()[0]

        logger.info("Current counts: signals=%d  signal_relevance=%d", count, rel_count)

        if not yes:
            answer = input(
                "\nThis will permanently DELETE all signals and related rows.\n"
                "Type 'yes' to confirm: "
            )
            if answer.strip().lower() != "yes":
                logger.info("Aborted.")
                sys.exit(0)

        with conn.cursor() as cur:
            cur.execute("TRUNCATE signals CASCADE")

        logger.info("Done — signals table (+ FK dependents) truncated.")
    finally:
        conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--yes", action="store_true", help="skip confirmation prompt")
    main(ap.parse_args().yes)
