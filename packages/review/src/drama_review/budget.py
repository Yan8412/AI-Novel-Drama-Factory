"""Estimated + recorded cost ledger. Mock engines always record USD zeros."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from drama_core import (
    BudgetLog,
    CostEntry,
    Project,
    Review,
    Settings,
    UsageUnits,
    drain_engine_usage,
)

# Rough USD guesses so a cloud run has a non-zero budget without usage data.
_STAGE_USD: dict[str, float] = {
    "novel": 0.02,
    "storyboard": 0.01,
    "vision": 0.04,
    "video": 0.10,
    "review": 0.002,
    "tts": 0.015,
    "assemble": 0.0,
}

DEFAULT_PRICE_TOKEN_PER_1K_USD = 0.00015
DEFAULT_PRICE_IMAGE_USD = 0.04
DEFAULT_PRICE_VIDEO_PER_SECOND_USD = 0.10
DEFAULT_PRICE_TTS_PER_1K_CHARS_USD = 0.015
DEFAULT_FX_CNY_PER_USD = 7.2

_FREE_NAMES = {
    "off",
    "structured",
    "ffmpeg",
    "comfy",
    "comfyui",
    "wan",
    "passthrough",
    "human-override",
}


def is_free_engine(engine: str) -> bool:
    name = (engine or "").lower()
    if not name or "mock" in name:
        return True
    if name in _FREE_NAMES:
        return True
    return name.startswith("llm-judge-media")


def uses_paid_engines(settings: Settings) -> bool:
    return any(
        not is_free_engine(value)
        for value in (
            settings.novel_engine,
            settings.review_engine,
            settings.storyboard_engine,
            settings.vision_engine,
            settings.video_engine,
            settings.tts_engine,
        )
    )


@dataclass(frozen=True)
class PriceBook:
    token_per_1k_usd: float = DEFAULT_PRICE_TOKEN_PER_1K_USD
    image_usd: float = DEFAULT_PRICE_IMAGE_USD
    video_per_second_usd: float = DEFAULT_PRICE_VIDEO_PER_SECOND_USD
    tts_per_1k_chars_usd: float = DEFAULT_PRICE_TTS_PER_1K_CHARS_USD
    fx_cny_per_usd: float = DEFAULT_FX_CNY_PER_USD
    currency: str = "USD"

    @classmethod
    def from_settings(cls, settings: Settings) -> PriceBook:
        currency = (settings.quota_currency or "USD").strip().upper() or "USD"
        if currency not in {"USD", "CNY"}:
            currency = "USD"
        return cls(
            token_per_1k_usd=float(settings.price_token_per_1k_usd),
            image_usd=float(settings.price_image_usd),
            video_per_second_usd=float(settings.price_video_per_second_usd),
            tts_per_1k_chars_usd=float(settings.price_tts_per_1k_chars_usd),
            fx_cny_per_usd=float(settings.fx_cny_per_usd),
            currency=currency,
        )

    @classmethod
    def from_payload(cls, data: dict[str, Any] | None) -> PriceBook:
        if not data:
            return cls()
        currency = str(data.get("currency") or "USD").strip().upper() or "USD"
        if currency not in {"USD", "CNY"}:
            currency = "USD"
        return cls(
            token_per_1k_usd=float(data.get("token_per_1k_usd") or DEFAULT_PRICE_TOKEN_PER_1K_USD),
            image_usd=float(data.get("image_usd") or DEFAULT_PRICE_IMAGE_USD),
            video_per_second_usd=float(
                data.get("video_per_second_usd") or DEFAULT_PRICE_VIDEO_PER_SECOND_USD
            ),
            tts_per_1k_chars_usd=float(
                data.get("tts_per_1k_chars_usd") or DEFAULT_PRICE_TTS_PER_1K_CHARS_USD
            ),
            fx_cny_per_usd=float(data.get("fx_cny_per_usd") or DEFAULT_FX_CNY_PER_USD),
            currency=currency,
        )

    def to_payload(self) -> dict[str, float | str]:
        return {
            "token_per_1k_usd": self.token_per_1k_usd,
            "image_usd": self.image_usd,
            "video_per_second_usd": self.video_per_second_usd,
            "tts_per_1k_chars_usd": self.tts_per_1k_chars_usd,
            "fx_cny_per_usd": self.fx_cny_per_usd,
            "currency": self.currency,
        }

    def to_cny(self, usd: float) -> float:
        return round(float(usd) * self.fx_cny_per_usd, 6)

    def cost_usd(self, units: UsageUnits, *, engine: str, stage: str) -> float:
        if is_free_engine(engine):
            return 0.0
        usd = (
            units.normalized_tokens() / 1000.0 * self.token_per_1k_usd
            + units.images * self.image_usd
            + units.video_seconds * self.video_per_second_usd
            + units.tts_chars / 1000.0 * self.tts_per_1k_chars_usd
        )
        if usd <= 0:
            usd = _STAGE_USD.get(stage, 0.0)
        return round(usd, 6)


@dataclass(frozen=True)
class QuotaStatus:
    currency: str
    soft_usd: float | None
    max_usd: float | None
    estimated_usd: float
    estimated_cny: float
    soft_exceeded: bool
    hard_exceeded: bool
    warning: str | None
    paid_engines: bool
    blocked: bool

    def to_payload(self) -> dict[str, object]:
        return {
            "currency": self.currency,
            "soft_usd": self.soft_usd,
            "max_usd": self.max_usd,
            "estimated_usd": self.estimated_usd,
            "estimated_cny": self.estimated_cny,
            "soft_exceeded": self.soft_exceeded,
            "hard_exceeded": self.hard_exceeded,
            "warning": self.warning,
            "paid_engines": self.paid_engines,
            "blocked": self.blocked,
        }


def evaluate_quota(
    settings: Settings,
    estimated_usd: float,
    *,
    prices: PriceBook | None = None,
) -> QuotaStatus:
    book = prices or PriceBook.from_settings(settings)
    paid = uses_paid_engines(settings)
    soft = settings.quota_soft_usd
    hard = settings.quota_max_usd
    soft_hit = soft is not None and estimated_usd >= soft
    hard_hit = hard is not None and estimated_usd >= hard
    warning: str | None = None
    if hard_hit:
        warning = (
            f"已达到硬配额 QUOTA_MAX_USD={hard:g}（当前估算 ${estimated_usd:g}）。"
            "付费 live 引擎将拒绝入队；mock 仍可跑。"
        )
    elif soft_hit:
        warning = (
            f"已达到软配额 QUOTA_SOFT_USD={soft:g}（当前估算 ${estimated_usd:g}）。"
            "后续 live 调用会产生费用。"
        )
    return QuotaStatus(
        currency=book.currency,
        soft_usd=soft,
        max_usd=hard,
        estimated_usd=round(estimated_usd, 6),
        estimated_cny=book.to_cny(estimated_usd),
        soft_exceeded=soft_hit,
        hard_exceeded=hard_hit,
        warning=warning,
        paid_engines=paid,
        blocked=hard_hit and paid,
    )


def prices_for(project: Project, prices: PriceBook | None = None) -> PriceBook:
    if prices is not None:
        return prices
    raw = project.metadata.get("billing")
    if isinstance(raw, dict):
        return PriceBook.from_payload(raw)
    return PriceBook()


def infer_units(project: Project, stage: str) -> UsageUnits:
    if stage == "novel":
        tokens = sum(ch.word_count for ch in project.chapters)
        return UsageUnits(tokens=tokens, prompt_tokens=tokens, source="estimate")
    if stage == "storyboard":
        tokens = max(0, len(project.shots)) * 180
        return UsageUnits(tokens=tokens, source="estimate")
    if stage in {"vision", "image"}:
        return UsageUnits(images=max(0, len(project.assets)), source="estimate")
    if stage == "video":
        seconds = sum(clip.duration_s for clip in project.clips)
        return UsageUnits(video_seconds=round(seconds, 6), source="estimate")
    if stage == "tts":
        chars = 0
        for shot in project.shots:
            chars += len((shot.dialogue or shot.action or "").strip())
        return UsageUnits(tts_chars=chars, source="estimate")
    if stage == "review":
        return UsageUnits(tokens=400, source="estimate")
    return UsageUnits()


def collect_usage(engine: object | None, estimated: UsageUnits) -> UsageUnits:
    recorded = drain_engine_usage(engine) if engine is not None else None
    if recorded is not None and recorded.has_values():
        recorded.source = "recorded"
        return recorded
    if not estimated.source:
        estimated.source = "estimate"
    return estimated


def estimate_usd(
    engine: str,
    stage: str,
    *,
    prices: PriceBook | None = None,
    units: UsageUnits | None = None,
) -> float:
    book = prices or PriceBook()
    return book.cost_usd(units or UsageUnits(), engine=engine, stage=stage)


def _run_id(project: Project) -> str:
    raw = project.metadata.get("last_run_id")
    return str(raw) if raw else project.budget.last_run_id


def record_review(
    project: Project,
    review: Review,
    *,
    engine: str = "",
    usage: UsageUnits | None = None,
    prices: PriceBook | None = None,
    engine_obj: object | None = None,
) -> CostEntry:
    retries = max(0, review.attempt - 1)
    name = engine or review.reviewer
    book = prices_for(project, prices)
    estimated = usage or (UsageUnits() if is_free_engine(name) else infer_units(project, "review"))
    units = collect_usage(engine_obj, estimated)
    usd = estimate_usd(name, "review", prices=book, units=units)
    recorded_usd = usd if units.source == "recorded" else 0.0
    return project.budget.record(
        stage=_layer_for(review.target_type.value),
        target_type=review.target_type.value,
        target_id=review.target_id,
        attempt=review.attempt,
        engine=name,
        estimated_usd=usd,
        estimated_cny=book.to_cny(usd),
        recorded_usd=recorded_usd,
        retries=retries,
        note=review.action.value,
        run_id=_run_id(project),
        tokens=units.normalized_tokens(),
        prompt_tokens=units.prompt_tokens,
        completion_tokens=units.completion_tokens,
        images=units.images,
        video_seconds=units.video_seconds,
        tts_chars=units.tts_chars,
        currency=book.currency,
        source=units.source,
    )


def record_step(
    project: Project,
    *,
    stage: str,
    engine: str,
    target_id: str = "",
    attempt: int = 1,
    note: str = "",
    usage: UsageUnits | None = None,
    prices: PriceBook | None = None,
    engine_obj: object | None = None,
) -> CostEntry:
    book = prices_for(project, prices)
    estimated = usage or infer_units(project, stage)
    units = collect_usage(engine_obj, estimated)
    usd = estimate_usd(engine, stage, prices=book, units=units)
    recorded_usd = usd if units.source == "recorded" else 0.0
    return project.budget.record(
        stage=stage,
        target_id=target_id,
        attempt=attempt,
        engine=engine,
        estimated_usd=usd,
        estimated_cny=book.to_cny(usd),
        recorded_usd=recorded_usd,
        retries=max(0, attempt - 1),
        note=note,
        run_id=_run_id(project),
        tokens=units.normalized_tokens(),
        prompt_tokens=units.prompt_tokens,
        completion_tokens=units.completion_tokens,
        images=units.images,
        video_seconds=units.video_seconds,
        tts_chars=units.tts_chars,
        currency=book.currency,
        source=units.source,
    )


def units_payload(log: BudgetLog) -> dict[str, float | int]:
    return {
        "tokens": log.tokens,
        "images": log.images,
        "video_seconds": log.video_seconds,
        "tts_chars": log.tts_chars,
    }


def budget_payload(
    project: Project,
    *,
    prices: PriceBook | None = None,
    quota: QuotaStatus | None = None,
) -> dict[str, object]:
    log: BudgetLog = project.budget
    book = prices_for(project, prices)
    return {
        "project_id": project.id,
        "max_retries": log.max_retries,
        "estimated_usd": log.estimated_usd,
        "estimated_cny": log.estimated_cny,
        "recorded_usd": log.recorded_usd,
        "currency": book.currency,
        "units": units_payload(log),
        "layers": log.layer_counts(),
        "last_run": log.run_totals(),
        "prices": book.to_payload(),
        "quota": None if quota is None else quota.to_payload(),
        "entries": [e.model_dump(mode="json") for e in log.entries],
    }


def aggregate_usage(
    projects: list[Project],
    *,
    settings: Settings,
) -> dict[str, object]:
    book = PriceBook.from_settings(settings)
    estimated = round(sum(item.budget.estimated_usd for item in projects), 6)
    estimated_cny = round(sum(item.budget.estimated_cny for item in projects), 6)
    if estimated_cny <= 0 and estimated > 0:
        estimated_cny = book.to_cny(estimated)
    recorded = round(sum(item.budget.recorded_usd for item in projects), 6)
    tokens = sum(item.budget.tokens for item in projects)
    images = sum(item.budget.images for item in projects)
    video_seconds = round(sum(item.budget.video_seconds for item in projects), 6)
    tts_chars = sum(item.budget.tts_chars for item in projects)
    quota = evaluate_quota(settings, estimated, prices=book)
    rows: list[dict[str, object]] = [
        {
            "id": item.id,
            "title": item.title,
            "stage": item.stage.value,
            "estimated_usd": item.budget.estimated_usd,
            "estimated_cny": item.budget.estimated_cny or book.to_cny(item.budget.estimated_usd),
            "recorded_usd": item.budget.recorded_usd,
            "units": units_payload(item.budget),
            "entries": len(item.budget.entries),
        }
        for item in projects
    ]

    def _usd(row: dict[str, object]) -> float:
        value = row.get("estimated_usd", 0.0)
        return value if isinstance(value, (int, float)) else 0.0

    rows.sort(key=_usd, reverse=True)
    return {
        "currency": book.currency,
        "estimated_usd": estimated,
        "estimated_cny": estimated_cny,
        "recorded_usd": recorded,
        "units": {
            "tokens": tokens,
            "images": images,
            "video_seconds": video_seconds,
            "tts_chars": tts_chars,
        },
        "projects": rows,
        "prices": book.to_payload(),
        "quota": quota.to_payload(),
        "paid_engines": quota.paid_engines,
    }


def _layer_for(target_type: str) -> str:
    if target_type == "chapter":
        return "novel"
    if target_type == "asset":
        return "image"
    if target_type == "clip":
        return "video"
    return target_type
