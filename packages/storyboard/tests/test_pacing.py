from drama_storyboard import (
    SHOTS_PER_CHAPTER_MAX,
    SHOTS_PER_CHAPTER_MIN,
    WORDS_PER_SHOT_MAX,
    WORDS_PER_SHOT_MIN,
    cluster_beats,
    plan_duration,
    plan_shot_count,
    split_beats,
    words_per_shot,
)


def test_plan_shot_count_short_drama_band() -> None:
    assert plan_shot_count(0) == SHOTS_PER_CHAPTER_MIN
    n = plan_shot_count(2500)
    assert SHOTS_PER_CHAPTER_MIN <= n <= SHOTS_PER_CHAPTER_MAX
    density = words_per_shot(2500, n)
    assert WORDS_PER_SHOT_MIN <= density <= WORDS_PER_SHOT_MAX
    n5k = plan_shot_count(5000)
    assert n5k <= SHOTS_PER_CHAPTER_MAX
    assert words_per_shot(5000, n5k) <= WORDS_PER_SHOT_MAX + 50


def test_plan_duration_clamped() -> None:
    assert 5.0 <= plan_duration(50) <= 15.0
    assert 5.0 <= plan_duration(2000) <= 15.0


def test_split_and_cluster_beats() -> None:
    body = "林晚推开门。顾沉没有抬头。“合同在桌上。”雨还在下。"
    beats = split_beats(body)
    assert len(beats) >= 3
    assert any(b.dialogue for b in beats)
    groups = cluster_beats(beats, 2)
    assert len(groups) == 2
    assert sum(len(g) for g in groups) >= len(beats)
