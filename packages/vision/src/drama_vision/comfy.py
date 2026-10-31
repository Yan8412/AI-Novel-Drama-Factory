"""ComfyUI HTTP stub. Talks to ``/prompt`` only — never imports ComfyUI (GPL-3.0)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
from drama_core import Asset, AssetKind, Character, Project, Prop, Scene, Shot

from drama_vision.errors import VisionError
from drama_vision.prompts import (
    NINE_VIEWS,
    PROP_VIEWS,
    SCENE_VIEWS,
    character_nine_view_prompt,
    prop_prompt,
    scene_multiview_prompt,
    shot_keyframe_prompt,
)

# Documented placeholder graph. Replace files in ``workflows/`` with real API JSON.
_STUB_GRAPH: dict[str, Any] = {
    "1": {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": ""},
        "_meta": {"title": "drama-factory prompt stub"},
    }
}

_WORKFLOW_BY_KIND: dict[AssetKind, str] = {
    AssetKind.CHARACTER_NINE_VIEW: "character_nine_view.json",
    AssetKind.SCENE: "scene_reference.json",
    AssetKind.PROP: "prop_reference.json",
    AssetKind.SHOT_KEYFRAME: "shot_keyframe.json",
}


class ComfyUIVisionEngine:
    """POST ``{base_url}/prompt``. Returns ``comfy://<prompt_id>`` placeholders.

    Does not download images or vendor ComfyUI Python. Live servers are opt-in
    via ``VISION_ENGINE=comfy`` / ``comfyui``; CI stays on mock.
    """

    name = "comfyui"

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8188",
        *,
        http: httpx.Client | None = None,
        workflows_dir: Path | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.workflows_dir = workflows_dir
        self._http = http or httpx.Client(timeout=30.0)
        self._owns_http = http is None

    def character_nine_view(
        self, project: Project, character: Character, *, revision: int = 0, feedback: str = ""
    ) -> Asset:
        prompt = character_nine_view_prompt(character, feedback=feedback)
        uri = self._submit(AssetKind.CHARACTER_NINE_VIEW, prompt)
        return _comfy_asset(
            project,
            AssetKind.CHARACTER_NINE_VIEW,
            character.id,
            revision,
            prompt,
            uri,
            views=list(NINE_VIEWS),
            width=2048,
            height=2048,
        )

    def scene_image(
        self, project: Project, scene: Scene, *, revision: int = 0, feedback: str = ""
    ) -> Asset:
        prompt = scene_multiview_prompt(scene, feedback=feedback)
        uri = self._submit(AssetKind.SCENE, prompt)
        return _comfy_asset(
            project,
            AssetKind.SCENE,
            scene.id,
            revision,
            prompt,
            uri,
            views=list(SCENE_VIEWS),
        )

    def prop_image(
        self, project: Project, prop: Prop, *, revision: int = 0, feedback: str = ""
    ) -> Asset:
        owner = next((c.name for c in project.characters if c.id == prop.owner_character_id), None)
        prompt = prop_prompt(prop, owner, feedback=feedback)
        uri = self._submit(AssetKind.PROP, prompt)
        return _comfy_asset(
            project,
            AssetKind.PROP,
            prop.id,
            revision,
            prompt,
            uri,
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
        prompt = shot_keyframe_prompt(
            project,
            shot,
            character_names=names,
            scene_name=scene,
            feedback=feedback,
            references=references,
            characters=project.characters,
        )
        uri = self._submit(AssetKind.SHOT_KEYFRAME, prompt)
        return _comfy_asset(project, AssetKind.SHOT_KEYFRAME, shot.id, revision, prompt, uri)

    def _graph(self, kind: AssetKind, prompt: str) -> dict[str, Any]:
        name = _WORKFLOW_BY_KIND[kind]
        if self.workflows_dir is not None:
            path = self.workflows_dir / name
            if path.is_file():
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict) and loaded:
                    return loaded
        graph = dict(_STUB_GRAPH)
        node = dict(graph["1"])
        inputs = dict(node.get("inputs") or {})
        inputs["text"] = prompt
        node["inputs"] = inputs
        graph["1"] = node
        return graph

    def _submit(self, kind: AssetKind, prompt: str) -> str:
        payload = {
            "prompt": self._graph(kind, prompt),
            "extra_data": {"workflow": _WORKFLOW_BY_KIND[kind], "stub": True},
        }
        try:
            resp = self._http.post(f"{self.base_url}/prompt", json=payload)
        except httpx.HTTPError as exc:
            raise VisionError(f"ComfyUI request failed: {exc}") from exc
        if resp.status_code >= 400:
            raise VisionError(f"ComfyUI HTTP {resp.status_code}: {resp.text[:500]}")
        try:
            data = resp.json()
        except ValueError as exc:
            raise VisionError("ComfyUI response is not JSON") from exc
        prompt_id = data.get("prompt_id") if isinstance(data, dict) else None
        if not isinstance(prompt_id, str) or not prompt_id:
            raise VisionError("ComfyUI response missing prompt_id")
        return f"comfy://{prompt_id}"

    def close(self) -> None:
        if self._owns_http:
            self._http.close()


def _comfy_asset(
    project: Project,
    kind: AssetKind,
    owner_id: str,
    revision: int,
    prompt: str,
    uri: str,
    **kw: object,
) -> Asset:
    return Asset.model_validate(
        {
            "kind": kind,
            "owner_id": owner_id,
            "uri": uri,
            "width": project.width,
            "height": project.height,
            "prompt": prompt,
            "engine": "comfyui",
            "revision": revision,
            **kw,
        }
    )
