from __future__ import annotations

from drama_core import Settings
from drama_novel import create_novel_engine
from drama_review import RetryPolicy, create_reviewer
from drama_storyboard import MockStoryboardEngine, StoryboardEngine
from drama_video import create_video_engine
from drama_vision import create_vision_engine

from drama_pipeline.orchestrator import (
    Orchestrator,
    PipelineError,
    ReviewListener,
    TransitionListener,
)


def _storyboard(settings: Settings) -> StoryboardEngine:
    if settings.storyboard_engine == "mock":
        return MockStoryboardEngine()
    raise ValueError(f"unknown STORYBOARD_ENGINE={settings.storyboard_engine!r}")


def build_orchestrator(
    settings: Settings | None = None,
    *,
    on_transition: TransitionListener | None = None,
    on_review: ReviewListener | None = None,
) -> Orchestrator:
    settings = settings or Settings.from_env()
    return Orchestrator(
        novel=create_novel_engine(settings),
        storyboard=_storyboard(settings),
        vision=create_vision_engine(settings),
        video=create_video_engine(settings),
        reviewer=create_reviewer(settings),
        policy=RetryPolicy(max_attempts=settings.review_max_attempts),
        output_dir=settings.output_dir,
        on_transition=on_transition,
        on_review=on_review,
    )


__all__ = ["Orchestrator", "PipelineError", "build_orchestrator"]
