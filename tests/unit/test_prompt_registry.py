"""Unit tests for the prompt registry — fallback, cache, and default coverage."""

from __future__ import annotations

import pytest

from apps.api.prompts.registry import DEFAULTS, PromptRegistry


# ── Defaults completeness ─────────────────────────────────────────────────────

EXPECTED_PROMPT_NAMES = {
    "relevance_scorer",
    "triage_classifier",
    "critic",
    "daily_brief",
}


def test_all_expected_prompts_have_defaults():
    assert EXPECTED_PROMPT_NAMES.issubset(set(DEFAULTS.keys()))


def test_all_defaults_are_non_empty():
    for name, text in DEFAULTS.items():
        assert len(text) > 100, f"Default '{name}' is suspiciously short ({len(text)} chars)"


def test_default_prompts_contain_domain_terms():
    """Each prompt should reference power transformers or procurement domain terms."""
    domain_terms = ["transformer", "procurement", "supply", "clause", "contract"]
    for name, text in DEFAULTS.items():
        lower = text.lower()
        found = [t for t in domain_terms if t in lower]
        assert found, f"Default '{name}' contains no domain terms"


# ── Registry fallback behaviour ───────────────────────────────────────────────

def test_get_returns_default_when_cache_empty():
    """A fresh registry with empty cache should return hardcoded default."""
    reg = PromptRegistry()
    # Don't load from DB — cache is empty, _loaded_at=0 would trigger load
    # Manually populate cache to avoid DB call in unit test
    reg._cache = {}
    reg._loaded_at = float("inf")  # pretend cache is fresh but empty

    result = reg.get("triage_classifier")
    assert result == DEFAULTS["triage_classifier"]


def test_get_returns_cached_value_over_default():
    """Cache takes priority over hardcoded defaults."""
    reg = PromptRegistry()
    reg._cache = {"critic": "Custom critic prompt for testing."}
    reg._loaded_at = float("inf")  # cache is fresh

    result = reg.get("critic")
    assert result == "Custom critic prompt for testing."


def test_get_unknown_name_returns_empty_string():
    reg = PromptRegistry()
    reg._cache = {}
    reg._loaded_at = float("inf")

    result = reg.get("nonexistent_prompt_name")
    assert result == ""


def test_get_version_returns_zero_when_not_in_cache():
    reg = PromptRegistry()
    reg._versions = {}
    assert reg.get_version("relevance_scorer") == 0


def test_get_version_returns_cached_version():
    reg = PromptRegistry()
    reg._versions = {"relevance_scorer": 3}
    assert reg.get_version("relevance_scorer") == 3


def test_reload_forces_refresh():
    """After reload(), _needs_refresh() should return True."""
    reg = PromptRegistry()
    reg._loaded_at = float("inf")  # mark as fresh
    assert not reg._needs_refresh()

    reg.reload()
    assert reg._needs_refresh()


def test_all_defaults_metadata_present():
    """Every default prompt should have metadata for admin UI."""
    from apps.api.prompts.registry import METADATA
    for name in DEFAULTS:
        assert name in METADATA, f"'{name}' has no metadata entry"
        meta = METADATA[name]
        assert meta.get("description"), f"'{name}' metadata missing description"
        assert meta.get("model_hint") in ("haiku", "opus"), \
            f"'{name}' model_hint should be haiku or opus"


# ── all_defaults() helper ─────────────────────────────────────────────────────

def test_all_defaults_returns_all_names():
    reg = PromptRegistry()
    result = reg.all_defaults()
    assert set(result.keys()) == EXPECTED_PROMPT_NAMES


def test_all_defaults_has_required_keys():
    reg = PromptRegistry()
    for name, data in reg.all_defaults().items():
        assert "system_text" in data, f"'{name}' missing system_text"
        assert "description" in data, f"'{name}' missing description"
        assert "model_hint" in data, f"'{name}' missing model_hint"
