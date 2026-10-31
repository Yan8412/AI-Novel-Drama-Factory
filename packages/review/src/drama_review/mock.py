"""Deterministic offline reviewer so demos exercise every revise loop."""

from __future__ import annotations

from collections.abc import Mapping

from drama_core import Review, ReviewAction, ReviewIssue, ReviewTargetType

from drama_review.contracts import ReviewRequest

DEFAULT_PASS_ON_ATTEMPT: Mapping[ReviewTargetType, int] = {
    ReviewTargetType.CHAPTER: 2,
    ReviewTargetType.ASSET: 2,
    ReviewTargetType.CLIP: 2,
}

_DIMENSIONS: Mapping[ReviewTargetType, tuple[str, ...]] = {
    ReviewTargetType.CHAPTER: ("plot", "character_consistency", "pacing", "hook"),
    ReviewTargetType.ASSET: ("identity_consistency", "composition", "artifact_free"),
    ReviewTargetType.CLIP: ("motion_quality", "identity_consistency", "temporal_coherence"),
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
