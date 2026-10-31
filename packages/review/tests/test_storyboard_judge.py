from collections.abc import Mapping, Sequence

from drama_core import ReviewAction, ReviewTargetType
from drama_review import LlmJudgeReviewer, ReviewRequest

PASS = (
    '{"scores": {"pacing": 8, "coverage": 8, "vertical_framing": 9, "continuity": 8},'
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


def test_storyboard_calls_llm() -> None:
    reviewer = LlmJudgeReviewer(ScriptedClient([PASS]))
    review = reviewer.review(
        ReviewRequest(
            target_type=ReviewTargetType.STORYBOARD,
            target_id="sb_1",
            attempt=1,
            content="# 分镜\n| 1 | 8 | 雨夜 | 林晚 |",
            context={"rubric": ("pacing", "coverage", "vertical_framing", "continuity")},
        )
    )
    assert review.action is ReviewAction.PASS
    assert review.reviewer == "llm-judge"
    assert set(review.scores) == {"pacing", "coverage", "vertical_framing", "continuity"}


def test_mock_asset_still_passthrough() -> None:
    reviewer = LlmJudgeReviewer(ScriptedClient([]))
    review = reviewer.review(
        ReviewRequest(
            target_type=ReviewTargetType.ASSET,
            target_id="a1",
            attempt=1,
            content="mock://vision/x.png",
        )
    )
    assert review.action is ReviewAction.PASS
    assert review.reviewer == "llm-judge-media-passthrough"
