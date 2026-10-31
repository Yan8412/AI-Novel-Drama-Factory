import json

import httpx
import pytest
from drama_core import (
    Appearance,
    Asset,
    AssetKind,
    Character,
    CharacterIdentity,
    Project,
    Prop,
    Scene,
    Settings,
    Shot,
)
from drama_vision import (
    CloudVisionEngine,
    ComfyUIVisionEngine,
    MockVisionEngine,
    VisionError,
    create_vision_engine,
    portrait_size,
)


def _project() -> Project:
    return Project(title="t", genre="g", premise="p", total_words=3000)


def _character() -> Character:
    return Character(
        name="林晚",
        identity=CharacterIdentity(role="女主"),
        appearance=Appearance(description="清冷", hair="黑长直", outfit="米白风衣"),
    )


def test_factory_names() -> None:
    assert isinstance(create_vision_engine(Settings()), MockVisionEngine)
    assert isinstance(create_vision_engine(Settings(vision_engine="cloud")), CloudVisionEngine)
    assert isinstance(create_vision_engine(Settings(vision_engine="comfy")), ComfyUIVisionEngine)
    assert isinstance(create_vision_engine(Settings(vision_engine="comfyui")), ComfyUIVisionEngine)
    with pytest.raises(ValueError, match="VISION_ENGINE"):
        create_vision_engine(Settings(vision_engine="nope"))


def test_cloud_images_post() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["Authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"data": [{"url": "https://img.test/a.png"}]})

    engine = CloudVisionEngine(
        Settings(openai_api_key="sk-test", openai_base_url="https://llm.test/v1"),
        http=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    asset = engine.character_nine_view(_project(), _character())
    assert asset.uri == "https://img.test/a.png"
    assert seen["url"] == "https://llm.test/v1/images/generations"
    assert seen["auth"] == "Bearer sk-test"
    body = seen["body"]
    assert isinstance(body, dict)
    assert "identity lock" in str(body["prompt"])


def test_portrait_size_follows_model() -> None:
    assert portrait_size("gpt-image-1", "9:16") == "1024x1536"
    assert portrait_size("dall-e-3", "9:16") == "1024x1792"
    assert portrait_size("dall-e-2", "9:16") == "1024x1024"
    assert portrait_size("gpt-image-1", "1:1") == "1024x1024"


def test_cloud_scene_uses_gpt_image_portrait_size() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"data": [{"url": "https://img.test/s.png"}]})

    engine = CloudVisionEngine(
        Settings(openai_api_key="sk-test", openai_base_url="https://llm.test/v1"),
        http=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    engine.scene_image(_project(), Scene(name="雨夜街头", description="霓虹", time_of_day="夜"))
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["size"] == "1024x1536"
    assert body["model"] == "gpt-image-1"


def test_cloud_keyframe_embeds_reference_prompts_and_edits_http_refs() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, content=b"png-bytes")
        seen["url"] = str(request.url)
        seen["path"] = request.url.path
        return httpx.Response(200, json={"data": [{"url": "https://img.test/kf.png"}]})

    project = _project()
    char = _character()
    project.characters = [char]
    engine = CloudVisionEngine(
        Settings(openai_api_key="sk-test", openai_base_url="https://llm.test/v1"),
        http=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    refs = [
        Asset(
            kind=AssetKind.CHARACTER_NINE_VIEW,
            owner_id=char.id,
            uri="https://img.test/sheet.png",
            prompt="identity lock: 林晚; outfit: 米白风衣",
            views=["front"],
        ),
        Asset(
            kind=AssetKind.SCENE,
            owner_id="scene_1",
            uri="https://img.test/scene.png",
            prompt="environment design sheet, rain street",
        ),
    ]
    shot = Shot(
        index=1,
        chapter_id="c",
        duration_s=8,
        character_ids=[char.id],
        image_prompt="vertical 9:16 confrontation",
    )
    asset = engine.shot_keyframe(project, shot, refs)
    assert asset.uri == "https://img.test/kf.png"
    assert "identity lock: 林晚" in asset.prompt
    assert "environment design sheet, rain street" in asset.prompt
    assert seen["path"] == "/v1/images/edits"


def test_cloud_requires_api_key() -> None:
    engine = CloudVisionEngine(Settings(openai_api_key=""))
    with pytest.raises(VisionError, match="OPENAI_API_KEY"):
        engine.prop_image(_project(), Prop(name="玉", description="白"))


def test_comfy_prompt_stub() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["prompt"]["1"]["class_type"] == "CLIPTextEncode"
        return httpx.Response(200, json={"prompt_id": "abc123"})

    engine = ComfyUIVisionEngine(
        "http://comfy.test",
        http=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    scene = Scene(name="雨夜街头", description="霓虹", time_of_day="夜")
    asset = engine.scene_image(_project(), scene)
    assert asset.uri == "comfy://abc123"
    assert asset.engine == "comfyui"


def test_comfy_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="down")

    engine = ComfyUIVisionEngine(
        "http://comfy.test",
        http=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    shot = Shot(index=1, chapter_id="c", duration_s=8, image_prompt="vertical 9:16")
    with pytest.raises(VisionError, match="503"):
        engine.shot_keyframe(_project(), shot, [])
