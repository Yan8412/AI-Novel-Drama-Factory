"""Storyboard review request + deterministic pacing / coverage rules."""

from __future__ import annotations

from drama_core import (
    VERTICAL_ASPECT_RATIO,
    Project,
    ReviewIssue,
    ReviewTargetType,
    Storyboard,
)
from drama_deslop import multi_action_markers
from drama_review import ReviewRequest

from drama_storyboard.markdown import to_markdown
from drama_storyboard.pacing import (
    SHOTS_PER_CHAPTER_MAX,
    SHOTS_PER_CHAPTER_MIN,
    words_per_shot,
)

STORYBOARD_RUBRIC: tuple[str, ...] = (
    "pacing",
    "coverage",
    "vertical_framing",
    "continuity",
)


def storyboard_review_request(project: Project, storyboard: Storyboard) -> ReviewRequest:
    chapter = next((c for c in project.chapters if c.id == storyboard.chapter_id), None)
    return ReviewRequest(
        target_type=ReviewTargetType.STORYBOARD,
        target_id=storyboard.id,
        attempt=storyboard.revision + 1,
        content=to_markdown(project, storyboard),
        context={
            "rubric": STORYBOARD_RUBRIC,
            "shot_count": len(storyboard.shots),
            "duration_s": storyboard.duration_s,
            "chapter_words": chapter.word_count if chapter else 0,
            "aspect_ratio": project.aspect_ratio,
        },
    )


def storyboard_rule_issues(project: Project, storyboard: Storyboard) -> list[ReviewIssue]:
    issues: list[ReviewIssue] = []
    n = len(storyboard.shots)
    if n < SHOTS_PER_CHAPTER_MIN:
        issues.append(
            ReviewIssue(
                severity="blocker",
                message=f"shot_count={n} below short-drama minimum {SHOTS_PER_CHAPTER_MIN}",
                suggestion="split the chapter into at least two vertical beats",
            )
        )
    if n > SHOTS_PER_CHAPTER_MAX:
        issues.append(
            ReviewIssue(
                severity="major",
                message=f"shot_count={n} exceeds short-drama cap {SHOTS_PER_CHAPTER_MAX}",
                suggestion="merge beats; this is not a feature film",
            )
        )
    for shot in storyboard.shots:
        if shot.aspect_ratio != VERTICAL_ASPECT_RATIO:
            issues.append(
                ReviewIssue(
                    severity="blocker",
                    message=f"shot {shot.index} aspect_ratio={shot.aspect_ratio} (need 9:16)",
                    suggestion="force vertical 9:16 framing",
                )
            )
        if not shot.action or not shot.image_prompt:
            issues.append(
                ReviewIssue(
                    severity="major",
                    message=f"shot {shot.index} missing action or image_prompt",
                    suggestion="fill action and a vertical still prompt",
                )
            )
        if not shot.character_ids and not shot.scene_id:
            issues.append(
                ReviewIssue(
                    severity="major",
                    message=f"shot {shot.index} has no character or scene reference",
                    suggestion="attach continuity refs from the bible",
                )
            )
        if not (shot.primary_action or shot.action):
            issues.append(
                ReviewIssue(
                    severity="minor",
                    message=f"shot {shot.index} missing primary_action",
                    suggestion="name one visible beat from start to end",
                )
            )
        extra_moves = multi_action_markers(shot.action)
        if extra_moves:
            issues.append(
                ReviewIssue(
                    severity="minor",
                    message=(
                        f"shot {shot.index} action looks like multiple beats "
                        f"({', '.join(extra_moves)})"
                    ),
                    suggestion="split into one primary action per shot",
                )
            )
        if not (shot.character_lock or shot.wardrobe_lock or shot.scene_lock):
            issues.append(
                ReviewIssue(
                    severity="minor",
                    message=f"shot {shot.index} missing continuity lock fields",
                    suggestion="fill character/wardrobe/scene locks before I2V",
                )
            )
        prompt = shot.image_prompt.lower()
        if "9:16" not in prompt and "vertical" not in prompt:
            issues.append(
                ReviewIssue(
                    severity="minor",
                    message=f"shot {shot.index} image_prompt does not mention 9:16/vertical",
                    suggestion="prefix the prompt with vertical 9:16",
                )
            )
    chapter = next((c for c in project.chapters if c.id == storyboard.chapter_id), None)
    if chapter is not None and n:
        density = words_per_shot(chapter.word_count, n)
        # Informational only — mock's 3-shot packing is denser than structured.
        if density > 2000:
            issues.append(
                ReviewIssue(
                    severity="minor",
                    message=f"words_per_shot={density:.0f} is novel-dense, not short-drama",
                    suggestion="add more 5–15s beats",
                )
            )
    return issues
