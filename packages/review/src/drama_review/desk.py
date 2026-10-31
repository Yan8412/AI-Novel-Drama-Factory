"""Review-desk listing: pending / failed targets with history and rerun stage."""

from __future__ import annotations

from typing import Any

from drama_core import (
    Asset,
    Chapter,
    Clip,
    PipelineStage,
    Project,
    Review,
    ReviewAction,
    ReviewTargetType,
    Storyboard,
)

from drama_review.override import OverrideBook

RERUN_STAGE: dict[str, str] = {
    ReviewTargetType.CHAPTER.value: PipelineStage.CHAPTERS.value,
    ReviewTargetType.STORYBOARD.value: PipelineStage.STORYBOARD.value,
    ReviewTargetType.ASSET.value: PipelineStage.ASSETS.value,
    ReviewTargetType.CLIP.value: PipelineStage.VIDEO.value,
}

_PENDING = frozenset({"pending", "revise"})
_FAILED = frozenset({"rejected", "failed"})


def _label_chapter(chapter: Chapter) -> str:
    return f"第{chapter.index}章 {chapter.title}".strip()


def _label_storyboard(project: Project, board: Storyboard) -> str:
    chapter = next((item for item in project.chapters if item.id == board.chapter_id), None)
    if chapter is None:
        return f"分镜 {board.id}"
    return f"分镜 · 第{chapter.index}章 {chapter.title}".strip()


def _label_asset(project: Project, asset: Asset) -> str:
    owner = asset.owner_id
    for character in project.characters:
        if character.id == asset.owner_id:
            owner = character.name
            break
    else:
        for scene in project.scenes:
            if scene.id == asset.owner_id:
                owner = scene.name
                break
        else:
            for prop in project.props:
                if prop.id == asset.owner_id:
                    owner = prop.name
                    break
            else:
                shot = next((item for item in project.shots if item.id == asset.owner_id), None)
                if shot is not None:
                    owner = f"镜 {shot.index}"
    return f"{asset.kind.value} · {owner}"


def _label_clip(project: Project, clip: Clip) -> str:
    shot = next((item for item in project.shots if item.id == clip.shot_id), None)
    if shot is None:
        return f"片段 {clip.id}"
    return f"镜头 {shot.index} · {clip.duration_s:g}s"


def _status(latest: Review | None, queued: bool) -> str:
    if latest is None:
        return "pending" if queued else "unreviewed"
    if latest.action is ReviewAction.REJECT:
        return "rejected"
    if latest.action is ReviewAction.REVISE or queued:
        return "pending"
    if latest.action is ReviewAction.PASS:
        return "passed"
    return latest.action.value


def _target(
    *,
    project: Project,
    target_type: ReviewTargetType,
    target_id: str,
    label: str,
    revision: int,
    book: OverrideBook,
) -> dict[str, Any]:
    history = project.reviews_for(target_id)
    history = sorted(history, key=lambda item: (item.attempt, item.created_at))
    latest = history[-1] if history else None
    queued = target_id in project.revision_queue
    forced = book.lookup(target_type, target_id)
    return {
        "target_type": target_type.value,
        "target_id": target_id,
        "label": label,
        "revision": revision,
        "attempts": latest.attempt if latest is not None else 0,
        "status": _status(latest, queued),
        "queued": queued,
        "override": None if forced is None else forced.value,
        "rerun_stage": RERUN_STAGE[target_type.value],
        "scores": {} if latest is None else latest.scores,
        "issues": []
        if latest is None
        else [issue.model_dump(mode="json") for issue in latest.issues],
        "latest": None if latest is None else latest.model_dump(mode="json"),
        "history": [item.model_dump(mode="json") for item in history],
    }


def list_review_targets(project: Project) -> list[dict[str, Any]]:
    book = OverrideBook.from_project(project)
    rows: list[dict[str, Any]] = []
    for chapter in project.chapters:
        rows.append(
            _target(
                project=project,
                target_type=ReviewTargetType.CHAPTER,
                target_id=chapter.id,
                label=_label_chapter(chapter),
                revision=chapter.revision,
                book=book,
            )
        )
    for board in project.storyboards:
        rows.append(
            _target(
                project=project,
                target_type=ReviewTargetType.STORYBOARD,
                target_id=board.id,
                label=_label_storyboard(project, board),
                revision=board.revision,
                book=book,
            )
        )
    for asset in project.assets:
        rows.append(
            _target(
                project=project,
                target_type=ReviewTargetType.ASSET,
                target_id=asset.id,
                label=_label_asset(project, asset),
                revision=asset.revision,
                book=book,
            )
        )
    for clip in project.clips:
        rows.append(
            _target(
                project=project,
                target_type=ReviewTargetType.CLIP,
                target_id=clip.id,
                label=_label_clip(project, clip),
                revision=clip.revision,
                book=book,
            )
        )
    return rows


def pending_targets(project: Project) -> list[dict[str, Any]]:
    return [row for row in list_review_targets(project) if row["status"] in _PENDING]


def failed_targets(project: Project) -> list[dict[str, Any]]:
    return [row for row in list_review_targets(project) if row["status"] in _FAILED]


def review_desk_payload(project: Project) -> dict[str, Any]:
    targets = list_review_targets(project)
    pending = [row for row in targets if row["status"] in _PENDING]
    failed = [row for row in targets if row["status"] in _FAILED]
    return {
        "project_id": project.id,
        "stage": project.stage.value,
        "failure_reason": project.failure_reason,
        "revision_queue": list(project.revision_queue),
        "pending": len(pending),
        "failed": len(failed),
        "targets": targets,
    }
