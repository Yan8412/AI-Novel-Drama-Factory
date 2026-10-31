from pathlib import Path

from drama_core import PipelineStage, Project, Settings
from drama_pipeline import build_orchestrator


def test_structured_storyboard_mock_vision_e2e(tmp_path: Path) -> None:
    orch = build_orchestrator(
        Settings(output_dir=tmp_path, storyboard_engine="structured", vision_engine="mock")
    )
    p = orch.run(Project(title="契约新娘", genre="都市甜宠", premise="契约", total_words=6000))
    assert p.stage is PipelineStage.DONE, p.failure_reason
    assert p.storyboards
    assert all(2 <= len(sb.shots) <= 10 for sb in p.storyboards)
    assert all(s.aspect_ratio == "9:16" for s in p.shots)
    assert all(c.visual_lock.locked for c in p.characters)
    assert any(a.views for a in p.assets)
    assert p.export is not None
    assert (Path(p.export.output_dir) / "videos" / "clips.json").is_file()
    assert (Path(p.export.output_dir) / "episode" / "concat_full.txt").is_file()
    assert all(c.prompt for c in p.clips)
