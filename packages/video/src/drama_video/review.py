"""Rule checks and review-request builder for per-shot clips."""

from __future__ import annotations

from drama_core import (
    SHOT_MAX_SECONDS,
    SHOT_MIN_SECONDS,
    VERTICAL_ASPECT_RATIO,
    Clip,
    Project,
    ReviewIssue,
    ReviewTargetType,
)
from drama_deslop import prompt_constraint_issues
from drama_review import ReviewRequest

from drama_video.stub import is_mock_clip_uri

VIDEO_RUBRIC: tuple[str, ...] = (
    "motion_quality",
    "identity_consistency",
    "temporal_coherence",
)

DURATION_SLACK_S = 1.0


def clip_review_request(project: Project, clip: Clip) -> ReviewRequest:
    shot = next((s for s in project.shots if s.id == clip.shot_id), None)
    return ReviewRequest(
        target_type=ReviewTargetType.CLIP,
        target_id=clip.id,
        attempt=clip.revision + 1,
        content=clip.uri,
        context={
            "rubric": VIDEO_RUBRIC,
            "duration_s": clip.duration_s,
            "shot_duration_s": shot.duration_s if shot else None,
            "width": clip.width,
            "height": clip.height,
            "aspect_ratio": project.aspect_ratio,
            "source_asset_id": clip.source_asset_id,
            "previous_clip_id": clip.previous_clip_id,
            "prompt": clip.prompt,
            "engine": clip.engine,
        },
    )


def clip_rule_issues(project: Project, clip: Clip) -> list[ReviewIssue]:
    issues: list[ReviewIssue] = []
    if clip.width != project.width or clip.height != project.height:
        issues.append(
            ReviewIssue(
                severity="blocker",
                message=(
                    f"clip {clip.id} size {clip.width}x{clip.height} "
                    f"!= project {project.width}x{project.height}"
                ),
                suggestion=f"render vertical {VERTICAL_ASPECT_RATIO} at project resolution",
            )
        )
    if project.height <= 0 or clip.width * project.height != clip.height * project.width:
        issues.append(
            ReviewIssue(
                severity="blocker",
                message=f"clip {clip.id} is not {VERTICAL_ASPECT_RATIO}",
                suggestion="force 9:16 framing",
            )
        )
    if not (SHOT_MIN_SECONDS <= clip.duration_s <= SHOT_MAX_SECONDS):
        issues.append(
            ReviewIssue(
                severity="major",
                message=(
                    f"clip {clip.id} duration_s={clip.duration_s:g} "
                    f"outside {SHOT_MIN_SECONDS:g}–{SHOT_MAX_SECONDS:g}s"
                ),
                suggestion="keep each shot at 5–15 seconds",
            )
        )
    shot = next((s for s in project.shots if s.id == clip.shot_id), None)
    if shot is not None and abs(clip.duration_s - shot.duration_s) > DURATION_SLACK_S:
        issues.append(
            ReviewIssue(
                severity="major",
                message=(
                    f"clip {clip.id} duration_s={clip.duration_s:g} != shot {shot.duration_s:g}"
                ),
                suggestion="match the storyboard beat length",
            )
        )
    asset_ids = {a.id for a in project.assets}
    if not clip.source_asset_id or clip.source_asset_id not in asset_ids:
        issues.append(
            ReviewIssue(
                severity="major",
                message=f"clip {clip.id} missing keyframe ref {clip.source_asset_id!r}",
                suggestion="I2V from the shot keyframe asset",
            )
        )
    if not clip.uri.strip():
        issues.append(
            ReviewIssue(
                severity="blocker",
                message=f"clip {clip.id} has an empty uri",
                suggestion="write a mock://, comfy://, or https URI",
            )
        )
    if not (clip.prompt or "").strip() and not is_mock_clip_uri(clip.uri):
        issues.append(
            ReviewIssue(
                severity="major",
                message=f"clip {clip.id} has an empty motion prompt",
                suggestion="include 9:16 motion + identity lock text",
            )
        )
    prompt = (clip.prompt or "").lower()
    if prompt and "9:16" not in prompt and "vertical" not in prompt:
        issues.append(
            ReviewIssue(
                severity="minor",
                message=f"clip {clip.id} prompt does not mention 9:16/vertical",
                suggestion="prefix the I2V prompt with vertical 9:16",
            )
        )
    has_refs = bool(clip.source_asset_id)
    for gap in prompt_constraint_issues(clip.prompt or "", has_identity_refs=has_refs):
        issues.append(
            ReviewIssue(
                severity="minor",
                message=f"clip {clip.id} {gap}",
                suggestion="use start→single motion→end and the shared negative block",
            )
        )
    if shot is not None:
        ordered = list(project.shots)
        idx = next((i for i, s in enumerate(ordered) if s.id == shot.id), -1)
        if idx > 0 and not clip.previous_clip_id:
            issues.append(
                ReviewIssue(
                    severity="minor",
                    message=f"clip {clip.id} has no previous_clip_id for continuity",
                    suggestion="pass the prior shot clip into image_to_video",
                )
            )
    return issues
