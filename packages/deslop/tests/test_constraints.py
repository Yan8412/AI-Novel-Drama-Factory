from drama_deslop import NO_BURNED_IN_TEXT, prompt_constraint_issues, prompt_guardrails


def test_guardrails_add_no_redescribe_only_when_refs_exist() -> None:
    bare = prompt_guardrails(has_identity_refs=False)
    locked = prompt_guardrails(has_identity_refs=True)
    assert NO_BURNED_IN_TEXT in bare
    assert "Do not re-describe face" not in bare
    assert "Do not re-describe face" in locked
    assert "One primary visible action" in locked


def test_constraint_issues_flag_mood_only_prompts() -> None:
    gaps = prompt_constraint_issues("cinematic atmosphere, emotional lighting")
    assert any("burned-in" in gap for gap in gaps)
    assert any("single primary" in gap for gap in gaps)
    filled = prompt_guardrails(has_identity_refs=True) + " start: door closed. single motion: push."
    assert prompt_constraint_issues(filled, has_identity_refs=True) == []
