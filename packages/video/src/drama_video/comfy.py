"""ComfyUI HTTP stub for I2V. Talks to ``/prompt`` only — never imports ComfyUI."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import httpx
from drama_core import Asset, Clip, Project, Shot

from drama_video.errors import VideoError
from drama_video.prompts import motion_prompt

# Documented placeholder graph. Replace ``workflows/wan21_i2v.json`` with a real API JSON.
_STUB_GRAPH: dict[str, Any] = {
    "1": {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": ""},
        "_meta": {"title": "drama-factory i2v prompt stub"},
    }
}

DEFAULT_WORKFLOW = "wan21_i2v.json"


class ComfyUIVideoEngine:
    """POST ``{base_url}/prompt``. Returns ``comfy://<prompt_id>`` placeholders.

    Does not download clips or vendor ComfyUI Python. Live servers are opt-in
    via ``VIDEO_ENGINE=comfy`` / ``comfyui`` / ``wan``; CI stays on mock.
    """

    name = "comfyui"

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8188",
        *,
        http: httpx.Client | None = None,
        workflows_dir: Path | None = None,
        workflow_name: str = DEFAULT_WORKFLOW,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.workflows_dir = workflows_dir
        self.workflow_name = workflow_name
        self._http = http or httpx.Client(timeout=30.0)
        self._owns_http = http is None

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
        uri = self._submit(prompt, keyframe=keyframe, previous_clip=previous_clip)
        return Clip(
            shot_id=shot.id,
            source_asset_id=keyframe.id,
            uri=uri,
            duration_s=shot.duration_s,
            width=project.width,
            height=project.height,
            fps=24,
            engine=self.name,
            revision=revision,
            prompt=prompt,
            previous_clip_id=previous_clip.id if previous_clip is not None else None,
        )

    def _graph(self, prompt: str) -> dict[str, Any]:
        if self.workflows_dir is not None:
            path = self.workflows_dir / self.workflow_name
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

    def _submit(self, prompt: str, *, keyframe: Asset, previous_clip: Clip | None) -> str:
        payload = {
            "prompt": self._graph(prompt),
            "extra_data": {
                "workflow": self.workflow_name,
                "stub": True,
                "keyframe_uri": keyframe.uri,
                "previous_clip_uri": previous_clip.uri if previous_clip is not None else "",
            },
        }
        try:
            resp = self._http.post(f"{self.base_url}/prompt", json=payload)
        except httpx.HTTPError as exc:
            raise VideoError(f"ComfyUI request failed: {exc}") from exc
        if resp.status_code >= 400:
            raise VideoError(f"ComfyUI HTTP {resp.status_code}: {resp.text[:500]}")
        try:
            data = resp.json()
        except ValueError as exc:
            raise VideoError("ComfyUI response is not JSON") from exc
        prompt_id = data.get("prompt_id") if isinstance(data, dict) else None
        if not isinstance(prompt_id, str) or not prompt_id:
            raise VideoError("ComfyUI response missing prompt_id")
        return f"comfy://{prompt_id}"

    def close(self) -> None:
        if self._owns_http:
            self._http.close()


class WanVideoEngine(ComfyUIVideoEngine):
    """Wan2.1 I2V through the same ComfyUI HTTP stub (weights stay in WEIGHTS_DIR)."""

    name = "wan"

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8188",
        *,
        http: httpx.Client | None = None,
        workflows_dir: Path | None = None,
    ) -> None:
        super().__init__(
            base_url,
            http=http,
            workflows_dir=workflows_dir,
            workflow_name=DEFAULT_WORKFLOW,
        )
