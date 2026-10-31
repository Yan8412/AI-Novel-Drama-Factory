"""Tiny offline clip stubs so mock export has files Phase 4 can discover."""

from __future__ import annotations

from pathlib import Path

from drama_core import Clip


def stub_clip_bytes(clip: Clip) -> bytes:
    """ASCII placeholder, not a playable MP4. Enough for CI path checks."""
    body = (
        "drama-factory mock clip\n"
        f"engine={clip.engine}\n"
        f"uri={clip.uri}\n"
        f"size={clip.width}x{clip.height}\n"
        f"duration_s={clip.duration_s}\n"
        f"fps={clip.fps}\n"
        f"revision={clip.revision}\n"
    )
    return body.encode("utf-8")


def write_stub_file(path: Path, clip: Clip) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(stub_clip_bytes(clip))
    return path


def is_mock_clip_uri(uri: str) -> bool:
    return uri.startswith("mock://")
