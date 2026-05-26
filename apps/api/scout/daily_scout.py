"""Daily Scout Agent — clusters yesterday's escalated signals, generates brief.

Algorithm:
  1. Fetch all escalated signals from the last 24h
  2. Group by event_class from classified_signals (fallback: source)
  3. Within each group, identify top signals by llm_score
  4. Claude Opus synthesises a markdown daily brief with themes + action items
  5. Persist to daily_briefs table (upsert on brief_date)

Called by the Inngest cron at 03:00 UTC daily, or manually:
  uv run python scripts/run_scout.py
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

import anthropic
from sqlalchemy import select, text

from apps.api.db.models import ClassifiedSignal, DailyBrief, Signal, SignalRelevance
from apps.api.db.session import async_session_factory
from apps.api.prompts.registry import registry as _prompt_registry
from apps.api.settings import settings

logger = logging.getLogger(__name__)

_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


async def run_daily_scout(target_date: date | None = None) -> DailyBrief:
    """Generate and persist a daily brief for target_date (defaults to today)."""
    if target_date is None:
        target_date = datetime.now(UTC).date()

    logger.info("[scout] Running daily scout for %s", target_date)

    # ── 1. Fetch escalated signals from last 24h ─────────────────────────────
    cutoff_start = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=UTC) - timedelta(hours=24)
    cutoff_end = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=UTC)

    async with async_session_factory() as session:
        rows = await session.execute(
            select(Signal, SignalRelevance, ClassifiedSignal)
            .join(SignalRelevance, Signal.id == SignalRelevance.signal_id)
            .outerjoin(ClassifiedSignal, Signal.id == ClassifiedSignal.signal_id)
            .where(
                SignalRelevance.decision == "escalate",
                Signal.ingested_at >= cutoff_start,
            )
            .order_by(SignalRelevance.llm_score.desc().nulls_last())
            .limit(60)
        )
        signals_data = rows.fetchall()

    logger.info("[scout] Found %d escalated signals", len(signals_data))

    if not signals_data:
        logger.info("[scout] No escalated signals — skipping brief generation")
        # Still upsert an empty brief so the cron doesn't retry
        return await _upsert_brief(
            brief_date=target_date,
            signal_count=0,
            themes={},
            body_markdown=f"# CIS Daily Brief — {target_date}\n\n*No escalated signals today.*",
            flagged=[],
        )

    # ── 2. Group by event_class → theme clusters ──────────────────────────────
    clusters: dict[str, list[dict]] = defaultdict(list)
    flagged_ids: list[str] = []

    for sig, rel, classified in signals_data:
        payload = sig.raw_payload or {}
        event_class = (classified.event_class if classified else None) or sig.source
        llm_score = rel.llm_score or 0.0

        entry = {
            "id": str(sig.id),
            "source": sig.source,
            "title": payload.get("title") or payload.get("headline") or payload.get("ticker", ""),
            "summary": (payload.get("summary") or payload.get("text") or "")[:300],
            "event_class": event_class,
            "llm_score": llm_score,
            "commodities": classified.commodities if classified else [],
            "geo_tags": classified.geo_tags if classified else [],
        }
        clusters[event_class].append(entry)

        if llm_score >= 0.75:
            flagged_ids.append(str(sig.id))

    # ── 3. Build prompt context ───────────────────────────────────────────────
    context_blocks: list[str] = []
    themes_meta: dict[str, int] = {}

    for event_class, entries in sorted(clusters.items(), key=lambda x: -len(x[1])):
        themes_meta[event_class] = len(entries)
        block = f"### {event_class.replace('_', ' ').title()} ({len(entries)} signals)\n"
        for e in entries[:8]:  # top 8 per cluster
            block += f"- [{e['source']}] {e['title']}: {e['summary'][:150]}\n"
        context_blocks.append(block)

    signal_context = "\n\n".join(context_blocks)

    # ── 4. Call Opus for brief generation ─────────────────────────────────────
    prompt = (
        f"Today's date: {target_date}\n"
        f"Total escalated signals: {len(signals_data)}\n\n"
        f"Signals grouped by theme:\n\n{signal_context}\n\n"
        "Write the daily intelligence brief now."
    )

    try:
        response = await _client.messages.create(
            model="claude-opus-4-5-20251101",
            max_tokens=1500,
            system=await _prompt_registry.aget("daily_brief"),
            messages=[{"role": "user", "content": prompt}],
        )
        body_markdown = response.content[0].text
    except Exception as exc:
        logger.warning("[scout] Opus call failed: %s — using stub brief", exc)
        body_markdown = (
            f"# CIS Daily Brief — {target_date}\n\n"
            f"*Brief generation failed: {exc}*\n\n"
            f"**Signals processed:** {len(signals_data)}\n\n"
            + signal_context
        )

    # ── 5. Persist ────────────────────────────────────────────────────────────
    brief = await _upsert_brief(
        brief_date=target_date,
        signal_count=len(signals_data),
        themes=themes_meta,
        body_markdown=body_markdown,
        flagged=flagged_ids[:20],
    )

    logger.info(
        "[scout] Brief persisted for %s | signals=%d themes=%d flagged=%d",
        target_date, len(signals_data), len(themes_meta), len(flagged_ids),
    )
    return brief


async def _upsert_brief(
    brief_date: date,
    signal_count: int,
    themes: dict,
    body_markdown: str,
    flagged: list[str],
) -> DailyBrief:
    """Upsert a DailyBrief row (unique on brief_date)."""
    async with async_session_factory() as session:
        existing = await session.execute(
            select(DailyBrief).where(DailyBrief.brief_date == brief_date)
        )
        brief = existing.scalar_one_or_none()

        if brief:
            brief.signal_count = signal_count
            brief.themes = themes
            brief.body_markdown = body_markdown
            brief.flagged_for_assessment = flagged
        else:
            brief = DailyBrief(
                brief_date=brief_date,
                signal_count=signal_count,
                themes=themes,
                body_markdown=body_markdown,
                flagged_for_assessment=flagged,
            )
            session.add(brief)

        await session.commit()
        await session.refresh(brief)
        return brief
