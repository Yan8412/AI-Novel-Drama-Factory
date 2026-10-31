"""Static files for the Phase 6 Web workbench."""

from pathlib import Path


def static_dir() -> Path:
    return Path(__file__).resolve().parent / "static"
