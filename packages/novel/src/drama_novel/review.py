"""Novel-review helpers: build reviewer requests and rule-based checks for chapters."""

from __future__ import annotations

from drama_core import Chapter, Project, Review, ReviewAction, ReviewIssue, ReviewTargetType
from drama_deslop import scan_text
from drama_review import ReviewRequest

from drama_novel.memory import NovelMemory

CHAPTER_RUBRIC: tuple[str, ...] = (
    "coherence",
    "character_consistency",
    "word_count_band",
    "sensitive_content",
    "anti_ai_flavor",
)


def chapter_review_request(
    project: Project, chapter: Chapter, memory: NovelMemory
) -> ReviewRequest:
    return ReviewRequest(
        target_type=ReviewTargetType.CHAPTER,
        target_id=chapter.id,
        attempt=chapter.revision + 1,
        content=chapter.body,
        context={
            "rubric": CHAPTER_RUBRIC,
            "memory": memory.to_markdown(),
            "word_min": project.word_min,
            "word_max": project.word_max,
            "deslop": scan_text(chapter.body, title=chapter.title).to_payload(),
        },
    )


def length_issues(project: Project, chapter: Chapter) -> list[ReviewIssue]:
    if chapter.within_bounds(project.word_min, project.word_max):
        return []
    return [
        ReviewIssue(
            severity="blocker",
            message=(
                f"word_count={chapter.word_count} outside [{project.word_min}, {project.word_max}]"
            ),
            suggestion="expand or trim the chapter",
        )
    ]


def flavor_issues(chapter: Chapter) -> list[ReviewIssue]:
    return scan_text(chapter.body, title=chapter.title).as_review_issues()


def merge_chapter_review(
    project: Project,
    chapter: Chapter,
    review: Review,
    *,
    deslop_enabled: bool = True,
    deslop_strict: bool = False,
) -> Review:
    extras = length_issues(project, chapter)
    flavor = flavor_issues(chapter) if deslop_enabled else []
    if not extras and not flavor:
        return review
    action = review.action
    force_flavor = deslop_strict and any(item.severity in {"major", "blocker"} for item in flavor)
    if extras or force_flavor:
        action = ReviewAction.REVISE
    return review.model_copy(
        update={"issues": [*review.issues, *extras, *flavor], "action": action}
    )
