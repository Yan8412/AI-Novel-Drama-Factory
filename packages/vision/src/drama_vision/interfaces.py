"""Image generation protocol: 9-view sheets, scenes, props, shot keyframes."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from drama_core import Asset, Character, Project, Prop, Scene, Shot


@runtime_checkable
class VisionEngine(Protocol):
    name: str

    def character_nine_view(
        self, project: Project, character: Character, *, revision: int = 0, feedback: str = ""
    ) -> Asset: ...

    def scene_image(
        self, project: Project, scene: Scene, *, revision: int = 0, feedback: str = ""
    ) -> Asset: ...

    def prop_image(
        self, project: Project, prop: Prop, *, revision: int = 0, feedback: str = ""
    ) -> Asset: ...

    def shot_keyframe(
        self,
        project: Project,
        shot: Shot,
        references: list[Asset],
        *,
        revision: int = 0,
        feedback: str = "",
    ) -> Asset: ...
