"""Shared review contract used by novel, image and video review stages.

``ReviewVerdict`` is the persisted review record (``drama_core.Review``); it lives
in core so that ``Project`` can store it without depending on this package.
"""

from __future__ import annotations

from drama_review.contracts import Reviewer, ReviewRequest, ReviewVerdict
from drama_review.factory import LLM_JUDGE_NAMES, create_reviewer
from drama_review.llm_judge import (
    NOVEL_DIMENSIONS,
    JudgePayload,
    LlmJudgeReviewer,
    parse_action,
    parse_judge_payload,
)
from drama_review.mock import DEFAULT_PASS_ON_ATTEMPT, DeterministicMockReviewer
from drama_review.policy import RetryPolicy
from drama_review.rules import DEFAULT_BANLIST, banlist_issues, word_count_issues

__all__ = [
    "DEFAULT_BANLIST",
    "DEFAULT_PASS_ON_ATTEMPT",
    "LLM_JUDGE_NAMES",
    "NOVEL_DIMENSIONS",
    "DeterministicMockReviewer",
    "JudgePayload",
    "LlmJudgeReviewer",
    "RetryPolicy",
    "ReviewRequest",
    "ReviewVerdict",
    "Reviewer",
    "banlist_issues",
    "create_reviewer",
    "parse_action",
    "parse_judge_payload",
    "word_count_issues",
]
