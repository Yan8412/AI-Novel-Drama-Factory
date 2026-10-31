"""OpenAI-compatible Images API client. Offline tests inject a fake ``httpx.Client``."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx
from drama_core import Asset, AssetKind, Character, Project, Prop, Scene, Settings, Shot

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


class CloudVisionEngine:
    """POST ``{base_url}/images/generations``. No secrets; key comes from Settings."""

    name = "cloud-vision"

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        http: httpx.Client | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        cfg = settings or Settings()
        self.api_key = cfg.openai_api_key if api_key is None else api_key
        self.base_url = (cfg.openai_base_url if base_url is None else base_url).rstrip("/")
        self.model = cfg.vision_model if model is None else model
        self._http = http or httpx.Client(timeout=180.0)
        self._owns_http = http is None

    @property
    def url(self) -> str:
        return f"{self.base_url}/images/generations"

    def character_nine_view(
        self, project: Project, character: Character, *, revision: int = 0, feedback: str = ""
    ) -> Asset:
        prompt = character_nine_view_prompt(character, feedback=feedback)
        uri = self._generate(prompt, size="1024x1024")
        return _asset(
            project,
            AssetKind.CHARACTER_NINE_VIEW,
            character.id,
            revision,
            prompt,
            uri,
            self.name,
            views=list(NINE_VIEWS),
            width=2048,
            height=2048,
        )

    def scene_image(
        self, project: Project, scene: Scene, *, revision: int = 0, feedback: str = ""
    ) -> Asset:
        prompt = scene_multiview_prompt(scene, feedback=feedback)
        uri = self._generate(prompt, size=_portrait_size(project))
        return _asset(
            project,
            AssetKind.SCENE,
            scene.id,
            revision,
            prompt,
            uri,
            self.name,
            views=list(SCENE_VIEWS),
        )

    def prop_image(
        self, project: Project, prop: Prop, *, revision: int = 0, feedback: str = ""
    ) -> Asset:
        owner = next((c.name for c in project.characters if c.id == prop.owner_character_id), None)
        prompt = prop_prompt(prop, owner, feedback=feedback)
        uri = self._generate(prompt, size="1024x1024")
        return _asset(
            project,
            AssetKind.PROP,
            prop.id,
            revision,
            prompt,
            uri,
            self.name,
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
            project, shot, character_names=names, scene_name=scene, feedback=feedback
        )
        if references:
            prompt += f" references={len(references)}"
        uri = self._generate(prompt, size=_portrait_size(project))
        return _asset(project, AssetKind.SHOT_KEYFRAME, shot.id, revision, prompt, uri, self.name)

    def _generate(self, prompt: str, *, size: str) -> str:
        if not self.api_key:
            raise VisionError("OPENAI_API_KEY is missing")
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "size": size,
            "n": 1,
        }
        try:
            resp = self._http.post(
                self.url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
        except httpx.HTTPError as exc:
            raise VisionError(f"vision request failed: {exc}") from exc
        if resp.status_code >= 400:
            raise VisionError(f"vision HTTP {resp.status_code}: {resp.text[:500]}")
        try:
            data = resp.json()
        except ValueError as exc:
            raise VisionError("vision response is not JSON") from exc
        uri = _image_uri(data)
        if not uri:
            raise VisionError("vision API returned no image url/b64")
        return uri

    def close(self) -> None:
        if self._owns_http:
            self._http.close()


def _portrait_size(project: Project) -> str:
    # Closest OpenAI Images portrait size to 9:16 (1080×1920).
    if project.aspect_ratio == "9:16":
        return "1024x1792"
    return "1024x1024"


def _image_uri(data: object) -> str:
    if not isinstance(data, Mapping):
        return ""
    items = data.get("data")
    if not isinstance(items, list) or not items:
        return ""
    first = items[0]
    if not isinstance(first, Mapping):
        return ""
    url = first.get("url")
    if isinstance(url, str) and url:
        return url
    b64 = first.get("b64_json")
    if isinstance(b64, str) and b64:
        return f"data:image/png;base64,{b64}"
    return ""


def _asset(
    project: Project,
    kind: AssetKind,
    owner_id: str,
    revision: int,
    prompt: str,
    uri: str,
    engine: str,
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
            "engine": engine,
            "revision": revision,
            **kw,
        }
    )
