"""Deterministic offline novel engine for demos and tests."""

from __future__ import annotations

from itertools import cycle

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
)

from drama_novel.interfaces import StoryBible
from drama_novel.memory import NovelMemory

_FILLER = (
    "雨声敲打着玻璃窗，城市的霓虹在水汽里晕开成一片模糊的光。",
    "她攥紧了掌心的玉佩，冰凉的触感让她想起多年前那个改变一切的夜晚。",
    "他没有说话，只是把那份合同推到桌子中央，眼神里藏着看不透的情绪。",
    "走廊尽头传来脚步声，每一步都像踩在心跳上，紧张得让人透不过气。",
    "所有人都以为这只是一场交易，却没人知道背后埋着怎样的秘密。",
    "她终于抬起头，目光坚定，像是在心里做出了一个再也无法回头的决定。",
)


def _body(target_words: int, chapter_index: int, revision: int) -> str:
    """Chinese-only filler trimmed so ``count_words(body) == target_words`` exactly."""
    header = f"第{_cn(chapter_index)}章"
    if revision:
        header += f"修订稿{_cn(revision)}"
    header += "。"
    parts = [header]
    total = count_words(header)
    sentences = cycle(_FILLER[(chapter_index + revision) % len(_FILLER) :] + _FILLER)
    while total < target_words:
        s = next(sentences)
        need = target_words - total
        n = count_words(s)
        if n > need:
            s = _truncate_words(s, need)
            n = need
        parts.append(s)
        total += n
    return "".join(parts)


def _truncate_words(sentence: str, n: int) -> str:
    for end in range(len(sentence) + 1):
        if count_words(sentence[:end]) == n:
            return sentence[:end] + "。"
    return sentence


_DIGITS = "零一二三四五六七八九"


def _cn(n: int) -> str:
    return "".join(_DIGITS[int(d)] for d in str(n))


class MockNovelEngine:
    name = "mock-novel"

    def create_bible(self, project: Project) -> StoryBible:
        jade = Prop(name="祖传玉佩", description="温润的白玉，刻着半个“林”字")
        contract = Prop(name="契约婚姻合同", description="一份为期一年的协议")
        lin = Character(
            name="林晚",
            identity=CharacterIdentity(role="女主", age=24, gender="女", occupation="设计师"),
            appearance=Appearance(
                description="清冷气质，杏眼",
                hair="黑色长直发",
                eyes="深棕",
                outfit="米白风衣",
                distinguishing_marks=["左耳垂小痣"],
            ),
            voice=Voice(tone="清冷", speech_style="话少而直接"),
            arc="从隐忍到反击，揭开家族真相",
        )
        gu = Character(
            name="顾沉",
            identity=CharacterIdentity(role="男主", age=29, gender="男", occupation="集团总裁"),
            appearance=Appearance(
                description="高冷霸总", hair="短黑发", eyes="黑", outfit="深灰西装"
            ),
            voice=Voice(tone="低沉", speech_style="命令式"),
            arc="从利用到守护",
        )
        su = Character(
            name="苏曼",
            identity=CharacterIdentity(role="反派", age=26, gender="女", occupation="名媛"),
            appearance=Appearance(description="明艳张扬", hair="酒红卷发", outfit="红色礼服"),
            voice=Voice(tone="甜腻", speech_style="绵里藏针"),
            arc="嫉妒驱动的步步紧逼",
        )
        lin.relations = [
            Relation(target_id=gu.id, kind="契约夫妻"),
            Relation(target_id=su.id, kind="宿敌"),
        ]
        gu.relations = [Relation(target_id=lin.id, kind="契约夫妻")]
        jade.owner_character_id = lin.id
        contract.owner_character_id = gu.id
        scenes = [
            Scene(
                name="雨夜街头",
                description="霓虹倒影的湿漉街道",
                time_of_day="夜",
                inventory=[InventoryItem(prop_id=jade.id, placement="林晚手中")],
            ),
            Scene(
                name="顾氏集团顶层办公室",
                description="落地窗俯瞰城市",
                time_of_day="日",
                inventory=[InventoryItem(prop_id=contract.id, placement="办公桌上")],
            ),
        ]
        return StoryBible(characters=[lin, gu, su], scenes=scenes, props=[jade, contract])

    def write_outline(self, project: Project, chapter_targets: list[int]) -> Outline:
        return Outline(
            logline=f"【{project.genre}】{project.premise}",
            chapters=[
                ChapterPlan(
                    index=i,
                    title=f"第{_cn(i)}章",
                    summary=f"{project.title} 第{i}章：冲突升级，结尾留钩子",
                    target_words=t,
                )
                for i, t in enumerate(chapter_targets, start=1)
            ],
        )

    def write_chapter(self, project: Project, plan: ChapterPlan, memory: NovelMemory) -> Chapter:
        return Chapter(
            index=plan.index,
            title=plan.title,
            summary=plan.summary,
            body=_body(plan.target_words, plan.index, 0),
            target_words=plan.target_words,
            memory_delta=self._delta(project, plan.index),
        )

    def revise_chapter(
        self, project: Project, chapter: Chapter, review: Review, memory: NovelMemory
    ) -> Chapter:
        revision = chapter.revision + 1
        return chapter.model_copy(
            update={
                "body": _body(chapter.target_words, chapter.index, revision),
                "revision": revision,
            }
        )

    def _delta(self, project: Project, index: int) -> MemoryDelta:
        lead = project.characters[0].name if project.characters else "主角"
        return MemoryDelta(
            new_facts=[f"第{index}章：{lead}发现了新的线索"],
            character_updates={lead: f"第{index}章后更加坚定"},
            open_threads=[f"线索{index}的来源"],
            closed_threads=[f"线索{index - 1}的来源"] if index > 1 else [],
        )
