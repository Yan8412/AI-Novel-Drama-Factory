"""Real concat via ffmpeg when available; otherwise the documented command + stub."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from drama_core import Episode, Project

from drama_assemble.export import (
    clip_file_for,
    episode_dir,
    materialize_groups,
    write_episode_stub,
    write_episodes_manifest,
)
from drama_assemble.packing import ffmpeg_concat_command


class FfmpegAssembler:
    """Shell out to ffmpeg for 9:16 concat when every clip looks like real media."""

    name = "ffmpeg"

    def assemble(
        self,
        project: Project,
        *,
        out_dir: Path,
        timeline: list[dict[str, Any]] | None = None,
    ) -> list[Episode]:
        rows = timeline or []
        episodes = materialize_groups(
            project, out_dir=out_dir, engine=self.name, timeline=rows, write_media=True
        )
        folder = episode_dir(out_dir)
        ffmpeg = shutil.which("ffmpeg")
        used_ffmpeg = False
        if ffmpeg and _clips_are_real(out_dir, project, rows):
            used_ffmpeg = _try_concat(ffmpeg, out_dir, folder, episodes, project)
        command = ffmpeg_concat_command("episode/concat_full.txt", "episode/full.mp4")
        write_episodes_manifest(folder, project, episodes, ffmpeg_command=command)
        if used_ffmpeg:
            for episode in episodes:
                episode.engine = self.name
                episode.uri = f"file://{(out_dir / (episode.path or '')).resolve()}"
        return episodes


def _clips_are_real(out_dir: Path, project: Project, timeline: list[dict[str, Any]]) -> bool:
    for clip in project.clips:
        path = clip_file_for(out_dir, clip, timeline)
        if path is None or not path.is_file():
            return False
        head = path.read_bytes()[:64]
        if head.startswith(b"drama-factory mock"):
            return False
    return bool(project.clips)


def _try_concat(
    ffmpeg: str,
    out_dir: Path,
    folder: Path,
    episodes: list[Episode],
    project: Project,
) -> bool:
    ok = True
    for episode in episodes:
        concat = out_dir / (episode.concat_path or "")
        media = out_dir / (episode.path or "")
        if not concat.is_file():
            ok = False
            continue
        if not _run_ffmpeg(ffmpeg, concat, media):
            write_episode_stub(
                media, episode, [c for c in project.clips if c.id in set(episode.clip_ids)]
            )
            ok = False
    full_concat = folder / "concat_full.txt"
    if full_concat.is_file() and not _run_ffmpeg(ffmpeg, full_concat, folder / "full.mp4"):
        ok = False
    return ok


def _run_ffmpeg(ffmpeg: str, concat: Path, output: Path) -> bool:
    try:
        completed = subprocess.run(
            [
                ffmpeg,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat),
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                str(output),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return False
    return completed.returncode == 0 and output.is_file() and output.stat().st_size > 0
