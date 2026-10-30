"""Novel-review helpers: build reviewer requests and rule-based checks for chapters."""

from __future__ import annotations

from drama_core import Chapter, Project, ReviewIssue, ReviewTargetType
from drama_review import ReviewRequest

from drama_novel.memory import NovelMemory

CHAPTER_RUBRIC: tuple[str, ...] = ("plot", "character_consistency", "pacing", "hook")


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
