"""Three-pass novel rewrite templates (architecture → discourse → wording).

Injected into cloud chapter generation and available as standalone prompt
blocks. Negative constraints only — they do not invent plot.
"""

from __future__ import annotations

ARCHITECTURE_PASS = (
    "第1层 叙事架构：先写人物此刻要什么、怕什么、肯付什么代价。"
    "每个转折给铺垫、一次具体尝试、阻碍、代价和余波，不要把章节写成大纲扩写。"
    "主题只通过选择呈现，不要旁白宣布意义。"
    "人物做一件看得见的事；允许误判，不要永远选最体面的路。"
)

DISCOURSE_PASS = (
    "第2层 话语流：每段最好只回答一个隐含问题，中段必须推进，不能只把金句放在段尾。"
    "对白带身份和当下利益，少互相汇报读者已知的背景；标签优先用「说」，不要轮换沉声道/淡淡道。"
    "章末钩子必须是具体剩余问题，禁止「他不知道的是 / 真正的危机才刚刚开始 / 未来可期」。"
)

WORDING_PASS = (
    "第3层 表面文字：少堆微微/淡淡/缓缓/轻轻/不禁；少用仿佛/宛如装饰；"
    "少写心中暗道、眼中闪过、嘴角勾起、带着一丝、不是A而是B、不难看出。"
    "情绪可以直接写，不要「感到一丝 + 抽象名词」。"
    "改写优先于增写：拿不准就删；只为补具体名字、数字、动作或物件而扩写。"
    "不要为了去味把每句都打磨成同一种短句节奏。"
)

CHAPTER_CHECKLIST = (
    "开头 300 字内给出具体冲突、危险、欲望或秘密；"
    "核心情节有铺垫/过程/余波；"
    "对白有打断、沉默或回避，不互相解释设定；"
    "环境只写影响行动或冲突的部分；"
    "章末改变读者对局势的判断，而不是口号收束。"
)


def novel_deslop_system_suffix() -> str:
    """Append to the cloud novel chapter system prompt."""
    return (
        "去AI味按三层执行，只改表达与用笔，不改已定事实、伏笔和结局："
        f"{ARCHITECTURE_PASS} {DISCOURSE_PASS} {WORDING_PASS} "
        f"交付前自检：{CHAPTER_CHECKLIST}"
    )


def novel_deslop_user_reminder() -> str:
    return (
        "写作约束：具体动作大于抽象心情；少用禁语簇；不要总结主题；章末留具体钩子而不是预告口号。"
    )


def storyboard_deslop_system_suffix() -> str:
    return (
        "每镜只有一个主要可见动作，写清起点→唯一动作→终点。"
        "填写 character_lock / wardrobe_lock / scene_lock，后续镜头不要重写脸、发、衣服。"
        "运镜每镜最多一次。动作用可见状态，不用抽象情绪词。"
        "默认不烧录字幕、caption 或对白文字叠加。"
    )
