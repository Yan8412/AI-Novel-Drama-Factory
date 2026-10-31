import json
from collections.abc import Mapping, Sequence
from pathlib import Path

from drama_core import (
    Chapter,
    ChapterPlan,
    Project,
    Review,
    ReviewAction,
    ReviewIssue,
    ReviewTargetType,
    count_words,
)
from drama_novel import CloudNovelEngine, NovelMemory


class ScriptedClient:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls: list[list[dict[str, str]]] = []

    def chat(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        temperature: float = 0.4,
        json_mode: bool = True,
    ) -> str:
        self.calls.append([dict(m) for m in messages])
        return self.responses.pop(0)


_BIBLE = {
    "characters": [
        {
            "name": "林晚",
            "identity": {"role": "女主", "age": "24", "gender": "女", "occupation": "设计师"},
            "appearance": {"description": "清冷", "hair": "黑长直"},
            "arc": "反击",
            "relations": [{"target_name": "顾沉", "kind": "契约夫妻"}],
        },
        {
            "name": "顾沉",
            "identity": {"role": "男主", "age": 29},
            "appearance": {"description": "高冷"},
            "arc": "守护",
            "relations": [],
        },
    ],
    "props": [{"name": "玉佩", "description": "祖传", "owner_name": "林晚"}],
    "scenes": [
        {
            "name": "雨夜街头",
            "description": "霓虹",
            "time_of_day": "夜",
            "prop_names": ["玉佩"],
        }
    ],
}


def _project() -> Project:
    return Project(
        title="契约新娘",
        genre="都市甜宠",
        premise="契约婚姻",
        total_words=30,
        word_min=8,
        word_max=40,
    )


def test_bible_outline_chapter_and_memory(tmp_path: Path) -> None:
    body = "雨夜里林晚攥紧玉佩决定不再退让顾沉站在落地窗前。"
    chapter_json = {
        "title": "雨夜",
        "summary": "对峙",
        "body": body,
        "memory_delta": {
            "new_facts": ["林晚拒绝续约"],
            "character_updates": {"林晚": "开始反击"},
            "open_threads": ["玉佩来历"],
            "closed_threads": [],
        },
    }
    engine = CloudNovelEngine(
        ScriptedClient(
            [
                json.dumps(_BIBLE, ensure_ascii=False),
                json.dumps(
                    {
                        "logline": "契约婚姻撕开旧案",
                        "chapters": [{"index": 1, "title": "雨夜", "summary": "对峙"}],
                    },
                    ensure_ascii=False,
                ),
                json.dumps(chapter_json, ensure_ascii=False),
            ]
        )
    )
    p = _project()
    bible = engine.create_bible(p)
    p.characters = bible.characters
    assert [c.name for c in bible.characters] == ["林晚", "顾沉"]
    assert bible.characters[0].relations[0].target_id == bible.characters[1].id
    assert bible.props[0].owner_character_id == bible.characters[0].id
    assert bible.scenes[0].inventory[0].prop_id == bible.props[0].id

    outline = engine.write_outline(p, [20])
    assert outline.chapters[0].target_words == 20
    assert outline.chapters[0].title == "雨夜"

    memory = NovelMemory()
    ch = engine.write_chapter(p, outline.chapters[0], memory)
    assert ch.body == body
    assert ch.word_count == count_words(body)
    assert ch.memory_delta.new_facts == ["林晚拒绝续约"]
    memory.apply(ch.index, ch.summary, ch.memory_delta)
    memory.save(tmp_path)
    assert "林晚拒绝续约" in (tmp_path / "memory.md").read_text(encoding="utf-8")


def test_write_chapter_retries_when_outside_band() -> None:
    short = {"title": "t", "summary": "s", "body": "太短了", "memory_delta": {}}
    long_enough = {
        "title": "t",
        "summary": "s",
        "body": "这一章写得刚刚好足够进入字数区间了。",
        "memory_delta": {"new_facts": ["推进"]},
    }
    client = ScriptedClient(
        [json.dumps(short, ensure_ascii=False), json.dumps(long_enough, ensure_ascii=False)]
    )
    engine = CloudNovelEngine(client, max_adjust_rounds=2)
    p = _project()
    plan = ChapterPlan(index=1, title="t", summary="s", target_words=16)
    ch = engine.write_chapter(p, plan, NovelMemory())
    assert ch.within_bounds(p.word_min, p.word_max)
    assert len(client.calls) == 2
    assert "当前字数" in client.calls[1][-1]["content"]


def test_revise_keeps_id_and_bumps_revision() -> None:
    first = {
        "title": "修订",
        "summary": "改",
        "body": "修订后的正文仍然落在字数区间之内。",
        "memory_delta": {"new_facts": ["已修订"]},
    }
    engine = CloudNovelEngine(ScriptedClient([json.dumps(first, ensure_ascii=False)]))
    p = _project()
    original = Chapter(
        index=1, title="旧", summary="旧", body="旧正文一二三四五六七八", target_words=16
    )
    review = Review(
        target_type=ReviewTargetType.CHAPTER,
        target_id=original.id,
        attempt=1,
        action=ReviewAction.REVISE,
        issues=[ReviewIssue(severity="major", message="扩写")],
    )
    revised = engine.revise_chapter(p, original, review, NovelMemory())
    assert revised.id == original.id
    assert revised.revision == 1
    assert "修订后" in revised.body
