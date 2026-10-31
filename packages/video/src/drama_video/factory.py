"""Pick a ``VideoEngine`` from ``VIDEO_ENGINE`` without touching the FSM."""

from __future__ import annotations

from drama_core import Settings

from drama_video.cloud import CloudVideoEngine
from drama_video.comfy import ComfyUIVideoEngine, WanVideoEngine
from drama_video.interfaces import VideoEngine
from drama_video.mock import MockVideoEngine

CLOUD_ENGINE_NAMES = frozenset({"cloud", "openai", "kling", "runway", "hailuo"})
COMFY_ENGINE_NAMES = frozenset({"comfy", "comfyui"})
WAN_ENGINE_NAMES = frozenset({"wan", "wan2.1", "wan21"})


def create_video_engine(settings: Settings | None = None) -> VideoEngine:
    settings = settings or Settings.from_env()
    raw = settings.video_engine.strip().lower()
    provider = ""
    if raw.startswith("cloud:"):
        provider = raw.removeprefix("cloud:").strip().lower()
        raw = "cloud"
    if raw == "mock":
        return MockVideoEngine()
    if raw in CLOUD_ENGINE_NAMES:
        return CloudVideoEngine(settings, provider=provider or raw)
    if raw in WAN_ENGINE_NAMES:
        return WanVideoEngine(settings.comfyui_url)
    if raw in COMFY_ENGINE_NAMES:
        return ComfyUIVideoEngine(settings.comfyui_url)
    raise ValueError(f"unknown VIDEO_ENGINE={settings.video_engine!r} (expected mock|cloud|comfy)")
