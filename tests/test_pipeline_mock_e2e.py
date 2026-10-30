"""End-to-end: project create -> export with mock engines and review records."""

import json
from pathlib import Path

from drama_core import (
    HAPPY_PATH,
    AssetKind,
    PipelineStage,
    Project,
    ReviewAction,
    ReviewTargetType,
    Settings,
)
from drama_novel import MockNovelEngine
from drama_pipeline import Orchestrator, build_orchestrator
from drama_review import DeterministicMockReviewer, RetryPolicy
from drama_storyboard import MockStoryboardEngine
from drama_video import MockVideoEngine
from drama_vision import NINE_VIEWS, MockVisionEngine

S = PipelineStage


def _project(total_words: int = 12000) -> Project:
    return Project(title="契约新娘", genre="都市甜宠", premise="契约婚姻", total_words=total_words)


def test_mock_pipeline_completes_with_review_records(tmp_path: Path) -> None:
    orch = build_orchestrator(Settings(output_dir=tmp_path))
    p = orch.run(_project())

    assert p.stage is S.DONE, p.failure_reason
    stages = [h.to_stage for h in p.stage_history]
    # every happy-path stage visited, plus one revise loop per review stage
    assert set(HAPPY_PATH[1:]) <= set(stages)
    assert stages.count(S.CHAPTERS) == 2
    assert stages.count(S.ASSETS) == 2
    assert stages.count(S.VIDEO) == 2

    assert len(p.chapters) == 3
    assert all(c.within_bounds(p.word_min, p.word_max) for c in p.chapters)
    assert all(c.revision == 1 for c in p.chapters)
    assert all(c.visual_lock.locked and c.visual_lock.nine_view_asset_id for c in p.characters)
    grids = [a for a in p.assets if a.kind is AssetKind.CHARACTER_NINE_VIEW]
    assert len(grids) == len(p.characters) and all(a.views == list(NINE_VIEWS) for a in grids)
    assert all(s.keyframe_asset_id for s in p.shots)
    assert len(p.clips) == len(p.shots) and all(
        c.width == 1080 and c.height == 1920 for c in p.clips
    )

    # every reviewed target has a revise then a pass, with stable ids across attempts
    for t, items in (
        (ReviewTargetType.CHAPTER, p.chapters),
        (ReviewTargetType.ASSET, p.assets),
        (ReviewTargetType.CLIP, p.clips),
    ):
        for item in items:
            rs = p.reviews_for(item.id)
            assert [r.action for r in rs] == [ReviewAction.REVISE, ReviewAction.PASS]
            assert [r.attempt for r in rs] == [1, 2]
            assert all(r.target_type is t for r in rs)

    assert p.export is not None
    out = Path(p.export.output_dir)
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["aspect_ratio"] == "9:16"
    assert len(manifest["timeline"]) == len(p.shots) == p.export.clip_count
    assert (out / "memory.md").exists()
    assert len(list((out / "storyboards").glob("*.md"))) == len(p.chapters)
    reloaded = Project.model_validate_json((out / "project.json").read_text(encoding="utf-8"))
    assert reloaded.stage is S.DONE and len(reloaded.reviews) == len(p.reviews)


def test_pipeline_fails_when_reviewer_never_passes(tmp_path: Path) -> None:
    orch = Orchestrator(
        novel=MockNovelEngine(),
        storyboard=MockStoryboardEngine(),
        vision=MockVisionEngine(),
        video=MockVideoEngine(),
        reviewer=DeterministicMockReviewer({ReviewTargetType.ASSET: 99}),
        policy=RetryPolicy(max_attempts=3),
        output_dir=tmp_path,
    )
    p = orch.run(_project(3000))
    assert p.stage is S.FAILED
    assert p.failure_reason and p.failure_reason.startswith("rejected")
    assert p.stage_history[-2].to_stage is S.IMAGE_REVIEW
    assert max(r.attempt for r in p.reviews if r.target_type is ReviewTargetType.ASSET) == 3
    assert p.export is None


def test_engine_errors_move_project_to_failed(tmp_path: Path) -> None:
    orch = build_orchestrator(Settings(output_dir=tmp_path, video_engine="wan"))
    p = orch.run(_project(3000))
    assert p.stage is S.FAILED
    assert p.failure_reason and "NotImplementedError" in p.failure_reason
