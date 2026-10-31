"""Image-to-video protocol: one clip per storyboard shot."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from drama_core import Asset, Clip, Project, Shot


@runtime_checkable
class VideoEngine(Protocol):
    name: str

    def image_to_video(
        self,
        project: Project,
        shot: Shot,
        keyframe: Asset,
        *,
        revision: int = 0,
        feedback: str = "",
        previous_clip: Clip | None = None,
        identity_refs: Sequence[Asset] = (),
    ) -> Clip: ...
