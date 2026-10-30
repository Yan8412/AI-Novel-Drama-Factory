from __future__ import annotations

from drama_core import Settings
from drama_novel import MockNovelEngine, NovelEngine
from drama_review import DeterministicMockReviewer, RetryPolicy, Reviewer
from drama_storyboard import MockStoryboardEngine, StoryboardEngine
from drama_video import create_video_engine
from drama_vision import create_vision_engine

from drama_pipeline.orchestrator import (
    Orchestrator,
    PipelineError,
    ReviewListener,
    TransitionListener,
)


def _novel(settings: Settings) -> NovelEngine:
    if settings.novel_engine == "mock":
        return MockNovelEngine()
    raise ValueError(f"unknown NOVEL_ENGINE={settings.novel_engine!r} (Phase 1 adds LLM engines)")


def _reviewer(settings: Settings) -> Reviewer:
    if settings.review_engine == "mock":
        return DeterministicMockReviewer()
    raise ValueError(f"unknown REVIEW_ENGINE={settings.review_engine!r}")


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
        novel=_novel(settings),
        storyboard=_storyboard(settings),
        vision=create_vision_engine(settings),
        video=create_video_engine(settings),
        reviewer=_reviewer(settings),
        policy=RetryPolicy(max_attempts=settings.review_max_attempts),
        output_dir=settings.output_dir,
        on_transition=on_transition,
        on_review=on_review,
    )


__all__ = ["Orchestrator", "PipelineError", "build_orchestrator"]
