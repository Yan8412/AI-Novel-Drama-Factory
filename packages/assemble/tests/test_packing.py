from drama_assemble import ffmpeg_concat_command, pack_clip_groups
from drama_core import (
    Chapter,
    Clip,
    EpisodeKind,
    Project,
    Shot,
    Storyboard,
)


def _project_with_clips(chapter_durs: list[list[float]]) -> Project:
    project = Project(title="t", genre="g", premise="p", total_words=6000)
    chapters: list[Chapter] = []
    boards: list[Storyboard] = []
    clips: list[Clip] = []
    prev: str | None = None
    for i, durs in enumerate(chapter_durs, start=1):
        chapter = Chapter(index=i, title=f"第{i}章", body="字" * 20, target_words=3000)
        chapters.append(chapter)
        shots: list[Shot] = []
        for j, dur in enumerate(durs, start=1):
            shot = Shot(
                index=j,
                chapter_id=chapter.id,
                duration_s=min(max(dur, 5), 15),
                action="走",
            )
            shots.append(shot)
            clip = Clip(
                shot_id=shot.id,
                source_asset_id="a",
                uri=f"mock://video/{i}_{j}.mp4",
                duration_s=dur,
                previous_clip_id=prev,
            )
            clips.append(clip)
            prev = clip.id
        boards.append(Storyboard(chapter_id=chapter.id, shots=shots))
    project.chapters = chapters
    project.storyboards = boards
    project.clips = clips
    return project


def test_pack_prefers_chapter_packages_inside_band() -> None:
    project = _project_with_clips([[8, 8, 8], [10, 10], [12, 12]])
    groups = pack_clip_groups(project)
    assert [g.kind for g in groups] == [EpisodeKind.CHAPTER] * 3
    assert [round(g.duration_s) for g in groups] == [24, 20, 24]


def test_pack_merges_short_chapters() -> None:
    project = _project_with_clips([[6, 6], [6, 6]])
    groups = pack_clip_groups(project)
    assert len(groups) == 1
    assert groups[0].kind is EpisodeKind.EPISODE
    assert groups[0].duration_s == 24


def test_pack_splits_overlong_chapter() -> None:
    project = _project_with_clips([[15, 15, 15, 15, 15]])
    groups = pack_clip_groups(project)
    assert len(groups) == 2
    assert all(g.duration_s <= 60 for g in groups)
    assert sum(g.duration_s for g in groups) == 75


def test_ffmpeg_command_is_copy_concat() -> None:
    cmd = ffmpeg_concat_command("episode/concat_full.txt", "episode/full.mp4")
    assert cmd.startswith("ffmpeg -y -f concat -safe 0")
    assert "-c copy" in cmd
    assert "episode/full.mp4" in cmd
