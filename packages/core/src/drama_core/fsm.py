"""Pipeline finite-state machine: legal stage transitions, independent of any engine."""

from __future__ import annotations

from collections.abc import Mapping

from drama_core.models import PipelineStage, Project, StageTransition

S = PipelineStage

TERMINAL_STAGES: frozenset[PipelineStage] = frozenset({S.DONE, S.FAILED})

# Review stages may loop back to their producing stage to revise flagged targets.
TRANSITIONS: Mapping[PipelineStage, frozenset[PipelineStage]] = {
    S.CREATED: frozenset({S.CHARACTERS}),
    S.CHARACTERS: frozenset({S.OUTLINE}),
    S.OUTLINE: frozenset({S.CHAPTERS}),
    S.CHAPTERS: frozenset({S.NOVEL_REVIEW}),
    S.NOVEL_REVIEW: frozenset({S.CHAPTERS, S.STORYBOARD}),
    S.STORYBOARD: frozenset({S.STORYBOARD_REVIEW}),
    S.STORYBOARD_REVIEW: frozenset({S.STORYBOARD, S.ASSETS}),
    S.ASSETS: frozenset({S.IMAGE_REVIEW}),
    S.IMAGE_REVIEW: frozenset({S.ASSETS, S.VIDEO}),
    S.VIDEO: frozenset({S.VIDEO_REVIEW}),
    S.VIDEO_REVIEW: frozenset({S.VIDEO, S.EXPORT}),
    S.EXPORT: frozenset({S.DONE}),
    S.DONE: frozenset(),
    S.FAILED: frozenset(),
}

HAPPY_PATH: tuple[PipelineStage, ...] = (
    S.CREATED,
    S.CHARACTERS,
    S.OUTLINE,
    S.CHAPTERS,
    S.NOVEL_REVIEW,
    S.STORYBOARD,
    S.STORYBOARD_REVIEW,
    S.ASSETS,
    S.IMAGE_REVIEW,
    S.VIDEO,
    S.VIDEO_REVIEW,
    S.EXPORT,
    S.DONE,
)


class InvalidTransitionError(RuntimeError):
    pass


def can_transition(src: PipelineStage, dst: PipelineStage) -> bool:
    if dst is S.FAILED:
        return src not in TERMINAL_STAGES
    return dst in TRANSITIONS[src]


def transition(project: Project, dst: PipelineStage, reason: str = "") -> StageTransition:
    """Move ``project`` to ``dst``, recording the hop in ``stage_history``."""
    src = project.stage
    if not can_transition(src, dst):
        raise InvalidTransitionError(f"{src.value} -> {dst.value} is not allowed")
    record = StageTransition(from_stage=src, to_stage=dst, reason=reason)
    project.stage_history.append(record)
    project.stage = dst
    return record
