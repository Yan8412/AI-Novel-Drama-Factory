"""Returns ``mock://`` placeholder URIs with structured Phase 2 prompts."""

from __future__ import annotations

from drama_core import Asset, AssetKind, Character, Project, Prop, Scene, Shot

from drama_vision.prompts import (
    NINE_VIEWS,
    PROP_VIEWS,
    SCENE_VIEWS,
    character_nine_view_prompt,
    prop_prompt,
    scene_multiview_prompt,
    shot_keyframe_prompt,
)


class MockVisionEngine:
    """Never touches disk or a GPU. Prompts still carry 9-view / identity anchors."""

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
        prompt = character_nine_view_prompt(character, feedback=feedback)
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
        return self._asset(
            project,
            AssetKind.SCENE,
            scene.id,
            revision,
            scene_multiview_prompt(scene, feedback=feedback),
            views=list(SCENE_VIEWS),
        )

    def prop_image(
        self, project: Project, prop: Prop, *, revision: int = 0, feedback: str = ""
    ) -> Asset:
        owner = next((c.name for c in project.characters if c.id == prop.owner_character_id), None)
        return self._asset(
            project,
            AssetKind.PROP,
            prop.id,
            revision,
            prop_prompt(prop, owner, feedback=feedback),
            views=list(PROP_VIEWS),
            width=1024,
            height=1024,
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
        names = [c.name for c in project.characters if c.id in shot.character_ids]
        scene = next((s.name for s in project.scenes if s.id == shot.scene_id), "")
        del references
        return self._asset(
            project,
            AssetKind.SHOT_KEYFRAME,
            shot.id,
            revision,
            shot_keyframe_prompt(
                project, shot, character_names=names, scene_name=scene, feedback=feedback
            ),
        )
