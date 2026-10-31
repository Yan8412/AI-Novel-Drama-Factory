"""Optional live Images call. Skipped in CI unless RUN_LIVE_VISION=1."""

from __future__ import annotations

import os

import pytest
from drama_core import Appearance, Character, CharacterIdentity, Project, Settings
from drama_vision import CloudVisionEngine


@pytest.mark.integration
@pytest.mark.skipif(os.environ.get("RUN_LIVE_VISION") != "1", reason="set RUN_LIVE_VISION=1")
def test_live_openai_compatible_image_create() -> None:
    engine = CloudVisionEngine(Settings.from_env())
    project = Project(title="live", genre="都市", premise="p", total_words=3000)
    character = Character(
        name="林晚",
        identity=CharacterIdentity(role="女主"),
        appearance=Appearance(description="清冷", hair="黑长直"),
    )
    asset = engine.character_nine_view(project, character)
    assert asset.uri
    assert asset.engine == "cloud-vision"
