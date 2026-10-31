from pathlib import Path

from drama_core import Project, Review, ReviewAction, ReviewTargetType, plan_chapter_lengths
from drama_novel import MockNovelEngine, NovelEngine, NovelMemory


def test_mock_chapters_hit_exact_targets_and_revise() -> None:
    engine = MockNovelEngine()
    assert isinstance(engine, NovelEngine)
    p = Project(title="t", genre="都市", premise="p", total_words=12000)
    bible = engine.create_bible(p)
    p.characters = bible.characters
    outline = engine.write_outline(p, plan_chapter_lengths(p.total_words))
    assert outline.logline.startswith("【都市】")
    memory = NovelMemory()
    for plan in outline.chapters:
        ch = engine.write_chapter(p, plan, memory)
        assert ch.body.startswith("【都市】")
        assert ch.word_count == plan.target_words
        assert ch.within_bounds(p.word_min, p.word_max)
        memory.apply(ch.index, ch.summary, ch.memory_delta)
    review = Review(
        target_type=ReviewTargetType.CHAPTER, target_id=ch.id, attempt=1, action=ReviewAction.REVISE
    )
    revised = engine.revise_chapter(p, ch, review, memory)
    assert revised.id == ch.id and revised.revision == 1
    assert revised.body != ch.body and revised.word_count == ch.word_count


def test_memory_tracks_threads_and_persists(tmp_path: Path) -> None:
    engine = MockNovelEngine()
    p = Project(title="t", genre="g", premise="p", total_words=3000)
    m = NovelMemory()
    m.apply(1, "s1", engine._delta(p, 1))
    m.apply(2, "s2", engine._delta(p, 2))
    assert m.open_threads == ["线索2的来源"]
    m.save(tmp_path)
    assert NovelMemory.load(tmp_path) == m
    assert "未解伏笔" in (tmp_path / "memory.md").read_text(encoding="utf-8")
