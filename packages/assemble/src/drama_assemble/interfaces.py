"""Assembler protocol: stitch per-shot clips into 9:16 episode packages."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from drama_core import Episode, Project


@runtime_checkable
class Assembler(Protocol):
    name: str

    def assemble(
        self,
        project: Project,
        *,
        out_dir: Path,
        timeline: list[dict[str, Any]] | None = None,
    ) -> list[Episode]:
        """Write concat lists + episode stubs (or a real ffmpeg concat) under ``out_dir``."""
        ...
