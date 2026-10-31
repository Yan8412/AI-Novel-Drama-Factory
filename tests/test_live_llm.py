"""Optional live call. Skipped in CI unless RUN_LIVE_LLM=1."""

from __future__ import annotations

import os

import pytest
from drama_llm import LlmClient, LlmConfig, extract_json


@pytest.mark.integration
@pytest.mark.skipif(os.environ.get("RUN_LIVE_LLM") != "1", reason="set RUN_LIVE_LLM=1")
def test_live_openai_compatible_json_roundtrip() -> None:
    client = LlmClient(LlmConfig.from_env(model_var="NOVEL_MODEL"))
    raw = client.chat(
        [
            {
                "role": "user",
                "content": '只用 JSON 回复 {"ok": true}，不要其它文字。',
            }
        ],
        temperature=0,
        json_mode=True,
    )
    assert extract_json(raw)["ok"] is True
