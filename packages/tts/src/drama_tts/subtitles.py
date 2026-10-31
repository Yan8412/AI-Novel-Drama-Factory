"""Mock subtitle writer: SRT/VTT from shot dialogue (no paid services)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from drama_core import Project, Shot

from drama_tts.cues import build_cues, render_srt, render_vtt


class MockSubtitleEngine:
    name = "mock-subtitles"

    def __init__(self, fmt: str = "both") -> None:
        self.fmt = (fmt or "both").strip().lower()

    def write_track(
        self,
        project: Project,
        shots: Sequence[Shot],
        *,
        out_dir: Path,
    ) -> list[Path]:
        if self.fmt in {"off", "none", "disabled"}:
            return []
        cues = build_cues(project, shots)
        folder = out_dir / "episode"
        folder.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []
        if self.fmt in {"srt", "both", "all"}:
            path = folder / "subtitles.srt"
            path.write_text(render_srt(cues), encoding="utf-8")
            written.append(path)
        if self.fmt in {"vtt", "both", "all"}:
            path = folder / "subtitles.vtt"
            path.write_text(render_vtt(cues), encoding="utf-8")
            written.append(path)
        return written


class NullSubtitleEngine:
    name = "off"

    def write_track(
        self,
        project: Project,
        shots: Sequence[Shot],
        *,
        out_dir: Path,
    ) -> list[Path]:
        return []
