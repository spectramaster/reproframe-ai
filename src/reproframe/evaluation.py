from __future__ import annotations

from .model_evaluation import ModelVisualEvaluator
from .models import Evaluation, GeneratedAsset, VisualBrief


class EvidenceEvaluator:
    """Deterministic guardrail evaluator used locally and before model-based review."""

    acceptance_score = 0.86

    def __init__(self, model_evaluator: ModelVisualEvaluator | None = None) -> None:
        self.model_evaluator = model_evaluator

    def evaluate(self, brief: VisualBrief, asset: GeneratedAsset) -> Evaluation:
        haystack = asset.extracted_text.casefold()
        required = [label for label in brief.required_labels if label]
        forbidden = [item for item in brief.forbidden_elements if item]
        required_claims = [claim for claim in brief.claims if claim.priority == "required"]

        label_checks = {f"required:{label}": label.casefold() in haystack for label in required}
        claim_checks = {
            f"claim:{claim.claim_id}": claim.text.casefold() in haystack
            for claim in required_claims
        }
        forbidden_checks = {
            f"forbidden:{item}": item.casefold() not in haystack for item in forbidden
        }
        integrity_checks = {
            "asset_sha256": len(asset.sha256) == 64,
            "provider_recorded": bool(asset.provider and asset.model),
            "claim_source_present": bool(brief.claims),
        }
        checks = {**label_checks, **claim_checks, **forbidden_checks, **integrity_checks}
        score = sum(checks.values()) / len(checks) if checks else 1.0
        feedback = []
        for name, passed in checks.items():
            if not passed:
                if name.startswith("required:"):
                    feedback.append(f"Add the exact label '{name.split(':', 1)[1]}'.")
                elif name.startswith("claim:"):
                    claim_id = name.split(":", 1)[1]
                    claim = next(item for item in required_claims if item.claim_id == claim_id)
                    feedback.append(f"Add the exact evidence-backed claim '{claim.text}'.")
                elif name.startswith("forbidden:"):
                    feedback.append(f"Remove '{name.split(':', 1)[1]}'.")
                else:
                    feedback.append(f"Resolve failed integrity check: {name}.")
        deterministic_passed = score >= self.acceptance_score and all(checks.values())
        model_review = None
        if deterministic_passed and self.model_evaluator is not None:
            model_review = self.model_evaluator.review(brief, asset)
            checks.update({f"model:{key}": value for key, value in model_review.checks.items()})
            feedback.extend(model_review.feedback)
            score = (score + model_review.score) / 2
        return Evaluation(
            passed=deterministic_passed and (model_review is None or model_review.passed),
            score=round(score, 4),
            checks=checks,
            feedback=feedback,
            model_review=model_review,
        )
