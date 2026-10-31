import json

import httpx
import pytest
from drama_core import (
    Appearance,
    Asset,
    AssetKind,
    Character,
    CharacterIdentity,
    Clip,
    Project,
    Settings,
    Shot,
)
from drama_video import (
    CloudVideoEngine,
    ComfyUIVideoEngine,
    MockVideoEngine,
    VideoError,
    WanVideoEngine,
    create_video_engine,
    portrait_video_size,
)


def _project() -> Project:
    return Project(title="t", genre="g", premise="p", total_words=3000)


def _character() -> Character:
    return Character(
        name="林晚",
        identity=CharacterIdentity(role="女主"),
        appearance=Appearance(description="清冷", hair="黑长直", outfit="米白风衣"),
    )


def _keyframe(owner_id: str) -> Asset:
    return Asset(
        kind=AssetKind.SHOT_KEYFRAME,
        owner_id=owner_id,
        uri="https://img.test/kf.png",
        prompt="vertical 9:16 keyframe identity lock: 林晚",
    )


def test_factory_names() -> None:
    assert isinstance(create_video_engine(Settings()), MockVideoEngine)
    assert isinstance(create_video_engine(Settings(video_engine="cloud")), CloudVideoEngine)
    assert isinstance(create_video_engine(Settings(video_engine="openai")), CloudVideoEngine)
    assert isinstance(create_video_engine(Settings(video_engine="cloud:kling")), CloudVideoEngine)
    assert isinstance(create_video_engine(Settings(video_engine="comfy")), ComfyUIVideoEngine)
    assert isinstance(create_video_engine(Settings(video_engine="comfyui")), ComfyUIVideoEngine)
    assert isinstance(create_video_engine(Settings(video_engine="wan")), WanVideoEngine)
    with pytest.raises(ValueError, match="VIDEO_ENGINE"):
        create_video_engine(Settings(video_engine="nope"))


def test_portrait_video_size_follows_model() -> None:
    assert portrait_video_size("sora-2", "9:16") == "720x1280"
    assert portrait_video_size("wan2.1", "9:16") == "1080x1920"
    assert portrait_video_size("sora-2", "16:9") == "1920x1080"


def test_cloud_videos_post() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["Authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"data": [{"url": "https://vid.test/a.mp4"}]})

    project = _project()
    char = _character()
    project.characters = [char]
    shot = Shot(
        index=1,
        chapter_id="c",
        duration_s=8,
        character_ids=[char.id],
        action="对峙",
        motion_prompt="slow push-in",
        camera="medium",
    )
    engine = CloudVideoEngine(
        Settings(openai_api_key="sk-test", openai_base_url="https://llm.test/v1"),
        http=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    clip = engine.image_to_video(project, shot, _keyframe(shot.id))
    assert clip.uri == "https://vid.test/a.mp4"
    assert clip.width == 1080 and clip.height == 1920
    assert clip.duration_s == 8
    assert seen["url"] == "https://llm.test/v1/videos"
    assert seen["auth"] == "Bearer sk-test"
    body = seen["body"]
    assert isinstance(body, dict)
    assert "identity lock" in str(body["prompt"])
    assert body["size"] == "720x1280"
    assert body["seconds"] == "8"
    assert body["input_reference"] == "https://img.test/kf.png"


def test_cloud_polls_async_job() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, json={"id": "vid_1", "status": "queued"})
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(200, json={"id": "vid_1", "status": "in_progress"})
        return httpx.Response(
            200, json={"id": "vid_1", "status": "completed", "url": "https://vid.test/done.mp4"}
        )

    engine = CloudVideoEngine(
        Settings(openai_api_key="sk-test", openai_base_url="https://llm.test/v1"),
        http=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    shot = Shot(index=1, chapter_id="c", duration_s=6, action="走")
    clip = engine.image_to_video(_project(), shot, _keyframe(shot.id))
    assert clip.uri == "https://vid.test/done.mp4"
    assert calls["n"] == 2


def test_cloud_requires_api_key() -> None:
    engine = CloudVideoEngine(Settings(openai_api_key=""))
    shot = Shot(index=1, chapter_id="c", duration_s=8, action="走")
    with pytest.raises(VideoError, match="API_KEY"):
        engine.image_to_video(_project(), shot, _keyframe(shot.id))


def test_cloud_uses_video_api_key_and_previous_clip() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["Authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"url": "https://vid.test/b.mp4"})

    project = _project()
    shot = Shot(index=2, chapter_id="c", duration_s=7, action="回头")
    prev = Clip(
        shot_id="shot_prev",
        source_asset_id="a",
        uri="https://vid.test/prev.mp4",
        duration_s=8,
        prompt="vertical 9:16 previous beat",
    )
    engine = CloudVideoEngine(
        Settings(video_api_key="sk-video", video_base_url="https://i2v.test/v1", video_model="wan"),
        http=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    clip = engine.image_to_video(
        project, shot, _keyframe(shot.id), previous_clip=prev, identity_refs=[]
    )
    assert seen["auth"] == "Bearer sk-video"
    body = seen["body"]
    assert isinstance(body, dict)
    assert "previous clip https://vid.test/prev.mp4" in str(body["prompt"])
    assert clip.previous_clip_id == prev.id
    assert seen["auth"] and "https://i2v.test/v1/videos" in str(
        # request url checked via engine.url
        engine.url
    )
    assert engine.url == "https://i2v.test/v1/videos"
    assert body["size"] == "1080x1920"


def test_comfy_prompt_stub() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        seen["payload"] = payload
        assert payload["prompt"]["1"]["class_type"] == "CLIPTextEncode"
        return httpx.Response(200, json={"prompt_id": "vidabc"})

    engine = ComfyUIVideoEngine(
        "http://comfy.test",
        http=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    shot = Shot(index=1, chapter_id="c", duration_s=8, action="推门", motion_prompt="dolly in")
    clip = engine.image_to_video(_project(), shot, _keyframe(shot.id))
    assert clip.uri == "comfy://vidabc"
    assert clip.engine == "comfyui"
    payload = seen["payload"]
    assert isinstance(payload, dict)
    extra = payload["extra_data"]
    assert extra["keyframe_uri"] == "https://img.test/kf.png"
    assert extra["workflow"] == "wan21_i2v.json"


def test_comfy_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="down")

    engine = WanVideoEngine(
        "http://comfy.test",
        http=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    shot = Shot(index=1, chapter_id="c", duration_s=8, action="走")
    with pytest.raises(VideoError, match="503"):
        engine.image_to_video(_project(), shot, _keyframe(shot.id))
