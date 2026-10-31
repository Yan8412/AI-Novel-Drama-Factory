from __future__ import annotations

from drama_assemble import create_assembler
from drama_core import Settings
from drama_novel import create_novel_engine
from drama_review import OverrideBook, PriceBook, RetryPolicy, create_reviewer
from drama_storyboard import create_storyboard_engine
from drama_tts import create_subtitle_engine, create_tts_engine
from drama_video import create_video_engine
from drama_vision import create_vision_engine

from drama_pipeline.orchestrator import (
    Orchestrator,
    PipelineError,
    ReviewListener,
    TransitionListener,
)


def build_orchestrator(
    settings: Settings | None = None,
    *,
    on_transition: TransitionListener | None = None,
    on_review: ReviewListener | None = None,
    overrides: OverrideBook | None = None,
) -> Orchestrator:
    settings = settings or Settings.from_env()
    book = overrides or OverrideBook.from_settings(settings)
    return Orchestrator(
        novel=create_novel_engine(settings),
        storyboard=create_storyboard_engine(settings),
        vision=create_vision_engine(settings),
        video=create_video_engine(settings),
        reviewer=create_reviewer(settings),
        assembler=create_assembler(settings),
        subtitles=create_subtitle_engine(settings),
        tts=create_tts_engine(settings),
        policy=RetryPolicy(max_attempts=settings.review_max_attempts),
        overrides=book,
        output_dir=settings.output_dir,
        prices=PriceBook.from_settings(settings),
        on_transition=on_transition,
        on_review=on_review,
        deslop_enabled=settings.deslop_enabled,
        deslop_strict=settings.deslop_strict,
    )


__all__ = ["Orchestrator", "PipelineError", "build_orchestrator"]
