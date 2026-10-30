"""Image-to-video (I2V) engines: one clip per storyboard shot."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from drama_core import Asset, Clip, Project, Settings, Shot


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
    ) -> Clip: ...


class MockVideoEngine:
    name = "mock-video"

    def __init__(self, fps: int = 24) -> None:
        self.fps = fps

    def image_to_video(
        self,
        project: Project,
        shot: Shot,
        keyframe: Asset,
        *,
        revision: int = 0,
        feedback: str = "",
    ) -> Clip:
        return Clip(
            shot_id=shot.id,
            source_asset_id=keyframe.id,
            uri=f"mock://video/{project.id}/{shot.id}_r{revision}.mp4",
            duration_s=shot.duration_s,
            width=project.width,
            height=project.height,
            fps=self.fps,
            engine=self.name,
            revision=revision,
        )


class WanVideoEngine:
    """Local Wan2.1 I2V (Apache-2.0), driven through a ComfyUI workflow or a model server.

    Weights are downloaded at runtime into ``WEIGHTS_DIR``; nothing is vendored.
    """

    name = "wan"

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url

    def image_to_video(
        self,
        project: Project,
        shot: Shot,
        keyframe: Asset,
        *,
        revision: int = 0,
        feedback: str = "",
    ) -> Clip:
        raise NotImplementedError("Wan2.1 I2V adapter lands in Phase 3")


class CloudVideoEngine:
    """Placeholder for hosted I2V APIs (Kling / Runway / Hailuo, etc.)."""

    name = "cloud"

    def __init__(self, provider: str) -> None:
        self.provider = provider

    def image_to_video(
        self,
        project: Project,
        shot: Shot,
        keyframe: Asset,
        *,
        revision: int = 0,
        feedback: str = "",
    ) -> Clip:
        raise NotImplementedError(f"cloud I2V provider {self.provider!r} lands in Phase 3")


def create_video_engine(settings: Settings) -> VideoEngine:
    name = settings.video_engine
    if name == "mock":
        return MockVideoEngine()
    if name == "wan":
        return WanVideoEngine(settings.comfyui_url)
    if name.startswith("cloud:"):
        return CloudVideoEngine(name.removeprefix("cloud:"))
    raise ValueError(f"unknown VIDEO_ENGINE={name!r}")


__all__ = [
    "CloudVideoEngine",
    "MockVideoEngine",
    "VideoEngine",
    "WanVideoEngine",
    "create_video_engine",
]
