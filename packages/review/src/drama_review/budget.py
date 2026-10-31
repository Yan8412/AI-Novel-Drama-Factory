"""Estimated cost + retry ledger. Mock engines always record zeros."""

from __future__ import annotations

from drama_core import BudgetLog, CostEntry, Project, Review

# Rough USD guesses so a cloud run has a non-zero budget without billing APIs.
_STAGE_USD: dict[str, float] = {
    "novel": 0.02,
    "storyboard": 0.01,
    "vision": 0.04,
    "video": 0.10,
    "review": 0.002,
    "tts": 0.015,
    "assemble": 0.0,
}


def estimate_usd(engine: str, stage: str) -> float:
    name = (engine or "").lower()
    if not name or "mock" in name or name in {"off", "passthrough", "human-override"}:
        return 0.0
    if name.startswith("llm-judge-media"):
        return 0.0
    return _STAGE_USD.get(stage, 0.0)


def record_review(project: Project, review: Review, *, engine: str = "") -> CostEntry:
    retries = max(0, review.attempt - 1)
    usd = estimate_usd(engine or review.reviewer, "review")
    return project.budget.record(
        stage=_layer_for(review.target_type.value),
        target_type=review.target_type.value,
        target_id=review.target_id,
        attempt=review.attempt,
        engine=engine or review.reviewer,
        estimated_usd=usd,
        retries=retries,
        note=review.action.value,
    )


def record_step(
    project: Project,
    *,
    stage: str,
    engine: str,
    target_id: str = "",
    attempt: int = 1,
    note: str = "",
) -> CostEntry:
    return project.budget.record(
        stage=stage,
        target_id=target_id,
        attempt=attempt,
        engine=engine,
        estimated_usd=estimate_usd(engine, stage),
        retries=max(0, attempt - 1),
        note=note,
    )


def budget_payload(project: Project) -> dict[str, object]:
    log: BudgetLog = project.budget
    return {
        "max_retries": log.max_retries,
        "estimated_usd": log.estimated_usd,
        "layers": log.layer_counts(),
        "entries": [e.model_dump(mode="json") for e in log.entries],
    }


def _layer_for(target_type: str) -> str:
    if target_type == "chapter":
        return "novel"
    if target_type == "asset":
        return "image"
    if target_type == "clip":
        return "video"
    return target_type
