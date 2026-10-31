from collections.abc import Mapping, Sequence

from drama_core import ReviewAction, ReviewTargetType
from drama_review import LlmJudgeReviewer, ReviewRequest

PASS = (
    '{"scores": {"motion_quality": 8, "identity_consistency": 8, "temporal_coherence": 8},'
    ' "issues": [], "action": "pass"}'
)


class ScriptedClient:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls: list[list[dict[str, str]]] = []

    def chat(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        temperature: float = 0.4,
        json_mode: bool = True,
    ) -> str:
        self.calls.append([dict(m) for m in messages])
        return self.responses.pop(0)


def test_mock_clip_passthrough() -> None:
    reviewer = LlmJudgeReviewer(ScriptedClient([]))
    review = reviewer.review(
        ReviewRequest(
            target_type=ReviewTargetType.CLIP,
            target_id="c1",
            attempt=1,
            content="mock://video/x.mp4",
        )
    )
    assert review.action is ReviewAction.PASS
    assert review.reviewer == "llm-judge-media-passthrough"


def test_real_clip_calls_llm() -> None:
    client = ScriptedClient([PASS])
    reviewer = LlmJudgeReviewer(client)
    review = reviewer.review(
        ReviewRequest(
            target_type=ReviewTargetType.CLIP,
            target_id="c1",
            attempt=1,
            content="https://vid.test/a.mp4",
            context={
                "rubric": ("motion_quality", "identity_consistency", "temporal_coherence"),
                "duration_s": 8,
                "width": 1080,
                "height": 1920,
                "prompt": "vertical 9:16 slow push-in",
            },
        )
    )
    assert review.action is ReviewAction.PASS
    assert review.reviewer == "llm-judge"
    assert set(review.scores) == {
        "motion_quality",
        "identity_consistency",
        "temporal_coherence",
    }
    assert "vertical 9:16" in client.calls[0][1]["content"]
