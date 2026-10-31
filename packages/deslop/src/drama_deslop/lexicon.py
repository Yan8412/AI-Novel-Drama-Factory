"""Curated Chinese web-novel AI-flavor lexicon.

Adapted from public MIT skills (see ``SOURCES`` and ``docs/anti-ai-flavor.md``).
This is a factory-owned subset: categories, density modes, and cluster-not-single
judgment — not a wholesale copy of any upstream wordlist or script.
"""

from __future__ import annotations

from dataclasses import dataclass

SOURCES: tuple[tuple[str, str, str], ...] = (
    (
        "ximencuisu/ximen-aimazi",
        "MIT",
        "three-layer deslop (architecture / discourse / wording) + scan lexicon pattern",
    ),
    (
        "Nanako0129/sepia",
        "MIT",
        "architecture-first humanize: narrative pass → discourse pass → wording pass",
    ),
    (
        "zenstory-ai/oh-story-claudecode",
        "MIT",
        "banned-word clusters, show-don't-tell, cluster-not-single judgment",
    ),
    (
        "deedeekong07-alt/fiction-humanizer-zh",
        "MIT",
        "chapter humanize checklist (setup / process / aftershock, natural hooks)",
    ),
    (
        "hestudy/snowflake-fiction",
        "MIT",
        "negative-constraint humanize prompts (avoid theme slogans and even syntax)",
    ),
    (
        "zenstory-ai/drama-skills",
        "MIT",
        "start → single action → end; no burned-in captions; continuity lock verbatim",
    ),
    (
        "ADC1920/AI-short-play-video-creation",
        "MIT",
        "@ref lock, do not re-describe appearance after refs, one motion per shot",
    ),
)


@dataclass(frozen=True)
class LexiconRule:
    """One countable surface-layer check.

    ``mode``:
      * ``each`` — a single term's count must be ``<= limit`` (cluster approximation)
      * ``total`` — summed hits of the group must be ``<= limit``
      * ``density`` — hits per 1000 counted words must be ``<= limit``
    ``scope``: ``chapter`` (full text), ``head`` (opening), ``tail`` (closing).
    Single isolated hits are not treated as evidence when ``limit >= 1``.
    """

    id: str
    label: str
    severity: str
    mode: str
    limit: float
    terms: tuple[str, ...]
    suggestion: str
    scope: str = "chapter"
    regex: bool = False


# Surface-layer rules only. Architecture / discourse stay in rewrite templates.
LEXICON: tuple[LexiconRule, ...] = (
    LexiconRule(
        id="weak_adverb",
        label="弱化副词（微微/淡淡/缓缓/不禁）",
        severity="hard",
        mode="density",
        limit=2.0,
        terms=("微微", "淡淡", "缓缓", "轻轻", "不禁", "不由自主"),
        suggestion="swap stacked softeners for one concrete verb or cut the adverb",
    ),
    LexiconRule(
        id="simile",
        label="套装比喻（仿佛/宛如）",
        severity="hard",
        mode="total",
        limit=2.0,
        terms=("仿佛", "宛如", "宛若", "犹如", "如同", "好像", "好似"),
        suggestion="keep functional similes; drop decorative 仿佛/宛如 stacks",
    ),
    LexiconRule(
        id="mind_tell",
        label="告知式心理（心中暗道）",
        severity="hard",
        mode="each",
        limit=2.0,
        terms=("心中暗道", "心中一动", "心头一震", "心下了然", "心底泛起", "不由得"),
        suggestion="write the choice or misread; do not stamp the feeling",
    ),
    LexiconRule(
        id="face_kit",
        label="模板化表情套件",
        severity="hard",
        mode="total",
        limit=2.0,
        terms=("眼中闪过", "嘴角勾起", "眉头微皱", "瞳孔微缩", "指节泛白"),
        suggestion="one specific face/hand beat is enough; do not rotate the kit",
    ),
    LexiconRule(
        id="judge",
        label="作者盖章判断",
        severity="hard",
        mode="each",
        limit=2.0,
        terms=("不容置疑", "显而易见", "毫无疑问", "不可否认", "前所未有"),
        suggestion="let the scene prove it; do not announce certainty",
    ),
    LexiconRule(
        id="emotion_wrap",
        label="包装式情绪",
        severity="hard",
        mode="total",
        limit=1.0,
        terms=("感到一丝", "感到一阵", "心中涌起", "难以名状"),
        suggestion="direct emotion is fine; drop 感到一丝 + abstract noun",
    ),
    LexiconRule(
        id="academic",
        label="论文体连词",
        severity="hard",
        mode="total",
        limit=0.0,
        terms=("不难看出", "由此可见", "综上所述", "与此同时", "换言之", "总而言之"),
        suggestion="cut thesis transitions; stay in the scene",
    ),
    LexiconRule(
        id="chapter_end",
        label="章末总结体",
        severity="hard",
        mode="total",
        limit=0.0,
        scope="tail",
        terms=("终于明白", "这才意识到", "未来可期", "前途无量", "充满希望"),
        suggestion="end on a concrete leftover, not a slogan or 他不知道的是",
    ),
    LexiconRule(
        id="air_freeze",
        label="空气/笑容凝固套语",
        severity="hard",
        mode="each",
        limit=1.0,
        terms=("空气凝固", "笑容凝固", "眼神空洞"),
        suggestion="name the silence or the failed smile once, then move on",
    ),
    LexiconRule(
        id="toxic_not_but",
        label="不是A而是B 翻转句",
        severity="hard",
        mode="total",
        limit=0.0,
        regex=True,
        terms=(r"不是[^，。！？\n]{1,8}，(?:而)?是",),
        suggestion="state the fact; skip the fake contrast",
    ),
    LexiconRule(
        id="toxic_with_trace",
        label="带着一丝/一抹 声线贴片",
        severity="hard",
        mode="total",
        limit=1.0,
        terms=("带着一丝", "带着一抹", "带着几分"),
        suggestion="give audible or visible speech info, not an abstract trace",
    ),
    LexiconRule(
        id="opening_weather",
        label="开场定场天气",
        severity="hint",
        mode="total",
        limit=1.0,
        scope="head",
        terms=("清晨", "黄昏", "阳光透过", "夜色降临"),
        suggestion="open on a want or a problem; weather only if it changes action",
    ),
)


def lexicon_catalog() -> list[dict[str, object]]:
    return [
        {
            "id": rule.id,
            "label": rule.label,
            "severity": rule.severity,
            "mode": rule.mode,
            "limit": rule.limit,
            "scope": rule.scope,
            "terms": list(rule.terms),
        }
        for rule in LEXICON
    ]
