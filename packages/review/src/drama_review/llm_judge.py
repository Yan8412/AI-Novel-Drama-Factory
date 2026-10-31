"""LLM-as-judge reviewer: structured JSON verdict plus deterministic rules."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence

from drama_core import Review, ReviewAction, ReviewIssue, ReviewTargetType, UsageUnits
from drama_llm import ChatClient, JsonExtractError, LlmClient, LlmConfig, LlmError, extract_json
from pydantic import BaseModel, ConfigDict, Field, field_validator

from drama_review.contracts import ReviewRequest
from drama_review.rules import banlist_issues, word_count_band_score, word_count_issues

NOVEL_DIMENSIONS: tuple[str, ...] = (
    "coherence",
    "character_consistency",
    "word_count_band",
    "sensitive_content",
)

_MEDIA_DIMENSIONS: Mapping[ReviewTargetType, tuple[str, ...]] = {
    ReviewTargetType.ASSET: ("identity_consistency", "composition", "artifact_free"),
    ReviewTargetType.CLIP: ("motion_quality", "identity_consistency", "temporal_coherence"),
}


class JudgeIssueDraft(BaseModel):
    model_config = ConfigDict(extra="ignore")
    severity: str = "minor"
    message: str
    suggestion: str = ""

    @field_validator("severity", mode="before")
    @classmethod
    def _severity(cls, value: object) -> str:
        text = str(value or "minor").strip().lower()
        return text if text in {"minor", "major", "blocker"} else "minor"


class JudgePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    scores: dict[str, float] = Field(default_factory=dict)
    issues: list[JudgeIssueDraft] = Field(default_factory=list)
    action: str = "revise"

    @field_validator("issues", mode="before")
    @classmethod
    def _issues(cls, value: object) -> object:
        if isinstance(value, list) and value and all(isinstance(item, str) for item in value):
            return [{"message": item} for item in value]
        return value

    @field_validator("scores", mode="before")
    @classmethod
    def _scores(cls, value: object) -> object:
        if not isinstance(value, dict):
            return {}
        clamped: dict[str, float] = {}
        for key, raw in value.items():
            try:
                score = float(raw)
            except (TypeError, ValueError):
                continue
            clamped[str(key)] = max(0.0, min(10.0, score))
        return clamped


def parse_judge_payload(text: str) -> JudgePayload:
    """Parse an LLM judge blob (raw JSON, fences, or prose-wrapped JSON)."""
    data = extract_json(text)
    if not isinstance(data, dict):
        raise JsonExtractError("judge payload must be a JSON object")
    return JudgePayload.model_validate(data)


def parse_action(raw: str) -> ReviewAction:
    try:
        return ReviewAction(raw.strip().lower())
    except ValueError:
        return ReviewAction.REVISE


class LlmJudgeReviewer:
    """Scores chapters, storyboards, assets and real clips with a cloud LLM.

    Mock image/video placeholders (``mock://``) stay auto-pass so CI never needs pixels.
    """

    name = "llm-judge"

    def __init__(
        self,
        client: ChatClient | None = None,
        *,
        config: LlmConfig | None = None,
        banlist: Sequence[str] | None = None,
    ) -> None:
        self._client = client
        self._config = config
        if banlist is not None:
            self.banlist = tuple(banlist)
        else:
            extra = os.environ.get("REVIEW_BANLIST", "")
            self.banlist = tuple(part.strip() for part in extra.split(",") if part.strip())

    @property
    def client(self) -> ChatClient:
        if self._client is None:
            self._client = LlmClient(self._config or LlmConfig.from_env(model_var="REVIEW_MODEL"))
        return self._client

    def drain_usage(self) -> UsageUnits:
        drain = getattr(self._client, "drain_usage", None)
        if not callable(drain):
            return UsageUnits()
        used = drain()
        prompt = int(getattr(used, "prompt_tokens", 0) or 0)
        completion = int(getattr(used, "completion_tokens", 0) or 0)
        total = int(getattr(used, "total_tokens", 0) or 0) or (prompt + completion)
        return UsageUnits(
            tokens=total,
            prompt_tokens=prompt,
            completion_tokens=completion,
            source="recorded" if total else "estimate",
        )

    def review(self, request: ReviewRequest) -> Review:
        if request.target_type in {ReviewTargetType.ASSET, ReviewTargetType.CLIP} and (
            request.content.startswith("mock://")
        ):
            return _media_passthrough(request)
        if request.target_type in {
            ReviewTargetType.CHAPTER,
            ReviewTargetType.STORYBOARD,
            ReviewTargetType.ASSET,
            ReviewTargetType.CLIP,
        }:
            return self._judge_text(request)
        return _media_passthrough(request)

    def _judge_text(self, request: ReviewRequest) -> Review:
        payload = self._judge_payload(request)
        scores = {dim: float(payload.scores.get(dim, 0.0)) for dim in _dimensions(request)}
        issues = [
            ReviewIssue(severity=i.severity, message=i.message, suggestion=i.suggestion)
            for i in payload.issues
        ]
        action = parse_action(payload.action)
        issues.extend(self._rule_issues(request, scores))
        if any(i.severity == "blocker" for i in issues) and action is ReviewAction.PASS:
            action = ReviewAction.REVISE
        return Review(
            target_type=request.target_type,
            target_id=request.target_id,
            attempt=request.attempt,
            scores=scores,
            issues=issues,
            action=action,
            reviewer=self.name,
        )

    def _judge_payload(self, request: ReviewRequest) -> JudgePayload:
        raw = self.client.chat(
            [
                {
                    "role": "system",
                    "content": (
                        "你是竖屏短剧审核编辑（LLM-as-judge）。只返回 JSON："
                        '{"scores": {dimension: 0-10}, "issues": '
                        '[{"severity": "minor|major|blocker", "message": str, "suggestion": str}],'
                        ' "action": "pass"|"revise"|"reject"}。'
                        "分数越高越好。sensitive_content：10 表示无敏感问题。"
                        f"必评维度：{', '.join(_dimensions(request))}。"
                    ),
                },
                {"role": "user", "content": _text_judge_prompt(request)},
            ],
            temperature=0.1,
            json_mode=True,
        )
        try:
            return parse_judge_payload(raw)
        except (JsonExtractError, ValueError) as exc:
            raise LlmError(f"judge JSON parse failed: {exc}") from exc

    def _rule_issues(self, request: ReviewRequest, scores: dict[str, float]) -> list[ReviewIssue]:
        issues: list[ReviewIssue] = []
        word_min = request.context.get("word_min")
        word_max = request.context.get("word_max")
        if isinstance(word_min, int) and isinstance(word_max, int):
            issues.extend(word_count_issues(request.content, word_min, word_max))
            scores["word_count_band"] = word_count_band_score(request.content, word_min, word_max)
        issues.extend(banlist_issues(request.content, self.banlist))
        return issues


_STORYBOARD_DIMENSIONS: tuple[str, ...] = (
    "pacing",
    "coverage",
    "vertical_framing",
    "continuity",
)


def _dimensions(request: ReviewRequest) -> tuple[str, ...]:
    rubric = request.context.get("rubric")
    if isinstance(rubric, (list, tuple)) and rubric:
        return tuple(str(item) for item in rubric)
    if request.target_type is ReviewTargetType.STORYBOARD:
        return _STORYBOARD_DIMENSIONS
    if request.target_type is ReviewTargetType.ASSET:
        return _MEDIA_DIMENSIONS[ReviewTargetType.ASSET]
    if request.target_type is ReviewTargetType.CLIP:
        return _MEDIA_DIMENSIONS[ReviewTargetType.CLIP]
    return NOVEL_DIMENSIONS


def _text_judge_prompt(request: ReviewRequest) -> str:
    ctx = request.context
    if request.target_type is ReviewTargetType.STORYBOARD:
        return (
            f"target_id={request.target_id} attempt={request.attempt}\n"
            f"镜头数：{ctx.get('shot_count', '')} 总时长：{ctx.get('duration_s', '')}s\n"
            f"章节字数：{ctx.get('chapter_words', '')} 画幅：{ctx.get('aspect_ratio', '9:16')}\n"
            f"评分维度：{', '.join(_dimensions(request))}\n"
            "这是竖屏短剧分镜，不要按电影长镜头来审。\n\n"
            f"{request.content}"
        )
    if request.target_type is ReviewTargetType.ASSET:
        return (
            f"target_id={request.target_id} attempt={request.attempt}\n"
            f"asset kind={ctx.get('kind', '')}\n"
            f"评分维度：{', '.join(_dimensions(request))}\n"
            f"prompt:\n{ctx.get('prompt', request.content)}"
        )
    if request.target_type is ReviewTargetType.CLIP:
        return (
            f"target_id={request.target_id} attempt={request.attempt}\n"
            f"duration={ctx.get('duration_s', '')}s "
            f"size={ctx.get('width', '')}x{ctx.get('height', '')}\n"
            f"previous_clip={ctx.get('previous_clip_id', '')} engine={ctx.get('engine', '')}\n"
            f"评分维度：{', '.join(_dimensions(request))}\n"
            "这是竖屏短剧单镜头 I2V 片段（5–15 秒，9:16）。\n"
            f"uri:\n{request.content}\n"
            f"prompt:\n{ctx.get('prompt', '')}"
        )
    memory = ctx.get("memory", "")
    word_min = ctx.get("word_min", "")
    word_max = ctx.get("word_max", "")
    return (
        f"target_id={request.target_id} attempt={request.attempt}\n"
        f"字数区间：[{word_min}, {word_max}]\n"
        f"评分维度：{', '.join(_dimensions(request))}\n"
        f"故事记忆：\n{memory}\n\n章节正文：\n{request.content}"
    )


def _media_passthrough(request: ReviewRequest) -> Review:
    dims = _MEDIA_DIMENSIONS.get(request.target_type, ("quality",))
    return Review(
        target_type=request.target_type,
        target_id=request.target_id,
        attempt=request.attempt,
        scores=dict.fromkeys(dims, 8.5),
        issues=[],
        action=ReviewAction.PASS,
        reviewer="llm-judge-media-passthrough",
    )
