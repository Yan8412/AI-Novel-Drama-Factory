"""Pack per-shot clips into 15–60s 9:16 episode (or chapter) groups."""

from __future__ import annotations

from dataclasses import dataclass

from drama_core import (
    EPISODE_MAX_SECONDS,
    EPISODE_MIN_SECONDS,
    Clip,
    EpisodeKind,
    Project,
)

# Keep a little slack so a 12s last shot can still join a 48s package.
_PACK_SLACK_S = 0.05


@dataclass(frozen=True)
class ClipGroup:
    kind: EpisodeKind
    title: str
    chapter_id: str | None
    clips: list[Clip]

    @property
    def duration_s(self) -> float:
        return sum(c.duration_s for c in self.clips)


def pack_clip_groups(project: Project) -> list[ClipGroup]:
    """Group clips in storyboard order, preferring chapter cuts inside 15–60s."""
    clips_by_shot = {c.shot_id: c for c in project.clips}
    chapter_runs: list[tuple[str | None, str, list[Clip]]] = []
    for chapter in project.chapters:
        shots = [s for s in project.shots if s.chapter_id == chapter.id]
        clips = [clips_by_shot[s.id] for s in shots if s.id in clips_by_shot]
        if clips:
            chapter_runs.append((chapter.id, chapter.title, clips))
    leftover = [
        c for c in project.clips if c.id not in {x.id for run in chapter_runs for x in run[2]}
    ]
    if leftover:
        chapter_runs.append((None, project.title, leftover))

    groups: list[ClipGroup] = []
    pending: list[Clip] = []
    pending_chapter: str | None = None
    pending_title = ""

    def _flush() -> None:
        nonlocal pending, pending_chapter, pending_title
        if not pending:
            return
        kind = (
            EpisodeKind.CHAPTER
            if pending_chapter and _same_chapter(project, pending, pending_chapter)
            else EpisodeKind.EPISODE
        )
        title = pending_title or project.title
        groups.append(
            ClipGroup(kind=kind, title=title, chapter_id=pending_chapter, clips=list(pending))
        )
        pending = []
        pending_chapter = None
        pending_title = ""

    for chapter_id, title, clips in chapter_runs:
        duration = sum(c.duration_s for c in clips)
        if duration > EPISODE_MAX_SECONDS + _PACK_SLACK_S:
            _flush()
            groups.extend(_split_overlong(project, chapter_id, title, clips))
            continue
        pending_dur = sum(c.duration_s for c in pending)
        if pending and pending_dur + duration > EPISODE_MAX_SECONDS + _PACK_SLACK_S:
            _flush()
        if not pending:
            pending_chapter = chapter_id
            pending_title = title
        elif pending_chapter != chapter_id:
            pending_chapter = None
            pending_title = project.title
        pending.extend(clips)
        pending_dur = sum(c.duration_s for c in pending)
        if pending_dur >= EPISODE_MIN_SECONDS:
            _flush()

    _flush()
    if not groups and project.clips:
        groups.append(
            ClipGroup(
                kind=EpisodeKind.EPISODE,
                title=project.title,
                chapter_id=None,
                clips=list(project.clips),
            )
        )
    return groups


def _same_chapter(project: Project, clips: list[Clip], chapter_id: str) -> bool:
    shot_chapter = {s.id: s.chapter_id for s in project.shots}
    return all(shot_chapter.get(c.shot_id) == chapter_id for c in clips)


def _split_overlong(
    project: Project, chapter_id: str | None, title: str, clips: list[Clip]
) -> list[ClipGroup]:
    groups: list[ClipGroup] = []
    chunk: list[Clip] = []
    for clip in clips:
        next_dur = sum(c.duration_s for c in chunk) + clip.duration_s
        if chunk and next_dur > EPISODE_MAX_SECONDS + _PACK_SLACK_S:
            groups.append(
                ClipGroup(
                    kind=EpisodeKind.EPISODE,
                    title=title,
                    chapter_id=chapter_id,
                    clips=list(chunk),
                )
            )
            chunk = []
        chunk.append(clip)
    if chunk:
        groups.append(
            ClipGroup(
                kind=EpisodeKind.EPISODE if len(groups) else EpisodeKind.CHAPTER,
                title=title,
                chapter_id=chapter_id,
                clips=list(chunk),
            )
        )
    return groups


def ffmpeg_concat_command(concat_path: str, output_path: str) -> str:
    return (
        f"ffmpeg -y -f concat -safe 0 -i {concat_path} -c copy -movflags +faststart {output_path}"
    )
