from __future__ import annotations

import json
from abc import ABC, abstractmethod

from .models import GeneratedAsset, ModelReview, VisualBrief
from .storage import ArtifactStore


class ModelVisualEvaluator(ABC):
    @abstractmethod
    def review(self, brief: VisualBrief, asset: GeneratedAsset) -> ModelReview:
        raise NotImplementedError


class GeminiSVGModelEvaluator(ModelVisualEvaluator):
    """Optional second-pass reviewer; deterministic checks remain mandatory first."""

    def __init__(
        self,
        store: ArtifactStore,
        *,
        api_key: str,
        model: str,
        client=None,
    ) -> None:
        if client is None:
            from google import genai

            client = genai.Client(api_key=api_key)
        self.store = store
        self.client = client
        self.model = model

    def review(self, brief: VisualBrief, asset: GeneratedAsset) -> ModelReview:
        if asset.media_type != "image/svg+xml":
            raise ValueError("Gemini SVG reviewer only accepts image/svg+xml assets")
        key = _asset_key(asset.url)
        if key is None:
            raise ValueError("Model reviewer cannot safely resolve the stored asset URL")
        payload, _ = self.store.get_bytes(key)
        svg = payload.decode("utf-8")
        prompt = f"""Review this scientific SVG as an advisory visual-quality evaluator.
The deterministic claim, label, prohibited-content, and SHA-256 checks already passed.
Assess only these four criteria: legibility, hierarchy, non-overlap, and whether the
visible composition clearly separates supplied claims from workflow labels.

TITLE: {brief.title}
AUDIENCE: {brief.audience}
SVG:
{svg}

Return JSON only with exactly these fields:
{{"passed": true, "score": 0.0, "checks": {{"legible": true,
"clear_hierarchy": true, "no_obvious_overlap": true, "claims_visually_distinct": true}},
"feedback": []}}
Score must be between 0 and 1. Passed must be false if any check is false.
Do not judge scientific truth and do not introduce new factual claims.
"""
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )
        data = json.loads(response.text or "{}")
        checks = {str(key): bool(value) for key, value in data.get("checks", {}).items()}
        feedback = [str(item)[:320] for item in data.get("feedback", [])][:12]
        passed = bool(data.get("passed")) and bool(checks) and all(checks.values())
        return ModelReview(
            passed=passed,
            score=float(data.get("score", 0.0)),
            checks=checks,
            feedback=feedback,
            provider="google-gemini",
            model=self.model,
        )


def _asset_key(url: str) -> str | None:
    for prefix in ("/api/artifacts/", "/artifacts/"):
        if url.startswith(prefix):
            return url.removeprefix(prefix)
    return None
