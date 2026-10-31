"""Optional TTS + subtitle tracks from shot dialogue."""

from drama_tts.cloud import CloudTtsEngine, TtsError
from drama_tts.cues import Cue, build_cues, cue_text, render_srt, render_vtt
from drama_tts.factory import CLOUD_TTS_NAMES, create_subtitle_engine, create_tts_engine
from drama_tts.interfaces import SubtitleEngine, TtsEngine
from drama_tts.mock import MockTtsEngine, NullTtsEngine
from drama_tts.subtitles import MockSubtitleEngine, NullSubtitleEngine

__all__ = [
    "CLOUD_TTS_NAMES",
    "CloudTtsEngine",
    "Cue",
    "MockSubtitleEngine",
    "MockTtsEngine",
    "NullSubtitleEngine",
    "NullTtsEngine",
    "SubtitleEngine",
    "TtsEngine",
    "TtsError",
    "build_cues",
    "create_subtitle_engine",
    "create_tts_engine",
    "cue_text",
    "render_srt",
    "render_vtt",
]
