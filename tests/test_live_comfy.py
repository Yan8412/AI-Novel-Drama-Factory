"""Optional live ComfyUI /prompt stub. Skipped unless RUN_LIVE_COMFY=1."""

from __future__ import annotations

import os

import pytest
from drama_core import (
    Appearance,
    Asset,
    AssetKind,
    Character,
    CharacterIdentity,
    Project,
    Settings,
    Shot,
)
from drama_video import ComfyUIVideoEngine
from drama_vision import ComfyUIVisionEngine


@pytest.mark.integration
@pytest.mark.skipif(os.environ.get("RUN_LIVE_COMFY") != "1", reason="set RUN_LIVE_COMFY=1")
def test_live_comfy_vision_prompt() -> None:
    settings = Settings.from_env()
    engine = ComfyUIVisionEngine(settings.comfyui_url)
    project = Project(title="live", genre="都市", premise="p", total_words=3000)
    character = Character(
        name="林晚",
        identity=CharacterIdentity(role="女主"),
        appearance=Appearance(description="清冷"),
    )
    asset = engine.character_nine_view(project, character)
    assert asset.uri.startswith("comfy://")


@pytest.mark.integration
@pytest.mark.skipif(os.environ.get("RUN_LIVE_COMFY") != "1", reason="set RUN_LIVE_COMFY=1")
def test_live_comfy_video_prompt() -> None:
    settings = Settings.from_env()
    engine = ComfyUIVideoEngine(settings.comfyui_url)
    project = Project(title="live", genre="都市", premise="p", total_words=3000)
    shot = Shot(index=1, chapter_id="c", duration_s=5, action="站立", motion_prompt="idle")
    keyframe = Asset(
        kind=AssetKind.SHOT_KEYFRAME,
        owner_id=shot.id,
        uri="mock://keyframe",
        prompt="vertical 9:16 still",
    )
    clip = engine.image_to_video(project, shot, keyframe)
    assert clip.uri.startswith("comfy://")
