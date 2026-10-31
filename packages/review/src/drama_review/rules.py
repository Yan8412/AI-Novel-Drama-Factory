"""Deterministic rule checks that run alongside an LLM judge."""

from __future__ import annotations

from collections.abc import Sequence

from drama_core import ReviewIssue, count_words

# Placeholder only — extend via ``LlmJudgeReviewer(banlist=...)`` or REVIEW_BANLIST.
DEFAULT_BANLIST: tuple[str, ...] = ()


def word_count_issues(content: str, word_min: int, word_max: int) -> list[ReviewIssue]:
    n = count_words(content)
    if word_min <= n <= word_max:
        return []
    return [
        ReviewIssue(
            severity="blocker",
            message=f"word_count={n} outside [{word_min}, {word_max}]",
            suggestion="expand or trim the chapter",
        )
    ]


def word_count_band_score(content: str, word_min: int, word_max: int) -> float:
    n = count_words(content)
    if word_min <= n <= word_max:
        return 10.0
    if n <= 0:
        return 0.0
    if n < word_min:
        ratio = n / word_min
    else:
        overflow = n - word_max
        ratio = max(0.0, 1.0 - overflow / word_max)
    return round(max(0.0, min(10.0, ratio * 6.0)), 2)


def banlist_issues(content: str, terms: Sequence[str] = DEFAULT_BANLIST) -> list[ReviewIssue]:
    hits = [term for term in terms if term and term in content]
    return [
        ReviewIssue(
            severity="blocker",
            message=f"banlist term: {term}",
            suggestion="remove the prohibited wording",
        )
        for term in hits
    ]
