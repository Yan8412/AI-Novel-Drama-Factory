from collections.abc import Mapping, Sequence
from pathlib import Path

from drama_core import ReviewAction, ReviewTargetType
from drama_review import (
    LlmJudgeReviewer,
    ReviewRequest,
    parse_action,
    parse_judge_payload,
)

FIXTURES = Path(__file__).parent / "fixtures"


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


def _chapter_req(content: str, *, words: tuple[int, int] = (10, 50)) -> ReviewRequest:
    return ReviewRequest(
        target_type=ReviewTargetType.CHAPTER,
        target_id="ch_1",
        attempt=1,
        content=content,
        context={
            "rubric": (
                "coherence",
                "character_consistency",
                "word_count_band",
                "sensitive_content",
            ),
            "word_min": words[0],
            "word_max": words[1],
            "memory": "# 故事记忆\n",
        },
    )


def test_parse_pass_fixture() -> None:
    payload = parse_judge_payload((FIXTURES / "judge_pass.json").read_text(encoding="utf-8"))
    assert payload.action == "pass"
    assert payload.scores["coherence"] == 8.5
    assert payload.issues == []


def test_parse_revise_and_reject_fixtures() -> None:
    revise = parse_judge_payload((FIXTURES / "judge_revise.json").read_text(encoding="utf-8"))
    assert revise.action == "revise"
    assert revise.issues[0].severity == "major"
    reject = parse_judge_payload((FIXTURES / "judge_reject.json").read_text(encoding="utf-8"))
    assert reject.action == "reject"
    assert reject.issues[0].severity == "blocker"


def test_parse_fenced_clamps_scores_and_unknown_action() -> None:
    payload = parse_judge_payload((FIXTURES / "judge_fenced.txt").read_text(encoding="utf-8"))
    assert payload.scores["coherence"] == 10.0
    assert payload.scores["character_consistency"] == 0.0
    assert payload.scores["sensitive_content"] == 9.0
    assert payload.issues[0].message == "节奏偏慢"
    assert parse_action(payload.action) is ReviewAction.REVISE


def test_reviewer_maps_pass_json() -> None:
    raw = (FIXTURES / "judge_pass.json").read_text(encoding="utf-8")
    reviewer = LlmJudgeReviewer(ScriptedClient([raw]))
    review = reviewer.review(_chapter_req("一二三四五六七八九十"))
    assert review.action is ReviewAction.PASS
    assert review.reviewer == "llm-judge"
    assert set(review.scores) == {
        "coherence",
        "character_consistency",
        "word_count_band",
        "sensitive_content",
    }
    assert review.scores["word_count_band"] == 10.0


def test_rule_word_count_forces_revise_on_llm_pass() -> None:
    raw = (FIXTURES / "judge_pass.json").read_text(encoding="utf-8")
    reviewer = LlmJudgeReviewer(ScriptedClient([raw]))
    review = reviewer.review(_chapter_req("短", words=(10, 50)))
    assert review.action is ReviewAction.REVISE
    assert any("word_count=" in i.message for i in review.issues)
    assert review.scores["word_count_band"] < 10.0


def test_banlist_stub_forces_revise() -> None:
    raw = (FIXTURES / "judge_pass.json").read_text(encoding="utf-8")
    reviewer = LlmJudgeReviewer(ScriptedClient([raw]), banlist=("禁词",))
    review = reviewer.review(_chapter_req("这里出现禁词一二三四五六七八"))
    assert review.action is ReviewAction.REVISE
    assert any("banlist term: 禁词" in i.message for i in review.issues)


def test_media_targets_passthrough_without_llm() -> None:
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
