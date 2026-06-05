"""Agent observability + configuration routes."""

from __future__ import annotations

import importlib
import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from apps.api import agent_configs, agent_runtime
from apps.api.db.models import AgentRun, Signal, SignalRelevance
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
    "ir":        ("apps.api.ingest.sources.ir_agent",        "IrAgent"),
    "mysteel":   ("apps.api.ingest.sources.mysteel_agent",   "MysteelAgent"),
}


# ── Status ─────────────────────────────────────────────────────────────────────

@router.get("/status")
async def agents_status(hours: int = Query(default=24, ge=1, le=168)) -> list[dict]:
    """Return per-source ingestion stats for the last N hours.

    All 6 ingestion agents are ALWAYS included in the response.
    For each: signal counts from the `signals` table PLUS real run telemetry
    from `agent_runs` (so "Last run" is honest even when the run produced
    zero above-threshold signals — common under the strict scorer).
    """
    cutoff = datetime.now(UTC) - timedelta(hours=hours)

    # Seed with zero-stat entries so the response is always len(_SOURCES) rows.
    active = agent_runtime.snapshot()
    by_source: dict[str, dict] = {
        src: {
            "source":     src,
            "total":      0,
            "escalated":  0,
            "discarded":  0,
            "last_seen":  None,        # last signal in DB
            # Live status (from in-process runtime registry)
            "is_running":     src in active,
            "running_since":  active.get(src),
            # Run telemetry (from agent_runs) — populated below
            "last_run_at":     None,
            "last_run_status": None,
            "last_pulled":     None,
            "last_passed_rules": None,
            "last_passed_llm": None,
            "last_classified": None,
            "last_notes":      None,
        }
        for src in _SOURCES
    }

    async with async_session_factory() as session:
        # ── Signal counts ──────────────────────────────────────────────────
        rows = await session.execute(
            select(
                Signal.source,
                func.count(Signal.id).label("total"),
                func.max(Signal.ingested_at).label("last_seen"),
            )
            .where(Signal.ingested_at >= cutoff)
            .group_by(Signal.source)
        )
        for source, total, last_seen in rows:
            if source not in by_source:
                by_source[source] = {
                    "source": source, "total": 0, "escalated": 0,
                    "discarded": 0, "last_seen": None,
                    "is_running": source in active,
                    "running_since": active.get(source),
                    "last_run_at": None, "last_run_status": None,
                    "last_pulled": None, "last_passed_rules": None,
                    "last_passed_llm": None, "last_classified": None,
                    "last_notes": None,
                }
            by_source[source]["total"]     = total
            by_source[source]["last_seen"] = last_seen.isoformat() if last_seen else None

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

        # ── Run telemetry: last AgentRun per source ────────────────────────
        # agent_runs.agent_name uses pattern "{source}_agent" (set by the
        # agent class constructor). Pull the latest finished run per source.
        for source in by_source:
            agent_name = f"{source}_agent"
            run_row = (await session.execute(
                select(AgentRun)
                .where(AgentRun.agent_name == agent_name)
                .order_by(AgentRun.started_at.desc().nullslast())
                .limit(1)
            )).scalar_one_or_none()
            if run_row:
                # Prefer finished_at, fall back to started_at
                stamp = run_row.finished_at or run_row.started_at
                by_source[source]["last_run_at"]      = stamp.isoformat() if stamp else None
                by_source[source]["last_run_status"]  = run_row.status
                by_source[source]["last_pulled"]      = run_row.items_pulled
                by_source[source]["last_passed_rules"]= run_row.items_passed_rules
                by_source[source]["last_passed_llm"]  = run_row.items_passed_llm
                by_source[source]["last_classified"]  = run_row.items_classified
                by_source[source]["last_notes"]       = run_row.notes

    # Preserve canonical _SOURCES ordering (prices, gdelt, logistics, press, demand, sec)
    return [by_source[src] for src in _SOURCES if src in by_source] + [
        by_source[src] for src in by_source if src not in _SOURCES
    ]


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
    """Background task: import + run a single agent with custom lookback.

    Registers the source in the live-runtime registry for the duration so
    the Agents UI can show a 'running…' indicator. Detailed logs go to API
    stdout; structured results land in agent_runs via the runner's telemetry
    node.
    """
    agent_runtime.register_run(source)
    try:
        module_path, class_name = _AGENT_MAP[source]
        module = importlib.import_module(module_path)
        agent = getattr(module, class_name)()
        state = await agent.run(lookback_hours=lookback_hours)
        logger.info(
            "[manual run] %s: pulled=%d pre_filtered=%d llm_scored=%d "
            "escalated=%d discarded=%d errors=%s",
            source,
            len(state.raw_items),
            len(state.pre_filtered),
            len(state.llm_scored),
            len(state.escalated),
            len(state.discarded),
            state.errors,
        )
    except Exception:
        # Keep the exception type + traceback in the API log so it can be
        # tracked down — never silently swallow.
        logger.exception("[manual run] %s failed", source)
    finally:
        agent_runtime.release_run(source)


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
