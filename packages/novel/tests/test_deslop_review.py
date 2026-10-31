from drama_core import Chapter, Project, Review, ReviewAction, ReviewTargetType
from drama_novel import flavor_issues, merge_chapter_review
from drama_novel.memory import NovelMemory
from drama_novel.review import CHAPTER_RUBRIC, chapter_review_request


def test_flavor_issues_quote_evidence() -> None:
    chapter = Chapter(
        index=1,
        title="觉醒",
        body="不难看出她微微一笑，又微微点头，再微微转身。心中暗道完了，心中暗道算了，心中暗道快走。",
        target_words=40,
    )
    issues = flavor_issues(chapter)
    assert issues
    assert any("deslop" in item.message for item in issues)
    assert any(item.severity in {"major", "blocker"} for item in issues)


def test_merge_does_not_force_revise_unless_strict() -> None:
    project = Project(title="t", genre="g", premise="p", total_words=3000, word_min=1, word_max=500)
    chapter = Chapter(
        index=1,
        title="觉醒",
        body="不难看出结局。",
        target_words=40,
    )
    review = Review(
        target_type=ReviewTargetType.CHAPTER,
        target_id=chapter.id,
        attempt=2,
        action=ReviewAction.PASS,
        scores={"coherence": 8},
    )
    soft = merge_chapter_review(project, chapter, review, deslop_enabled=True, deslop_strict=False)
    assert soft.action is ReviewAction.PASS
    assert any("deslop" in item.message for item in soft.issues)
    hard = merge_chapter_review(project, chapter, review, deslop_enabled=True, deslop_strict=True)
    assert hard.action is ReviewAction.REVISE
    off = merge_chapter_review(project, chapter, review, deslop_enabled=False)
    assert off.issues == []


def test_chapter_review_request_includes_deslop_payload() -> None:
    project = Project(title="t", genre="g", premise="p", total_words=3000)
    chapter = Chapter(index=1, title="一", body="林晚推开门。", target_words=40)
    req = chapter_review_request(project, chapter, NovelMemory())
    assert "anti_ai_flavor" in CHAPTER_RUBRIC
    assert req.context["rubric"] == CHAPTER_RUBRIC
    payload = req.context["deslop"]
    assert isinstance(payload, dict)
    assert payload["word_count"] == chapter.word_count
