"""Image generation: character 9-view sheets, scenes, props and per-shot keyframes."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from drama_core import Asset, AssetKind, Character, Project, Prop, Scene, Settings, Shot

NINE_VIEWS: tuple[str, ...] = (
    "front",
    "front_left_45",
    "left",
    "back_left_45",
    "back",
    "back_right_45",
    "right",
    "front_right_45",
    "face_closeup",
)


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


class MockVisionEngine:
    """Returns ``mock://`` placeholder URIs; never touches disk or a GPU."""

    name = "mock-vision"

    def _asset(
        self,
        project: Project,
        kind: AssetKind,
        owner_id: str,
        revision: int,
        prompt: str,
        **kw: object,
    ) -> Asset:
        uri = f"mock://vision/{project.id}/{kind.value}/{owner_id}_r{revision}.png"
        return Asset.model_validate(
            {
                "kind": kind,
                "owner_id": owner_id,
                "uri": uri,
                "width": project.width,
                "height": project.height,
                "prompt": prompt,
                "engine": self.name,
                "revision": revision,
                **kw,
            }
        )

    def character_nine_view(
        self, project: Project, character: Character, *, revision: int = 0, feedback: str = ""
    ) -> Asset:
        prompt = (
            f"character turnaround 3x3 grid, {character.name}, {character.appearance.description}"
        )
        return self._asset(
            project,
            AssetKind.CHARACTER_NINE_VIEW,
            character.id,
            revision,
            prompt,
            views=list(NINE_VIEWS),
            width=2048,
            height=2048,
        )

    def scene_image(
        self, project: Project, scene: Scene, *, revision: int = 0, feedback: str = ""
    ) -> Asset:
        return self._asset(project, AssetKind.SCENE, scene.id, revision, scene.description)

    def prop_image(
        self, project: Project, prop: Prop, *, revision: int = 0, feedback: str = ""
    ) -> Asset:
        return self._asset(
            project, AssetKind.PROP, prop.id, revision, prop.description, width=1024, height=1024
        )

    def shot_keyframe(
        self,
        project: Project,
        shot: Shot,
        references: list[Asset],
        *,
        revision: int = 0,
        feedback: str = "",
    ) -> Asset:
        return self._asset(project, AssetKind.SHOT_KEYFRAME, shot.id, revision, shot.image_prompt)


class ComfyUIVisionEngine:
    """Adapter skeleton for a ComfyUI server (PuLID / InstantID workflows).

    ComfyUI is GPL-3.0: talk to it only over its HTTP/WebSocket API with workflow
    JSON from ``workflows/``; never import or vendor its Python code here.
    """

    name = "comfyui"

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url

    def _todo(self) -> Asset:
        raise NotImplementedError("ComfyUI vision adapter lands in Phase 2")

    def character_nine_view(
        self, project: Project, character: Character, *, revision: int = 0, feedback: str = ""
    ) -> Asset:
        return self._todo()

    def scene_image(
        self, project: Project, scene: Scene, *, revision: int = 0, feedback: str = ""
    ) -> Asset:
        return self._todo()

    def prop_image(
        self, project: Project, prop: Prop, *, revision: int = 0, feedback: str = ""
    ) -> Asset:
        return self._todo()

    def shot_keyframe(
        self,
        project: Project,
        shot: Shot,
        references: list[Asset],
        *,
        revision: int = 0,
        feedback: str = "",
    ) -> Asset:
        return self._todo()


def create_vision_engine(settings: Settings) -> VisionEngine:
    if settings.vision_engine == "mock":
        return MockVisionEngine()
    if settings.vision_engine == "comfyui":
        return ComfyUIVisionEngine(settings.comfyui_url)
    raise ValueError(f"unknown VISION_ENGINE={settings.vision_engine!r}")


__all__ = [
    "NINE_VIEWS",
    "ComfyUIVisionEngine",
    "MockVisionEngine",
    "VisionEngine",
    "create_vision_engine",
]
