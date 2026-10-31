"""Pick a ``StoryboardEngine`` from ``STORYBOARD_ENGINE`` without touching the FSM."""

from __future__ import annotations

from drama_core import Settings
from drama_llm import ChatClient, LlmConfig

from drama_storyboard.cloud import CloudStoryboardEngine
from drama_storyboard.interfaces import StoryboardEngine
from drama_storyboard.mock import MockStoryboardEngine
from drama_storyboard.structured import StructuredStoryboardEngine

CLOUD_ENGINE_NAMES = frozenset({"cloud", "llm", "openai", "deepseek", "qwen"})
STRUCTURED_ENGINE_NAMES = frozenset({"structured", "rule", "rules"})


def create_storyboard_engine(
    settings: Settings | None = None,
    *,
    client: ChatClient | None = None,
) -> StoryboardEngine:
    settings = settings or Settings.from_env()
    name = settings.storyboard_engine.strip().lower()
    if name == "mock":
        return MockStoryboardEngine()
    if name in STRUCTURED_ENGINE_NAMES:
        return StructuredStoryboardEngine()
    if name in CLOUD_ENGINE_NAMES:
        config = LlmConfig(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            model=settings.storyboard_model,
        )
        return CloudStoryboardEngine(client, config=config)
    raise ValueError(
        f"unknown STORYBOARD_ENGINE={settings.storyboard_engine!r} (expected mock|structured|cloud)"
    )
