#!/usr/bin/env python3
"""Seed the prompt_templates table with all hardcoded prompt defaults (v1).

Run once after the migration, or re-run to add a new version if defaults changed.
Already-existing (name, version) pairs are skipped (ON CONFLICT DO NOTHING).

Usage:
    uv run python scripts/seed_prompts.py
    uv run python scripts/seed_prompts.py --force   # deactivate all, re-seed as new version
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

sys.path.insert(0, ".")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def seed(force: bool = False) -> None:
    from sqlalchemy import select
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from apps.api.db.models import PromptTemplate
    from apps.api.db.session import async_session_factory
    from apps.api.prompts.registry import registry

    defaults = registry.all_defaults()

    async with async_session_factory() as session:
        for name, data in defaults.items():
            # Determine next version number
            existing = await session.execute(
                select(PromptTemplate)
                .where(PromptTemplate.name == name)
                .order_by(PromptTemplate.version.desc())
                .limit(1)
            )
            latest = existing.scalar_one_or_none()

            if latest and not force:
                logger.info("[seed] %s already exists at v%d — skipping", name, latest.version)
                continue

            next_version = (latest.version + 1) if latest else 1

            if force and latest:
                # Deactivate all existing versions for this name
                all_active = await session.execute(
                    select(PromptTemplate).where(
                        PromptTemplate.name == name,
                        PromptTemplate.is_active == True,  # noqa: E712
                    )
                )
                for row in all_active.scalars():
                    row.is_active = False

            template = PromptTemplate(
                name=name,
                version=next_version,
                system_text=data["system_text"],
                description=data["description"],
                model_hint=data["model_hint"],
                is_active=True,
                created_by="seed",
            )
            session.add(template)
            logger.info("[seed] Inserted %s v%d (active)", name, next_version)

        await session.commit()

    logger.info("[seed] Done. Prompt registry seeded with %d prompts.", len(defaults))

    # Force registry to reload from DB on next access
    from apps.api.prompts.registry import registry
    registry.reload()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--force",
        action="store_true",
        help="Insert a new version even if one already exists (bumps version number)",
    )
    args = parser.parse_args()
    asyncio.run(seed(force=args.force))
