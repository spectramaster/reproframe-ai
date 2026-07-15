from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import UUID, uuid4

from genblaze_core import (
    AgentContext,
    AgentLoop,
    Asset,
    CallableEvaluator,
    Modality,
    Pipeline,
    SyncProvider,
)
from genblaze_core import (
    EvaluationResult as GenblazeEvaluationResult,
)

from .config import Settings
from .evaluation import EvidenceEvaluator
from .generation import (
    FixtureScientificGenerator,
    GenblazeGMIImageGenerator,
    MediaGenerator,
)
from .models import (
    Attempt,
    Evaluation,
    GeneratedAsset,
    ReproducibilityManifest,
    RunSummary,
    VisualBrief,
)
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
        provider = _GeneratorProvider(self.generator, brief, run_id)

        def pipeline_factory(context: AgentContext) -> Pipeline:
            feedback = []
            if context.last_evaluation and context.last_evaluation.feedback:
                feedback = context.last_evaluation.feedback.splitlines()
            attempt = context.iteration + 1
            return Pipeline(
                f"reproframe-review-{run_id}-attempt-{attempt}",
                project_id="reproframe-ai",
            ).step(
                provider,
                model="evidence-bound-media-v1",
                prompt=build_generation_prompt(brief, feedback),
                modality=Modality.IMAGE,
                _reproframe_attempt=attempt,
            )

        def judge(result) -> GenblazeEvaluationResult:
            step = result.run.steps[-1]
            asset = provider.asset_for(step.step_id)
            evaluation = self.evaluator.evaluate(brief, asset)
            provider.record_evaluation(step.step_id, evaluation)
            return GenblazeEvaluationResult(
                passed=evaluation.passed,
                score=evaluation.score,
                feedback="\n".join(evaluation.feedback) or None,
                metadata={"checks": evaluation.checks},
            )

        agent_result = AgentLoop(
            pipeline_factory,
            CallableEvaluator(judge),
            max_iterations=self.max_iterations,
        ).run(raise_on_failure=True)

        attempts: list[Attempt] = []
        for index, iteration in enumerate(agent_result.iterations, start=1):
            step = iteration.result.run.steps[-1]
            genblaze_manifest = iteration.result.manifest
            provenance_url = self.store.put_bytes(
                f"{run_id}/genblaze-attempt-{index:02d}.json",
                genblaze_manifest.to_canonical_json().encode("utf-8"),
                "application/json",
            )
            asset = provider.asset_for(step.step_id).model_copy(
                update={
                    "provenance_url": provenance_url,
                    "provenance_sha256": genblaze_manifest.canonical_hash,
                }
            )
            attempts.append(
                Attempt(
                    index=index,
                    prompt=step.prompt,
                    asset=asset,
                    evaluation=provider.evaluation_for(step.step_id),
                )
            )

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


class _GeneratorProvider(SyncProvider):
    """Adapts a ReproFrame generator into a real Genblaze pipeline provider."""

    name = "reproframe-orchestrator"

    def __init__(
        self,
        generator: MediaGenerator,
        brief: VisualBrief,
        run_id: UUID,
    ) -> None:
        super().__init__()
        self.generator = generator
        self.brief = brief
        self.run_id = run_id
        self._assets: dict[str, GeneratedAsset] = {}
        self._evaluations: dict[str, Evaluation] = {}

    def generate(self, step, config=None):
        del config
        attempt = int(step.params.get("_reproframe_attempt", 1))
        asset = self.generator.generate(
            brief=self.brief,
            prompt=step.prompt,
            attempt=attempt,
            run_id=self.run_id,
        )
        self._assets[step.step_id] = asset
        step.assets.append(
            Asset(
                url=asset.url,
                media_type=asset.media_type,
                sha256=asset.sha256,
                metadata={
                    "source_provider": asset.provider,
                    "source_model": asset.model,
                    "reproframe_attempt": attempt,
                },
            )
        )
        return step

    def asset_for(self, step_id: str) -> GeneratedAsset:
        return self._assets[step_id]

    def record_evaluation(self, step_id: str, evaluation: Evaluation) -> None:
        self._evaluations[step_id] = evaluation

    def evaluation_for(self, step_id: str) -> Evaluation:
        return self._evaluations[step_id]


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
