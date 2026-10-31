"""Redact credentials from LLM client errors (kept local so drama-llm stays core-free)."""

from __future__ import annotations

import re

_BEARER = re.compile(r"(?i)(bearer\s+)\S+")
_SK_TOKEN = re.compile(r"sk-[A-Za-z0-9_\-]{6,}")
_KEY_ASSIGN = re.compile(r"(?i)((?:api[_-]?key|token|secret|password|authorization)[=:]\s*)\S+")


def public_error_text(message: object, *, limit: int = 240) -> str:
    text = " ".join(str(message).split())
    text = _BEARER.sub(r"\1***", text)
    text = _SK_TOKEN.sub("sk-***", text)
    text = _KEY_ASSIGN.sub(r"\1***", text)
    if len(text) > limit:
        return text[: limit - 1] + "…"
    return text
