"""JSON-serializable domain schemas shared by every package."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from drama_core.planning import DEFAULT_WORD_MAX, DEFAULT_WORD_MIN
from drama_core.text import count_words

VERTICAL_ASPECT_RATIO = "9:16"
VERTICAL_WIDTH = 1080
VERTICAL_HEIGHT = 1920
SHOT_MIN_SECONDS = 5.0
SHOT_MAX_SECONDS = 15.0


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


class Project(Model):
    id: str = Field(default_factory=lambda: new_id("proj"))
    title: str
    genre: str
    premise: str
    total_words: int = Field(gt=0)
    word_min: int = DEFAULT_WORD_MIN
    word_max: int = DEFAULT_WORD_MAX
    aspect_ratio: str = VERTICAL_ASPECT_RATIO
    width: int = VERTICAL_WIDTH
    height: int = VERTICAL_HEIGHT

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
    reviews: list[Review] = Field(default_factory=list)
    export: ExportResult | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)

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
