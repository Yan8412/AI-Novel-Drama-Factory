"""Shared review contract used by novel, image and video review stages.

``ReviewVerdict`` is the persisted review record (``drama_core.Review``); it lives
in core so that ``Project`` can store it without depending on this package.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from drama_core import Review, ReviewAction, ReviewIssue, ReviewTargetType

ReviewVerdict = Review


@dataclass(frozen=True)
class ReviewRequest:
    target_type: ReviewTargetType
    target_id: str
    attempt: int
    content: str = ""
    context: Mapping[str, Any] = field(default_factory=dict)


@runtime_checkable
class Reviewer(Protocol):
    name: str

    def review(self, request: ReviewRequest) -> Review: ...


@dataclass(frozen=True)
class RetryPolicy:
    """Turns a raw reviewer opinion into the action the pipeline must take.

    * ``revise`` on the last allowed attempt escalates to ``reject``.
    * ``pass`` with a mean score below ``pass_threshold`` is downgraded to ``revise``
      (guards against lenient LLM judges).
    """

    max_attempts: int = 3
    pass_threshold: float = 7.0

    def resolve(self, review: Review) -> Review:
        action = review.action
        issues = list(review.issues)
        if (
            action is ReviewAction.PASS
            and review.scores
            and review.mean_score < self.pass_threshold
        ):
            action = ReviewAction.REVISE
            issues.append(
                ReviewIssue(
                    severity="major",
                    message=f"mean score {review.mean_score:.1f} < threshold {self.pass_threshold}",
                )
            )
        if action is ReviewAction.REVISE and review.attempt >= self.max_attempts:
            action = ReviewAction.REJECT
            issues.append(
                ReviewIssue(
                    severity="blocker",
                    message=f"still failing after {review.attempt}/{self.max_attempts} attempts",
                )
            )
        if action is review.action:
            return review
        return review.model_copy(update={"action": action, "issues": issues})


DEFAULT_PASS_ON_ATTEMPT: Mapping[ReviewTargetType, int] = {
    ReviewTargetType.CHAPTER: 2,
    ReviewTargetType.ASSET: 2,
    ReviewTargetType.CLIP: 2,
}


class DeterministicMockReviewer:
    """Asks for one revision, then passes, so demos exercise every revise loop.

    ``pass_on_attempt[target_type] = N`` means attempts ``1..N-1`` get ``revise``
    and attempt ``N`` gets ``pass``.
    """

    name = "mock-deterministic"

    def __init__(self, pass_on_attempt: Mapping[ReviewTargetType, int] | None = None) -> None:
        self.pass_on_attempt = dict(DEFAULT_PASS_ON_ATTEMPT)
        if pass_on_attempt:
            self.pass_on_attempt.update(pass_on_attempt)

    def review(self, request: ReviewRequest) -> Review:
        passes = request.attempt >= self.pass_on_attempt[request.target_type]
        score = 8.5 if passes else 6.0
        dims = _DIMENSIONS[request.target_type]
        issues = (
            []
            if passes
            else [
                ReviewIssue(
                    severity="major",
                    message=f"[mock] {request.target_type.value} needs another pass",
                    suggestion="tighten pacing and consistency",
                )
            ]
        )
        return Review(
            target_type=request.target_type,
            target_id=request.target_id,
            attempt=request.attempt,
            scores=dict.fromkeys(dims, score),
            issues=issues,
            action=ReviewAction.PASS if passes else ReviewAction.REVISE,
            reviewer=self.name,
        )


_DIMENSIONS: Mapping[ReviewTargetType, tuple[str, ...]] = {
    ReviewTargetType.CHAPTER: ("plot", "character_consistency", "pacing", "hook"),
    ReviewTargetType.ASSET: ("identity_consistency", "composition", "artifact_free"),
    ReviewTargetType.CLIP: ("motion_quality", "identity_consistency", "temporal_coherence"),
}

__all__ = [
    "DEFAULT_PASS_ON_ATTEMPT",
    "DeterministicMockReviewer",
    "RetryPolicy",
    "ReviewRequest",
    "ReviewVerdict",
    "Reviewer",
]
