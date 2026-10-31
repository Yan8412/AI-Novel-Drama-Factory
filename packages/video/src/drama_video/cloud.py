"""OpenAI-compatible video API client. Offline tests inject a fake ``httpx.Client``.

Documented request shape (POST ``{base_url}/videos``)::

    {
      "model": "<VIDEO_MODEL>",
      "prompt": "<motion + identity + previous-shot refs>",
      "seconds": "8",
      "size": "1080x1920",
      "input_reference": "<keyframe URI when the gateway accepts a URL>"
    }

Immediate success::

    {"data": [{"url": "https://.../clip.mp4"}]}
    or {"url": "https://.../clip.mp4"}

Async job (then GET ``{base_url}/videos/{id}`` until completed)::

    {"id": "vid_...", "status": "queued"}

``VIDEO_ENGINE=cloud|openai|kling|runway`` (or ``cloud:<provider>``) share this
HTTP shape; only base URL and API key change. Native Kling / Runway payloads
differ — point ``VIDEO_BASE_URL`` at a compatible gateway. No secrets in-repo.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import httpx
from drama_core import (
    Asset,
    Clip,
    Project,
    Settings,
    Shot,
    UsageMeter,
    UsageUnits,
    http_status_text,
    missing_credential_text,
    public_error_text,
    transport_error_text,
)

from drama_video.errors import VideoError
from drama_video.prompts import motion_prompt

_DONE = frozenset({"completed", "succeeded", "success", "ready"})
_FAILED = frozenset({"failed", "error", "canceled", "cancelled"})


class CloudVideoEngine:
    """POST ``{base_url}/videos``. Key comes from Settings, never from source."""

    name = "cloud-video"

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        provider: str = "openai",
        http: httpx.Client | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        poll_attempts: int = 8,
    ) -> None:
        cfg = settings or Settings()
        self.provider = provider.strip().lower() or "openai"
        self.api_key = _first_str(api_key, cfg.video_api_key, cfg.openai_api_key)
        self.base_url = _first_str(base_url, cfg.video_base_url, cfg.openai_base_url).rstrip("/")
        self.model = _first_str(model, cfg.video_model)
        self.poll_attempts = poll_attempts
        self._http = http or httpx.Client(timeout=180.0)
        self._owns_http = http is None
        self._meter = UsageMeter()

    @property
    def url(self) -> str:
        return f"{self.base_url}/videos"

    def drain_usage(self) -> UsageUnits:
        return self._meter.drain()

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
        uri = self._generate(prompt, shot=shot, project=project, keyframe=keyframe)
        self._meter.add_video(shot.duration_s)
        return Clip(
            shot_id=shot.id,
            source_asset_id=keyframe.id,
            uri=uri,
            duration_s=shot.duration_s,
            width=project.width,
            height=project.height,
            fps=24,
            engine=f"{self.name}:{self.provider}",
            revision=revision,
            prompt=prompt,
            previous_clip_id=previous_clip.id if previous_clip is not None else None,
        )

    def _generate(self, prompt: str, *, shot: Shot, project: Project, keyframe: Asset) -> str:
        if not self.api_key:
            raise VideoError(
                missing_credential_text("VIDEO_ENGINE=cloud", "VIDEO_API_KEY", "OPENAI_API_KEY")
            )
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "seconds": _seconds_field(shot.duration_s),
            "size": portrait_video_size(self.model, project.aspect_ratio),
            "input_reference": keyframe.uri,
        }
        data = self._post_json(self.url, payload)
        uri = _video_uri(data)
        if uri:
            return uri
        job_id = _job_id(data)
        if job_id:
            return self._poll(job_id)
        raise VideoError("video API returned no url or job id")

    def _poll(self, job_id: str) -> str:
        url = f"{self.url}/{job_id}"
        last: object = None
        for _ in range(self.poll_attempts):
            last = self._get_json(url)
            if not isinstance(last, Mapping):
                continue
            status = str(last.get("status") or "").strip().lower()
            if status in _FAILED:
                raise VideoError(public_error_text(f"video job {job_id} {status}"))
            uri = _video_uri(last)
            if uri and (status in _DONE or not status):
                return uri
            if uri and status in {"in_progress", "queued", "processing"}:
                continue
            if uri:
                return uri
        raise VideoError(public_error_text(f"video job {job_id} did not complete: {last!r}"))

    def _post_json(self, url: str, payload: dict[str, Any]) -> object:
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
            raise VideoError(transport_error_text("video", exc)) from exc
        return _json_body(resp)

    def _get_json(self, url: str) -> object:
        try:
            resp = self._http.get(
                url,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
        except httpx.HTTPError as exc:
            raise VideoError(transport_error_text("video poll", exc)) from exc
        return _json_body(resp)

    def close(self) -> None:
        if self._owns_http:
            self._http.close()


def portrait_video_size(model: str, aspect_ratio: str) -> str:
    """Pick a documented portrait size. 9:16 → 1080x1920 unless the model is Sora-class."""
    if aspect_ratio != "9:16":
        return "1920x1080"
    name = model.strip().lower()
    if name.startswith("sora"):
        return "720x1280"
    return "1080x1920"


def _seconds_field(duration_s: float) -> str:
    return str(max(1, round(duration_s)))


def _first_str(*values: str | None) -> str:
    for value in values:
        if value:
            return value
    return ""


def _json_body(resp: httpx.Response) -> object:
    if resp.status_code >= 400:
        raise VideoError(http_status_text("video", resp.status_code, resp.text[:300]))
    try:
        return resp.json()
    except ValueError as exc:
        raise VideoError("video response is not JSON") from exc


def _job_id(data: object) -> str:
    if not isinstance(data, Mapping):
        return ""
    for key in ("id", "job_id", "task_id"):
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _video_uri(data: object) -> str:
    if not isinstance(data, Mapping):
        return ""
    for key in ("url", "video_url"):
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    items = data.get("data")
    if isinstance(items, list) and items and isinstance(items[0], Mapping):
        nested = items[0]
        for key in ("url", "video_url"):
            value = nested.get(key)
            if isinstance(value, str) and value:
                return value
    video = data.get("video")
    if isinstance(video, Mapping):
        url = video.get("url")
        if isinstance(url, str) and url:
            return url
    return ""
