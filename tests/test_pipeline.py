from pathlib import Path

from reproframe.cli import sample_brief
from reproframe.pipeline import build_fixture_pipeline


def test_fixture_pipeline_creates_verified_bundle(tmp_path: Path) -> None:
    result = build_fixture_pipeline(tmp_path).run(sample_brief())

    assert result.status == "accepted"
    assert result.score == 1.0
    assert result.attempts == 1
    assert len(result.canonical_sha256) == 64
    assert (tmp_path / str(result.run_id) / "manifest.json").is_file()


def test_manifest_does_not_contain_secret_fields(tmp_path: Path) -> None:
    result = build_fixture_pipeline(tmp_path).run(sample_brief())
    manifest = (tmp_path / str(result.run_id) / "manifest.json").read_text()

    assert "GMI_API_KEY" not in manifest
    assert "B2_APP_KEY" not in manifest

