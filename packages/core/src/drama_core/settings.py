"""Runtime settings read from environment variables (see ``.env.example``)."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    novel_engine: str = "mock"
    review_engine: str = "mock"
    storyboard_engine: str = "mock"
    vision_engine: str = "mock"
    video_engine: str = "mock"
    assemble_engine: str = "mock"
    tts_engine: str = "mock"
    subtitle_format: str = "both"
    output_dir: Path = Path("output")
    review_max_attempts: int = 3
    review_override: str = ""
    review_override_file: str = ""
    comfyui_url: str = "http://127.0.0.1:8188"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    novel_model: str = "gpt-4o-mini"
    review_model: str = "gpt-4o-mini"
    storyboard_model: str = "gpt-4o-mini"
    vision_model: str = "gpt-image-1"
    video_model: str = "sora-2"
    video_api_key: str = ""
    video_base_url: str = ""
    tts_api_key: str = ""
    tts_base_url: str = ""
    tts_model: str = "tts-1"
    tts_voice: str = "alloy"
    redis_url: str = "redis://127.0.0.1:6379/0"
    job_queue: str = "auto"
    # Phase 7 billing. Mock engines stay $0; live engines use these unit prices.
    price_token_per_1k_usd: float = 0.00015
    price_image_usd: float = 0.04
    price_video_per_second_usd: float = 0.10
    price_tts_per_1k_chars_usd: float = 0.015
    fx_cny_per_usd: float = 7.2
    quota_currency: str = "USD"
    quota_soft_usd: float | None = None
    quota_max_usd: float | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        env = os.environ if env is None else env
        fields = {
            "novel_engine": "NOVEL_ENGINE",
            "review_engine": "REVIEW_ENGINE",
            "storyboard_engine": "STORYBOARD_ENGINE",
            "vision_engine": "VISION_ENGINE",
            "video_engine": "VIDEO_ENGINE",
            "assemble_engine": "ASSEMBLE_ENGINE",
            "tts_engine": "TTS_ENGINE",
            "subtitle_format": "SUBTITLE_FORMAT",
            "output_dir": "OUTPUT_DIR",
            "review_max_attempts": "REVIEW_MAX_ATTEMPTS",
            "review_override": "REVIEW_OVERRIDE",
            "review_override_file": "REVIEW_OVERRIDE_FILE",
            "comfyui_url": "COMFYUI_URL",
            "openai_api_key": "OPENAI_API_KEY",
            "openai_base_url": "OPENAI_BASE_URL",
            "novel_model": "NOVEL_MODEL",
            "review_model": "REVIEW_MODEL",
            "storyboard_model": "STORYBOARD_MODEL",
            "vision_model": "VISION_MODEL",
            "video_model": "VIDEO_MODEL",
            "video_api_key": "VIDEO_API_KEY",
            "video_base_url": "VIDEO_BASE_URL",
            "tts_api_key": "TTS_API_KEY",
            "tts_base_url": "TTS_BASE_URL",
            "tts_model": "TTS_MODEL",
            "tts_voice": "TTS_VOICE",
            "redis_url": "REDIS_URL",
            "job_queue": "JOB_QUEUE",
            "price_token_per_1k_usd": "PRICE_TOKEN_PER_1K_USD",
            "price_image_usd": "PRICE_IMAGE_USD",
            "price_video_per_second_usd": "PRICE_VIDEO_PER_SECOND_USD",
            "price_tts_per_1k_chars_usd": "PRICE_TTS_PER_1K_CHARS_USD",
            "fx_cny_per_usd": "FX_CNY_PER_USD",
            "quota_currency": "QUOTA_CURRENCY",
            "quota_soft_usd": "QUOTA_SOFT_USD",
            "quota_max_usd": "QUOTA_MAX_USD",
        }
        values = {f: env[k] for f, k in fields.items() if env.get(k)}
        if not values.get("review_max_attempts") and env.get("REVIEW_MAX_RETRIES"):
            values["review_max_attempts"] = env["REVIEW_MAX_RETRIES"]
        if not values.get("tts_api_key") and env.get("OPENAI_API_KEY"):
            values["tts_api_key"] = env["OPENAI_API_KEY"]
        if not values.get("tts_base_url") and env.get("OPENAI_BASE_URL"):
            values["tts_base_url"] = env["OPENAI_BASE_URL"]
        if not values.get("video_api_key"):
            provider = str(values.get("video_engine") or env.get("VIDEO_ENGINE") or "").lower()
            if provider.startswith("cloud:"):
                provider = provider.removeprefix("cloud:")
            fallback = {
                "kling": "KLING_API_KEY",
                "runway": "RUNWAY_API_KEY",
            }.get(provider)
            if fallback and env.get(fallback):
                values["video_api_key"] = env[fallback]
        return cls.model_validate(values)
