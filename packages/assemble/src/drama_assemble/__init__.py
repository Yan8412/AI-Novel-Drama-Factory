"""Clip assembly: 15–60s 9:16 episode packages from per-shot clips."""

from drama_assemble.export import (
    episode_dir,
    materialize_groups,
    write_concat_list,
    write_episode_stub,
    write_episodes_manifest,
    write_playbook,
)
from drama_assemble.factory import FFMPEG_ENGINE_NAMES, create_assembler
from drama_assemble.ffmpeg import FfmpegAssembler
from drama_assemble.interfaces import Assembler
from drama_assemble.mock import MockAssembler
from drama_assemble.packing import ClipGroup, ffmpeg_concat_command, pack_clip_groups

__all__ = [
    "FFMPEG_ENGINE_NAMES",
    "Assembler",
    "ClipGroup",
    "FfmpegAssembler",
    "MockAssembler",
    "create_assembler",
    "episode_dir",
    "ffmpeg_concat_command",
    "materialize_groups",
    "pack_clip_groups",
    "write_concat_list",
    "write_episode_stub",
    "write_episodes_manifest",
    "write_playbook",
]
