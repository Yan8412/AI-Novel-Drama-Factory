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
    genre_family,
    genre_style_hint,
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

_FILLER_BY_FAMILY: dict[str, tuple[str, ...]] = {
    "都市": _FILLER,
    "甜宠": (
        "他伸手替她拢了拢额发，动作轻得像怕惊扰一场刚开口的梦。",
        "她假装生气地别过脸，耳根却已经红了。",
        "一句漫不经心的「我在」，把整座城市的夜色都烘暖了。",
        "外卖袋里多出来的甜汤，是他记得她不说出口的口味。",
        "所有人都当这是契约，只有他们自己知道心跳已经违约。",
        "她终于笑出声，像把整段委屈都换成了糖。",
    ),
    "玄幻": (
        "灵气在丹田里流转一圈，她掌心的玉佩忽然热了起来。",
        "远处秘境裂开一道光缝，旧日仇敌的气息贴着风涌来。",
        "他按住剑柄，没有拔剑，却让整座峰的云都静了一息。",
        "宗门大殿里钟声连响，有人已经踏过了不该踏的禁制。",
        "所谓交易，不过是更高境界的人随口立下的契。",
        "她抬眼时，眸底已经压着一层将破未破的锋芒。",
    ),
    "古言": (
        "宫灯摇曳，廊外的夜露把朱红门槛浸得发暗。",
        "她把那半块玉佩藏进袖中，指尖冰得像刚触过井水。",
        "他只把婚书推到案上，连一声「接旨」都不肯替她说。",
        "巷口更鼓敲过三声，脚步却停在她窗下。",
        "满城都当这是一桩权宜之婚，没人问旧案埋在哪一年。",
        "她抬起头来，礼数还在，眼神却已经不再退。",
    ),
    "悬疑": (
        "监控少了三秒，那三秒里走廊的灯偏偏灭过一次。",
        "玉佩内侧新刻的字不是当年的刀法。",
        "他把合同翻到最后一页，签名的时间对不上出行记录。",
        "脚步声在防火门后停住，像有人在数她的呼吸。",
        "谁都说这是联姻，档案却指向二十年前的失踪。",
        "她抬头的瞬间，已经把那条不该存在的线索记住了。",
    ),
    "爽文": (
        "对面还在冷笑，下一秒已经接不住她回敬的那一记。",
        "合同摔在桌上，条款反过来咬了起草的人。",
        "他刚想施压，现场的人已经自动让出一条路。",
        "走廊里的窃窃私语还没散，打脸的证据已经到了。",
        "谁把她当筹码，谁就先从棋盘上翻下去。",
        "她抬眼，声线平稳，像终于轮到自己揭牌。",
    ),
}


def _fillers(genre: str) -> tuple[str, ...]:
    family = genre_family(genre)
    return _FILLER_BY_FAMILY.get(family or "", _FILLER)


def _body(target_words: int, chapter_index: int, revision: int, genre: str) -> str:
    """Chinese-only filler trimmed so ``count_words(body) == target_words`` exactly."""
    header = f"【{genre}】第{_cn(chapter_index)}章"
    if revision:
        header += f"修订稿{_cn(revision)}"
    header += "。"
    parts = [header]
    total = count_words(header)
    pool = _fillers(genre)
    sentences = cycle(pool[(chapter_index + revision) % len(pool) :] + pool)
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
            arc=f"从隐忍到反击，揭开家族真相（{genre_style_hint(project.genre)}）",
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
            body=_body(plan.target_words, plan.index, 0, project.genre),
            target_words=plan.target_words,
            memory_delta=self._delta(project, plan.index),
        )

    def revise_chapter(
        self, project: Project, chapter: Chapter, review: Review, memory: NovelMemory
    ) -> Chapter:
        revision = chapter.revision + 1
        return chapter.model_copy(
            update={
                "body": _body(chapter.target_words, chapter.index, revision, project.genre),
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
