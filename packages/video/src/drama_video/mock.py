"""Offline I2V: ``mock://`` URIs plus structured continuity prompts."""

from __future__ import annotations

from collections.abc import Sequence

from drama_core import Asset, Clip, Project, Shot

from drama_video.prompts import motion_prompt


class MockVideoEngine:
    """Never touches a GPU. Prompts still carry identity + previous-shot refs."""

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
        previous_clip: Clip | None = None,
        identity_refs: Sequence[Asset] = (),
    ) -> Clip:
        prompt = motion_prompt(
            project,
            shot,
            keyframe,
            characters=project.characters,
            identity_refs=identity_refs,
            previous_clip=previous_clip,
            feedback=feedback,
        )
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
            prompt=prompt,
            previous_clip_id=previous_clip.id if previous_clip is not None else None,
        )
