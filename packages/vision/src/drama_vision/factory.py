"""Pick a ``VisionEngine`` from ``VISION_ENGINE`` without touching the FSM."""

from __future__ import annotations

from drama_core import Settings

from drama_vision.cloud import CloudVisionEngine
from drama_vision.comfy import ComfyUIVisionEngine
from drama_vision.interfaces import VisionEngine
from drama_vision.mock import MockVisionEngine

CLOUD_ENGINE_NAMES = frozenset({"cloud", "openai"})
COMFY_ENGINE_NAMES = frozenset({"comfy", "comfyui"})


def create_vision_engine(settings: Settings | None = None) -> VisionEngine:
    settings = settings or Settings.from_env()
    name = settings.vision_engine.strip().lower()
    if name == "mock":
        return MockVisionEngine()
    if name in CLOUD_ENGINE_NAMES:
        return CloudVisionEngine(settings)
    if name in COMFY_ENGINE_NAMES:
        return ComfyUIVisionEngine(settings.comfyui_url)
    raise ValueError(
        f"unknown VISION_ENGINE={settings.vision_engine!r} (expected mock|cloud|comfy)"
    )
