"""Minimal OpenAI-compatible Chat Completions client (httpx)."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from typing import Any, Protocol, runtime_checkable

import httpx
from pydantic import BaseModel, ConfigDict, Field

from drama_llm.sanitize import public_error_text


class LlmError(RuntimeError):
    pass


@runtime_checkable
class ChatClient(Protocol):
    def chat(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        temperature: float = 0.4,
        json_mode: bool = True,
    ) -> str: ...


class LlmConfig(BaseModel):
    """Credentials + routing for one OpenAI-compatible endpoint."""

    model_config = ConfigDict(frozen=True)

    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    timeout_s: float = Field(default=180.0, gt=0)

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        *,
        model_var: str = "NOVEL_MODEL",
        default_model: str = "gpt-4o-mini",
    ) -> LlmConfig:
        env = os.environ if env is None else env
        return cls(
            api_key=env.get("OPENAI_API_KEY", ""),
            base_url=env.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
            or "https://api.openai.com/v1",
            model=env.get(model_var) or default_model,
        )


class LlmClient:
    """POST ``{base_url}/chat/completions``. Injectable ``httpx.Client`` for tests."""

    def __init__(
        self,
        config: LlmConfig | None = None,
        *,
        http: httpx.Client | None = None,
    ) -> None:
        self.config = config or LlmConfig.from_env()
        self._http = http or httpx.Client(timeout=self.config.timeout_s)
        self._owns_http = http is None

    @property
    def url(self) -> str:
        return f"{self.config.base_url.rstrip('/')}/chat/completions"

    def chat(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        temperature: float = 0.4,
        json_mode: bool = True,
    ) -> str:
        if not self.config.api_key:
            raise LlmError(
                "OPENAI_API_KEY is missing. "
                "Set it in a local .env (never commit) or keep NOVEL_ENGINE=mock."
            )
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": [dict(m) for m in messages],
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        try:
            resp = self._http.post(
                self.url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                },
            )
        except httpx.HTTPError as exc:
            raise LlmError(public_error_text(f"LLM request failed: {exc}")) from exc
        if resp.status_code >= 400:
            raise LlmError(public_error_text(f"LLM HTTP {resp.status_code}: {resp.text[:300]}"))
        try:
            data = resp.json()
        except ValueError as exc:
            raise LlmError("LLM response is not JSON") from exc
        content = _message_content(data)
        if not content:
            raise LlmError("LLM returned empty content")
        return content

    def close(self) -> None:
        if self._owns_http:
            self._http.close()


def _message_content(data: object) -> str:
    if not isinstance(data, dict):
        return ""
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    return content if isinstance(content, str) else ""
