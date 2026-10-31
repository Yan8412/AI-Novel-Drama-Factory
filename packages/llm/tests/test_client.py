import json

import httpx
import pytest
from drama_llm import LlmClient, LlmConfig, LlmError


def test_from_env_reads_key_url_model() -> None:
    cfg = LlmConfig.from_env(
        {
            "OPENAI_API_KEY": "sk-test",
            "OPENAI_BASE_URL": "https://example.test/v1",
            "NOVEL_MODEL": "novel-x",
            "REVIEW_MODEL": "judge-x",
        },
        model_var="REVIEW_MODEL",
        default_model="fallback",
    )
    assert cfg.api_key == "sk-test"
    assert cfg.base_url == "https://example.test/v1"
    assert cfg.model == "judge-x"


def test_chat_posts_openai_compatible_body() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["Authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"hello": "world"}'}}]},
        )

    client = LlmClient(
        LlmConfig(api_key="sk-test", base_url="https://llm.test/v1", model="m1"),
        http=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    text = client.chat([{"role": "user", "content": "hi"}], json_mode=True)
    assert text == '{"hello": "world"}'
    assert seen["url"] == "https://llm.test/v1/chat/completions"
    assert seen["auth"] == "Bearer sk-test"
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["model"] == "m1"
    assert body["response_format"] == {"type": "json_object"}


def test_chat_requires_api_key() -> None:
    client = LlmClient(LlmConfig(api_key=""))
    with pytest.raises(LlmError, match="OPENAI_API_KEY"):
        client.chat([{"role": "user", "content": "x"}])


def test_chat_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="nope Bearer sk-leaked-secret-value")

    client = LlmClient(
        LlmConfig(api_key="sk"),
        http=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(LlmError, match="401") as exc_info:
        client.chat([{"role": "user", "content": "x"}])
    assert "sk-leaked-secret-value" not in str(exc_info.value)
    assert "***" in str(exc_info.value)
