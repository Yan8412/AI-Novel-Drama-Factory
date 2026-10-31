import pytest
from drama_core import Settings
from drama_review import (
    DeterministicMockReviewer,
    LlmJudgeReviewer,
    Reviewer,
    create_reviewer,
)


def test_default_reviewer_is_mock() -> None:
    reviewer = create_reviewer(Settings())
    assert isinstance(reviewer, DeterministicMockReviewer)
    assert isinstance(reviewer, Reviewer)


def test_llm_judge_aliases() -> None:
    for name in ("llm_judge", "llm-judge"):
        reviewer = create_reviewer(Settings(review_engine=name))
        assert isinstance(reviewer, LlmJudgeReviewer)
        assert reviewer.name == "llm-judge"


def test_unknown_review_engine() -> None:
    with pytest.raises(ValueError, match="REVIEW_ENGINE"):
        create_reviewer(Settings(review_engine="nope"))
