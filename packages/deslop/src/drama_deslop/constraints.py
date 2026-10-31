"""Shared negative constraints for image / I2V prompts."""

from __future__ import annotations

from collections.abc import Sequence

NO_BURNED_IN_TEXT = (
    "Do not generate burned-in subtitles, captions, lower-thirds, "
    "or dialogue text overlay at any frame."
)
ONE_MOTION = "One primary visible action only. One camera move only (or a hold)."
NO_ABSTRACT_MOOD = (
    "Direct with concrete visible actions and end states, "
    "not abstract mood-only adjectives (cinematic atmosphere, emotional, poignant)."
)
NO_REDISCRIBE = (
    "Do not re-describe face, hair, eyes, or clothes; "
    "identity refs and the continuity lock already hold appearance."
)

SHARED_NEGATIVES: tuple[str, ...] = (NO_BURNED_IN_TEXT, ONE_MOTION, NO_ABSTRACT_MOOD)

_ABSTRACT_MOOD = (
    "cinematic atmosphere",
    "emotional lighting",
    "poignant",
    "dreamlike mood",
    "epic atmosphere",
)


def prompt_guardrails(*, has_identity_refs: bool) -> str:
    parts = list(SHARED_NEGATIVES)
    if has_identity_refs:
        parts.append(NO_REDISCRIBE)
    return " ".join(parts)


def has_identity_refs(references: Sequence[object] | None) -> bool:
    return bool(references)


def prompt_constraint_issues(prompt: str, *, has_identity_refs: bool = False) -> list[str]:
    """Return human-readable gaps in a finished image/video prompt (minors)."""
    text = (prompt or "").strip()
    if not text:
        return []
    lower = text.lower()
    issues: list[str] = []
    if "burned-in" not in lower and "caption" not in lower and "subtitle" not in lower:
        issues.append("prompt does not forbid burned-in captions/subtitles")
    if "single motion" not in lower and "single action" not in lower and "one primary" not in lower:
        issues.append("prompt does not state a single primary motion")
    if has_identity_refs and "do not re-describe" not in lower and "re-describe" not in lower:
        issues.append("refs present but prompt does not forbid re-describing appearance")
    if (
        any(token in lower for token in _ABSTRACT_MOOD)
        and "start:" not in lower
        and "not abstract mood" not in lower
    ):
        issues.append("abstract mood words without a visible start/end state")
    return issues
