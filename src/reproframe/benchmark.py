from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from time import perf_counter

from .models import VisualBrief
from .pipeline import build_fixture_pipeline
from .runs import load_run_details


def run_benchmark(
    briefs_path: Path,
    output_path: Path,
    *,
    runs_root: Path,
) -> dict:
    cases = json.loads(briefs_path.read_text(encoding="utf-8"))
    results = []
    for case in cases:
        case_id = case["case_id"]
        brief = VisualBrief.model_validate(
            {key: value for key, value in case.items() if key != "case_id"}
        )
        pipeline = build_fixture_pipeline(runs_root / case_id)
        started = perf_counter()
        summary = pipeline.run(brief)
        latency_seconds = perf_counter() - started
        details = load_run_details(pipeline.store, summary.run_id)
        final = details.manifest.attempts[details.manifest.final_attempt - 1]
        coverage_checks = {
            key: value
            for key, value in final.evaluation.checks.items()
            if key.startswith(("required:", "claim:"))
        }
        coverage = (
            sum(coverage_checks.values()) / len(coverage_checks) if coverage_checks else 1.0
        )
        results.append(
            {
                "case_id": case_id,
                "run_id": str(summary.run_id),
                "accepted": summary.status == "accepted",
                "score": summary.score,
                "coverage": round(coverage, 4),
                "attempts": summary.attempts,
                "retry_succeeded": summary.attempts > 1 and summary.status == "accepted",
                "latency_seconds": round(latency_seconds, 4),
                "provider_cost_usd": 0.0,
                "storage_integrity": details.verification.valid,
                "stored_objects": details.verification.object_count,
            }
        )

    retried = [item for item in results if item["attempts"] > 1]
    report = {
        "schema_version": "reproframe-benchmark/0.1",
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "deterministic-fixture",
        "case_count": len(results),
        "metrics": {
            "acceptance_rate": mean(item["accepted"] for item in results),
            "mean_guardrail_score": mean(item["score"] for item in results),
            "mean_claim_label_coverage": mean(item["coverage"] for item in results),
            "retry_trigger_rate": len(retried) / len(results),
            "retry_success_rate": mean(item["accepted"] for item in retried) if retried else None,
            "storage_integrity_rate": mean(item["storage_integrity"] for item in results),
            "mean_latency_seconds": mean(item["latency_seconds"] for item in results),
            "mean_provider_cost_usd": mean(item["provider_cost_usd"] for item in results),
        },
        "cases": results,
        "scope_note": (
            "These figures cover five deterministic scientific-communication fixtures. "
            "They are not a benchmark of Gemini, GMI, scientific truth, or visual preference."
        ),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
