# 去 AI 味（小说 / 短剧 / 提示词）

竖屏短剧工厂的三层去味：小说正文扫描与改写模板、分镜连续性、图像/视频提示词约束。
**只借鉴公开 MIT 技能的模式，不 vendor 整库。** 扫描给出密度与原文证据，不输出「AI 概率」或作者身份判定。

开关：`DESLOP_ENABLED` / `ANTI_AI_FLAVOR`（默认开，注入提示词并把扫描结果挂到章节审核）；`DESLOP_STRICT=1` 时成簇硬项会把审核打成 `revise`。默认不严格，避免 mock 填料误伤流水线。

```bash
uv run drama-factory deslop path/to/chapter.md
uv run drama-factory deslop --text "……" --json
# POST /deslop/scan  {"text": "……", "title": "第1章"}
```

## 1. 小说

`packages/deslop` 提供词表扫描与三层改写模板，挂在 `CloudNovelEngine` 章节系统提示和 `chapter_review_request`。

| 层 | 管什么 | 本仓库落点 |
|---|---|---|
| 叙事架构 | 欲望/代价、铺垫→尝试→余波，不把章节写成大纲 | `ARCHITECTURE_PASS` |
| 话语流 | 段落隐含问题、朴素对话标签、具体章末钩子 | `DISCOURSE_PASS` |
| 表面文字 | 禁语簇、密度、证据 | `WORDING_PASS` + `scan_text` |

词表覆盖：微微/淡淡/缓缓/不禁、仿佛/宛如、心中暗道、眼中闪过/嘴角勾起、带着一丝、不是 A 而是 B、不难看出、章末「终于明白」等。判定：**单次不算，成簇才算**；直陈情绪合法；要去的是「感到一丝 + 抽象名词」包装。

分档（禁语命中 / 千字）：clean / 轻度 ≤5 / 中度 6–15 / 重度 >15。

## 2. 短剧分镜

`Shot` 增加连续性字段：`primary_action`、`start_state`、`end_state`、`character_lock`、`wardrobe_lock`、`scene_lock`。mock / structured / cloud 引擎在出镜时回填；markdown 分镜表写出「起点 → 唯一动作 → 终点」和三把锁。审核对多动作标记（然后/接着/同时）和缺锁给 **minor**，不阻断 mock。

## 3. 图像 / 视频提示词

共享负向约束（`prompt_guardrails`）：

- 默认不烧录字幕、caption、对白叠加
- 每镜一个可见动作、一次运镜（或固定）
- 用可见起止状态，不用抽象气氛词代替动作
- **已有 identity / 九视图参考时**：连续性锁原文照抄，禁止再写脸/发/衣服

`motion_prompt` / `shot_keyframe_prompt` 结构：静态锚点 + 连续性锁原文 + `start → single motion → end` + Refs。

## 来源（MIT，已核许可证；模式提取，非整文件复制）

| 项目 | 借鉴 |
|---|---|
| [ximencuisu/ximen-aimazi](https://github.com/ximencuisu/ximen-aimazi) | 三层去味 + deslop-scan 词表/密度/证据 |
| [Nanako0129/sepia](https://github.com/Nanako0129/sepia) | architecture → discourse → wording |
| [zenstory-ai/oh-story-claudecode](https://github.com/zenstory-ai/oh-story-claudecode) (`skills/story-deslop`) | 禁语簇、Show-don't-tell、成簇判定 |
| [deedeekong07-alt/fiction-humanizer-zh](https://github.com/deedeekong07-alt/fiction-humanizer-zh) | 章节检查表（铺垫/过程/余波、自然钩子） |
| [hestudy/snowflake-fiction](https://github.com/hestudy/snowflake-fiction) (`humanize-text`) | 负向约束：少主题口号、少整齐句式 |
| [zenstory-ai/drama-skills](https://github.com/zenstory-ai/drama-skills) | 起点→唯一动作→终点；默认不烧字幕；锁面原文保留 |
| [ADC1920/AI-short-play-video-creation](https://github.com/ADC1920/AI-short-play-video-creation) | @ref 锁定、有参考后不重写外貌、单动作 |

上游版权声明见各仓库 `LICENSE`（均为 MIT）。本仓库词表与模板是工厂自维护子集，不包含其 skill 正文、脚本或无关 agent 配置。
