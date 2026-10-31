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
from drama_review import DeterministicMockReviewer, OverrideBook, RetryPolicy
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
    assert stages.count(S.STORYBOARD) == 2
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
        (ReviewTargetType.STORYBOARD, p.storyboards),
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
    assert all(item.get("path") for item in manifest["timeline"])
    assert (out / "memory.md").exists()
    assert len(list((out / "storyboards").glob("*.md"))) == len(p.chapters)
    assert list((out / "assets").glob("*.md"))
    clips_manifest = json.loads((out / "videos" / "clips.json").read_text(encoding="utf-8"))
    assert clips_manifest["clip_count"] == len(p.clips)
    assert len(list((out / "videos").glob("*.mp4"))) == len(p.clips)
    assert all(c.previous_clip_id or i == 0 for i, c in enumerate(p.clips))
    assert all("vertical 9:16" in c.prompt for c in p.clips)
    assert p.episodes and p.export is not None and p.export.episode_count == len(p.episodes)
    assert (out / "episode" / "concat_full.txt").is_file()
    assert (out / "episode" / "PLAY.md").is_file()
    assert (out / "episode" / "episodes.json").is_file()
    assert (out / "episode" / "subtitles.srt").is_file()
    assert (out / "episode" / "subtitles.vtt").is_file()
    assert len(list((out / "episode" / "tts").glob("*.json"))) == len(p.shots)
    budget = json.loads((out / "budget.json").read_text(encoding="utf-8"))
    assert budget["max_retries"] == 3
    assert budget["estimated_usd"] == 0.0
    assert budget["units"]["tokens"] > 0
    assert budget["units"]["images"] > 0
    assert "prices" in budget
    assert budget["layers"]["novel"]["retries"] >= 1
    assert budget["layers"]["image"]["retries"] >= 1
    assert budget["layers"]["video"]["retries"] >= 1
    assert manifest["episodes"]
    assert "ffmpeg" in (out / "episode" / "PLAY.md").read_text(encoding="utf-8")
    reloaded = Project.model_validate_json((out / "project.json").read_text(encoding="utf-8"))
    assert reloaded.stage is S.DONE and len(reloaded.reviews) == len(p.reviews)
    assert reloaded.budget.entries


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


def test_human_override_pass_skips_revise_loops(tmp_path: Path) -> None:
    orch = build_orchestrator(
        Settings(output_dir=tmp_path),
        overrides=OverrideBook(global_action=ReviewAction.PASS),
    )
    p = orch.run(_project(3000))
    assert p.stage is S.DONE, p.failure_reason
    stages = [h.to_stage for h in p.stage_history]
    assert stages.count(S.CHAPTERS) == 1
    assert stages.count(S.ASSETS) == 1
    assert stages.count(S.VIDEO) == 1
    assert all(r.action is ReviewAction.PASS for r in p.reviews)
    assert all(r.reviewer == "human-override" for r in p.reviews)
    assert all(c.revision == 0 for c in p.chapters)
    assert p.export is not None and p.export.episode_count >= 1


def test_engine_errors_move_project_to_failed(tmp_path: Path) -> None:
    orch = build_orchestrator(Settings(output_dir=tmp_path, video_engine="cloud"))
    p = orch.run(_project(3000))
    assert p.stage is S.FAILED
    assert p.failure_reason and "VideoError" in p.failure_reason
