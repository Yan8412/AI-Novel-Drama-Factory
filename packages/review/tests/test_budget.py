from drama_core import Project, Review, ReviewAction, ReviewTargetType
from drama_review import budget_payload, estimate_usd, record_review, record_step


def test_mock_costs_are_zero() -> None:
    assert estimate_usd("mock-novel", "novel") == 0.0
    assert estimate_usd("human-override", "review") == 0.0
    assert estimate_usd("cloud-novel", "novel") > 0


def test_budget_records_retries() -> None:
    project = Project(title="t", genre="g", premise="p", total_words=3000)
    project.budget.max_retries = 3
    record_step(project, stage="novel", engine="mock-novel", note="wrote")
    record_review(
        project,
        Review(
            target_type=ReviewTargetType.CHAPTER,
            target_id="c1",
            attempt=2,
            action=ReviewAction.PASS,
            reviewer="mock-deterministic",
        ),
    )
    payload = budget_payload(project)
    layers = payload["layers"]
    assert isinstance(layers, dict)
    novel = layers["novel"]
    assert isinstance(novel, dict)
    assert payload["max_retries"] == 3
    assert payload["estimated_usd"] == 0.0
    assert novel["retries"] == 1
    assert novel["reviews"] == 2
