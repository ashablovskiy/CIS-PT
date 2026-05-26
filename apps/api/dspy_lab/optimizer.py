"""DSPy MIPROv2 optimization pipeline for the ImpactAssessment synthesizer.

Workflow:
  1. Load training examples (bootstrap + any feedback-accepted assessments)
  2. Split 80/20 train/dev
  3. Run MIPROv2 with assessment_quality_metric
  4. Evaluate on dev set: compiled vs. baseline
  5. Persist compiled program to dspy_programs table + compiled/ directory
  6. Hot-swap synthesizer predictor if improvement is meaningful (> +0.03)

Usage:
  uv run python scripts/run_optimizer.py
  uv run python scripts/run_optimizer.py --auto heavy  # more thorough search
"""

from __future__ import annotations

import json
import logging
import os
import random
from datetime import UTC, datetime
from pathlib import Path

import dspy
from dspy.teleprompt import MIPROv2

from apps.api.dspy_lab.metrics import assessment_quality_metric
from apps.api.dspy_lab.training_data import BOOTSTRAP_EXAMPLES, get_trainset
from apps.api.assess.nodes.synthesizer import ImpactAssessment

logger = logging.getLogger(__name__)

COMPILED_DIR = Path(__file__).parent / "compiled"
COMPILED_DIR.mkdir(exist_ok=True)

_OPUS = "claude-opus-4-5-20251101"
_HAIKU = "claude-haiku-4-5-20251001"

# Use Haiku for the optimizer's meta-reasoning (cheaper) while Opus stays as student
_OPTIMIZER_LM = dspy.LM(
    model=f"anthropic/{_HAIKU}",
    api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
    max_tokens=1024,
    temperature=0.7,
)

_STUDENT_LM = dspy.LM(
    model=f"anthropic/{_OPUS}",
    api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
    max_tokens=2048,
    temperature=0.1,
)


async def run_optimization(
    auto: str = "light",
    min_improvement: float = 0.03,
    seed: int = 42,
) -> dict:
    """Run MIPROv2 and persist the compiled program.

    Args:
        auto:            MIPROv2 search budget — "light" | "medium" | "heavy"
        min_improvement: Minimum dev-set score gain to persist (avoid regressing)
        seed:            Random seed for reproducibility

    Returns:
        dict with baseline_score, optimized_score, improvement, version, persisted
    """
    random.seed(seed)

    # ── 1. Build training set ──────────────────────────────────────────────────
    trainset = get_trainset(max_bootstrap=5)

    # Shuffle and split 80/20
    random.shuffle(trainset)
    split = max(1, int(len(trainset) * 0.8))
    train = trainset[:split]
    devset = trainset[split:] or trainset[:1]  # at least 1 dev example

    logger.info(
        "[optimizer] Starting MIPROv2 | auto=%s train=%d dev=%d",
        auto, len(train), len(devset),
    )

    # ── 2. Baseline score ─────────────────────────────────────────────────────
    baseline_program = dspy.Predict(ImpactAssessment)
    with dspy.context(lm=_STUDENT_LM):
        baseline_scores = [
            assessment_quality_metric(ex, baseline_program(**ex.inputs()))
            for ex in devset
        ]
    baseline_score = sum(baseline_scores) / len(baseline_scores)
    logger.info("[optimizer] Baseline dev score: %.4f", baseline_score)

    # ── 3. MIPROv2 optimization ───────────────────────────────────────────────
    optimizer = MIPROv2(
        metric=assessment_quality_metric,
        auto=auto,
        num_threads=2,          # conservative — Anthropic rate limits
        prompt_model=_OPTIMIZER_LM,
        task_model=_STUDENT_LM,
    )

    compiled_program = optimizer.compile(
        student=dspy.Predict(ImpactAssessment),
        trainset=train,
        max_bootstrapped_demos=2,
        max_labeled_demos=3,
        requires_permission_to_run=False,
    )

    # ── 4. Evaluate compiled program ──────────────────────────────────────────
    with dspy.context(lm=_STUDENT_LM):
        opt_scores = [
            assessment_quality_metric(ex, compiled_program(**ex.inputs()))
            for ex in devset
        ]
    optimized_score = sum(opt_scores) / len(opt_scores)
    improvement = optimized_score - baseline_score

    logger.info(
        "[optimizer] Optimized dev score: %.4f (Δ=%.4f)",
        optimized_score, improvement,
    )

    # ── 5. Persist if improved ────────────────────────────────────────────────
    version = datetime.now(UTC).strftime("v%Y%m%d_%H%M")
    persisted = False

    if improvement >= min_improvement:
        # Save to filesystem
        program_path = COMPILED_DIR / f"impact_assessment_{version}.json"
        compiled_program.save(str(program_path))
        logger.info("[optimizer] Saved compiled program: %s", program_path)

        # Persist to Neon dspy_programs table
        await _persist_to_db(
            version=version,
            program_path=program_path,
            baseline_score=baseline_score,
            optimized_score=optimized_score,
            auto=auto,
            train_size=len(train),
        )
        persisted = True

        # Update symlink so synthesizer loads the latest
        latest = COMPILED_DIR / "impact_assessment_latest.json"
        if latest.exists() or latest.is_symlink():
            latest.unlink()
        latest.symlink_to(program_path.name)
        logger.info("[optimizer] Updated 'latest' symlink → %s", program_path.name)
    else:
        logger.info(
            "[optimizer] Improvement %.4f < threshold %.4f — not persisting",
            improvement, min_improvement,
        )

    return {
        "version": version,
        "baseline_score": round(baseline_score, 4),
        "optimized_score": round(optimized_score, 4),
        "improvement": round(improvement, 4),
        "persisted": persisted,
        "auto": auto,
        "train_size": len(train),
        "dev_size": len(devset),
    }


async def _persist_to_db(
    version: str,
    program_path: Path,
    baseline_score: float,
    optimized_score: float,
    auto: str,
    train_size: int,
) -> None:
    from sqlalchemy import select
    from apps.api.db.models import DspyProgram
    from apps.api.db.session import async_session_factory

    serialized = json.loads(program_path.read_text())

    async with async_session_factory() as session:
        # Deactivate all previous programs
        prev = await session.execute(
            select(DspyProgram).where(DspyProgram.is_active == True)  # noqa: E712
        )
        for p in prev.scalars():
            p.is_active = False

        # Insert new program
        program = DspyProgram(
            version=version,
            serialized_program=serialized,
            compile_metrics={
                "baseline_score": baseline_score,
                "optimized_score": optimized_score,
                "improvement": optimized_score - baseline_score,
                "auto": auto,
                "train_size": train_size,
            },
            is_active=True,
        )
        session.add(program)
        await session.commit()
        logger.info("[optimizer] Persisted DspyProgram version=%s to Neon", version)


def load_compiled_program() -> dspy.Predict | None:
    """Load the latest compiled program from disk, if available.

    Called by synthesizer.py at startup. Returns None if no compiled
    program exists (falls back to baseline dspy.Predict).
    """
    latest = COMPILED_DIR / "impact_assessment_latest.json"
    if not latest.exists():
        logger.debug("[optimizer] No compiled program found — using baseline predictor")
        return None
    try:
        program = dspy.Predict(ImpactAssessment)
        program.load(str(latest))
        logger.info("[optimizer] Loaded compiled program from %s", latest.resolve())
        return program
    except Exception as exc:
        logger.warning("[optimizer] Failed to load compiled program: %s — using baseline", exc)
        return None
