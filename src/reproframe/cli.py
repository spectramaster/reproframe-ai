from __future__ import annotations

import argparse
import json

from .config import get_settings
from .models import VisualBrief
from .pipeline import build_fixture_pipeline


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


def main() -> None:
    parser = argparse.ArgumentParser(prog="reproframe")
    parser.add_argument("command", choices=["demo"])
    args = parser.parse_args()
    if args.command == "demo":
        settings = get_settings()
        result = build_fixture_pipeline(settings.artifact_dir).run(sample_brief())
        print(json.dumps(result.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    main()
