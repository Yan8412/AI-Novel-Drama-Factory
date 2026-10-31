"""Turns a raw reviewer opinion into the action the pipeline must take."""

from __future__ import annotations

from dataclasses import dataclass

from drama_core import Review, ReviewAction, ReviewIssue


@dataclass(frozen=True)
class RetryPolicy:
    """Normalize reviewer output before the orchestrator records it.

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
