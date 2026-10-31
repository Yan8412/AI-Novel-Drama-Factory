"""JSON-serializable domain schemas shared by every package."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from drama_core.genre import LicenseStatus, normalize_genre
from drama_core.planning import DEFAULT_WORD_MAX, DEFAULT_WORD_MIN
from drama_core.text import count_words

VERTICAL_ASPECT_RATIO = "9:16"
VERTICAL_WIDTH = 1080
VERTICAL_HEIGHT = 1920
SHOT_MIN_SECONDS = 5.0
SHOT_MAX_SECONDS = 15.0
EPISODE_MIN_SECONDS = 15.0
EPISODE_MAX_SECONDS = 60.0


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def utcnow() -> datetime:
    return datetime.now(UTC)


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


# --------------------------------------------------------------------------- pipeline


class PipelineStage(StrEnum):
    CREATED = "created"
    CHARACTERS = "characters"
    OUTLINE = "outline"
    CHAPTERS = "chapters"
    NOVEL_REVIEW = "novel_review"
    STORYBOARD = "storyboard"
    STORYBOARD_REVIEW = "storyboard_review"
    ASSETS = "assets"
    IMAGE_REVIEW = "image_review"
    VIDEO = "video"
    VIDEO_REVIEW = "video_review"
    EXPORT = "export"
    DONE = "done"
    FAILED = "failed"


class StageTransition(Model):
    from_stage: PipelineStage
    to_stage: PipelineStage
    reason: str = ""
    at: datetime = Field(default_factory=utcnow)


# --------------------------------------------------------------------------- characters


class CharacterIdentity(Model):
    role: str = Field(description="主角/反派/配角 等叙事角色")
    age: int | None = None
    gender: str | None = None
    occupation: str | None = None
    background: str = ""


class Appearance(Model):
    description: str
    hair: str = ""
    eyes: str = ""
    build: str = ""
    outfit: str = ""
    distinguishing_marks: list[str] = Field(default_factory=list)


class Voice(Model):
    tone: str = ""
    speech_style: str = ""
    catchphrases: list[str] = Field(default_factory=list)
    tts_voice_id: str | None = None


class Relation(Model):
    target_id: str
    kind: str = Field(description="e.g. 恋人/宿敌/师徒")
    note: str = ""


class VisualLock(Model):
    """Everything needed to keep a character visually consistent across shots."""

    seed: int | None = None
    nine_view_asset_id: str | None = None
    reference_images: list[str] = Field(default_factory=list)
    id_method: str | None = Field(default=None, description="pulid | instantid | lora | None")
    locked: bool = False


class Character(Model):
    id: str = Field(default_factory=lambda: new_id("char"))
    name: str
    identity: CharacterIdentity
    appearance: Appearance
    voice: Voice = Field(default_factory=Voice)
    arc: str = ""
    relations: list[Relation] = Field(default_factory=list)
    visual_lock: VisualLock = Field(default_factory=VisualLock)


# --------------------------------------------------------------------------- world


class Prop(Model):
    id: str = Field(default_factory=lambda: new_id("prop"))
    name: str
    description: str
    owner_character_id: str | None = None
    reference_asset_id: str | None = None


class InventoryItem(Model):
    prop_id: str
    placement: str = ""
    note: str = ""


class Scene(Model):
    id: str = Field(default_factory=lambda: new_id("scene"))
    name: str
    description: str
    time_of_day: str = ""
    inventory: list[InventoryItem] = Field(default_factory=list)
    reference_asset_id: str | None = None


# --------------------------------------------------------------------------- novel


class ChapterPlan(Model):
    index: int = Field(ge=1)
    title: str
    summary: str
    target_words: int = Field(gt=0)


class Outline(Model):
    logline: str
    chapters: list[ChapterPlan]


class MemoryDelta(Model):
    """What a chapter adds to long-term story memory (consumed by later chapters)."""

    new_facts: list[str] = Field(default_factory=list)
    character_updates: dict[str, str] = Field(default_factory=dict)
    open_threads: list[str] = Field(default_factory=list)
    closed_threads: list[str] = Field(default_factory=list)


class Chapter(Model):
    id: str = Field(default_factory=lambda: new_id("ch"))
    index: int = Field(ge=1)
    title: str
    summary: str = ""
    body: str
    word_count: int = 0
    target_words: int = Field(gt=0)
    memory_delta: MemoryDelta = Field(default_factory=MemoryDelta)
    revision: int = 0

    @model_validator(mode="after")
    def _sync_word_count(self) -> Chapter:
        actual = count_words(self.body)
        if self.word_count != actual:
            # bypass validate_assignment recursion
            object.__setattr__(self, "word_count", actual)
        return self

    def within_bounds(self, word_min: int, word_max: int) -> bool:
        return word_min <= self.word_count <= word_max


# --------------------------------------------------------------------------- storyboard


class Shot(Model):
    id: str = Field(default_factory=lambda: new_id("shot"))
    index: int = Field(ge=1)
    chapter_id: str
    scene_id: str | None = None
    character_ids: list[str] = Field(default_factory=list)
    prop_ids: list[str] = Field(default_factory=list)
    duration_s: float = Field(ge=SHOT_MIN_SECONDS, le=SHOT_MAX_SECONDS)
    camera: str = ""
    action: str = ""
    dialogue: str = ""
    image_prompt: str = ""
    motion_prompt: str = ""
    aspect_ratio: str = VERTICAL_ASPECT_RATIO
    keyframe_asset_id: str | None = None
    primary_action: str = ""
    start_state: str = ""
    end_state: str = ""
    character_lock: str = ""
    wardrobe_lock: str = ""
    scene_lock: str = ""


class Storyboard(Model):
    id: str = Field(default_factory=lambda: new_id("sb"))
    chapter_id: str
    shots: list[Shot]
    revision: int = 0

    @property
    def duration_s(self) -> float:
        return sum(s.duration_s for s in self.shots)


# --------------------------------------------------------------------------- media


class AssetKind(StrEnum):
    CHARACTER_NINE_VIEW = "character_nine_view"
    SCENE = "scene"
    PROP = "prop"
    SHOT_KEYFRAME = "shot_keyframe"


class Asset(Model):
    id: str = Field(default_factory=lambda: new_id("asset"))
    kind: AssetKind
    owner_id: str = Field(description="Character/Scene/Prop/Shot id this asset depicts")
    uri: str
    width: int = VERTICAL_WIDTH
    height: int = VERTICAL_HEIGHT
    prompt: str = ""
    views: list[str] = Field(default_factory=list, description="9-view labels for grids")
    engine: str = ""
    revision: int = 0


class Clip(Model):
    id: str = Field(default_factory=lambda: new_id("clip"))
    shot_id: str
    source_asset_id: str
    uri: str
    duration_s: float = Field(gt=0)
    width: int = VERTICAL_WIDTH
    height: int = VERTICAL_HEIGHT
    fps: int = 24
    engine: str = ""
    revision: int = 0
    prompt: str = ""
    previous_clip_id: str | None = None


class EpisodeKind(StrEnum):
    EPISODE = "episode"
    CHAPTER = "chapter"


class Episode(Model):
    """A 15–60s 9:16 package assembled from per-shot clips."""

    id: str = Field(default_factory=lambda: new_id("ep"))
    kind: EpisodeKind = EpisodeKind.EPISODE
    index: int = Field(ge=1, default=1)
    title: str = ""
    chapter_id: str | None = None
    clip_ids: list[str] = Field(default_factory=list)
    duration_s: float = Field(default=0, ge=0)
    width: int = VERTICAL_WIDTH
    height: int = VERTICAL_HEIGHT
    path: str | None = None
    concat_path: str | None = None
    subtitle_path: str | None = None
    uri: str = ""
    engine: str = ""


class CostEntry(Model):
    """One retry/cost line. Mock engines record USD zeros; units may still be estimated."""

    stage: str
    target_type: str = ""
    target_id: str = ""
    attempt: int = Field(default=1, ge=1)
    engine: str = ""
    estimated_usd: float = 0.0
    estimated_cny: float = 0.0
    recorded_usd: float = 0.0
    retries: int = 0
    note: str = ""
    at: datetime = Field(default_factory=utcnow)
    run_id: str = ""
    tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    images: int = 0
    video_seconds: float = 0.0
    tts_chars: int = 0
    currency: str = "USD"
    source: str = Field(default="estimate", description="estimate | recorded")


class BudgetLog(Model):
    """Shared retry + estimated-cost ledger for the three review layers."""

    max_retries: int = 3
    estimated_usd: float = 0.0
    estimated_cny: float = 0.0
    recorded_usd: float = 0.0
    tokens: int = 0
    images: int = 0
    video_seconds: float = 0.0
    tts_chars: int = 0
    last_run_id: str = ""
    entries: list[CostEntry] = Field(default_factory=list)

    def record(
        self,
        *,
        stage: str,
        target_type: str = "",
        target_id: str = "",
        attempt: int = 1,
        engine: str = "",
        estimated_usd: float = 0.0,
        estimated_cny: float = 0.0,
        recorded_usd: float = 0.0,
        retries: int = 0,
        note: str = "",
        run_id: str = "",
        tokens: int = 0,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        images: int = 0,
        video_seconds: float = 0.0,
        tts_chars: int = 0,
        currency: str = "USD",
        source: str = "estimate",
    ) -> CostEntry:
        entry = CostEntry(
            stage=stage,
            target_type=target_type,
            target_id=target_id,
            attempt=attempt,
            engine=engine,
            estimated_usd=estimated_usd,
            estimated_cny=estimated_cny,
            recorded_usd=recorded_usd,
            retries=retries,
            note=note,
            run_id=run_id,
            tokens=tokens,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            images=images,
            video_seconds=video_seconds,
            tts_chars=tts_chars,
            currency=currency,
            source=source,
        )
        self.entries.append(entry)
        self._recompute()
        if run_id:
            self.last_run_id = run_id
        return entry

    def _recompute(self) -> None:
        self.estimated_usd = round(sum(item.estimated_usd for item in self.entries), 6)
        self.estimated_cny = round(sum(item.estimated_cny for item in self.entries), 6)
        self.recorded_usd = round(sum(item.recorded_usd for item in self.entries), 6)
        self.tokens = sum(item.tokens for item in self.entries)
        self.images = sum(item.images for item in self.entries)
        self.video_seconds = round(sum(item.video_seconds for item in self.entries), 6)
        self.tts_chars = sum(item.tts_chars for item in self.entries)

    def layer_counts(self) -> dict[str, dict[str, float | int]]:
        layers: dict[str, dict[str, float | int]] = {}
        for entry in self.entries:
            bucket = layers.setdefault(
                entry.stage,
                {
                    "reviews": 0,
                    "retries": 0,
                    "estimated_usd": 0.0,
                    "estimated_cny": 0.0,
                    "tokens": 0,
                    "images": 0,
                    "video_seconds": 0.0,
                    "tts_chars": 0,
                },
            )
            bucket["reviews"] = int(bucket["reviews"]) + 1
            bucket["retries"] = int(bucket["retries"]) + entry.retries
            bucket["estimated_usd"] = round(float(bucket["estimated_usd"]) + entry.estimated_usd, 6)
            bucket["estimated_cny"] = round(float(bucket["estimated_cny"]) + entry.estimated_cny, 6)
            bucket["tokens"] = int(bucket["tokens"]) + entry.tokens
            bucket["images"] = int(bucket["images"]) + entry.images
            bucket["video_seconds"] = round(float(bucket["video_seconds"]) + entry.video_seconds, 6)
            bucket["tts_chars"] = int(bucket["tts_chars"]) + entry.tts_chars
        return layers

    def run_totals(self, run_id: str | None = None) -> dict[str, float | int | str]:
        wanted = run_id or self.last_run_id
        rows = [item for item in self.entries if wanted and item.run_id == wanted]
        return {
            "run_id": wanted,
            "estimated_usd": round(sum(item.estimated_usd for item in rows), 6),
            "estimated_cny": round(sum(item.estimated_cny for item in rows), 6),
            "recorded_usd": round(sum(item.recorded_usd for item in rows), 6),
            "tokens": sum(item.tokens for item in rows),
            "images": sum(item.images for item in rows),
            "video_seconds": round(sum(item.video_seconds for item in rows), 6),
            "tts_chars": sum(item.tts_chars for item in rows),
            "entries": len(rows),
        }


# --------------------------------------------------------------------------- review


class ReviewTargetType(StrEnum):
    CHAPTER = "chapter"
    STORYBOARD = "storyboard"
    ASSET = "asset"
    CLIP = "clip"


class ReviewAction(StrEnum):
    PASS = "pass"
    REVISE = "revise"
    REJECT = "reject"


class ReviewIssue(Model):
    severity: str = Field(default="minor", description="minor | major | blocker")
    message: str
    suggestion: str = ""


class Review(Model):
    id: str = Field(default_factory=lambda: new_id("rev"))
    target_type: ReviewTargetType
    target_id: str
    attempt: int = Field(ge=1)
    scores: dict[str, float] = Field(default_factory=dict)
    issues: list[ReviewIssue] = Field(default_factory=list)
    action: ReviewAction
    reviewer: str = ""
    created_at: datetime = Field(default_factory=utcnow)

    @field_validator("scores")
    @classmethod
    def _scores_in_range(cls, v: dict[str, float]) -> dict[str, float]:
        for k, s in v.items():
            if not 0.0 <= s <= 10.0:
                raise ValueError(f"score {k}={s} outside 0-10")
        return v

    @property
    def mean_score(self) -> float:
        return sum(self.scores.values()) / len(self.scores) if self.scores else 0.0


# --------------------------------------------------------------------------- project


class ExportResult(Model):
    output_dir: str
    manifest_path: str
    clip_count: int
    total_duration_s: float
    episode_count: int = 0
    episode_dir: str | None = None
    concat_path: str | None = None
    subtitle_path: str | None = None
    budget_path: str | None = None


class Project(Model):
    id: str = Field(default_factory=lambda: new_id("proj"))
    title: str
    genre: str = Field(description="都市/玄幻/古言/悬疑/甜宠/爽文 or free-text theme")
    premise: str
    total_words: int = Field(gt=0)
    word_min: int = DEFAULT_WORD_MIN
    word_max: int = DEFAULT_WORD_MAX
    aspect_ratio: str = VERTICAL_ASPECT_RATIO
    width: int = VERTICAL_WIDTH
    height: int = VERTICAL_HEIGHT
    license_status: LicenseStatus = Field(
        default=LicenseStatus.UNKNOWN,
        description="Documentation-only rights marker; not a legal claim.",
    )
    rights_note: str = Field(
        default="",
        description="Optional rights memo. Placeholder only; not a legal opinion.",
    )

    stage: PipelineStage = PipelineStage.CREATED
    stage_history: list[StageTransition] = Field(default_factory=list)
    revision_queue: list[str] = Field(
        default_factory=list, description="Target ids flagged for revision by the last review"
    )
    failure_reason: str | None = None

    characters: list[Character] = Field(default_factory=list)
    scenes: list[Scene] = Field(default_factory=list)
    props: list[Prop] = Field(default_factory=list)
    outline: Outline | None = None
    chapters: list[Chapter] = Field(default_factory=list)
    storyboards: list[Storyboard] = Field(default_factory=list)
    assets: list[Asset] = Field(default_factory=list)
    clips: list[Clip] = Field(default_factory=list)
    episodes: list[Episode] = Field(default_factory=list)
    reviews: list[Review] = Field(default_factory=list)
    budget: BudgetLog = Field(default_factory=BudgetLog)
    export: ExportResult | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)

    @field_validator("genre")
    @classmethod
    def _normalize_genre(cls, value: str) -> str:
        return normalize_genre(value)

    @model_validator(mode="after")
    def _check_bounds(self) -> Project:
        if self.word_max < self.word_min:
            raise ValueError("word_max must be >= word_min")
        return self

    @property
    def shots(self) -> list[Shot]:
        return [s for sb in self.storyboards for s in sb.shots]

    def reviews_for(self, target_id: str) -> list[Review]:
        return [r for r in self.reviews if r.target_id == target_id]
