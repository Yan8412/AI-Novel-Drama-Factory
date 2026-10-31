"""Pick subtitle / TTS engines from settings. Paid TTS is never the default."""

from __future__ import annotations

from drama_core import Settings

from drama_tts.cloud import CloudTtsEngine
from drama_tts.interfaces import SubtitleEngine, TtsEngine
from drama_tts.mock import MockTtsEngine, NullTtsEngine
from drama_tts.subtitles import MockSubtitleEngine, NullSubtitleEngine

CLOUD_TTS_NAMES = frozenset({"openai", "cloud", "tts"})
OFF_NAMES = frozenset({"off", "none", "disabled", "0", "false"})


def create_subtitle_engine(settings: Settings | None = None) -> SubtitleEngine:
    settings = settings or Settings.from_env()
    fmt = settings.subtitle_format.strip().lower()
    if fmt in OFF_NAMES:
        return NullSubtitleEngine()
    return MockSubtitleEngine(fmt=fmt or "both")


def create_tts_engine(settings: Settings | None = None) -> TtsEngine:
    settings = settings or Settings.from_env()
    name = settings.tts_engine.strip().lower()
    if name in OFF_NAMES:
        return NullTtsEngine()
    if name in CLOUD_TTS_NAMES:
        return CloudTtsEngine(settings)
    return MockTtsEngine()
