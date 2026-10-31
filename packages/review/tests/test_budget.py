from drama_core import Project, Review, ReviewAction, ReviewTargetType, Settings, UsageUnits
from drama_review import (
    PriceBook,
    aggregate_usage,
    budget_payload,
    estimate_usd,
    evaluate_quota,
    is_free_engine,
    record_review,
    record_step,
    uses_paid_engines,
)


def test_mock_costs_are_zero() -> None:
    assert estimate_usd("mock-novel", "novel") == 0.0
    assert estimate_usd("human-override", "review") == 0.0
    assert estimate_usd("cloud-novel", "novel") > 0
    assert is_free_engine("structured")
    assert is_free_engine("comfyui")
    assert not is_free_engine("cloud-novel")
    assert not is_free_engine("llm-judge")


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
    assert payload["estimated_cny"] == 0.0
    assert novel["retries"] == 1
    assert novel["reviews"] == 2


def test_recorded_tokens_use_unit_prices() -> None:
    project = Project(title="t", genre="g", premise="p", total_words=3000)
    project.metadata["last_run_id"] = "run_test"
    prices = PriceBook(token_per_1k_usd=1.0, fx_cny_per_usd=7.0)
    record_step(
        project,
        stage="novel",
        engine="cloud-novel",
        note="wrote",
        usage=UsageUnits(tokens=2000, prompt_tokens=1200, completion_tokens=800, source="recorded"),
        prices=prices,
    )
    assert project.budget.tokens == 2000
    assert project.budget.estimated_usd == 2.0
    assert project.budget.estimated_cny == 14.0
    assert project.budget.recorded_usd == 2.0
    assert project.budget.entries[0].source == "recorded"
    assert project.budget.entries[0].run_id == "run_test"
    assert project.budget.run_totals()["tokens"] == 2000


def test_quota_blocks_only_paid_engines() -> None:
    settings = Settings(quota_max_usd=0.0, quota_soft_usd=0.0, novel_engine="cloud")
    hard = evaluate_quota(settings, 0.0)
    assert hard.hard_exceeded
    assert hard.blocked
    assert uses_paid_engines(settings)
    mock = evaluate_quota(Settings(quota_max_usd=0.0), 0.0)
    assert mock.hard_exceeded
    assert not mock.blocked
    assert mock.warning


def test_aggregate_usage_sums_projects() -> None:
    a = Project(title="a", genre="g", premise="p", total_words=3000)
    b = Project(title="b", genre="g", premise="p", total_words=3000)
    prices = PriceBook(image_usd=0.5)
    record_step(
        a,
        stage="vision",
        engine="cloud-vision",
        usage=UsageUnits(images=2, source="recorded"),
        prices=prices,
    )
    record_step(b, stage="novel", engine="mock-novel")
    payload = aggregate_usage([a, b], settings=Settings())
    assert payload["estimated_usd"] == 1.0
    units = payload["units"]
    assert isinstance(units, dict)
    assert units["images"] == 2
    rows = payload["projects"]
    assert isinstance(rows, list)
    first = rows[0]
    assert isinstance(first, dict)
    assert first["title"] == "a"
