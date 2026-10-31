"""Pick a ``NovelEngine`` from ``NOVEL_ENGINE`` without touching the FSM."""

from __future__ import annotations

from drama_core import Settings
from drama_llm import ChatClient, LlmConfig

from drama_novel.cloud import CloudNovelEngine
from drama_novel.interfaces import NovelEngine
from drama_novel.mock import MockNovelEngine

CLOUD_ENGINE_NAMES = frozenset({"cloud", "openai", "deepseek", "qwen"})


def create_novel_engine(
    settings: Settings | None = None,
    *,
    client: ChatClient | None = None,
) -> NovelEngine:
    settings = settings or Settings.from_env()
    name = settings.novel_engine.strip().lower()
    if name == "mock":
        return MockNovelEngine()
    if name in CLOUD_ENGINE_NAMES:
        config = LlmConfig(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            model=settings.novel_model,
        )
        return CloudNovelEngine(client, config=config)
    raise ValueError(f"unknown NOVEL_ENGINE={settings.novel_engine!r} (expected mock|cloud)")
