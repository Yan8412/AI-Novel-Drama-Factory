from pathlib import Path

from drama_core import Chapter, Clip, Project, Shot, Storyboard
from drama_tts import MockSubtitleEngine, build_cues, render_srt, render_vtt


def _project() -> Project:
    project = Project(title="t", genre="g", premise="p", total_words=3000)
    chapter = Chapter(index=1, title="一", body="字" * 10, target_words=3000)
    shot = Shot(
        index=1,
        chapter_id=chapter.id,
        duration_s=8,
        action="对峙",
        dialogue="“这一次，我不会再退。”",
    )
    silent = Shot(index=2, chapter_id=chapter.id, duration_s=6, action="转身离开")
    project.chapters = [chapter]
    project.storyboards = [Storyboard(chapter_id=chapter.id, shots=[shot, silent])]
    project.clips = [
        Clip(shot_id=shot.id, source_asset_id="a", uri="mock://a", duration_s=8),
        Clip(shot_id=silent.id, source_asset_id="a", uri="mock://b", duration_s=6),
    ]
    return project


def test_cues_use_dialogue_then_action() -> None:
    cues = build_cues(_project())
    assert len(cues) == 2
    assert cues[0].text.startswith("“这一次")
    assert cues[0].start_s == 0
    assert cues[0].end_s == 8
    assert cues[1].text == "（转身离开）"
    assert cues[1].start_s == 8
    assert cues[1].end_s == 14


def test_srt_and_vtt_roundtrip() -> None:
    cues = build_cues(_project())
    srt = render_srt(cues)
    assert "00:00:00,000 --> 00:00:08,000" in srt
    assert "这一次" in srt
    vtt = render_vtt(cues)
    assert vtt.startswith("WEBVTT")
    assert "00:00:08.000 --> 00:00:14.000" in vtt


def test_mock_subtitle_engine_writes_both(tmp_path: Path) -> None:
    paths = MockSubtitleEngine("both").write_track(_project(), _project().shots, out_dir=tmp_path)
    names = {p.name for p in paths}
    assert names == {"subtitles.srt", "subtitles.vtt"}
    assert (tmp_path / "episode" / "subtitles.srt").read_text(encoding="utf-8")
