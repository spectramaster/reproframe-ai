from __future__ import annotations

from .models import Evaluation, GeneratedAsset, VisualBrief


class EvidenceEvaluator:
    """Deterministic guardrail evaluator used locally and before model-based review."""

    acceptance_score = 0.86

    def evaluate(self, brief: VisualBrief, asset: GeneratedAsset) -> Evaluation:
        haystack = asset.extracted_text.casefold()
        required = [label for label in brief.required_labels if label]
        forbidden = [item for item in brief.forbidden_elements if item]

        label_checks = {f"required:{label}": label.casefold() in haystack for label in required}
        forbidden_checks = {
            f"forbidden:{item}": item.casefold() not in haystack for item in forbidden
        }
        integrity_checks = {
            "asset_sha256": len(asset.sha256) == 64,
            "provider_recorded": bool(asset.provider and asset.model),
            "claim_source_present": bool(brief.claims),
        }
        checks = {**label_checks, **forbidden_checks, **integrity_checks}
        score = sum(checks.values()) / len(checks) if checks else 1.0
        feedback = []
        for name, passed in checks.items():
            if not passed:
                if name.startswith("required:"):
                    feedback.append(f"Add the exact label '{name.split(':', 1)[1]}'.")
                elif name.startswith("forbidden:"):
                    feedback.append(f"Remove '{name.split(':', 1)[1]}'.")
                else:
                    feedback.append(f"Resolve failed integrity check: {name}.")
        return Evaluation(
            passed=score >= self.acceptance_score and all(checks.values()),
            score=round(score, 4),
            checks=checks,
            feedback=feedback,
        )

