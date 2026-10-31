"""Usage units + a small meter engines can drain after a live call."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class UsageUnits:
    """Token / image / video / TTS counts for one ledger line or a drained meter."""

    tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    images: int = 0
    video_seconds: float = 0.0
    tts_chars: int = 0
    source: str = "estimate"

    def has_values(self) -> bool:
        return bool(
            self.tokens
            or self.prompt_tokens
            or self.completion_tokens
            or self.images
            or self.video_seconds
            or self.tts_chars
        )

    def normalized_tokens(self) -> int:
        return self.tokens or (self.prompt_tokens + self.completion_tokens)


@dataclass
class UsageMeter:
    """Mutable accumulator. Live engines increment this, then ``drain()`` into the ledger."""

    tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    images: int = 0
    video_seconds: float = 0.0
    tts_chars: int = 0
    recorded: bool = False

    def add_tokens(self, prompt: int = 0, completion: int = 0, total: int = 0) -> None:
        prompt = max(0, int(prompt))
        completion = max(0, int(completion))
        total = max(0, int(total) or (prompt + completion))
        if prompt == 0 and completion == 0 and total == 0:
            return
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.tokens += total
        self.recorded = True

    def add_images(self, count: int = 1) -> None:
        if count <= 0:
            return
        self.images += int(count)
        self.recorded = True

    def add_video(self, seconds: float) -> None:
        if seconds <= 0:
            return
        self.video_seconds = round(self.video_seconds + float(seconds), 6)
        self.recorded = True

    def add_tts(self, chars: int) -> None:
        if chars <= 0:
            return
        self.tts_chars += int(chars)
        self.recorded = True

    def drain(self) -> UsageUnits:
        units = UsageUnits(
            tokens=self.tokens,
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
            images=self.images,
            video_seconds=self.video_seconds,
            tts_chars=self.tts_chars,
            source="recorded" if self.recorded else "estimate",
        )
        self.tokens = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.images = 0
        self.video_seconds = 0.0
        self.tts_chars = 0
        self.recorded = False
        return units


def drain_engine_usage(engine: object) -> UsageUnits | None:
    """Call ``engine.drain_usage()`` when present. Unknown shapes are ignored."""
    drain = getattr(engine, "drain_usage", None)
    if not callable(drain):
        return None
    raw = drain()
    if isinstance(raw, UsageUnits):
        return raw
    if isinstance(raw, UsageMeter):
        return raw.drain()
    if isinstance(raw, dict):
        tokens = int(raw.get("tokens") or 0)
        prompt = int(raw.get("prompt_tokens") or 0)
        completion = int(raw.get("completion_tokens") or 0)
        units = UsageUnits(
            tokens=tokens or (prompt + completion),
            prompt_tokens=prompt,
            completion_tokens=completion,
            images=int(raw.get("images") or 0),
            video_seconds=float(raw.get("video_seconds") or 0.0),
            tts_chars=int(raw.get("tts_chars") or 0),
            source=str(raw.get("source") or "recorded"),
        )
        return units if units.has_values() else None
    prompt = int(getattr(raw, "prompt_tokens", 0) or 0)
    completion = int(getattr(raw, "completion_tokens", 0) or 0)
    total = int(getattr(raw, "total_tokens", 0) or 0) or (prompt + completion)
    if total <= 0:
        return None
    return UsageUnits(
        tokens=total,
        prompt_tokens=prompt,
        completion_tokens=completion,
        source="recorded",
    )
