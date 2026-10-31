from drama_core import Settings
from drama_novel import CloudNovelEngine, MockNovelEngine
from drama_pipeline import build_orchestrator
from drama_review import DeterministicMockReviewer, LlmJudgeReviewer
from drama_storyboard import CloudStoryboardEngine, MockStoryboardEngine, StructuredStoryboardEngine
from drama_video import CloudVideoEngine, ComfyUIVideoEngine, MockVideoEngine, WanVideoEngine
from drama_vision import CloudVisionEngine, ComfyUIVisionEngine, MockVisionEngine


def test_build_orchestrator_defaults_to_mock() -> None:
    orch = build_orchestrator(Settings())
    assert isinstance(orch.novel, MockNovelEngine)
    assert isinstance(orch.reviewer, DeterministicMockReviewer)
    assert isinstance(orch.storyboard, MockStoryboardEngine)
    assert isinstance(orch.vision, MockVisionEngine)
    assert isinstance(orch.video, MockVideoEngine)


def test_build_orchestrator_selects_cloud_and_llm_judge() -> None:
    orch = build_orchestrator(Settings(novel_engine="cloud", review_engine="llm_judge"))
    assert isinstance(orch.novel, CloudNovelEngine)
    assert isinstance(orch.reviewer, LlmJudgeReviewer)


def test_build_orchestrator_selects_phase2_engines() -> None:
    structured = build_orchestrator(Settings(storyboard_engine="structured", vision_engine="cloud"))
    assert isinstance(structured.storyboard, StructuredStoryboardEngine)
    assert isinstance(structured.vision, CloudVisionEngine)
    cloud_sb = build_orchestrator(Settings(storyboard_engine="cloud", vision_engine="comfy"))
    assert isinstance(cloud_sb.storyboard, CloudStoryboardEngine)
    assert isinstance(cloud_sb.vision, ComfyUIVisionEngine)
    video_cloud = build_orchestrator(Settings(video_engine="cloud"))
    assert isinstance(video_cloud.video, CloudVideoEngine)
    video_comfy = build_orchestrator(Settings(video_engine="comfy"))
    assert isinstance(video_comfy.video, ComfyUIVideoEngine)
    video_wan = build_orchestrator(Settings(video_engine="wan"))
    assert isinstance(video_wan.video, WanVideoEngine)
