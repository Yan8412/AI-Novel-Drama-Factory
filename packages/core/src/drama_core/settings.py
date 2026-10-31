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
    output_dir: Path = Path("output")
    review_max_attempts: int = 3
    comfyui_url: str = "http://127.0.0.1:8188"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    novel_model: str = "gpt-4o-mini"
    review_model: str = "gpt-4o-mini"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        env = os.environ if env is None else env
        fields = {
            "novel_engine": "NOVEL_ENGINE",
            "review_engine": "REVIEW_ENGINE",
            "storyboard_engine": "STORYBOARD_ENGINE",
            "vision_engine": "VISION_ENGINE",
            "video_engine": "VIDEO_ENGINE",
            "output_dir": "OUTPUT_DIR",
            "review_max_attempts": "REVIEW_MAX_ATTEMPTS",
            "comfyui_url": "COMFYUI_URL",
            "openai_api_key": "OPENAI_API_KEY",
            "openai_base_url": "OPENAI_BASE_URL",
            "novel_model": "NOVEL_MODEL",
            "review_model": "REVIEW_MODEL",
        }
        return cls.model_validate({f: env[k] for f, k in fields.items() if env.get(k)})
