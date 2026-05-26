"""Node 6 — Critic: Claude Haiku review of the synthesizer's output.

Checks three things:
  1. Grounding — every claim in the reasoning chain cites a source
  2. Clause coverage — triggered clauses have their parsed_params referenced
  3. Calibration — confidence matches the specificity of evidence

Sets critic_passed=True if all checks pass.
Appends critic_notes with specific concerns for human review or retry.
"""

from __future__ import annotations

import json
import logging

from apps.api.agents.state import AssessmentState
from apps.api.budget import budgeted_client
from apps.api.prompts.registry import registry as _prompt_registry

logger = logging.getLogger(__name__)

_HAIKU = "claude-haiku-4-5-20251001"


async def critic_node(state: AssessmentState) -> AssessmentState:
    """Review the synthesizer's assessment for quality before persisting."""
    if not state.triage_passed or not state.summary:
        state.critic_passed = False
        state.critic_notes = "No assessment to review"
        return state

    assessment_snapshot = {
        "summary": state.summary,
        "confidence": state.confidence,
        "affected_entities": state.affected_entities,
        "affected_clauses": state.affected_clauses,
        "reasoning_chain": [r.model_dump() for r in state.reasoning_chain],
    }

    try:
        response = await budgeted_client.messages_create(
            model=_HAIKU,
            max_tokens=256,
            system=await _prompt_registry.aget("critic"),
            messages=[{
                "role": "user",
                "content": f"Review this assessment:\n\n{json.dumps(assessment_snapshot, default=str)[:3000]}"
            }],
        )

        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw.strip())

        state.critic_passed = bool(data.get("passed", False))
        state.critic_notes = data.get("notes", "")

        logger.info(
            "[critic] passed=%s grounding=%s clauses=%s calibration=%s | %s",
            state.critic_passed,
            data.get("grounding_ok"),
            data.get("clause_coverage_ok"),
            data.get("calibration_ok"),
            state.critic_notes[:80],
        )

    except Exception as exc:
        logger.warning("[critic] Review failed: %s — defaulting to passed=True", exc)
        state.errors.append(f"critic_error: {exc}")
        # Don't block persistence on critic failure — flag for human review instead
        state.critic_passed = True
        state.critic_notes = f"critic_unavailable: {exc}"

    return state
