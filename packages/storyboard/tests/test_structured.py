from drama_core import Chapter, ChapterPlan, Project
from drama_novel import MockNovelEngine, NovelMemory
from drama_storyboard import (
    MockStoryboardEngine,
    StructuredStoryboardEngine,
    storyboard_rule_issues,
    to_markdown,
    words_per_shot,
)
from drama_storyboard.pacing import WORDS_PER_SHOT_MAX, WORDS_PER_SHOT_MIN


def _project_chapter() -> tuple[Project, Chapter]:
    project = Project(title="契约新娘", genre="都市甜宠", premise="契约", total_words=3000)
    bible = MockNovelEngine().create_bible(project)
    project.characters = bible.characters
    project.scenes = bible.scenes
    project.props = bible.props
    chapter = MockNovelEngine().write_chapter(
        project, ChapterPlan(index=1, title="雨夜", summary="对峙", target_words=800), NovelMemory()
    )
    return project, chapter


def test_structured_assigns_refs_and_vertical_prompts() -> None:
    project, chapter = _project_chapter()
    body = (
        "林晚站在雨夜街头攥紧祖传玉佩。"
        "顾沉把契约婚姻合同推到顾氏集团顶层办公室的桌上。"
        "苏曼冷笑一声。“这一次，我不会再退。”"
        "霓虹在水里碎成光。"
    ) * 40
    chapter = chapter.model_copy(update={"body": body})
    board = StructuredStoryboardEngine().build(project, chapter)
    assert 2 <= len(board.shots) <= 10
    density = words_per_shot(chapter.word_count, len(board.shots))
    assert WORDS_PER_SHOT_MIN <= density <= WORDS_PER_SHOT_MAX
    assert all(s.aspect_ratio == "9:16" for s in board.shots)
    assert all(s.character_ids for s in board.shots)
    assert any(s.scene_id for s in board.shots)
    assert any("林晚" in s.image_prompt or "顾沉" in s.image_prompt for s in board.shots)
    assert all("9:16" in s.image_prompt or "vertical" in s.image_prompt for s in board.shots)
    hard = [i for i in storyboard_rule_issues(project, board) if i.severity in {"major", "blocker"}]
    assert hard == []
    md = to_markdown(project, board)
    assert "画幅：9:16" in md
    assert "画面:" in md


def test_mock_storyboard_keeps_three_shots() -> None:
    project, chapter = _project_chapter()
    board = MockStoryboardEngine().build(project, chapter)
    assert len(board.shots) == 3
    assert all(s.aspect_ratio == "9:16" for s in board.shots)
