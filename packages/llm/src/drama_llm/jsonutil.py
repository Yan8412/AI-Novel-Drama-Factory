"""Pull a JSON value out of typical LLM chat text (fences, leading/trailing prose)."""

from __future__ import annotations

import json
from typing import Any


class JsonExtractError(ValueError):
    pass


def extract_json(text: str) -> Any:
    """Return the first JSON object or array embedded in ``text``.

    Accepts raw JSON, ``` / ```json fenced blocks, and a JSON value surrounded
    by short prose. Raises ``JsonExtractError`` when nothing decodes.
    """
    stripped = text.strip()
    if not stripped:
        raise JsonExtractError("empty LLM text")

    for candidate in (_fenced(stripped), stripped):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
        decoded = _first_json_value(candidate)
        if decoded is not None:
            return decoded

    raise JsonExtractError(f"no JSON object/array in LLM text: {stripped[:200]!r}")


def _fenced(text: str) -> str:
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    body = lines[1:]
    if body and body[-1].strip() == "```":
        body = body[:-1]
    return "\n".join(body).strip()


def _first_json_value(text: str) -> Any | None:
    decoder = json.JSONDecoder()
    starts = [i for i in (text.find("{"), text.find("[")) if i >= 0]
    if not starts:
        return None
    start = min(starts)
    try:
        value, _end = decoder.raw_decode(text[start:])
    except json.JSONDecodeError:
        return None
    return value
