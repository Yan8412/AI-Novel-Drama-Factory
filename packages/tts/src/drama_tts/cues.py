"""Build timed subtitle cues from shot dialogue and clip durations."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from drama_core import Clip, Project, Shot


@dataclass(frozen=True)
class Cue:
    index: int
    start_s: float
    end_s: float
    text: str
    speaker: str = ""


def shot_speaker(project: Project, shot: Shot) -> str:
    names = [c.name for c in project.characters if c.id in shot.character_ids]
    return "、".join(names)


def cue_text(project: Project, shot: Shot) -> str:
    dialogue = (shot.dialogue or "").strip()
    if dialogue:
        return dialogue
    action = (shot.action or "").strip()
    return f"（{action}）" if action else ""


def build_cues(project: Project, shots: Sequence[Shot] | None = None) -> list[Cue]:
    ordered = list(shots) if shots is not None else list(project.shots)
    clips = {c.shot_id: c for c in project.clips}
    cues: list[Cue] = []
    cursor = 0.0
    index = 1
    for shot in ordered:
        clip: Clip | None = clips.get(shot.id)
        duration = clip.duration_s if clip is not None else shot.duration_s
        text = cue_text(project, shot)
        start = cursor
        end = cursor + max(duration, 0.0)
        cursor = end
        if not text:
            continue
        cues.append(
            Cue(
                index=index,
                start_s=start,
                end_s=end,
                text=text,
                speaker=shot_speaker(project, shot),
            )
        )
        index += 1
    return cues


def _stamp(seconds: float) -> tuple[int, int, int, int]:
    total_ms = max(0, round(seconds * 1000))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1000)
    return hours, minutes, secs, millis


def srt_timestamp(seconds: float) -> str:
    h, m, s, ms = _stamp(seconds)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def vtt_timestamp(seconds: float) -> str:
    h, m, s, ms = _stamp(seconds)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def render_srt(cues: Sequence[Cue]) -> str:
    blocks: list[str] = []
    for cue in cues:
        line = cue.text
        if cue.speaker:
            line = f"{cue.speaker}: {cue.text}"
        blocks.append(
            f"{cue.index}\n{srt_timestamp(cue.start_s)} --> {srt_timestamp(cue.end_s)}\n{line}\n"
        )
    return "\n".join(blocks).rstrip() + ("\n" if blocks else "")


def render_vtt(cues: Sequence[Cue]) -> str:
    lines = ["WEBVTT", ""]
    for cue in cues:
        line = cue.text
        if cue.speaker:
            line = f"{cue.speaker}: {cue.text}"
        lines.append(f"{vtt_timestamp(cue.start_s)} --> {vtt_timestamp(cue.end_s)}")
        lines.append(line)
        lines.append("")
    return "\n".join(lines)
