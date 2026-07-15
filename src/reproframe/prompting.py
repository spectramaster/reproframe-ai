from __future__ import annotations

from .models import VisualBrief


def build_generation_prompt(brief: VisualBrief, feedback: list[str] | None = None) -> str:
    required_claims = [claim.text for claim in brief.claims if claim.priority == "required"]
    supporting_claims = [claim.text for claim in brief.claims if claim.priority == "supporting"]

    sections = [
        "Create a single scientific visual abstract.",
        f"TITLE: {brief.title}",
        f"AUDIENCE: {brief.audience}",
        f"STYLE: {brief.style}",
        f"ASPECT RATIO: {brief.aspect_ratio}",
        "REQUIRED CLAIMS (show only these claims, without adding new facts):",
        *[f"- {claim}" for claim in required_claims],
    ]
    if supporting_claims:
        sections.extend(
            ["SUPPORTING CLAIMS:", *[f"- {claim}" for claim in supporting_claims]]
        )
    if brief.required_labels:
        sections.extend(
            ["REQUIRED EXACT LABELS:", *[f"- {label}" for label in brief.required_labels]]
        )
    if brief.forbidden_elements:
        sections.extend(
            ["DO NOT INCLUDE:", *[f"- {item}" for item in brief.forbidden_elements]]
        )
    sections.append(
        "Use a restrained layout, legible hierarchy, generous whitespace, and no invented numbers."
    )
    if feedback:
        sections.extend(["REVISION REQUESTS:", *[f"- {item}" for item in feedback]])
    return "\n".join(sections)

