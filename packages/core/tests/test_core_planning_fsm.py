from itertools import pairwise

import pytest
from drama_core import (
    HAPPY_PATH,
    InvalidTransitionError,
    PipelineStage,
    Project,
    can_transition,
    plan_chapter_lengths,
    transition,
)


@pytest.mark.parametrize("total", [2500, 3000, 5000, 7400, 12000, 100_000, 1_000_000])
def test_plan_chapter_lengths_within_bounds(total: int) -> None:
    plan = plan_chapter_lengths(total)
    assert sum(plan) == total
    assert all(2500 <= n <= 5000 for n in plan)
    assert max(plan) - min(plan) <= 1


def test_plan_prefers_target_length() -> None:
    assert len(plan_chapter_lengths(35_000)) == 10


@pytest.mark.parametrize("total", [100, 2499])
def test_plan_rejects_too_short(total: int) -> None:
    with pytest.raises(ValueError):
        plan_chapter_lengths(total)


def test_plan_rejects_unsplittable() -> None:
    with pytest.raises(ValueError):
        plan_chapter_lengths(5500, word_min=3000, word_max=5000)


def test_happy_path_is_legal() -> None:
    for a, b in pairwise(HAPPY_PATH):
        assert can_transition(a, b)


def test_illegal_transition_raises_and_history_records() -> None:
    p = Project(title="t", genre="g", premise="p", total_words=3000)
    with pytest.raises(InvalidTransitionError):
        transition(p, PipelineStage.VIDEO)
    transition(p, PipelineStage.CHARACTERS, "go")
    transition(p, PipelineStage.FAILED, "boom")
    assert [h.to_stage for h in p.stage_history] == [PipelineStage.CHARACTERS, PipelineStage.FAILED]
    with pytest.raises(InvalidTransitionError):
        transition(p, PipelineStage.FAILED)
