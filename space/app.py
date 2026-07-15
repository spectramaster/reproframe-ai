from __future__ import annotations

import hashlib
import html
import json
from datetime import datetime, timezone
from uuid import uuid4

import gradio as gr


def _split_lines(value: str, *, maximum: int) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()][:maximum]


def _split_commas(value: str, *, maximum: int) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()][:maximum]


def _build_svg(title: str, claims: list[str], labels: list[str], style: str) -> str:
    safe_title = html.escape(title or "Evidence-grounded visual")
    safe_style = html.escape(style or "clean scientific editorial")
    safe_claims = [html.escape(claim) for claim in claims]
    safe_labels = [html.escape(label) for label in labels]
    claim_rows = "".join(
        f'<text x="84" y="{286 + index * 70}" font-size="22" fill="#243f39">'
        f'<tspan font-weight="700">{index + 1:02d}</tspan>'
        f'<tspan x="132">{claim[:86]}</tspan></text>'
        for index, claim in enumerate(safe_claims[:5])
    )
    step_width = 890 / max(len(safe_labels), 1)
    steps = "".join(
        f'<rect x="{75 + index * step_width:.0f}" y="620" width="{step_width - 14:.0f}" '
        'height="72" rx="18" fill="#e9eeff" stroke="#899ce6"/>'
        f'<text x="{75 + index * step_width + (step_width - 14) / 2:.0f}" y="665" '
        f'text-anchor="middle" font-size="21" font-weight="700" fill="#34478f">{label}</text>'
        for index, label in enumerate(safe_labels[:8])
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 760" role="img"
 aria-label="{safe_title}">
  <rect width="1200" height="760" fill="#f5f8f7"/>
  <rect x="42" y="42" width="1116" height="676" rx="32" fill="#ffffff" stroke="#d7e3df"/>
  <text x="76" y="122" font-size="42" font-weight="800" fill="#173f36">{safe_title}</text>
  <text x="78" y="168" font-size="19" fill="#60736e">{safe_style}</text>
  <line x1="76" y1="202" x2="1124" y2="202" stroke="#cfe0db" stroke-width="2"/>
  <text x="78" y="248" font-size="19" font-weight="700" fill="#596c67">BOUNDED CLAIMS</text>
  {claim_rows}
  <text x="78" y="586" font-size="19" font-weight="700" fill="#596c67">VERIFICATION LOOP</text>
  {steps}
  <text x="1118" y="704" text-anchor="end" font-size="16" fill="#70827d">
    fixture proof · SHA-256 attached
  </text>
</svg>'''


def _evaluate(svg: str, labels: list[str], forbidden: list[str]) -> tuple[float, list[str]]:
    checks = [label.lower() in svg.lower() for label in labels]
    checks.extend(term.lower() not in svg.lower() for term in forbidden)
    feedback = [
        f"Missing required label: {label}"
        for label in labels
        if label.lower() not in svg.lower()
    ]
    feedback.extend(
        f"Remove forbidden content: {term}" for term in forbidden if term.lower() in svg.lower()
    )
    return (sum(checks) / len(checks) if checks else 1.0), feedback


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
    labels = _split_commas(labels_text, maximum=8)
    forbidden = _split_commas(forbidden_text, maximum=12)

    attempts = []
    first_labels = labels[:-1] if len(labels) > 1 else labels
    first_svg = _build_svg(title, claims, first_labels, style)
    first_score, first_feedback = _evaluate(first_svg, labels, forbidden)
    attempts.append({"attempt": 1, "score": first_score, "feedback": first_feedback})

    if first_feedback:
        final_svg = _build_svg(title, claims, labels, style)
        final_score, final_feedback = _evaluate(final_svg, labels, forbidden)
        attempts.append({"attempt": 2, "score": final_score, "feedback": final_feedback})
    else:
        final_svg, final_score = first_svg, first_score

    digest = hashlib.sha256(final_svg.encode("utf-8")).hexdigest()
    manifest = {
        "run_id": str(uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),  # noqa: UP017
        "mode": "credential-free deterministic fixture",
        "audience": audience,
        "claims": claims,
        "required_labels": labels,
        "forbidden_elements": forbidden,
        "attempts": attempts,
        "final_score": final_score,
        "asset_sha256": digest,
        "boundary": "generate -> evaluate -> feedback -> retry -> verify",
        "implementation_note": (
            "The public Space replays the deterministic contract around the AgentLoop. "
            "The public GitHub repository contains the actual Genblaze and "
            "Backblaze B2 integration."
        ),
    }
    preview = f'<div class="rf-preview" aria-label="Generated scientific visual">{final_svg}</div>'
    metrics = (
        "### Verified fixture result\n\n"
        f"- **Guardrail score:** {final_score:.2f}\n"
        f"- **Attempts:** {len(attempts)}\n"
        f"- **Asset SHA-256:** `{digest}`\n"
        "- **Public demo mode:** credential-free deterministic fixture\n\n"
        "This Space exposes no project credentials. The repository documents the separate "
        "verified Gemini + Genblaze + encrypted Backblaze B2 run."
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
        "Turn evidence-backed claims into a visual abstract while keeping evaluation, retries, "
        "content hashes, and provenance attached."
    )
    gr.Markdown(
        "This public evaluation demo runs in deterministic, credential-free fixture mode. "
        "It does not receive or expose Gemini, GMI, or Backblaze credentials.",
        elem_classes="rf-note",
    )

    with gr.Row():
        with gr.Column(scale=5):
            title = gr.Textbox(label="Title", value="Safer scientific visuals from generative AI")
            audience = gr.Textbox(label="Audience", value="researchers and journal editors")
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
                label="Required exact labels", value="Generate, Evaluate, Retry, Verify"
            )
            forbidden = gr.Textbox(
                label="Forbidden content", value="fabricated statistic, medical diagnosis"
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
