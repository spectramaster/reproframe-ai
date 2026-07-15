import hashlib
import json
from pathlib import Path
from uuid import UUID

import pytest

from reproframe.cli import sample_brief
from reproframe.config import Settings
from reproframe.evaluation import EvidenceEvaluator
from reproframe.generation import GeminiSVGGenerator, MediaGenerator, _validated_svg
from reproframe.model_evaluation import ModelVisualEvaluator
from reproframe.models import GeneratedAsset, ModelReview, VisualBrief
from reproframe.pipeline import ReproFramePipeline, build_fixture_pipeline, build_pipeline
from reproframe.runs import build_bundle, list_runs, load_run_details, verify_run
from reproframe.storage import LocalArtifactStore


def test_fixture_pipeline_creates_verified_bundle(tmp_path: Path) -> None:
    result = build_fixture_pipeline(tmp_path).run(sample_brief())

    assert result.status == "accepted"
    assert result.score == 1.0
    assert result.attempts == 2
    assert len(result.canonical_sha256) == 64
    assert (tmp_path / str(result.run_id) / "manifest.json").is_file()
    genblaze_manifest = tmp_path / str(result.run_id) / "genblaze-attempt-02.json"
    assert genblaze_manifest.is_file()
    assert json.loads(genblaze_manifest.read_text())["run"]["project_id"] == "reproframe-ai"
    run_dir = tmp_path / str(result.run_id)
    assert (run_dir / "brief.json").is_file()
    assert (run_dir / "evaluation-attempt-01.json").is_file()
    assert (run_dir / "evaluation-attempt-02.json").is_file()
    assert (run_dir / "final-selection.json").is_file()

    details = load_run_details(LocalArtifactStore(tmp_path), result.run_id)
    assert details.verification.valid is True
    assert details.verification.object_count == 9
    assert list_runs(LocalArtifactStore(tmp_path))[0].title == result.title
    assert len(build_bundle(LocalArtifactStore(tmp_path), result.run_id)) > 1000


def test_verification_detects_tampered_asset(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path)
    result = build_fixture_pipeline(tmp_path).run(sample_brief())
    manifest = json.loads((tmp_path / str(result.run_id) / "manifest.json").read_text())
    asset_url = manifest["attempts"][0]["asset"]["url"]
    asset_path = tmp_path / asset_url.removeprefix("/artifacts/")
    asset_path.write_bytes(b"tampered")

    report = verify_run(store, result.run_id)

    assert report.valid is False
    assert report.asset_hashes_valid is False
    assert "do not match" in " ".join(report.errors)


def test_manifest_does_not_contain_secret_fields(tmp_path: Path) -> None:
    result = build_fixture_pipeline(tmp_path).run(sample_brief())
    manifest = (tmp_path / str(result.run_id) / "manifest.json").read_text()

    assert "GMI_API_KEY" not in manifest
    assert "B2_APP_KEY" not in manifest


def test_real_mode_requires_all_provider_credentials() -> None:
    settings = Settings(
        _env_file=None,
        mode="gmi",
        GMI_API_KEY="gmi-test",  # pragma: allowlist secret
        B2_BUCKET="test-bucket",
        B2_REGION="us-east-005",
    )

    with pytest.raises(RuntimeError, match="B2_KEY_ID"):
        build_pipeline(settings)


class _FakeGeminiModels:
    def generate_content(self, *, model: str, contents: str):
        assert model == "gemini-test"
        assert "Return one complete" in contents
        return type(
            "Response",
            (),
            {
                "text": """<svg xmlns="http://www.w3.org/2000/svg"
viewBox="0 0 1600 900"><text>Observe Evaluate</text></svg>"""
            },
        )()


class _FakeGeminiClient:
    models = _FakeGeminiModels()


def test_gemini_svg_generator_stores_validated_asset(tmp_path: Path) -> None:
    brief = sample_brief()
    generator = GeminiSVGGenerator(
        LocalArtifactStore(tmp_path),
        api_key="test",  # pragma: allowlist secret
        model="gemini-test",
        client=_FakeGeminiClient(),
    )

    asset = generator.generate(
        brief=brief,
        prompt="Generate",
        attempt=1,
        run_id=UUID("00000000-0000-0000-0000-000000000001"),
    )

    assert asset.provider == "google-gemini"
    assert "Observe Evaluate" in asset.extracted_text
    assert next(tmp_path.rglob("*.svg")).is_file()


def test_svg_validation_rejects_active_content() -> None:
    with pytest.raises(ValueError, match="forbidden element"):
        _validated_svg(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 900">'
            "<script>alert(1)</script></svg>"
        )


def test_svg_validation_allows_internal_gradient_reference() -> None:
    payload, _ = _validated_svg(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 900">'
        '<defs><linearGradient id="safe"><stop offset="0" /></linearGradient></defs>'
        '<rect width="1600" height="900" fill="url(#safe)" /></svg>'
    )

    assert b"url(#safe)" in payload


class RetryGenerator(MediaGenerator):
    def generate(
        self,
        *,
        brief: VisualBrief,
        prompt: str,
        attempt: int,
        run_id: UUID,
    ) -> GeneratedAsset:
        del prompt, run_id
        text = (
            " ".join(
                [
                    *brief.required_labels,
                    *(claim.text for claim in brief.claims if claim.priority == "required"),
                ]
            )
            if attempt > 1
            else "Generate only"
        )
        payload = text.encode()
        return GeneratedAsset(
            url=f"https://example.test/attempt-{attempt}.png",
            media_type="image/png",
            sha256=hashlib.sha256(payload).hexdigest(),
            provider="retry-fixture",
            model="retry-v1",
            extracted_text=text,
        )


def test_genblaze_agent_loop_feeds_feedback_into_retry(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path)
    result = ReproFramePipeline(RetryGenerator(), store).run(sample_brief())
    manifest = json.loads(
        (tmp_path / str(result.run_id) / "manifest.json").read_text()
    )

    assert result.status == "accepted"
    assert result.attempts == 2
    assert "Add the exact label 'Evaluate'." in manifest["attempts"][1]["prompt"]
    assert manifest["attempts"][1]["asset"]["provenance_sha256"]


class _PassingModelReviewer(ModelVisualEvaluator):
    def review(self, brief: VisualBrief, asset: GeneratedAsset) -> ModelReview:
        del brief, asset
        return ModelReview(
            passed=True,
            score=0.8,
            checks={"legible": True, "clear_hierarchy": True},
            feedback=[],
            provider="test-reviewer",
            model="review-v1",
        )


def test_optional_model_review_runs_after_deterministic_gate() -> None:
    brief = sample_brief()
    visible_text = " ".join(
        [
            *brief.required_labels,
            *(claim.text for claim in brief.claims if claim.priority == "required"),
        ]
    )
    asset = GeneratedAsset(
        url="/artifacts/test.svg",
        sha256=hashlib.sha256(visible_text.encode()).hexdigest(),
        provider="fixture",
        model="fixture-v1",
        extracted_text=visible_text,
    )

    evaluation = EvidenceEvaluator(_PassingModelReviewer()).evaluate(brief, asset)

    assert evaluation.passed is True
    assert evaluation.score == 0.9
    assert evaluation.checks["model:legible"] is True
    assert evaluation.model_review and evaluation.model_review.provider == "test-reviewer"
