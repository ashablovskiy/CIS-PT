"""Per-agent configuration — JSON-backed, persisted to disk.

Stores schedule preferences and enabled flags for the 6 ingestion agents.
Defaults match the cron definitions in inngest_functions/agent_crons.py.

Changes to `enabled` take effect immediately (checked before each cron run).
Changes to schedule take effect at next API restart (Inngest crons are
registered at startup, so a redeploy/restart is needed to re-register them
with the updated cron expression).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).parent / "agent_configs.json"

SOURCES = ["prices", "gdelt", "logistics", "press", "demand", "sec"]

# Defaults match the cron cadences in agent_crons.py
_DEFAULTS: dict[str, dict] = {
    "prices":    {"enabled": True, "schedule_mode": "interval", "interval_hours": 1,  "daily_hour": 0,  "lookback_hours": 2},
    "gdelt":     {"enabled": True, "schedule_mode": "interval", "interval_hours": 1,  "daily_hour": 0,  "lookback_hours": 1},
    "logistics": {"enabled": True, "schedule_mode": "interval", "interval_hours": 1,  "daily_hour": 0,  "lookback_hours": 1},
    "press":     {"enabled": True, "schedule_mode": "interval", "interval_hours": 2,  "daily_hour": 0,  "lookback_hours": 3},
    "demand":    {"enabled": True, "schedule_mode": "interval", "interval_hours": 4,  "daily_hour": 0,  "lookback_hours": 5},
    "sec":       {"enabled": True, "schedule_mode": "daily",    "interval_hours": 24, "daily_hour": 6,  "lookback_hours": 25},
}

ALLOWED_KEYS = {"enabled", "schedule_mode", "interval_hours", "daily_hour", "lookback_hours"}


def _load() -> dict[str, dict]:
    """Load config from disk, merging with defaults so new keys always appear."""
    if _CONFIG_PATH.exists():
        try:
            data = json.loads(_CONFIG_PATH.read_text())
            return {src: {**_DEFAULTS[src], **data.get(src, {})} for src in SOURCES}
        except Exception as exc:
            logger.warning("Could not load agent_configs.json: %s — using defaults", exc)
    return {src: dict(cfg) for src, cfg in _DEFAULTS.items()}


def _save(configs: dict[str, dict]) -> None:
    _CONFIG_PATH.write_text(json.dumps(configs, indent=2))


def get_all() -> dict[str, dict]:
    return _load()


def get(source: str) -> dict:
    return _load().get(source, dict(_DEFAULTS.get(source, {})))


def update(source: str, patch: dict) -> dict:
    configs = _load()
    if source not in configs:
        raise KeyError(f"Unknown source: {source}")
    configs[source].update({k: v for k, v in patch.items() if k in ALLOWED_KEYS})
    _save(configs)
    return configs[source]


def is_enabled(source: str) -> bool:
    return bool(_load().get(source, {}).get("enabled", True))
