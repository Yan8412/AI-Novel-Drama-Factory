"""TTS + subtitle protocols. Paid synthesis is optional and env-flagged."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol, runtime_checkable

from drama_core import Project, Shot


@runtime_checkable
class SubtitleEngine(Protocol):
    name: str

    def write_track(
        self,
        project: Project,
        shots: Sequence[Shot],
        *,
        out_dir: Path,
    ) -> list[Path]:
        """Write SRT/VTT (and return the paths that were created)."""
        ...


@runtime_checkable
class TtsEngine(Protocol):
    name: str

    def synthesize(
        self,
        project: Project,
        shots: Sequence[Shot],
        *,
        out_dir: Path,
    ) -> list[Path]:
        """Write per-shot audio (or mock sidecars). Empty list is OK."""
        ...
