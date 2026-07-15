import hashlib
import json
from pathlib import Path
from uuid import UUID

import pytest

from reproframe.cli import sample_brief
from reproframe.config import Settings
from reproframe.generation import GeminiSVGGenerator, MediaGenerator, _validated_svg
from reproframe.models import GeneratedAsset, VisualBrief
from reproframe.pipeline import ReproFramePipeline, build_fixture_pipeline, build_pipeline
from reproframe.storage import LocalArtifactStore


def test_fixture_pipeline_creates_verified_bundle(tmp_path: Path) -> None:
    result = build_fixture_pipeline(tmp_path).run(sample_brief())

    assert result.status == "accepted"
    assert result.score == 1.0
    assert result.attempts == 1
    assert len(result.canonical_sha256) == 64
    assert (tmp_path / str(result.run_id) / "manifest.json").is_file()
    genblaze_manifest = tmp_path / str(result.run_id) / "genblaze-attempt-01.json"
    assert genblaze_manifest.is_file()
    assert json.loads(genblaze_manifest.read_text())["run"]["project_id"] == "reproframe-ai"


def test_manifest_does_not_contain_secret_fields(tmp_path: Path) -> None:
    result = build_fixture_pipeline(tmp_path).run(sample_brief())
    manifest = (tmp_path / str(result.run_id) / "manifest.json").read_text()

    assert "GMI_API_KEY" not in manifest
    assert "B2_APP_KEY" not in manifest


def test_real_mode_requires_all_provider_credentials() -> None:
    settings = Settings(
        _env_file=None,
        mode="gmi",
        GMI_API_KEY="gmi-test",
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
        api_key="test",
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
        text = " ".join(brief.required_labels) if attempt > 1 else "Generate only"
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
