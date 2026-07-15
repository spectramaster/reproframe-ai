from reproframe.cli import sample_brief
from reproframe.prompting import build_generation_prompt


def test_prompt_preserves_constraints() -> None:
    prompt = build_generation_prompt(sample_brief(), ["Increase label contrast."])

    assert "REQUIRED CLAIMS" in prompt
    assert "Generate" in prompt
    assert "fabricated statistic" in prompt
    assert "Increase label contrast" in prompt

