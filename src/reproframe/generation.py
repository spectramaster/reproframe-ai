from __future__ import annotations

import hashlib
import html
import re
from abc import ABC, abstractmethod
from uuid import UUID
from xml.etree import ElementTree

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


class GeminiSVGGenerator(MediaGenerator):
    """Generate a self-contained scientific SVG with a free-tier Gemini text model."""

    def __init__(
        self,
        store: ArtifactStore,
        *,
        api_key: str,
        model: str = "gemini-3.1-flash-lite",
        client=None,
    ) -> None:
        if client is None:
            from google import genai

            client = genai.Client(api_key=api_key)
        self.store = store
        self.client = client
        self.model = model

    def generate(
        self,
        *,
        brief: VisualBrief,
        prompt: str,
        attempt: int,
        run_id: UUID,
    ) -> GeneratedAsset:
        svg_prompt = f"""{prompt}

Return one complete, self-contained SVG document and nothing else.
Technical constraints:
- Use viewBox="0 0 1600 900" and a 16:9 editorial layout.
- Include every required exact label and supplied claim as visible SVG text.
- Do not use scripts, foreignObject, event handlers, external URLs, embedded data URLs,
  animation, or imported fonts. Use only SVG shapes, paths, gradients, and text.
- Do not wrap the SVG in Markdown fences.
- This is revision attempt {attempt}; prioritize legibility and evidence fidelity.
"""
        response = None
        selected_model = self.model
        last_error: Exception | None = None
        model_candidates = dict.fromkeys(
            (self.model, "gemini-3.1-flash-lite", "gemini-3-flash-preview")
        )
        for candidate in model_candidates:
            try:
                response = self.client.models.generate_content(
                    model=candidate,
                    contents=svg_prompt,
                )
                selected_model = candidate
                break
            except Exception as exc:
                last_error = exc
        if response is None:
            raise RuntimeError("All configured Gemini SVG models failed") from last_error
        payload, extracted_text = _validated_svg(response.text or "")
        digest = hashlib.sha256(payload).hexdigest()
        key = f"{run_id}/attempt-{attempt:02d}-{digest[:12]}.svg"
        url = self.store.put_bytes(key, payload, "image/svg+xml")
        return GeneratedAsset(
            url=url,
            sha256=digest,
            provider="google-gemini",
            model=selected_model,
            extracted_text=extracted_text,
        )


def _validated_svg(raw: str) -> tuple[bytes, str]:
    start = raw.find("<svg")
    end = raw.rfind("</svg>")
    if start < 0 or end < start:
        raise ValueError("Gemini response did not contain a complete SVG document")
    svg = raw[start : end + len("</svg>")]
    if len(svg.encode("utf-8")) > 1_500_000:
        raise ValueError("Generated SVG exceeds the 1.5 MB safety limit")
    if re.search(r"<!DOCTYPE|<!ENTITY", svg, re.IGNORECASE):
        raise ValueError("Generated SVG contains a forbidden document declaration")

    root = ElementTree.fromstring(svg)
    if root.tag.rsplit("}", 1)[-1] != "svg":
        raise ValueError("Generated document root is not SVG")
    if root.get("viewBox") != "0 0 1600 900":
        raise ValueError("Generated SVG must use viewBox 0 0 1600 900")

    forbidden_tags = {"script", "foreignObject", "animate", "set"}
    for element in root.iter():
        local_tag = element.tag.rsplit("}", 1)[-1]
        if local_tag in forbidden_tags:
            raise ValueError(f"Generated SVG contains forbidden element: {local_tag}")
        for name, value in element.attrib.items():
            local_name = name.rsplit("}", 1)[-1].casefold()
            normalized_value = value.strip().casefold()
            if local_name.startswith("on"):
                raise ValueError("Generated SVG contains an event handler")
            if local_name == "href" and not normalized_value.startswith("#"):
                raise ValueError("Generated SVG contains an external reference")
            if _contains_external_url(normalized_value) or normalized_value.startswith("data:"):
                raise ValueError("Generated SVG contains an embedded or external URL")
        if local_tag == "style" and element.text:
            style = element.text.casefold()
            if "@import" in style or _contains_external_url(style):
                raise ValueError("Generated SVG style contains an external reference")

    payload = ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)
    extracted_text = "\n".join(text.strip() for text in root.itertext() if text.strip())
    return payload, extracted_text


def _contains_external_url(value: str) -> bool:
    targets = re.findall(r"url\(([^)]+)\)", value, flags=re.IGNORECASE)
    return any(not target.strip(" \t\r\n\"'").startswith("#") for target in targets)


class GenblazeGMIImageGenerator(MediaGenerator):
    """Real Genblaze image pipeline with Backblaze B2 as its durable sink."""

    def __init__(
        self,
        *,
        bucket: str,
        region: str,
        b2_key_id: str,
        b2_app_key: str,
        gmi_api_key: str,
        model: str,
        timeout_seconds: int = 180,
    ) -> None:
        from genblaze_core import KeyStrategy, ObjectStorageSink
        from genblaze_gmicloud import GMICloudImageProvider
        from genblaze_s3 import S3StorageBackend

        self.model = model
        self.timeout_seconds = timeout_seconds
        self.provider = GMICloudImageProvider(api_key=gmi_api_key)
        self.sink = ObjectStorageSink(
            S3StorageBackend.for_backblaze(
                bucket,
                region=region,
                key_id=b2_key_id,
                app_key=b2_app_key,
            ),
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
