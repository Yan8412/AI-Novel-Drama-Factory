"""Pick a ``Reviewer`` from ``REVIEW_ENGINE`` without touching the FSM."""

from __future__ import annotations

from drama_core import Settings
from drama_llm import ChatClient, LlmConfig

from drama_review.contracts import Reviewer
from drama_review.llm_judge import LlmJudgeReviewer
from drama_review.mock import DeterministicMockReviewer

LLM_JUDGE_NAMES = frozenset({"llm_judge", "llm-judge"})


def create_reviewer(
    settings: Settings | None = None,
    *,
    client: ChatClient | None = None,
) -> Reviewer:
    settings = settings or Settings.from_env()
    name = settings.review_engine.strip().lower()
    if name == "mock":
        return DeterministicMockReviewer()
    if name in LLM_JUDGE_NAMES:
        config = LlmConfig(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            model=settings.review_model,
        )
        return LlmJudgeReviewer(client, config=config)
    raise ValueError(f"unknown REVIEW_ENGINE={settings.review_engine!r} (expected mock|llm_judge)")
