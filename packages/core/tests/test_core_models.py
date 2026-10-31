import json

import pytest
from drama_core import (
    Appearance,
    BudgetLog,
    Chapter,
    Character,
    CharacterIdentity,
    Episode,
    EpisodeKind,
    Project,
    Review,
    ReviewAction,
    ReviewTargetType,
    Shot,
    count_words,
)
from pydantic import ValidationError


def test_count_words_chinese_first() -> None:
    assert count_words("你好，世界。") == 4
    assert count_words("林晚 met CEO Gu-Chen at 9pm") == 2 + 5


def test_chapter_word_count_is_derived_from_body() -> None:
    ch = Chapter(index=1, title="t", body="一二三四五", target_words=3000, word_count=999)
    assert ch.word_count == 5
    ch.body = "一二三"
    assert ch.word_count == 3
    assert not ch.within_bounds(2500, 5000)


def test_shot_duration_bounds() -> None:
    Shot(index=1, chapter_id="c", duration_s=5)
    Shot(index=1, chapter_id="c", duration_s=15)
    with pytest.raises(ValidationError):
        Shot(index=1, chapter_id="c", duration_s=4.9)
    with pytest.raises(ValidationError):
        Shot(index=1, chapter_id="c", duration_s=16)


def test_review_scores_validated() -> None:
    with pytest.raises(ValidationError):
        Review(
            target_type=ReviewTargetType.CHAPTER,
            target_id="x",
            attempt=1,
            scores={"plot": 11},
            action=ReviewAction.PASS,
        )


def test_project_roundtrips_through_json() -> None:
    char = Character(
        name="林晚",
        identity=CharacterIdentity(role="女主"),
        appearance=Appearance(description="清冷"),
    )
    p = Project(title="t", genre="g", premise="p", total_words=10000, characters=[char])
    data = json.loads(p.model_dump_json())
    assert data["aspect_ratio"] == "9:16"
    assert (data["width"], data["height"]) == (1080, 1920)
    assert Project.model_validate(data) == p


def test_budget_and_episode_defaults_roundtrip() -> None:
    p = Project(title="t", genre="g", premise="p", total_words=3000)
    p.budget.record(stage="novel", engine="mock-novel", note="wrote")
    p.episodes.append(
        Episode(kind=EpisodeKind.CHAPTER, title="一", duration_s=24, path="episode/chapter_001.mp4")
    )
    clone = Project.model_validate_json(p.model_dump_json())
    assert clone.budget.entries[0].estimated_usd == 0.0
    assert clone.episodes[0].kind is EpisodeKind.CHAPTER
    assert isinstance(p.budget, BudgetLog)


def test_project_rejects_inverted_bounds() -> None:
    with pytest.raises(ValidationError):
        Project(title="t", genre="g", premise="p", total_words=1, word_min=5000, word_max=2500)
