from drama_core import Chapter, Project, Shot, Storyboard
from drama_storyboard import storyboard_review_request, storyboard_rule_issues


def test_empty_board_is_blocker() -> None:
    project = Project(title="t", genre="g", premise="p", total_words=3000)
    chapter = Chapter(index=1, title="一", body="一二三四五", target_words=3000)
    project.chapters = [chapter]
    board = Storyboard(chapter_id=chapter.id, shots=[])
    issues = storyboard_rule_issues(project, board)
    assert any(i.severity == "blocker" for i in issues)
    req = storyboard_review_request(project, board)
    assert req.target_id == board.id
    assert req.context["shot_count"] == 0


def test_missing_refs_is_major() -> None:
    project = Project(title="t", genre="g", premise="p", total_words=3000)
    chapter = Chapter(index=1, title="一", body="一二三四五", target_words=3000)
    project.chapters = [chapter]
    board = Storyboard(
        chapter_id=chapter.id,
        shots=[
            Shot(
                index=1,
                chapter_id=chapter.id,
                duration_s=8,
                action="对峙",
                image_prompt="cinematic wide shot",
            ),
            Shot(
                index=2,
                chapter_id=chapter.id,
                duration_s=7,
                action="离开",
                image_prompt="another wide shot",
            ),
        ],
    )
    messages = [i.message for i in storyboard_rule_issues(project, board)]
    assert any("no character or scene" in m for m in messages)
    assert any("9:16" in m or "vertical" in m for m in messages)
