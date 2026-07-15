from __future__ import annotations

import html
import json
from pathlib import Path

import gradio as gr

from reproframe.models import EvidenceClaim, VisualBrief
from reproframe.pipeline import build_fixture_pipeline

ARTIFACT_ROOT = Path("/tmp/reproframe-space-runs")


def _split_lines(value: str, *, maximum: int) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()][:maximum]


def _split_commas(value: str, *, maximum: int) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()][:maximum]


def generate_visual(
    title: str,
    audience: str,
    claims_text: str,
    labels_text: str,
    forbidden_text: str,
    style: str,
) -> tuple[str, str, str]:
    claims = _split_lines(claims_text, maximum=8)
    if not claims:
        raise gr.Error("Add at least one evidence-backed claim.")

    brief = VisualBrief(
        title=title,
        audience=audience,
        claims=[
            EvidenceClaim(
                claim_id=f"c{index}",
                text=claim,
                priority="required" if index <= 2 else "supporting",
            )
            for index, claim in enumerate(claims, start=1)
        ],
        required_labels=_split_commas(labels_text, maximum=12),
        forbidden_elements=_split_commas(forbidden_text, maximum=12),
        style=style,
        aspect_ratio="16:9",
    )
    summary = build_fixture_pipeline(ARTIFACT_ROOT).run(brief)

    asset_path = ARTIFACT_ROOT / summary.asset_url.removeprefix("/artifacts/")
    manifest_path = ARTIFACT_ROOT / summary.manifest_url.removeprefix("/artifacts/")
    svg = asset_path.read_text(encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    preview = (
        '<div class="rf-preview" aria-label="Generated scientific visual">'
        f"{svg}"
        "</div>"
    )
    metrics = (
        f"### {html.escape(summary.status.replace('_', ' ').title())}\n\n"
        f"- **Guardrail score:** {summary.score:.2f}\n"
        f"- **Attempts:** {summary.attempts}\n"
        f"- **SHA-256 manifest:** `{summary.canonical_sha256}`\n"
        "- **Demo provider:** `reproframe-fixture` (no cloud credentials)\n\n"
        "The public Space exercises the same Genblaze generate → evaluate → feedback "
        "boundary without transmitting project secrets. The repository documents a separate "
        "verified Gemini + encrypted Backblaze B2 run."
    )
    return preview, metrics, json.dumps(manifest, indent=2)


CSS = """
.gradio-container { max-width: 1240px !important; }
.rf-preview { background: #edf3f1; border: 1px solid #d6e1dd; border-radius: 18px;
  overflow: hidden; padding: 12px; }
.rf-preview svg { display: block; width: 100%; height: auto; }
.rf-note { color: #566963; }
"""


with gr.Blocks(title="ReproFrame AI") as demo:
    gr.Markdown(
        "# ReproFrame AI\n"
        "**Scientific visuals you can verify, not just admire.**\n\n"
        "Turn evidence-backed claims into a visual abstract while keeping generation, "
        "evaluation, retries, content hashes, and provenance attached."
    )
    gr.Markdown(
        "This public evaluation demo runs in deterministic, credential-free proof mode. "
        "It does not receive or expose Gemini, GMI, or Backblaze credentials.",
        elem_classes="rf-note",
    )

    with gr.Row():
        with gr.Column(scale=5):
            title = gr.Textbox(
                label="Title",
                value="Safer scientific visuals from generative AI",
            )
            audience = gr.Textbox(
                label="Audience",
                value="researchers and journal editors",
            )
            claims = gr.Textbox(
                label="Evidence-backed claims (one per line)",
                lines=6,
                value=(
                    "Every generated asset is linked to its prompt, model, and evaluation.\n"
                    "Failed checks produce explicit feedback before a new attempt is created.\n"
                    "The final bundle includes a content hash and replayable manifest."
                ),
            )
            labels = gr.Textbox(
                label="Required exact labels",
                value="Generate, Evaluate, Retry, Verify",
            )
            forbidden = gr.Textbox(
                label="Forbidden content",
                value="fabricated statistic, medical diagnosis",
            )
            style = gr.Textbox(
                label="Visual direction",
                value="clean scientific editorial, restrained green and indigo palette",
            )
            run = gr.Button("Generate with evidence guardrails", variant="primary")

        with gr.Column(scale=7):
            preview = gr.HTML(label="Generated visual")
            metrics = gr.Markdown()

    manifest = gr.Textbox(label="Replayable manifest", lines=18, interactive=False)
    gr.Markdown(
        "[Source code](https://github.com/spectramaster/reproframe-ai) · "
        "Genblaze AgentLoop · Backblaze B2 provenance"
    )

    run.click(
        fn=generate_visual,
        inputs=[title, audience, claims, labels, forbidden, style],
        outputs=[preview, metrics, manifest],
        api_name="generate_visual",
    )


if __name__ == "__main__":
    demo.queue().launch(css=CSS)
