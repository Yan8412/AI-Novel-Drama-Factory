"""Write concat lists, episode stubs, and a PLAY.md that documents ffmpeg."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from drama_core import Clip, Episode, EpisodeKind, Project, new_id

from drama_assemble.packing import ClipGroup, ffmpeg_concat_command, pack_clip_groups

STUB_PREFIX = b"drama-factory mock episode"


def episode_dir(out_dir: Path) -> Path:
    folder = out_dir / "episode"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def clip_file_for(out_dir: Path, clip: Clip, timeline: list[dict[str, Any]]) -> Path | None:
    for row in timeline:
        if row.get("clip_id") == clip.id and row.get("path"):
            return out_dir / str(row["path"])
    return None


def write_concat_list(path: Path, files: list[Path]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"file '{item.resolve().as_posix()}'" for item in files]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return path


def write_episode_stub(path: Path, episode: Episode, clips: list[Clip]) -> Path:
    body = (
        "drama-factory mock episode\n"
        f"id={episode.id}\n"
        f"title={episode.title}\n"
        f"kind={episode.kind.value}\n"
        f"size={episode.width}x{episode.height}\n"
        f"duration_s={episode.duration_s}\n"
        f"clips={','.join(c.id for c in clips)}\n"
        "not a playable MP4 — see episode/PLAY.md for the ffmpeg concat command\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body.encode("utf-8"))
    return path


def write_playbook(
    folder: Path,
    *,
    concat_full: Path,
    episode_full: Path,
    subtitle: Path | None,
) -> Path:
    burn = ""
    if subtitle is not None:
        burn = (
            "\n# Optional: burn subtitles (needs a real encoded episode)\n"
            f"ffmpeg -y -i {episode_full.name} -vf subtitles={subtitle.name} "
            "episode_subs.mp4\n"
        )
    text = f"""# Play / assemble a 9:16 episode

Mock clip and episode files are **ASCII stubs**, not playable media. They exist
so CI and `drama-factory demo` can assert paths. When `VIDEO_ENGINE` produced
real MP4s (or you replaced the stubs), stitch them with ffmpeg:

```bash
# Copy codecs (clips must share codec / timebase)
{ffmpeg_concat_command(concat_full.name, episode_full.name)}
```

Play the result in any 9:16-aware player (`ffplay`, VLC, a phone).
{burn}
`ASSEMBLE_ENGINE=ffmpeg` runs that command when `ffmpeg` is on PATH **and**
every clip file looks like real media. Otherwise the exact command is written
here and in `episodes.json`.
"""
    path = folder / "PLAY.md"
    path.write_text(text, encoding="utf-8")
    return path


def materialize_groups(
    project: Project,
    *,
    out_dir: Path,
    engine: str,
    timeline: list[dict[str, Any]],
    write_media: bool = True,
) -> list[Episode]:
    """Write per-group concat lists + optional stub files. Does not shell out."""
    folder = episode_dir(out_dir)
    groups = pack_clip_groups(project)
    episodes: list[Episode] = []
    for index, group in enumerate(groups, start=1):
        slug = _slug(group, index)
        concat = folder / f"concat_{slug}.txt"
        media = folder / f"{slug}.mp4"
        files = [p for c in group.clips if (p := clip_file_for(out_dir, c, timeline)) is not None]
        write_concat_list(concat, files)
        episode = Episode(
            id=new_id("ep"),
            kind=group.kind,
            index=index,
            title=group.title or project.title,
            chapter_id=group.chapter_id,
            clip_ids=[c.id for c in group.clips],
            duration_s=group.duration_s,
            width=project.width,
            height=project.height,
            path=f"episode/{media.name}",
            concat_path=f"episode/{concat.name}",
            uri=f"mock://episode/{slug}.mp4" if engine.startswith("mock") else f"file://{media}",
            engine=engine,
        )
        if write_media:
            write_episode_stub(media, episode, group.clips)
        episodes.append(episode)

    all_files = [p for c in project.clips if (p := clip_file_for(out_dir, c, timeline)) is not None]
    full_concat = write_concat_list(folder / "concat_full.txt", all_files)
    full_media = folder / "full.mp4"
    write_playbook(folder, concat_full=full_concat, episode_full=full_media, subtitle=None)
    if write_media and not (folder / "full.mp4").exists():
        write_episode_stub(
            full_media,
            Episode(
                kind=EpisodeKind.EPISODE,
                title=project.title,
                clip_ids=[c.id for c in project.clips],
                duration_s=sum(c.duration_s for c in project.clips),
                width=project.width,
                height=project.height,
                engine=engine,
            ),
            list(project.clips),
        )
    return episodes


def write_episodes_manifest(
    folder: Path,
    project: Project,
    episodes: list[Episode],
    *,
    ffmpeg_command: str,
) -> Path:
    payload = {
        "project_id": project.id,
        "title": project.title,
        "aspect_ratio": project.aspect_ratio,
        "resolution": [project.width, project.height],
        "episode_count": len(episodes),
        "total_duration_s": sum(e.duration_s for e in episodes),
        "ffmpeg": ffmpeg_command,
        "episodes": [e.model_dump(mode="json") for e in episodes],
    }
    path = folder / "episodes.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _slug(group: ClipGroup, index: int) -> str:
    if group.kind is EpisodeKind.CHAPTER and group.chapter_id:
        return f"chapter_{index:03d}"
    return f"episode_{index:03d}"
