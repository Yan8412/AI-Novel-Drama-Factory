from drama_core import Settings
from drama_novel import CloudNovelEngine, MockNovelEngine
from drama_pipeline import build_orchestrator
from drama_review import DeterministicMockReviewer, LlmJudgeReviewer


def test_build_orchestrator_defaults_to_mock() -> None:
    orch = build_orchestrator(Settings())
    assert isinstance(orch.novel, MockNovelEngine)
    assert isinstance(orch.reviewer, DeterministicMockReviewer)


def test_build_orchestrator_selects_cloud_and_llm_judge() -> None:
    orch = build_orchestrator(Settings(novel_engine="cloud", review_engine="llm_judge"))
    assert isinstance(orch.novel, CloudNovelEngine)
    assert isinstance(orch.reviewer, LlmJudgeReviewer)
