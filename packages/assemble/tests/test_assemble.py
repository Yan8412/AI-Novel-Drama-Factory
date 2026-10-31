from pathlib import Path

import pytest
from drama_assemble import FfmpegAssembler, MockAssembler, create_assembler
from drama_core import Chapter, Clip, Project, Settings, Shot, Storyboard


def _tiny(tmp_path: Path) -> tuple[Project, list[dict[str, object]]]:
    project = Project(title="契约", genre="都市", premise="p", total_words=3000)
    chapter = Chapter(index=1, title="一", body="字" * 20, target_words=3000)
    shot_a = Shot(index=1, chapter_id=chapter.id, duration_s=8, action="推门", dialogue="站住")
    shot_b = Shot(index=2, chapter_id=chapter.id, duration_s=10, action="回头")
    project.chapters = [chapter]
    project.storyboards = [Storyboard(chapter_id=chapter.id, shots=[shot_a, shot_b])]
    a = Clip(shot_id=shot_a.id, source_asset_id="k", uri="mock://a.mp4", duration_s=8)
    b = Clip(
        shot_id=shot_b.id,
        source_asset_id="k",
        uri="mock://b.mp4",
        duration_s=10,
        previous_clip_id=a.id,
    )
    project.clips = [a, b]
    videos = tmp_path / "videos"
    videos.mkdir()
    (videos / "a.mp4").write_bytes(b"drama-factory mock clip a")
    (videos / "b.mp4").write_bytes(b"drama-factory mock clip b")
    timeline: list[dict[str, object]] = [
        {"clip_id": a.id, "path": "videos/a.mp4"},
        {"clip_id": b.id, "path": "videos/b.mp4"},
    ]
    return project, timeline


def test_mock_assembler_writes_concat_and_stub(tmp_path: Path) -> None:
    project, timeline = _tiny(tmp_path)
    episodes = MockAssembler().assemble(project, out_dir=tmp_path, timeline=timeline)
    assert episodes
    assert (tmp_path / "episode" / "concat_full.txt").is_file()
    concat = (tmp_path / "episode" / "concat_full.txt").read_text(encoding="utf-8")
    assert "videos/a.mp4" in concat
    assert (tmp_path / "episode" / "PLAY.md").is_file()
    assert "ffmpeg -y -f concat" in (tmp_path / "episode" / "PLAY.md").read_text(encoding="utf-8")
    stub = tmp_path / (episodes[0].path or "")
    assert stub.read_bytes().startswith(b"drama-factory mock episode")
    assert (tmp_path / "episode" / "episodes.json").is_file()


def test_ffmpeg_assembler_falls_back_on_mock_stubs(tmp_path: Path) -> None:
    project, timeline = _tiny(tmp_path)
    episodes = FfmpegAssembler().assemble(project, out_dir=tmp_path, timeline=timeline)
    assert episodes
    assert (tmp_path / "episode" / "concat_full.txt").is_file()
    manifest = (tmp_path / "episode" / "episodes.json").read_text(encoding="utf-8")
    assert "ffmpeg -y -f concat" in manifest


def test_create_assembler() -> None:
    assert create_assembler(Settings()).name == "mock-assemble"
    assert create_assembler(Settings(assemble_engine="ffmpeg")).name == "ffmpeg"
    with pytest.raises(ValueError, match="ASSEMBLE_ENGINE"):
        create_assembler(Settings(assemble_engine="nope"))
