"""Agent observability + configuration routes."""

from __future__ import annotations

import importlib
import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from apps.api import agent_configs
from apps.api.db.models import Signal, SignalRelevance
from apps.api.db.session import async_session_factory

router = APIRouter()
logger = logging.getLogger(__name__)

_SOURCES = agent_configs.SOURCES

# Maps source key → (module path, class name) for on-demand runs
_AGENT_MAP: dict[str, tuple[str, str]] = {
    "prices":    ("apps.api.ingest.sources.prices_agent",    "PricesAgent"),
    "gdelt":     ("apps.api.ingest.sources.gdelt_agent",     "GdeltAgent"),
    "logistics": ("apps.api.ingest.sources.logistics_agent", "LogisticsAgent"),
    "press":     ("apps.api.ingest.sources.press_agent",     "PressAgent"),
    "demand":    ("apps.api.ingest.sources.demand_agent",    "DemandAgent"),
    "sec":       ("apps.api.ingest.sources.sec_agent",       "SecAgent"),
}


# ── Status ─────────────────────────────────────────────────────────────────────

@router.get("/status")
async def agents_status(hours: int = Query(default=24, ge=1, le=168)) -> list[dict]:
    """Return per-source ingestion stats for the last N hours."""
    cutoff = datetime.now(UTC) - timedelta(hours=hours)

    async with async_session_factory() as session:
        rows = await session.execute(
            select(
                Signal.source,
                func.count(Signal.id).label("total"),
                func.max(Signal.ingested_at).label("last_seen"),
            )
            .where(Signal.ingested_at >= cutoff)
            .group_by(Signal.source)
        )
        by_source: dict[str, dict] = {}
        for source, total, last_seen in rows:
            by_source[source] = {
                "source": source,
                "total": total,
                "last_seen": last_seen.isoformat() if last_seen else None,
                "escalated": 0,
                "discarded": 0,
            }

        drows = await session.execute(
            select(
                Signal.source,
                SignalRelevance.decision,
                func.count(Signal.id).label("cnt"),
            )
            .join(SignalRelevance, Signal.id == SignalRelevance.signal_id)
            .where(Signal.ingested_at >= cutoff)
            .group_by(Signal.source, SignalRelevance.decision)
        )
        for source, decision, cnt in drows:
            if source not in by_source:
                continue
            if decision == "escalate":
                by_source[source]["escalated"] = cnt
            elif decision == "discard":
                by_source[source]["discarded"] = cnt

        return sorted(by_source.values(), key=lambda x: x["source"])


# ── Config ─────────────────────────────────────────────────────────────────────

@router.get("/config")
async def get_configs() -> dict:
    """Return configuration for all agents."""
    return agent_configs.get_all()


class AgentConfigPatch(BaseModel):
    enabled: bool | None = None
    schedule_mode: str | None = None        # "interval" | "daily"
    interval_hours: int | None = Field(None, ge=1, le=24)
    daily_hour: int | None = Field(None, ge=0, le=23)
    lookback_hours: int | None = Field(None, ge=1, le=168)


@router.put("/config/{source}")
async def update_config(source: str, patch: AgentConfigPatch) -> dict:
    """Update an agent's configuration. Enabled flag takes effect immediately;
    schedule changes apply at next API restart."""
    if source not in _SOURCES:
        raise HTTPException(status_code=404, detail=f"Unknown source: {source}")
    try:
        return agent_configs.update(source, patch.model_dump(exclude_none=True))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ── Manual run ─────────────────────────────────────────────────────────────────

class RunRequest(BaseModel):
    lookback_hours: int = Field(default=6, ge=1, le=168)


async def _run_agent_bg(source: str, lookback_hours: int) -> None:
    """Background task: import + run a single agent with custom lookback."""
    try:
        module_path, class_name = _AGENT_MAP[source]
        module = importlib.import_module(module_path)
        agent = getattr(module, class_name)()
        state = await agent.run(lookback_hours=lookback_hours)
        logger.info(
            "[manual run] %s: pulled=%d escalated=%d errors=%s",
            source, len(state.raw_items), len(state.escalated), state.errors,
        )
    except Exception as exc:
        logger.error("[manual run] %s failed: %s", source, exc)


@router.post("/run/{source}")
async def run_agent_now(
    source: str,
    body: RunRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    """Trigger a single agent run immediately with a custom lookback window."""
    if source not in _SOURCES:
        raise HTTPException(status_code=404, detail=f"Unknown source: {source}")
    background_tasks.add_task(_run_agent_bg, source, body.lookback_hours)
    return {"status": "started", "source": source, "lookback_hours": body.lookback_hours}
