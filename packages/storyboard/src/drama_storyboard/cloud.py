"""Cloud LLM storyboard: JSON shot list for vertical short drama."""

from __future__ import annotations

from typing import Any

from drama_core import VERTICAL_ASPECT_RATIO, Chapter, Project, Shot, Storyboard, UsageUnits
from drama_llm import ChatClient, JsonExtractError, LlmClient, LlmConfig, LlmError, extract_json
from pydantic import BaseModel, ConfigDict, Field, field_validator

from drama_storyboard.pacing import plan_shot_count
from drama_storyboard.refs import resolve_refs
from drama_storyboard.structured import StructuredStoryboardEngine


class _ShotDraft(BaseModel):
    model_config = ConfigDict(extra="ignore")
    index: int = 1
    duration_s: float = 8.0
    camera: str = "中景 跟拍"
    action: str = ""
    dialogue: str = ""
    character_names: list[str] = Field(default_factory=list)
    scene_name: str = ""
    prop_names: list[str] = Field(default_factory=list)
    image_prompt: str = ""
    motion_prompt: str = "slow push-in"

    @field_validator("duration_s", mode="before")
    @classmethod
    def _duration(cls, value: object) -> float:
        try:
            n = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 8.0
        return min(15.0, max(5.0, n))


class _BoardDraft(BaseModel):
    model_config = ConfigDict(extra="ignore")
    shots: list[_ShotDraft] = Field(default_factory=list)


class CloudStoryboardEngine:
    """OpenAI-compatible ``StoryboardEngine``. Falls back to structured packing."""

    name = "cloud-storyboard"

    def __init__(
        self,
        client: ChatClient | None = None,
        *,
        config: LlmConfig | None = None,
        fallback: StructuredStoryboardEngine | None = None,
    ) -> None:
        self._client = client
        self._config = config
        self.fallback = fallback or StructuredStoryboardEngine()

    @property
    def client(self) -> ChatClient:
        if self._client is None:
            self._client = LlmClient(
                self._config or LlmConfig.from_env(model_var="STORYBOARD_MODEL")
            )
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

    def build(
        self,
        project: Project,
        chapter: Chapter,
        *,
        revision: int = 0,
        feedback: str = "",
    ) -> Storyboard:
        target = plan_shot_count(chapter.word_count)
        try:
            data = self._chat_json(project, chapter, target, revision, feedback)
            draft = _BoardDraft.model_validate(data)
        except (LlmError, JsonExtractError, ValueError):
            return self.fallback.build(project, chapter, revision=revision, feedback=feedback)
        if not draft.shots:
            return self.fallback.build(project, chapter, revision=revision, feedback=feedback)
        shots = [_materialize(project, chapter, item, i) for i, item in enumerate(draft.shots[:12])]
        for i, shot in enumerate(shots, start=1):
            shot.index = i
        return Storyboard(chapter_id=chapter.id, shots=shots, revision=revision)

    def _chat_json(
        self,
        project: Project,
        chapter: Chapter,
        target: int,
        revision: int,
        feedback: str,
    ) -> dict[str, Any]:
        raw = self.client.chat(
            [
                {
                    "role": "system",
                    "content": (
                        "你是竖屏短剧（9:16）分镜师。只返回 JSON："
                        '{"shots":[{"index":int,"duration_s":5-15,"camera":str,'
                        '"action":str,"dialogue":str,"character_names":[str],'
                        '"scene_name":str,"prop_names":[str],"image_prompt":str,'
                        '"motion_prompt":str}]}。'
                        f"大约 {target} 个镜头，不要电影长镜头。每个镜头 5–15 秒。"
                        "image_prompt 必须写明 vertical 9:16。"
                    ),
                },
                {
                    "role": "user",
                    "content": _user_prompt(project, chapter, target, revision, feedback),
                },
            ],
            json_mode=True,
        )
        data = extract_json(raw)
        if not isinstance(data, dict):
            raise LlmError("storyboard JSON must be an object")
        return data


def _user_prompt(
    project: Project, chapter: Chapter, target: int, revision: int, feedback: str
) -> str:
    cast = "、".join(f"{c.name}({c.identity.role})" for c in project.characters) or "（未定）"
    scenes = "、".join(s.name for s in project.scenes) or "（未定）"
    props = "、".join(p.name for p in project.props) or "（无）"
    parts = [
        f"书名：{project.title} 类型：{project.genre} 画幅：{project.aspect_ratio}",
        f"第{chapter.index}章《{chapter.title}》摘要：{chapter.summary}",
        f"目标镜头数：{target} 修订：{revision}",
        f"角色：{cast}",
        f"场景：{scenes}",
        f"道具：{props}",
        "章节正文：",
        chapter.body[:4000],
    ]
    if feedback:
        parts.append(f"审核意见（必须逐条修改）：{feedback}")
    return "\n".join(parts)


def _materialize(project: Project, chapter: Chapter, draft: _ShotDraft, index: int) -> Shot:
    text = " ".join(
        [
            draft.action,
            draft.dialogue,
            draft.scene_name,
            *draft.character_names,
            *draft.prop_names,
        ]
    )
    chars, scene_id, props = resolve_refs(project, text, index=index)
    if draft.character_names:
        by_name = {c.name: c.id for c in project.characters}
        named = [by_name[n] for n in draft.character_names if n in by_name]
        if named:
            chars = named
    if draft.scene_name:
        scene = next((s for s in project.scenes if s.name == draft.scene_name), None)
        if scene is not None:
            scene_id = scene.id
    if draft.prop_names:
        by_prop = {p.name: p.id for p in project.props}
        named_props = [by_prop[n] for n in draft.prop_names if n in by_prop]
        if named_props:
            props = named_props
    names = "、".join(c.name for c in project.characters if c.id in chars)
    where = next((s.name for s in project.scenes if s.id == scene_id), draft.scene_name or "室内")
    action = draft.action or f"{names}在{where}"
    prompt = draft.image_prompt or (
        f"vertical {VERTICAL_ASPECT_RATIO}, {where}, {names}, {action}, short-drama still"
    )
    if "9:16" not in prompt and "vertical" not in prompt.lower():
        prompt = f"vertical {VERTICAL_ASPECT_RATIO}, {prompt}"
    return Shot(
        index=draft.index or index + 1,
        chapter_id=chapter.id,
        scene_id=scene_id,
        character_ids=chars,
        prop_ids=props,
        duration_s=draft.duration_s,
        camera=draft.camera,
        action=action,
        dialogue=draft.dialogue,
        image_prompt=prompt,
        motion_prompt=draft.motion_prompt or "slow push-in",
        aspect_ratio=project.aspect_ratio or VERTICAL_ASPECT_RATIO,
    )
