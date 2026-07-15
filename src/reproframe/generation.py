from __future__ import annotations

import hashlib
import html
from abc import ABC, abstractmethod
from uuid import UUID

from .models import GeneratedAsset, VisualBrief
from .storage import ArtifactStore


class MediaGenerator(ABC):
    @abstractmethod
    def generate(
        self,
        *,
        brief: VisualBrief,
        prompt: str,
        attempt: int,
        run_id: UUID,
    ) -> GeneratedAsset:
        raise NotImplementedError


class FixtureScientificGenerator(MediaGenerator):
    """Produces a real, inspectable SVG so the complete app runs without credentials."""

    def __init__(self, store: ArtifactStore) -> None:
        self.store = store

    def generate(
        self,
        *,
        brief: VisualBrief,
        prompt: str,
        attempt: int,
        run_id: UUID,
    ) -> GeneratedAsset:
        del prompt
        labels = brief.required_labels
        claims = [claim.text for claim in brief.claims]
        text_lines = [brief.title, *labels, *claims]
        escaped_title = html.escape(brief.title)
        escaped_audience = html.escape(brief.audience)
        cards = []
        for index, claim in enumerate(claims[:3]):
            y = 300 + index * 155
            cards.append(
                f'<rect x="110" y="{y}" width="1380" height="118" rx="24" fill="#f7faf9" '
                f'stroke="#dbe8e3"/><text x="160" y="{y + 50}" class="eyebrow">CLAIM '
                f'{index + 1:02d}</text><text x="160" y="{y + 88}" class="claim">'
                f'{html.escape(claim[:116])}</text>'
            )
        label_text = "  ·  ".join(html.escape(label) for label in labels)
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900"
viewBox="0 0 1600 900">
<rect width="1600" height="900" fill="#edf3f1"/>
<circle cx="1440" cy="95" r="250" fill="#b9f5d8" opacity=".72"/>
<circle cx="70" cy="820" r="230" fill="#ced8ff" opacity=".75"/>
<rect x="64" y="60" width="1472" height="780" rx="44" fill="#ffffff" stroke="#d6e1dd"/>
<style>
.kicker{{font:700 22px -apple-system,BlinkMacSystemFont,sans-serif;letter-spacing:4px;fill:#08775d}}
.title{{font:700 60px -apple-system,BlinkMacSystemFont,sans-serif;fill:#142520}}
.sub{{font:400 24px -apple-system,BlinkMacSystemFont,sans-serif;fill:#566963}}
.eyebrow{{font:700 18px -apple-system,BlinkMacSystemFont,sans-serif;
letter-spacing:2px;fill:#08775d}}
.claim{{font:500 25px -apple-system,BlinkMacSystemFont,sans-serif;fill:#21332d}}
.labels{{font:600 19px -apple-system,BlinkMacSystemFont,sans-serif;fill:#344740}}
</style>
<text x="110" y="128" class="kicker">REPROFRAME · EVIDENCE-BOUND VISUAL</text>
<text x="110" y="210" class="title">{escaped_title}</text>
<text x="110" y="258" class="sub">Prepared for {escaped_audience} · attempt {attempt}</text>
{''.join(cards)}
<line x1="110" y1="760" x2="1490" y2="760" stroke="#dbe8e3"/>
<text x="110" y="808" class="labels">{label_text}</text>
</svg>'''
        payload = svg.encode("utf-8")
        digest = hashlib.sha256(payload).hexdigest()
        key = f"{run_id}/attempt-{attempt:02d}-{digest[:12]}.svg"
        url = self.store.put_bytes(key, payload, "image/svg+xml")
        return GeneratedAsset(
            url=url,
            sha256=digest,
            provider="reproframe-fixture",
            model="scientific-svg-v1",
            extracted_text="\n".join(text_lines),
        )


class GenblazeGMIImageGenerator(MediaGenerator):
    """Real Genblaze image pipeline with Backblaze B2 as its durable sink."""

    def __init__(
        self,
        *,
        bucket: str,
        model: str,
        timeout_seconds: int = 180,
    ) -> None:
        from genblaze_core import KeyStrategy, ObjectStorageSink
        from genblaze_gmicloud import GMICloudImageProvider
        from genblaze_s3 import S3StorageBackend

        self.model = model
        self.timeout_seconds = timeout_seconds
        self.provider = GMICloudImageProvider()
        self.sink = ObjectStorageSink(
            S3StorageBackend.for_backblaze(bucket),
            key_strategy=KeyStrategy.HIERARCHICAL,
        )

    def generate(
        self,
        *,
        brief: VisualBrief,
        prompt: str,
        attempt: int,
        run_id: UUID,
    ) -> GeneratedAsset:
        from genblaze_core import Modality, Pipeline

        result = (
            Pipeline(
                f"reproframe-{run_id}-attempt-{attempt}",
                project_id="reproframe-ai",
            )
            .step(
                self.provider,
                model=self.model,
                prompt=prompt,
                modality=Modality.IMAGE,
                aspect_ratio=brief.aspect_ratio,
                _reproframe_attempt=attempt,
            )
            .run(
                sink=self.sink,
                timeout=self.timeout_seconds,
                max_retries=1,
                raise_on_failure=True,
            )
        )
        step = result.run.steps[-1]
        if not step.assets:
            raise RuntimeError("Genblaze completed without an output asset")
        asset = step.assets[-1]
        if not asset.sha256:
            raise RuntimeError("B2-backed Genblaze asset is missing its SHA-256 digest")
        return GeneratedAsset(
            url=asset.url,
            media_type=asset.media_type,
            sha256=asset.sha256,
            provider=step.provider,
            model=step.model,
            provenance_url=result.manifest.manifest_uri,
            provenance_sha256=result.manifest.canonical_hash,
        )
