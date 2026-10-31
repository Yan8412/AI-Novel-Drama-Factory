"""OpenAI-compatible Images API client. Offline tests inject a fake ``httpx.Client``."""

from __future__ import annotations

import base64
from collections.abc import Mapping, Sequence
from typing import Any

import httpx
from drama_core import (
    Asset,
    AssetKind,
    Character,
    Project,
    Prop,
    Scene,
    Settings,
    Shot,
    UsageMeter,
    UsageUnits,
    http_status_text,
    missing_credential_text,
    transport_error_text,
)

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
        self._meter = UsageMeter()

    @property
    def url(self) -> str:
        return f"{self.base_url}/images/generations"

    def drain_usage(self) -> UsageUnits:
        return self._meter.drain()

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
        uri = self._generate(prompt, size=portrait_size(self.model, project.aspect_ratio))
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
            project,
            shot,
            character_names=names,
            scene_name=scene,
            feedback=feedback,
            references=references,
            characters=project.characters,
        )
        size = portrait_size(self.model, project.aspect_ratio)
        uri = self._generate(prompt, size=size, references=references)
        return _asset(project, AssetKind.SHOT_KEYFRAME, shot.id, revision, prompt, uri, self.name)

    def _generate(
        self, prompt: str, *, size: str, references: Sequence[Asset] | None = None
    ) -> str:
        if not self.api_key:
            raise VisionError(missing_credential_text("VISION_ENGINE=cloud", "OPENAI_API_KEY"))
        blobs = _reference_blobs(self._http, references or ())
        uri: str | None = None
        if blobs and _supports_edits(self.model):
            try:
                uri = self._edit(prompt, size=size, blobs=blobs)
            except VisionError:
                uri = None
        if uri is None:
            uri = self._create(prompt, size=size)
        self._meter.add_images(1)
        return uri

    def _create(self, prompt: str, *, size: str) -> str:
        return self._post_json(
            self.url,
            {
                "model": self.model,
                "prompt": prompt,
                "size": size,
                "n": 1,
            },
        )

    def _edit(self, prompt: str, *, size: str, blobs: list[tuple[str, bytes]]) -> str:
        files: list[tuple[str, tuple[str, bytes, str]]] = [
            ("image[]" if len(blobs) > 1 else "image", (name, data, "image/png"))
            for name, data in blobs
        ]
        data = {"model": self.model, "prompt": prompt, "size": size, "n": "1"}
        try:
            resp = self._http.post(
                f"{self.base_url}/images/edits",
                data=data,
                files=files,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
        except httpx.HTTPError as exc:
            raise VisionError(transport_error_text("vision edits", exc)) from exc
        return _uri_from_response(resp)

    def _post_json(self, url: str, payload: dict[str, Any]) -> str:
        try:
            resp = self._http.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
        except httpx.HTTPError as exc:
            raise VisionError(transport_error_text("vision", exc)) from exc
        return _uri_from_response(resp)

    def close(self) -> None:
        if self._owns_http:
            self._http.close()


def portrait_size(model: str, aspect_ratio: str) -> str:
    """Pick a documented Images API size for the configured model."""
    if aspect_ratio != "9:16":
        return "1024x1024"
    name = model.strip().lower()
    if name.startswith("dall-e-3") or name.startswith("dalle-3"):
        return "1024x1792"
    if name.startswith("dall-e-2") or name.startswith("dalle-2"):
        return "1024x1024"
    # gpt-image-1 and later GPT image models: 1024x1536 is the portrait size.
    return "1024x1536"


def _supports_edits(model: str) -> bool:
    name = model.strip().lower()
    return name.startswith("gpt-image") or name.startswith("gpt-4o")


def _reference_blobs(http: httpx.Client, references: Sequence[Asset]) -> list[tuple[str, bytes]]:
    blobs: list[tuple[str, bytes]] = []
    for asset in references:
        raw = _fetch_bytes(http, asset.uri)
        if raw:
            blobs.append((f"{asset.kind.value}_{asset.id}.png", raw))
    return blobs


def _fetch_bytes(http: httpx.Client, uri: str) -> bytes | None:
    if uri.startswith("data:image/") and ";base64," in uri:
        try:
            return base64.b64decode(uri.split(",", 1)[1])
        except ValueError:
            return None
    if uri.startswith("http://") or uri.startswith("https://"):
        try:
            resp = http.get(uri)
        except httpx.HTTPError:
            return None
        if resp.status_code < 400 and resp.content:
            return resp.content
    return None


def _uri_from_response(resp: httpx.Response) -> str:
    if resp.status_code >= 400:
        raise VisionError(http_status_text("vision", resp.status_code, resp.text[:300]))
    try:
        data = resp.json()
    except ValueError as exc:
        raise VisionError("vision response is not JSON") from exc
    uri = _image_uri(data)
    if not uri:
        raise VisionError("vision API returned no image url/b64")
    return uri


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
