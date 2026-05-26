"""In-memory registry of agents currently running in this API process.

Used to surface a live "running…" indicator in the Agents UI so users can
see that a triggered run is actually in flight (otherwise long-running
agents like GDELT, which can take a minute to score 200 items, look frozen).

Covers BOTH manual runs (POST /api/agents/run/{source}) AND Inngest cron
runs — both call register_run() / release_run() at start/end.

Limitation: single-process only. If you scale to multiple API workers a
parallel run on worker A is invisible to a /status request hitting worker B.
For the current single-worker deployment this is fine; for multi-worker
production, replace with a Redis SETEX or similar.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

# Map: source key (e.g. "gdelt") → ISO timestamp when the run started.
_ACTIVE: dict[str, str] = {}


def register_run(source: str) -> None:
    """Mark an agent as currently running. Call at the start of every run."""
    _ACTIVE[source] = datetime.now(UTC).isoformat()
    logger.info("[runtime] %s registered as running", source)


def release_run(source: str) -> None:
    """Mark an agent as no longer running. Call in a finally block."""
    if source in _ACTIVE:
        del _ACTIVE[source]
        logger.info("[runtime] %s released", source)


def is_running(source: str) -> bool:
    return source in _ACTIVE


def started_at(source: str) -> str | None:
    return _ACTIVE.get(source)


def snapshot() -> dict[str, str]:
    """Return a copy of all active runs {source: started_at_iso}."""
    return dict(_ACTIVE)
