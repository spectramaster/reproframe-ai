from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import uuid4

from .config import Settings
from .evaluation import EvidenceEvaluator
from .generation import (
    FixtureScientificGenerator,
    GenblazeGMIImageGenerator,
    MediaGenerator,
)
from .models import Attempt, ReproducibilityManifest, RunSummary, VisualBrief
from .prompting import build_generation_prompt
from .storage import ArtifactStore, B2ArtifactStore, LocalArtifactStore


class ReproFramePipeline:
    def __init__(
        self,
        generator: MediaGenerator,
        store: ArtifactStore,
        *,
        max_iterations: int = 3,
    ) -> None:
        self.generator = generator
        self.store = store
        self.evaluator = EvidenceEvaluator()
        self.max_iterations = max_iterations

    def run(self, brief: VisualBrief) -> RunSummary:
        run_id = uuid4()
        attempts: list[Attempt] = []
        feedback: list[str] = []

        for index in range(1, self.max_iterations + 1):
            prompt = build_generation_prompt(brief, feedback)
            asset = self.generator.generate(
                brief=brief,
                prompt=prompt,
                attempt=index,
                run_id=run_id,
            )
            evaluation = self.evaluator.evaluate(brief, asset)
            attempts.append(
                Attempt(index=index, prompt=prompt, asset=asset, evaluation=evaluation)
            )
            if evaluation.passed:
                break
            feedback = evaluation.feedback

        final = attempts[-1]
        status = "accepted" if final.evaluation.passed else "needs_review"
        unsigned = ReproducibilityManifest(
            run_id=run_id,
            brief=brief,
            attempts=attempts,
            final_attempt=final.index,
            status=status,
            canonical_sha256="0" * 64,
        )
        canonical_payload = unsigned.model_dump_json(
            exclude={"canonical_sha256"},
            exclude_none=True,
        ).encode("utf-8")
        canonical_sha256 = hashlib.sha256(canonical_payload).hexdigest()
        manifest = unsigned.model_copy(update={"canonical_sha256": canonical_sha256})
        manifest_key = f"{run_id}/manifest.json"
        manifest_url = self.store.put_bytes(
            manifest_key,
            manifest.model_dump_json(indent=2).encode("utf-8"),
            "application/json",
        )
        return RunSummary(
            run_id=run_id,
            status=status,
            score=final.evaluation.score,
            attempts=len(attempts),
            asset_url=final.asset.url,
            manifest_url=manifest_url,
            canonical_sha256=canonical_sha256,
        )


def build_fixture_pipeline(root: Path, *, max_iterations: int = 3) -> ReproFramePipeline:
    store = LocalArtifactStore(root)
    return ReproFramePipeline(
        FixtureScientificGenerator(store),
        store,
        max_iterations=max_iterations,
    )


def build_pipeline(settings: Settings) -> ReproFramePipeline:
    if settings.mode == "fixture":
        return build_fixture_pipeline(
            settings.artifact_dir,
            max_iterations=settings.max_iterations,
        )
    if not settings.b2_bucket or not settings.b2_region:
        raise RuntimeError("gmi mode requires B2_BUCKET and B2_REGION")
    store = B2ArtifactStore(settings.b2_bucket, settings.b2_region)
    generator = GenblazeGMIImageGenerator(
        bucket=settings.b2_bucket,
        model=settings.gmi_image_model,
        timeout_seconds=settings.generation_timeout_seconds,
    )
    return ReproFramePipeline(
        generator,
        store,
        max_iterations=settings.max_iterations,
    )
