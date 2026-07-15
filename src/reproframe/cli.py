from __future__ import annotations

import argparse
import json
from pathlib import Path

from .benchmark import run_benchmark
from .config import get_settings
from .models import VisualBrief
from .pipeline import build_fixture_pipeline, build_pipeline, build_store
from .runs import build_bundle, list_runs, verify_run


def sample_brief() -> VisualBrief:
    return VisualBrief.model_validate(
        {
            "title": "Safer scientific visuals from generative AI",
            "audience": "researchers and journal editors",
            "claims": [
                {
                    "claim_id": "c1",
                    "text": "Every generated asset is linked to its prompt, model, and evaluation.",
                },
                {
                    "claim_id": "c2",
                    "text": (
                        "Failed checks produce explicit feedback before a new attempt is created."
                    ),
                },
                {
                    "claim_id": "c3",
                    "text": "The final bundle includes a content hash and replayable manifest.",
                    "priority": "supporting",
                },
            ],
            "required_labels": ["Generate", "Evaluate", "Retry", "Verify"],
            "forbidden_elements": ["fabricated statistic", "medical diagnosis"],
            "style": "clean scientific editorial, restrained green and indigo palette",
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="reproframe")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("demo", help="Run the deterministic offline fixture.")
    commands.add_parser("cloud-demo", help="Run the configured Gemini/GMI + B2 path.")
    history = commands.add_parser("history", help="List durable runs in the active store.")
    history.add_argument("--limit", type=int, default=12)
    verify = commands.add_parser("verify", help="Re-hash a stored run and its Genblaze manifests.")
    verify.add_argument("run_id")
    bundle = commands.add_parser("bundle", help="Build a portable ZIP evidence package.")
    bundle.add_argument("run_id")
    bundle.add_argument("--output", type=Path)
    benchmark = commands.add_parser("benchmark", help="Run five reproducible fixture cases.")
    benchmark.add_argument("--briefs", type=Path, default=Path("benchmarks/briefs.json"))
    benchmark.add_argument(
        "--output", type=Path, default=Path("benchmarks/results/latest.json")
    )
    benchmark.add_argument(
        "--runs-root", type=Path, default=Path("artifacts/benchmark-runs")
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    settings = get_settings()
    if args.command == "demo":
        result = build_fixture_pipeline(settings.artifact_dir).run(sample_brief())
        print(json.dumps(result.model_dump(mode="json"), indent=2))
        return
    if args.command == "cloud-demo":
        if settings.mode == "fixture":
            raise SystemExit("Set REPROFRAME_MODE=gemini-svg or gmi before cloud-demo.")
        result = build_pipeline(settings).run(sample_brief())
        print(json.dumps(result.model_dump(mode="json"), indent=2))
        return
    if args.command == "benchmark":
        report = run_benchmark(args.briefs, args.output, runs_root=args.runs_root)
        print(json.dumps(report, indent=2))
        return

    store = build_store(settings)
    if args.command == "history":
        runs = list_runs(store, limit=max(1, min(args.limit, 50)))
        print(json.dumps([run.model_dump(mode="json") for run in runs], indent=2))
        return
    if args.command == "verify":
        report = verify_run(store, args.run_id)
        print(report.model_dump_json(indent=2))
        raise SystemExit(0 if report.valid else 1)
    if args.command == "bundle":
        output = args.output or Path(f"reproframe-{args.run_id}-evidence.zip")
        output.write_bytes(build_bundle(store, args.run_id))
        print(output.resolve())


if __name__ == "__main__":
    main()
