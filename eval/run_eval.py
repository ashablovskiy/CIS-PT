"""CIS Evaluation Harness — three-tier assessment quality testing.

Tier 1 — Schema validation (runs on all assessments in DB):
  Every assessment must have: summary, at least 1 affected entity,
  non-empty reasoning chain with grounded_in, valid confidence 0–1.

Tier 2 — Golden scenarios (5 hand-crafted test cases):
  Runs each golden signal payload through the full 7-node pipeline,
  scores output against expected event_class, clause types, severity.

Tier 3 — Feedback comparison (when ≥10 feedback rows):
  Compares DSPy metric scores on analyst-accepted vs. analyst-rejected assessments.
  Accepted should score higher than rejected. Gap measures calibration quality.

Usage:
    uv run python eval/run_eval.py              # all tiers
    uv run python eval/run_eval.py --tier 1     # schema only (fast)
    uv run python eval/run_eval.py --tier 2     # golden scenarios (calls Opus)
    uv run python eval/run_eval.py --tier 3     # feedback comparison
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

sys.path.insert(0, ".")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

GOLDEN_PATH = Path(__file__).parent / "golden.jsonl"

# ── Synthetic signal payloads for each golden scenario ───────────────────────
# These are the signal.raw_payload dicts that will be injected into the pipeline.

GOLDEN_PAYLOADS: dict[str, dict] = {
    "golden-001": {
        "source": "gdelt", "signal_type": "regulatory_trade",
        "title": "US Commerce Dept expands GOES export restrictions to 12 additional countries",
        "summary": (
            "New Export Administration Regulations (EAR) controls on grain-oriented electrical "
            "steel (GOES) require export license for shipments to 12 additional countries. "
            "Effective 60 days from Federal Register publication. Impacts Cogent Power, "
            "Nippon Steel, JFE Steel, and POSCO shipments to EU transformer manufacturers."
        ),
    },
    "golden-002": {
        "source": "logistics", "signal_type": "logistics_disruption",
        "title": "Busan port congestion: 8-day vessel queues amid Korean dock worker strike",
        "summary": (
            "Korea's largest port reports 8-day waiting times for bulk cargo vessels following "
            "dock worker strike action. Multiple transformer shipments from Korean OEMs delayed. "
            "Hyundai Heavy Industries and LS Electric notifying buyers of force majeure conditions. "
            "Alternative routing via Incheon and Gwangyang being evaluated."
        ),
    },
    "golden-003": {
        "source": "sec", "signal_type": "financial_disclosure",
        "title": "GE Vernova 8-K: power transformer backlog +38% YoY to $8.2B",
        "summary": (
            "GE Vernova files 8-K disclosing power transformer order backlog reached $8.2 billion "
            "(+38% year-over-year). Lead times extending to 24-30 months for large power "
            "transformers. Management notes capacity constraints at Pittsburgh and Memphis plants. "
            "Slot availability for new orders severely limited through 2027."
        ),
    },
    "golden-004": {
        "source": "prices", "signal_type": "commodity_price_move",
        "ticker": "HG=F",
        "label": "Copper futures 30-day move +12.3%",
        "moves_pct": {"1d": "+2.1%", "30d": "+12.3%"},
        "summary": (
            "CME Copper futures (HG=F) advanced 12.3% over the past 30 days and 2.1% today. "
            "Prices driven by supply constraints at Codelco and Freeport-McMoRan. "
            "Cu_Winding_Strip spot prices following futures higher. "
            "Indexation clause triggers expected for contracts with >5% threshold."
        ),
    },
    "golden-005": {
        "source": "demand", "signal_type": "demand_surge",
        "company": "Microsoft",
        "title": "Microsoft announces 2 GW AI datacenter campus in Loudoun County, Virginia",
        "summary": (
            "Microsoft breaks ground on 2 GW AI datacenter campus requiring procurement of "
            "15+ GSU transformers (200-500 MVA) and 40+ medium power transformers. "
            "RFQ process launching Q3. Construction timeline 36 months. "
            "Google, Amazon, and Meta also expanding Virginia presence — compounding OEM backlog."
        ),
    },
}


# ── Tier 1: Schema validation ─────────────────────────────────────────────────

async def run_tier1() -> dict[str, Any]:
    """Validate all assessments in DB against structural quality criteria."""
    from sqlalchemy import select
    from apps.api.db.models import Assessment
    from apps.api.db.session import async_session_factory

    results = {"tier": 1, "passed": 0, "failed": 0, "failures": []}

    async with async_session_factory() as session:
        rows = await session.execute(
            select(Assessment).where(Assessment.summary.isnot(None)).limit(100)
        )
        assessments = rows.scalars().all()

    for a in assessments:
        errors = []

        if not a.summary or len(a.summary) < 50:
            errors.append("summary too short (<50 chars)")

        entities = a.affected_entities or {}
        total_entities = sum(
            len(v) for v in entities.values() if isinstance(v, list)
        )
        if total_entities == 0:
            errors.append("no affected entities")

        chain = (a.reasoning_chain or {}).get("steps", [])
        if not chain:
            errors.append("empty reasoning chain")
        else:
            grounded = [
                s for s in chain
                if isinstance(s.get("grounded_in"), dict)
                and len(s.get("grounded_in", {}).get("source", "")) > 5
            ]
            if len(grounded) < min(2, len(chain)):
                errors.append(f"only {len(grounded)}/{len(chain)} steps have grounding")

        if a.confidence is None or not (0.0 <= a.confidence <= 1.0):
            errors.append(f"invalid confidence: {a.confidence}")

        if errors:
            results["failed"] += 1
            results["failures"].append({
                "assessment_id": str(a.id)[:8],
                "status": a.status,
                "errors": errors,
            })
        else:
            results["passed"] += 1

    results["total"] = results["passed"] + results["failed"]
    results["pass_rate"] = (
        results["passed"] / results["total"] if results["total"] > 0 else 0.0
    )
    return results


# ── Tier 2: Golden scenario tests ─────────────────────────────────────────────

async def run_tier2() -> dict[str, Any]:
    """Run golden scenario payloads through the pipeline and score outputs."""
    from apps.api.assess.pipeline import run_assessment
    from apps.api.dspy_lab.metrics import assessment_quality_metric
    import dspy

    goldens = [json.loads(line) for line in GOLDEN_PATH.read_text().splitlines() if line.strip()]
    results = {"tier": 2, "scenarios": [], "mean_quality": 0.0}

    scores = []
    for golden in goldens:
        gid = golden["id"]
        payload = GOLDEN_PAYLOADS.get(gid)
        if not payload:
            logger.warning("[eval] No payload for %s — skipping", gid)
            continue

        signal_id = uuid4()
        logger.info("[eval] Running golden scenario %s: %s", gid, golden["description"])

        try:
            state = await run_assessment(signal_id, payload)
        except Exception as exc:
            logger.error("[eval] Pipeline failed for %s: %s", gid, exc)
            results["scenarios"].append({"id": gid, "error": str(exc)})
            continue

        if not state.triage_passed:
            results["scenarios"].append({
                "id": gid, "triage": "SKIPPED",
                "expected_event_class": golden["expected_event_class"],
                "error": "triage rejected signal",
            })
            continue

        # Score against expected outputs
        triage_ok = _triage_class_from_state(state) == golden["expected_event_class"]

        clause_types_found = {
            c.get("clause_type") for c in state.affected_clauses or []
        }
        expected_types = set(golden["expected_affected_clause_types"])
        clause_recall = (
            len(clause_types_found & expected_types) / len(expected_types)
            if expected_types else 1.0
        )

        # DSPy structural quality score
        class _FakePred:
            def __init__(self, s):
                import json
                self.summary = s.summary or ""
                self.affected_entities_json = json.dumps(s.affected_entities or {})
                self.affected_clauses_json = json.dumps(s.affected_clauses or [])
                self.impact_json = json.dumps(s.impact_by_dimension or {})
                self.reasoning_chain_json = json.dumps([
                    r.model_dump() for r in (s.reasoning_chain or [])
                ])
                self.confidence = s.confidence or 0.5

        quality_score = assessment_quality_metric(
            dspy.Example(), _FakePred(state)
        )
        scores.append(quality_score)

        scenario_result = {
            "id": gid,
            "description": golden["description"],
            "triage": "PASSED",
            "event_class_correct": triage_ok,
            "expected_event_class": golden["expected_event_class"],
            "actual_event_class": _triage_class_from_state(state),
            "clause_recall": round(clause_recall, 2),
            "expected_clause_types": list(expected_types),
            "found_clause_types": list(clause_types_found),
            "quality_score": quality_score,
            "confidence": state.confidence,
            "critic_passed": state.critic_passed,
            "errors": state.errors,
        }
        results["scenarios"].append(scenario_result)
        logger.info(
            "[eval] %s: event_class_ok=%s clause_recall=%.2f quality=%.3f",
            gid, triage_ok, clause_recall, quality_score,
        )

    results["mean_quality"] = round(sum(scores) / len(scores), 4) if scores else 0.0
    results["triage_pass_rate"] = sum(
        1 for s in results["scenarios"] if s.get("triage") == "PASSED"
    ) / max(len(results["scenarios"]), 1)
    results["event_class_accuracy"] = sum(
        1 for s in results["scenarios"] if s.get("event_class_correct")
    ) / max(len(results["scenarios"]), 1)
    return results


def _triage_class_from_state(state) -> str:
    for item in state.graph_context:
        if "_triage" in item:
            return item["_triage"].get("event_class", "other")
    return "other"


# ── Tier 3: Feedback comparison ───────────────────────────────────────────────

async def run_tier3() -> dict[str, Any]:
    """Compare quality scores of accepted vs. rejected assessments."""
    from sqlalchemy import select
    from apps.api.db.models import Assessment, Feedback
    from apps.api.db.session import async_session_factory
    from apps.api.dspy_lab.metrics import assessment_quality_metric
    import dspy

    results = {"tier": 3, "accepted_mean": None, "rejected_mean": None, "gap": None}

    async with async_session_factory() as session:
        rows = await session.execute(
            select(Feedback, Assessment)
            .join(Assessment, Feedback.assessment_id == Assessment.id)
            .where(Feedback.user_action.in_(["accept", "reject"]))
        )
        feedback_rows = rows.fetchall()

    if len(feedback_rows) < 10:
        results["skipped"] = f"Only {len(feedback_rows)} feedback rows (need 10)"
        return results

    class _FakePred:
        def __init__(self, a):
            import json
            self.summary = a.summary or ""
            self.affected_entities_json = json.dumps(a.affected_entities or {})
            self.affected_clauses_json = json.dumps(
                (a.affected_clauses or {}).get("clauses", [])
            )
            self.impact_json = json.dumps(a.impact or {})
            self.reasoning_chain_json = json.dumps(
                (a.reasoning_chain or {}).get("steps", [])
            )
            self.confidence = a.confidence or 0.5

    accepted_scores, rejected_scores = [], []
    for fb, assessment in feedback_rows:
        score = assessment_quality_metric(dspy.Example(), _FakePred(assessment))
        if fb.user_action == "accept":
            accepted_scores.append(score)
        else:
            rejected_scores.append(score)

    if accepted_scores:
        results["accepted_mean"] = round(sum(accepted_scores) / len(accepted_scores), 4)
        results["accepted_count"] = len(accepted_scores)
    if rejected_scores:
        results["rejected_mean"] = round(sum(rejected_scores) / len(rejected_scores), 4)
        results["rejected_count"] = len(rejected_scores)
    if accepted_scores and rejected_scores:
        results["gap"] = round(results["accepted_mean"] - results["rejected_mean"], 4)
        results["metric_discriminates"] = results["gap"] > 0.05

    return results


# ── Main ──────────────────────────────────────────────────────────────────────

async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--tier", type=int, choices=[1, 2, 3],
        help="Run a specific tier only (default: all)",
    )
    args = parser.parse_args()

    all_results = {}

    if not args.tier or args.tier == 1:
        print("\n── Tier 1: Schema Validation ──────────────────────────────")
        r1 = await run_tier1()
        all_results["tier1"] = r1
        print(f"  Total: {r1['total']}  Passed: {r1['passed']}  Failed: {r1['failed']}")
        print(f"  Pass rate: {r1['pass_rate']:.1%}")
        if r1["failures"]:
            for f in r1["failures"]:
                print(f"  ✗ {f['assessment_id']} [{f['status']}]: {', '.join(f['errors'])}")

    if not args.tier or args.tier == 2:
        print("\n── Tier 2: Golden Scenarios ───────────────────────────────")
        r2 = await run_tier2()
        all_results["tier2"] = r2
        print(f"  Mean quality score : {r2['mean_quality']:.4f}")
        print(f"  Triage pass rate   : {r2['triage_pass_rate']:.1%}")
        print(f"  Event class accuracy: {r2['event_class_accuracy']:.1%}")
        for s in r2["scenarios"]:
            if "error" in s:
                print(f"  ✗ {s['id']}: {s['error']}")
            else:
                icon = "✓" if s.get("event_class_correct") else "✗"
                print(
                    f"  {icon} {s['id']}: "
                    f"event={s.get('actual_event_class','?')} "
                    f"clause_recall={s.get('clause_recall','?')} "
                    f"quality={s.get('quality_score','?'):.3f}"
                )

    if not args.tier or args.tier == 3:
        print("\n── Tier 3: Feedback Comparison ────────────────────────────")
        r3 = await run_tier3()
        all_results["tier3"] = r3
        if "skipped" in r3:
            print(f"  Skipped: {r3['skipped']}")
        else:
            print(f"  Accepted mean quality: {r3['accepted_mean']}")
            print(f"  Rejected mean quality: {r3['rejected_mean']}")
            print(f"  Gap: {r3['gap']} (discriminates: {r3.get('metric_discriminates')})")

    # Save results
    out = Path(__file__).parent / "runs" / f"eval_{datetime.now(UTC).strftime('%Y%m%d_%H%M')}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(all_results, indent=2, default=str))
    print(f"\n  Results saved to {out}")


if __name__ == "__main__":
    asyncio.run(main())
