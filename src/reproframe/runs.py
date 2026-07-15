from __future__ import annotations

import hashlib
import io
import json
import zipfile
from uuid import UUID

from genblaze_core import Manifest

from .models import (
    ReproducibilityManifest,
    ReviewDecision,
    RunDetails,
    RunSummary,
    VerificationReport,
)
from .storage import ArtifactStore

MAX_BUNDLE_BYTES = 50 * 1024 * 1024


def normalize_run_id(run_id: UUID | str) -> UUID:
    return run_id if isinstance(run_id, UUID) else UUID(str(run_id))


def load_manifest(store: ArtifactStore, run_id: UUID | str) -> ReproducibilityManifest:
    normalized = normalize_run_id(run_id)
    payload, _ = store.get_bytes(f"{normalized}/manifest.json")
    return ReproducibilityManifest.model_validate_json(payload)


def list_runs(store: ArtifactStore, *, limit: int = 25) -> list[RunSummary]:
    summaries: list[tuple[str, RunSummary]] = []
    for key in store.list_keys():
        if not key.endswith("/manifest.json"):
            continue
        try:
            payload, _ = store.get_bytes(key)
            manifest = ReproducibilityManifest.model_validate_json(payload)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        final = manifest.attempts[manifest.final_attempt - 1]
        summaries.append(
            (
                manifest.created_at.isoformat(),
                RunSummary(
                    run_id=manifest.run_id,
                    title=manifest.brief.title,
                    created_at=manifest.created_at,
                    status=manifest.status,
                    score=final.evaluation.score,
                    attempts=len(manifest.attempts),
                    asset_url=final.asset.url,
                    manifest_url=store.url_for(f"{manifest.run_id}/manifest.json"),
                    canonical_sha256=manifest.canonical_sha256,
                ),
            )
        )
    summaries.sort(key=lambda item: item[0], reverse=True)
    return [summary for _, summary in summaries[:limit]]


def save_review(
    store: ArtifactStore,
    run_id: UUID | str,
    review: ReviewDecision,
) -> str:
    normalized = normalize_run_id(run_id)
    load_manifest(store, normalized)
    return store.put_bytes(
        f"{normalized}/human-review.json",
        review.model_dump_json(indent=2).encode("utf-8"),
        "application/json",
    )


def load_review(store: ArtifactStore, run_id: UUID | str) -> ReviewDecision | None:
    normalized = normalize_run_id(run_id)
    key = f"{normalized}/human-review.json"
    if key not in store.list_keys(f"{normalized}/"):
        return None
    payload, _ = store.get_bytes(key)
    return ReviewDecision.model_validate_json(payload)


def verify_run(store: ArtifactStore, run_id: UUID | str) -> VerificationReport:
    normalized = normalize_run_id(run_id)
    errors: list[str] = []
    manifest = load_manifest(store, normalized)
    unsigned = manifest.model_dump_json(
        exclude={"canonical_sha256"},
        exclude_none=True,
    ).encode("utf-8")
    manifest_hash_valid = hashlib.sha256(unsigned).hexdigest() == manifest.canonical_sha256
    if not manifest_hash_valid:
        errors.append("ReproFrame manifest canonical hash does not match its payload.")

    checked_assets = 0
    asset_hashes_valid = True
    for attempt in manifest.attempts:
        key = _asset_key(attempt.asset.url)
        if key is None:
            asset_hashes_valid = False
            errors.append(f"Attempt {attempt.index} asset URL cannot be re-read through the store.")
            continue
        try:
            payload, _ = store.get_bytes(key)
        except (OSError, ValueError, KeyError):
            asset_hashes_valid = False
            errors.append(f"Attempt {attempt.index} asset is missing from durable storage.")
            continue
        checked_assets += 1
        if hashlib.sha256(payload).hexdigest() != attempt.asset.sha256:
            asset_hashes_valid = False
            errors.append(f"Attempt {attempt.index} asset bytes do not match the recorded SHA-256.")

    keys = store.list_keys(f"{normalized}/")
    provenance_keys = [key for key in keys if "/genblaze-attempt-" in key]
    checked_genblaze = 0
    genblaze_valid = True
    for key in provenance_keys:
        try:
            payload, _ = store.get_bytes(key)
            candidate = Manifest.model_validate_json(payload)
            current_valid = candidate.verify()
        except (OSError, ValueError, json.JSONDecodeError):
            current_valid = False
        checked_genblaze += 1
        if not current_valid:
            genblaze_valid = False
            errors.append(f"Genblaze provenance failed verification: {key}")
    if not provenance_keys:
        genblaze_valid = False
        errors.append("No Genblaze provenance manifests were found for this run.")

    valid = manifest_hash_valid and asset_hashes_valid and genblaze_valid and not errors
    return VerificationReport(
        run_id=normalized,
        valid=valid,
        manifest_hash_valid=manifest_hash_valid,
        asset_hashes_valid=asset_hashes_valid,
        genblaze_manifests_valid=genblaze_valid,
        checked_assets=checked_assets,
        checked_genblaze_manifests=checked_genblaze,
        object_count=len(keys),
        errors=errors,
    )


def load_run_details(store: ArtifactStore, run_id: UUID | str) -> RunDetails:
    normalized = normalize_run_id(run_id)
    return RunDetails(
        manifest=load_manifest(store, normalized),
        review=load_review(store, normalized),
        verification=verify_run(store, normalized),
    )


def build_bundle(store: ArtifactStore, run_id: UUID | str) -> bytes:
    normalized = normalize_run_id(run_id)
    load_manifest(store, normalized)
    keys = store.list_keys(f"{normalized}/")
    output = io.BytesIO()
    total = 0
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for key in keys:
            payload, _ = store.get_bytes(key)
            total += len(payload)
            if total > MAX_BUNDLE_BYTES:
                raise ValueError("run evidence bundle exceeds the 50 MB safety limit")
            archive.writestr(key.removeprefix(f"{normalized}/"), payload)
        report = verify_run(store, normalized)
        archive.writestr("verification-report.json", report.model_dump_json(indent=2))
    return output.getvalue()


def _asset_key(url: str) -> str | None:
    for prefix in ("/api/artifacts/", "/artifacts/"):
        if url.startswith(prefix):
            return url.removeprefix(prefix)
    return None
