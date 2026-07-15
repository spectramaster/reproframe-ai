import hashlib
import json
from pathlib import Path
from uuid import UUID

import pytest

from reproframe.cli import sample_brief
from reproframe.config import Settings
from reproframe.generation import MediaGenerator
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
