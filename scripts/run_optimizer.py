#!/usr/bin/env python3
"""Manual runner for the DSPy MIPROv2 optimization loop.

Usage:
    uv run python scripts/run_optimizer.py              # light search (fast, ~5 min)
    uv run python scripts/run_optimizer.py --auto medium  # medium search (~20 min)
    uv run python scripts/run_optimizer.py --auto heavy   # thorough search (~60 min)

What it does:
  1. Loads 5 bootstrap training examples (golden scenarios)
     + any analyst-accepted feedback rows from Neon
  2. Runs MIPROv2 to find better instructions/demos for the ImpactAssessment signature
  3. Evaluates on held-out dev set (baseline vs. compiled)
  4. Persists improved program to dspy_lab/compiled/ and Neon dspy_programs table
  5. Updates 'latest' symlink so synthesizer auto-loads on next pipeline run
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

sys.path.insert(0, ".")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--auto",
        choices=["light", "medium", "heavy"],
        default="light",
        help="MIPROv2 search budget (default: light)",
    )
    parser.add_argument(
        "--min-improvement",
        type=float,
        default=0.03,
        help="Minimum dev-set score gain to persist (default: 0.03)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed (default: 42)",
    )
    args = parser.parse_args()

    from apps.api.dspy_lab.optimizer import run_optimization

    print(f"\n{'═' * 60}")
    print(f"DSPy MIPROv2 Optimization — auto={args.auto}")
    print(f"{'═' * 60}\n")

    result = await run_optimization(
        auto=args.auto,
        min_improvement=args.min_improvement,
        seed=args.seed,
    )

    print(f"\n{'═' * 60}")
    print(f"Results")
    print(f"{'═' * 60}")
    print(f"  Baseline score  : {result['baseline_score']:.4f}")
    print(f"  Optimized score : {result['optimized_score']:.4f}")
    print(f"  Improvement     : {result['improvement']:+.4f}")
    print(f"  Train / Dev     : {result['train_size']} / {result['dev_size']}")
    print(f"  Persisted       : {'YES → ' + result['version'] if result['persisted'] else 'NO (below threshold)'}")
    if result["persisted"]:
        print(f"\n  ✓ Compiled program saved. Next assessment run will use it automatically.")
    else:
        print(f"\n  ℹ Baseline program unchanged (add more feedback to improve training data).")


if __name__ == "__main__":
    asyncio.run(main())
