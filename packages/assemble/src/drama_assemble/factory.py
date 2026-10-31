"""Pick an ``Assembler`` from ``ASSEMBLE_ENGINE`` without touching the FSM."""

from __future__ import annotations

from drama_core import Settings

from drama_assemble.ffmpeg import FfmpegAssembler
from drama_assemble.interfaces import Assembler
from drama_assemble.mock import MockAssembler

FFMPEG_ENGINE_NAMES = frozenset({"ffmpeg", "ff", "real"})


def create_assembler(settings: Settings | None = None) -> Assembler:
    settings = settings or Settings.from_env()
    name = settings.assemble_engine.strip().lower()
    if name in {"", "mock"}:
        return MockAssembler()
    if name in FFMPEG_ENGINE_NAMES:
        return FfmpegAssembler()
    raise ValueError(f"unknown ASSEMBLE_ENGINE={settings.assemble_engine!r} (expected mock|ffmpeg)")
