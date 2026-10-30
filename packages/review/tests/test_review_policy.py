from drama_core import Review, ReviewAction, ReviewTargetType
from drama_review import DeterministicMockReviewer, RetryPolicy, Reviewer, ReviewRequest


def _req(attempt: int, t: ReviewTargetType = ReviewTargetType.CHAPTER) -> ReviewRequest:
    return ReviewRequest(target_type=t, target_id="x", attempt=attempt)


def test_mock_reviewer_is_deterministic() -> None:
    r = DeterministicMockReviewer({ReviewTargetType.CHAPTER: 3})
    assert isinstance(r, Reviewer)
    actions = [r.review(_req(a)).action for a in (1, 2, 3, 4)]
    assert actions == [
        ReviewAction.REVISE,
        ReviewAction.REVISE,
        ReviewAction.PASS,
        ReviewAction.PASS,
    ]


def test_policy_escalates_to_reject_on_last_attempt() -> None:
    policy = RetryPolicy(max_attempts=2)
    r = DeterministicMockReviewer({ReviewTargetType.CLIP: 5})
    assert policy.resolve(r.review(_req(1, ReviewTargetType.CLIP))).action is ReviewAction.REVISE
    final = policy.resolve(r.review(_req(2, ReviewTargetType.CLIP)))
    assert final.action is ReviewAction.REJECT
    assert final.issues[-1].severity == "blocker"


def test_policy_downgrades_low_score_pass() -> None:
    lenient = Review(
        target_type=ReviewTargetType.ASSET,
        target_id="a",
        attempt=1,
        scores={"x": 4.0},
        action=ReviewAction.PASS,
    )
    assert RetryPolicy().resolve(lenient).action is ReviewAction.REVISE
