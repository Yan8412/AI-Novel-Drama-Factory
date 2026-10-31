"""Optional live I2V call. Skipped in CI unless RUN_LIVE_VIDEO=1."""

from __future__ import annotations

import os

import pytest
from drama_core import Asset, AssetKind, Project, Settings, Shot
from drama_video import CloudVideoEngine


@pytest.mark.integration
@pytest.mark.skipif(os.environ.get("RUN_LIVE_VIDEO") != "1", reason="set RUN_LIVE_VIDEO=1")
def test_live_openai_compatible_video_create() -> None:
    engine = CloudVideoEngine(Settings.from_env())
    project = Project(title="live", genre="test", premise="p", total_words=3000)
    shot = Shot(index=1, chapter_id="c", duration_s=5, action="站立", motion_prompt="idle")
    keyframe = Asset(
        kind=AssetKind.SHOT_KEYFRAME,
        owner_id=shot.id,
        uri="https://example.com/keyframe.png",
        prompt="vertical 9:16 still",
    )
    clip = engine.image_to_video(project, shot, keyframe)
    assert clip.uri
    assert clip.width == project.width
    assert clip.duration_s == 5
