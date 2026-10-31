from drama_storyboard import (
    SHOTS_PER_CHAPTER_MAX,
    SHOTS_PER_CHAPTER_MIN,
    WORDS_PER_SHOT_MAX,
    WORDS_PER_SHOT_MIN,
    Beat,
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


def test_cluster_reserves_beats_when_weight_is_at_the_end() -> None:
    beats = [Beat(text=str(i), word_count=1) for i in range(5)]
    beats.append(Beat(text="climax", word_count=100))
    groups = cluster_beats(beats, 3)
    assert len(groups) == 3
    assert groups[-1][0].text == "climax"
    assert all(g for g in groups)
    # First five light beats must not all collapse into one padded group.
    assert [b.text for g in groups[:-1] for b in g] == ["0", "1", "2", "3", "4"]
