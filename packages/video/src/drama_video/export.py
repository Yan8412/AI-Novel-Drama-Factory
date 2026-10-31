"""Write clip manifests and mock stub files under ``<project>/videos/``."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from drama_core import Clip, Project, Shot

from drama_video.stub import is_mock_clip_uri, write_stub_file


def clip_stem(project: Project, shot: Shot, clip: Clip) -> str:
    chapter = next((c.index for c in project.chapters if c.id == shot.chapter_id), 0)
    return f"shot_{chapter:03d}_{shot.index:03d}_r{clip.revision}"


def clip_record(
    project: Project,
    shot: Shot,
    clip: Clip,
    *,
    rel_path: str | None,
) -> dict[str, Any]:
    return {
        "clip_id": clip.id,
        "shot_id": shot.id,
        "chapter": next((c.index for c in project.chapters if c.id == shot.chapter_id), 0),
        "shot_index": shot.index,
        "uri": clip.uri,
        "path": rel_path,
        "duration_s": clip.duration_s,
        "width": clip.width,
        "height": clip.height,
        "fps": clip.fps,
        "engine": clip.engine,
        "revision": clip.revision,
        "previous_clip_id": clip.previous_clip_id,
        "source_asset_id": clip.source_asset_id,
        "prompt": clip.prompt,
    }


def write_video_export(out_dir: Path, project: Project) -> Path:
    """Write ``videos/clips.json`` plus mock ``.mp4`` stubs. Returns the manifest path."""
    videos = out_dir / "videos"
    videos.mkdir(parents=True, exist_ok=True)
    shots = {s.id: s for s in project.shots}
    records: list[dict[str, Any]] = []
    for clip in project.clips:
        shot = shots.get(clip.shot_id)
        if shot is None:
            continue
        rel_path: str | None = None
        if is_mock_clip_uri(clip.uri):
            filename = f"{clip_stem(project, shot, clip)}.mp4"
            write_stub_file(videos / filename, clip)
            rel_path = f"videos/{filename}"
        sidecar = {
            "clip": clip_record(project, shot, clip, rel_path=rel_path),
        }
        (videos / f"{clip_stem(project, shot, clip)}.json").write_text(
            json.dumps(sidecar, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        records.append(clip_record(project, shot, clip, rel_path=rel_path))
    manifest = {
        "project_id": project.id,
        "title": project.title,
        "aspect_ratio": project.aspect_ratio,
        "resolution": [project.width, project.height],
        "clip_count": len(records),
        "total_duration_s": sum(c.duration_s for c in project.clips),
        "clips": records,
    }
    path = videos / "clips.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
