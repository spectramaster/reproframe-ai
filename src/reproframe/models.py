from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl, field_validator


class EvidenceClaim(BaseModel):
    claim_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,32}$")
    text: str = Field(min_length=3, max_length=320)
    evidence_url: HttpUrl | None = None
    priority: Literal["required", "supporting"] = "required"


class VisualBrief(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    audience: str = Field(min_length=3, max_length=120)
    claims: list[EvidenceClaim] = Field(min_length=1, max_length=8)
    required_labels: list[str] = Field(default_factory=list, max_length=12)
    forbidden_elements: list[str] = Field(default_factory=list, max_length=12)
    style: str = Field(default="clean scientific editorial", min_length=3, max_length=160)
    aspect_ratio: Literal["16:9", "4:3", "1:1"] = "16:9"

    @field_validator("required_labels", "forbidden_elements")
    @classmethod
    def normalize_phrases(cls, values: list[str]) -> list[str]:
        cleaned = []
        for value in values:
            phrase = " ".join(value.split()).strip()
            if phrase and phrase.casefold() not in {v.casefold() for v in cleaned}:
                cleaned.append(phrase[:80])
        return cleaned


class GeneratedAsset(BaseModel):
    url: str
    media_type: str = "image/svg+xml"
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider: str
    model: str
    extracted_text: str = ""
    provenance_url: str | None = None
    provenance_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class Evaluation(BaseModel):
    passed: bool
    score: float = Field(ge=0, le=1)
    checks: dict[str, bool]
    feedback: list[str] = Field(default_factory=list)


class Attempt(BaseModel):
    index: int = Field(ge=1)
    prompt: str
    asset: GeneratedAsset
    evaluation: Evaluation


class ReproducibilityManifest(BaseModel):
    schema_version: str = "reproframe/0.1"
    run_id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    brief: VisualBrief
    attempts: list[Attempt]
    final_attempt: int
    status: Literal["accepted", "needs_review"]
    canonical_sha256: str


class RunSummary(BaseModel):
    run_id: UUID
    status: Literal["accepted", "needs_review"]
    score: float
    attempts: int
    asset_url: str
    manifest_url: str
    canonical_sha256: str
