"""Offline TTS stub: sidecar JSON, no audio bytes, no network."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from drama_core import Project, Shot

from drama_tts.cues import cue_text, shot_speaker


class MockTtsEngine:
    name = "mock-tts"

    def synthesize(
        self,
        project: Project,
        shots: Sequence[Shot],
        *,
        out_dir: Path,
    ) -> list[Path]:
        folder = out_dir / "episode" / "tts"
        folder.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []
        clips = {c.shot_id: c for c in project.clips}
        chapters = {c.id: c.index for c in project.chapters}
        for shot in shots:
            text = cue_text(project, shot)
            if not text:
                continue
            clip = clips.get(shot.id)
            voice = next(
                (
                    c.voice.tts_voice_id or c.voice.tone
                    for c in project.characters
                    if c.id in shot.character_ids
                ),
                "",
            )
            payload = {
                "shot_id": shot.id,
                "speaker": shot_speaker(project, shot),
                "voice": voice,
                "text": text,
                "duration_s": clip.duration_s if clip is not None else shot.duration_s,
                "engine": self.name,
                "audio": None,
                "note": "mock sidecar — set TTS_ENGINE=openai for paid synthesis",
            }
            chapter = chapters.get(shot.chapter_id, 0)
            path = folder / f"shot_{chapter:03d}_{shot.index:03d}.json"
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            written.append(path)
        return written


class NullTtsEngine:
    name = "off"

    def synthesize(
        self,
        project: Project,
        shots: Sequence[Shot],
        *,
        out_dir: Path,
    ) -> list[Path]:
        return []
