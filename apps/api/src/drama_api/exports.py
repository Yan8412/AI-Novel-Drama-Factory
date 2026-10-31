"""Read-only export metadata. Never serves secrets or arbitrary paths."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from drama_core import ExportResult, PipelineStage, Project
from pydantic import BaseModel

MAX_TEXT_CHARS = 200_000

# Allowlisted relative paths under the project output dir only.
SAFE_FILES: tuple[tuple[str, str, str], ...] = (
    ("PLAY.md", "episode/PLAY.md", "text/markdown"),
    ("budget.json", "budget.json", "application/json"),
    ("manifest.json", "manifest.json", "application/json"),
    ("episodes.json", "episode/episodes.json", "application/json"),
)


class ChapterSnippet(BaseModel):
    id: str
    index: int
    title: str
    word_count: int
    revision: int


class EpisodeSnippet(BaseModel):
    id: str
    index: int
    title: str
    kind: str
    duration_s: float
    path: str | None = None
    concat_path: str | None = None
    subtitle_path: str | None = None
    clip_count: int = 0


class ExportFile(BaseModel):
    name: str
    relative_path: str
    available: bool
    media_type: str


class ExportView(BaseModel):
    project_id: str
    stage: PipelineStage
    shot_count: int
    clip_count: int
    chapter_count: int
    chapters: list[ChapterSnippet]
    episodes: list[EpisodeSnippet]
    budget: dict[str, Any]
    export: ExportResult | None
    files: list[ExportFile]
    play_md: str | None = None
    budget_json: dict[str, Any] | None = None


def export_root(project: Project, output_dir: Path) -> Path:
    if project.export and project.export.output_dir:
        return Path(project.export.output_dir)
    return Path(output_dir) / project.id


def safe_read_text(root: Path, relative: str) -> str | None:
    """Read ``relative`` only if it resolves inside ``root``."""
    if not relative or relative.startswith("/") or "\\" in relative:
        return None
    root_resolved = root.resolve()
    target = (root_resolved / relative).resolve()
    try:
        target.relative_to(root_resolved)
    except ValueError:
        return None
    if not target.is_file():
        return None
    text = target.read_text(encoding="utf-8")
    if len(text) > MAX_TEXT_CHARS:
        return text[:MAX_TEXT_CHARS] + "\n…(truncated)"
    return text


def _parse_json(text: str | None) -> dict[str, Any] | None:
    if not text:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def build_export_view(project: Project, output_dir: Path) -> ExportView:
    root = export_root(project, output_dir)
    files: list[ExportFile] = []
    texts: dict[str, str | None] = {}
    for name, rel, media_type in SAFE_FILES:
        text = safe_read_text(root, rel)
        texts[name] = text
        files.append(
            ExportFile(
                name=name,
                relative_path=rel,
                available=text is not None,
                media_type=media_type,
            )
        )
    budget = {
        "max_retries": project.budget.max_retries,
        "estimated_usd": project.budget.estimated_usd,
        "estimated_cny": project.budget.estimated_cny,
        "recorded_usd": project.budget.recorded_usd,
        "units": {
            "tokens": project.budget.tokens,
            "images": project.budget.images,
            "video_seconds": project.budget.video_seconds,
            "tts_chars": project.budget.tts_chars,
        },
        "layers": project.budget.layer_counts(),
        "entries": len(project.budget.entries),
    }
    return ExportView(
        project_id=project.id,
        stage=project.stage,
        shot_count=len(project.shots),
        clip_count=len(project.clips),
        chapter_count=len(project.chapters),
        chapters=[
            ChapterSnippet(
                id=ch.id,
                index=ch.index,
                title=ch.title,
                word_count=ch.word_count,
                revision=ch.revision,
            )
            for ch in project.chapters
        ],
        episodes=[
            EpisodeSnippet(
                id=ep.id,
                index=ep.index,
                title=ep.title,
                kind=ep.kind.value,
                duration_s=ep.duration_s,
                path=ep.path,
                concat_path=ep.concat_path,
                subtitle_path=ep.subtitle_path,
                clip_count=len(ep.clip_ids),
            )
            for ep in project.episodes
        ],
        budget=budget,
        export=project.export,
        files=files,
        play_md=texts.get("PLAY.md"),
        budget_json=_parse_json(texts.get("budget.json")),
    )
