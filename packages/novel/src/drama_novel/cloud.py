"""Cloud LLM novel engine: bible, outline, Chinese chapters, memory deltas."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from drama_core import (
    Appearance,
    Chapter,
    ChapterPlan,
    Character,
    CharacterIdentity,
    InventoryItem,
    MemoryDelta,
    Outline,
    Project,
    Prop,
    Relation,
    Review,
    Scene,
    Voice,
    count_words,
    genre_style_hint,
)
from drama_llm import ChatClient, JsonExtractError, LlmClient, LlmConfig, LlmError, extract_json
from pydantic import BaseModel, ConfigDict, Field, field_validator

from drama_novel.interfaces import StoryBible
from drama_novel.memory import NovelMemory

_WORD_RULE = "字数统计规则：每个汉字计 1 字，每个连续英文/数字词计 1 字，标点与空白不计。"


class _LlmIdentity(BaseModel):
    model_config = ConfigDict(extra="ignore")
    role: str
    age: int | None = None
    gender: str | None = None
    occupation: str | None = None
    background: str = ""

    @field_validator("age", mode="before")
    @classmethod
    def _age(cls, value: object) -> int | None:
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            raise ValueError("age must be an integer")
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            return int(value)
        raise ValueError("age must be an integer")


class _LlmAppearance(BaseModel):
    model_config = ConfigDict(extra="ignore")
    description: str
    hair: str = ""
    eyes: str = ""
    build: str = ""
    outfit: str = ""
    distinguishing_marks: list[str] = Field(default_factory=list)


class _LlmVoice(BaseModel):
    model_config = ConfigDict(extra="ignore")
    tone: str = ""
    speech_style: str = ""
    catchphrases: list[str] = Field(default_factory=list)


class _LlmRelation(BaseModel):
    model_config = ConfigDict(extra="ignore")
    target_name: str
    kind: str
    note: str = ""


class _LlmCharacter(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    identity: _LlmIdentity
    appearance: _LlmAppearance
    voice: _LlmVoice = Field(default_factory=_LlmVoice)
    arc: str = ""
    relations: list[_LlmRelation] = Field(default_factory=list)


class _LlmProp(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    description: str
    owner_name: str | None = None


class _LlmScene(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str
    description: str
    time_of_day: str = ""
    prop_names: list[str] = Field(default_factory=list)


class _BibleDraft(BaseModel):
    model_config = ConfigDict(extra="ignore")
    characters: list[_LlmCharacter]
    scenes: list[_LlmScene] = Field(default_factory=list)
    props: list[_LlmProp] = Field(default_factory=list)


class _ChapterDraft(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str = ""
    summary: str = ""
    body: str
    memory_delta: MemoryDelta = Field(default_factory=MemoryDelta)

    @field_validator("body", mode="before")
    @classmethod
    def _body(cls, value: object) -> str:
        if isinstance(value, list):
            return "".join(str(part) for part in value)
        if not isinstance(value, str) or not value.strip():
            raise ValueError("chapter body must be a non-empty string")
        return value


class CloudNovelEngine:
    """OpenAI-compatible ``NovelEngine``. Visual/video stages stay mock."""

    name = "cloud-novel"

    def __init__(
        self,
        client: ChatClient | None = None,
        *,
        config: LlmConfig | None = None,
        max_adjust_rounds: int = 2,
    ) -> None:
        self._client = client
        self._config = config
        self.max_adjust_rounds = max_adjust_rounds

    @property
    def client(self) -> ChatClient:
        if self._client is None:
            self._client = LlmClient(self._config or LlmConfig.from_env(model_var="NOVEL_MODEL"))
        return self._client

    def create_bible(self, project: Project) -> StoryBible:
        data = self._chat_json(
            [
                {
                    "role": "system",
                    "content": (
                        "你是网文策划。只返回一个 JSON 对象，字段为 characters/scenes/props。"
                        "人物 2–4 个，中文名；relations 用 target_name 指向其他人物姓名；"
                        "props.owner_name、scenes.prop_names 用道具名。"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"书名：{project.title}\n类型：{project.genre}\n"
                        f"{genre_style_hint(project.genre)}\n"
                        f"梗概：{project.premise}\n目标总字数：{project.total_words}\n"
                        "请给出人设圣经（角色、场景、关键道具）。"
                    ),
                },
            ]
        )
        draft = _BibleDraft.model_validate(data)
        return _materialize_bible(draft)

    def write_outline(self, project: Project, chapter_targets: list[int]) -> Outline:
        data = self._chat_json(
            [
                {
                    "role": "system",
                    "content": (
                        "你是网文大纲作者。只返回 JSON："
                        '{"logline": str, "chapters": '
                        '[{"index": int, "title": str, "summary": str}]}。'
                        f"必须恰好 {len(chapter_targets)} 章，中文标题与摘要，每章结尾留钩子。"
                    ),
                },
                {
                    "role": "user",
                    "content": _outline_user_prompt(project, chapter_targets),
                },
            ]
        )
        logline = str(data.get("logline") or f"【{project.genre}】{project.premise}")
        raw_chapters = data.get("chapters")
        drafts = raw_chapters if isinstance(raw_chapters, list) else []
        chapters: list[ChapterPlan] = []
        for i, target in enumerate(chapter_targets, start=1):
            item = drafts[i - 1] if i - 1 < len(drafts) and isinstance(drafts[i - 1], dict) else {}
            title = str(item.get("title") or f"第{i}章")
            summary = str(item.get("summary") or f"{project.title} 第{i}章")
            chapters.append(ChapterPlan(index=i, title=title, summary=summary, target_words=target))
        return Outline(logline=logline, chapters=chapters)

    def write_chapter(self, project: Project, plan: ChapterPlan, memory: NovelMemory) -> Chapter:
        draft = self._draft_chapter(project, plan, memory, revision=0, review=None)
        return Chapter(
            index=plan.index,
            title=draft.title or plan.title,
            summary=draft.summary or plan.summary,
            body=draft.body,
            target_words=plan.target_words,
            memory_delta=_memory_or_fallback(project, plan.index, draft.memory_delta),
        )

    def revise_chapter(
        self, project: Project, chapter: Chapter, review: Review, memory: NovelMemory
    ) -> Chapter:
        plan = ChapterPlan(
            index=chapter.index,
            title=chapter.title,
            summary=chapter.summary,
            target_words=chapter.target_words,
        )
        draft = self._draft_chapter(
            project, plan, memory, revision=chapter.revision + 1, review=review
        )
        return chapter.model_copy(
            update={
                "title": draft.title or chapter.title,
                "summary": draft.summary or chapter.summary,
                "body": draft.body,
                "revision": chapter.revision + 1,
                "memory_delta": _memory_or_fallback(project, chapter.index, draft.memory_delta)
                if draft.memory_delta.new_facts or draft.memory_delta.character_updates
                else chapter.memory_delta,
            }
        )

    def _draft_chapter(
        self,
        project: Project,
        plan: ChapterPlan,
        memory: NovelMemory,
        *,
        revision: int,
        review: Review | None,
    ) -> _ChapterDraft:
        messages = [
            {
                "role": "system",
                "content": (
                    "你是中文网文章节作者。只返回 JSON，字段 title/summary/body/memory_delta。"
                    "body 必须是完整中文正文（可含对话），不要用列表代替正文。"
                    f"{_WORD_RULE} 目标 {plan.target_words} 字，区间 "
                    f"[{project.word_min}, {project.word_max}]。"
                    "memory_delta 形状："
                    '{"new_facts": [str], "character_updates": {name: str},'
                    ' "open_threads": [str], "closed_threads": [str]}。'
                ),
            },
            {
                "role": "user",
                "content": _chapter_user_prompt(project, plan, memory, revision, review),
            },
        ]
        draft = _ChapterDraft.model_validate(self._chat_json(messages))
        for _ in range(self.max_adjust_rounds):
            n = count_words(draft.body)
            if project.word_min <= n <= project.word_max:
                return draft
            direction = "扩写" if n < project.word_min else "删减"
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"当前字数 {n}，目标 {plan.target_words}，"
                        f"必须落在 [{project.word_min}, {project.word_max}]。"
                        f"请{direction}后返回完整 JSON（含修订后的 body 与 memory_delta）。"
                    ),
                }
            )
            draft = _ChapterDraft.model_validate(self._chat_json(messages))
        return draft

    def _chat_json(self, messages: Sequence[Mapping[str, str]]) -> dict[str, Any]:
        raw = self.client.chat(messages, json_mode=True)
        try:
            data = extract_json(raw)
        except JsonExtractError:
            raw = self.client.chat(
                [
                    *messages,
                    {
                        "role": "user",
                        "content": "刚才的输出不是合法 JSON，请只返回一个 JSON 对象。",
                    },
                ],
                json_mode=True,
            )
            data = extract_json(raw)
        if not isinstance(data, dict):
            raise LlmError("LLM JSON must be an object")
        return data


def _outline_user_prompt(project: Project, chapter_targets: list[int]) -> str:
    cast = "、".join(c.name for c in project.characters) or "（尚未定名）"
    targets = "，".join(f"第{i}章 {n}字" for i, n in enumerate(chapter_targets, start=1))
    return (
        f"书名：{project.title}\n类型：{project.genre}\n{genre_style_hint(project.genre)}\n"
        f"梗概：{project.premise}\n"
        f"角色：{cast}\n各章目标字数：{targets}\n"
        "请写 logline 与每章标题、摘要。"
    )


def _chapter_user_prompt(
    project: Project,
    plan: ChapterPlan,
    memory: NovelMemory,
    revision: int,
    review: Review | None,
) -> str:
    cast = json.dumps(
        [{"name": c.name, "role": c.identity.role, "arc": c.arc} for c in project.characters],
        ensure_ascii=False,
    )
    parts = [
        f"书名：{project.title} 类型：{project.genre} {genre_style_hint(project.genre)}",
        f"第{plan.index}章《{plan.title}》 摘要：{plan.summary}",
        f"目标字数：{plan.target_words} 修订轮次：{revision}",
        f"角色：{cast}",
        "故事记忆：",
        memory.to_markdown(),
    ]
    if review is not None:
        issues = "；".join(f"{i.severity}:{i.message}" for i in review.issues) or "（无细则）"
        parts.append(f"审核意见（必须逐条修改）：action={review.action.value} {issues}")
    return "\n".join(parts)


def _memory_or_fallback(project: Project, index: int, delta: MemoryDelta) -> MemoryDelta:
    if delta.new_facts or delta.character_updates or delta.open_threads:
        return delta
    lead = project.characters[0].name if project.characters else "主角"
    return MemoryDelta(
        new_facts=[f"第{index}章：{lead}推进了剧情"],
        character_updates={lead: f"第{index}章后状态更新"},
        open_threads=[f"第{index}章留下的悬念"],
        closed_threads=[f"第{index - 1}章的悬念"] if index > 1 else [],
    )


def _materialize_bible(draft: _BibleDraft) -> StoryBible:
    props = [
        Prop(name=p.name, description=p.description, owner_character_id=None) for p in draft.props
    ]
    props_by_name = {p.name: p for p in props}
    characters: list[Character] = []
    for item in draft.characters:
        characters.append(
            Character(
                name=item.name,
                identity=CharacterIdentity(
                    role=item.identity.role,
                    age=item.identity.age,
                    gender=item.identity.gender,
                    occupation=item.identity.occupation,
                    background=item.identity.background,
                ),
                appearance=Appearance(
                    description=item.appearance.description,
                    hair=item.appearance.hair,
                    eyes=item.appearance.eyes,
                    build=item.appearance.build,
                    outfit=item.appearance.outfit,
                    distinguishing_marks=item.appearance.distinguishing_marks,
                ),
                voice=Voice(
                    tone=item.voice.tone,
                    speech_style=item.voice.speech_style,
                    catchphrases=item.voice.catchphrases,
                ),
                arc=item.arc,
            )
        )
    by_name = {c.name: c for c in characters}
    for item, char in zip(draft.characters, characters, strict=True):
        char.relations = [
            Relation(target_id=by_name[rel.target_name].id, kind=rel.kind, note=rel.note)
            for rel in item.relations
            if rel.target_name in by_name
        ]
    for spec, prop in zip(draft.props, props, strict=True):
        owner = by_name.get(spec.owner_name or "")
        if owner is not None:
            prop.owner_character_id = owner.id
    scenes = [
        Scene(
            name=s.name,
            description=s.description,
            time_of_day=s.time_of_day,
            inventory=[
                InventoryItem(prop_id=props_by_name[name].id, placement="")
                for name in s.prop_names
                if name in props_by_name
            ],
        )
        for s in draft.scenes
    ]
    return StoryBible(characters=characters, scenes=scenes, props=props)
