"""Public-facing adapter errors. Never echo secrets or raw credential headers."""

from __future__ import annotations

import re

_BEARER = re.compile(r"(?i)(bearer\s+)\S+")
_SK_TOKEN = re.compile(r"sk-[A-Za-z0-9_\-]{6,}")
_KEY_ASSIGN = re.compile(r"(?i)((?:api[_-]?key|token|secret|password|authorization)[=:]\s*)\S+")


def public_error_text(message: object, *, limit: int = 240) -> str:
    """Redact credentials and collapse whitespace so logs/API errors stay shareable."""
    text = " ".join(str(message).split())
    text = _BEARER.sub(r"\1***", text)
    text = _SK_TOKEN.sub("sk-***", text)
    text = _KEY_ASSIGN.sub(r"\1***", text)
    if len(text) > limit:
        return text[: limit - 1] + "…"
    return text


def missing_credential_text(engine: str, *env_vars: str) -> str:
    names = " / ".join(env_vars) if env_vars else "API key"
    return (
        f"{names} is missing for {engine}. "
        "Set it in a local .env (never commit) or keep the default mock engine."
    )


def http_status_text(service: str, status_code: int, body: object = "") -> str:
    suffix = f": {body}" if body not in ("", None) else ""
    return public_error_text(f"{service} HTTP {status_code}{suffix}")


def transport_error_text(service: str, exc: BaseException) -> str:
    return public_error_text(f"{service} request failed: {exc}")
