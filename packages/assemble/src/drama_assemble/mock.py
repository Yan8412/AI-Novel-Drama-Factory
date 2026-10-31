"""Offline assembler: concat list + ASCII episode stub (CI / demo default)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from drama_core import Episode, Project

from drama_assemble.export import (
    episode_dir,
    materialize_groups,
    write_episodes_manifest,
)
from drama_assemble.packing import ffmpeg_concat_command


class MockAssembler:
    name = "mock-assemble"

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
        command = ffmpeg_concat_command("episode/concat_full.txt", "episode/full.mp4")
        write_episodes_manifest(folder, project, episodes, ffmpeg_command=command)
        return episodes
