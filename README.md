# AI-Novel-Drama-Factory

**AI 小说 → 竖屏短剧（9:16）工厂。** 从题材与人设出发，自动完成「大纲 → 章节 → 小说审核 → 分镜 → 角色九视图/场景/道具 → 图像审核 → 图生视频 → 视频审核 → 导出」的全流程，每个产出环节都有可追溯的审核记录与重试闭环。

> 当前阶段：**Phase 0 — 脚手架 + Mock 流水线**。不调用任何真实模型，即可端到端跑通状态机。

## 已锁定的产品决策

| 决策 | 内容 |
|---|---|
| 输出格式 | **竖屏短剧 9:16**（默认 1080×1920）。先做 5–15 秒单镜头片段，后续扩展为 15–60 秒剧集。 |
| 推理方式 | **混合**：小说写作与审核走云端 LLM API；图像/视频通过可插拔适配器，本地（ComfyUI / Wan2.1）或云端均可。Phase 0 全部为 mock。 |
| 语言 | 中文优先（README、文档、生成内容）；代码标识符使用英文。 |
| 章节约束 | 单章 `word_min=2500`、`word_max=5000`；总字数由用户指定，自动规划章节数。 |

## 流水线状态机

```
created → characters → outline → chapters → novel_review ─┬→ storyboard → assets → image_review ─┬→ video → video_review ─┬→ export → done
                                    ↑            revise   │                  ↑        revise     │     ↑       revise    │
                                    └─────────────────────┘                  └───────────────────┘     └─────────────────┘
                              任意非终态 → failed（审核超过重试上限被 reject，或引擎异常）
```

- 状态与转移定义在 `packages/core/src/drama_core/fsm.py`，非法转移直接抛错，每一跳记录在 `Project.stage_history`。
- 审核结果统一为 `Review`（`target_type` / `scores` / `issues` / `action: pass|revise|reject`）。`RetryPolicy` 负责把「最后一次仍需修改」升级为 `reject`，并把「低分 pass」降级为 `revise`。
- 被修改的章节/图片/视频保持 **id 不变**、`revision` 递增，因此同一目标的多轮审核记录可以串起来看。
- 所有状态都存在 `Project` 上（JSON 可序列化），任意 worker 都能断点续跑。

## 仓库结构

```
apps/api/            FastAPI 编排 API 桩 + 内存 Job 队列桩
apps/cli/            drama-factory 命令行，跑 mock 全流程
packages/core/       Project/Character/Scene/Prop/Chapter/Storyboard/Shot/Clip/Review 模型、FSM、章节规划、字数统计
packages/review/     Reviewer 协议、DeterministicMockReviewer、RetryPolicy（ReviewVerdict）
packages/novel/      NovelEngine 协议（人设/大纲/写作/修订）、NovelMemory 文件记忆、MockNovelEngine
packages/storyboard/ StoryboardEngine 协议、MockStoryboardEngine、分镜 markdown 导出
packages/vision/     VisionEngine 协议（九视图/场景/道具/首帧）、MockVisionEngine、ComfyUI 适配器桩
packages/video/      VideoEngine 协议（I2V）、MockVideoEngine、Wan / 云端适配器桩
packages/pipeline/   Orchestrator：按 FSM 驱动各引擎 + 审核闭环 + 导出
workflows/           未来的 ComfyUI 工作流 JSON（仅说明，不含二进制）
docs/opensource.md   开源借鉴清单与许可证边界
tests/               端到端 mock 流水线测试
```

## 安装与运行

需要 Python ≥ 3.11 和 [uv](https://docs.astral.sh/uv/)。

```bash
# 安装 uv（任选其一）
curl -LsSf https://astral.sh/uv/install.sh | sh   # 或: pip install uv

# 安装整个 workspace（含开发依赖）
uv sync

# 跑 mock 全流程（默认 12000 字 → 3 章 → 9 个镜头）
uv run drama-factory demo
uv run drama-factory demo --total-words 30000 --out output -v   # -v 打印每条审核记录

# 可选：从 .env 读取引擎配置
cp .env.example .env
uv run --env-file .env drama-factory demo
```

输出示例（节选）：

```
  [    chapters] -> [novel_review] wrote 3 chapters
  [novel_review] -> [chapters    ] 3 need revision
  [    chapters] -> [novel_review] revised 3 chapters
  [novel_review] -> [storyboard  ] all passed
  ...
  [      export] -> [done        ] exported 9 clips

完成: 3 章 / 9 镜头 / 56 条审核记录 / 总时长 84s
```

导出目录 `output/<project_id>/` 包含：`project.json`（完整项目状态 + 全部审核记录）、`manifest.json`（9:16 时间线）、`memory.md`（故事记忆）、`storyboards/chapter_XXX.md`（分镜表）。

Mock 审核是**确定性**的：每个目标第 1 次审核 `revise`、第 2 次 `pass`，所以 demo 必然走完每个审核环节的一次返工闭环。

### API 桩

```bash
uv run uvicorn drama_api.app:app --reload
# POST /projects            创建项目
# POST /projects/{id}/run   提交流水线任务（Phase 0 为同步执行）
# GET  /jobs/{id}           查询任务
# GET  /projects/{id}       查看完整项目（含审核记录）
```

### 开发检查（与 CI 一致）

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
```

## 路线图

| 阶段 | 目标 | 状态 |
|---|---|---|
| **Phase 0** | 脚手架、领域模型、FSM、mock 引擎、端到端测试、CI | ✅ 本 PR |
| **Phase 1** | **真实小说生成**：在 `NovelEngine` / `Reviewer` 接口后接入云端 LLM（OpenAI 兼容 / DeepSeek / Qwen / Claude）；人设圣经与大纲生成；基于 `NovelMemory` 的逐章写作；LLM-as-judge 小说审核（借鉴 JudgeLM 的多维打分）；字数硬约束校验；章节级断点续跑与持久化 | ⏭ 下一步 |
| Phase 2 | 分镜 LLM 化；ComfyUI 适配器：角色九视图 + PuLID/InstantID ID 锁定、场景/道具参考图、分镜首帧；图像审核（视觉模型 judge） | 规划中 |
| Phase 3 | I2V：本地 Wan2.1 与云端 I2V 适配器；视频审核；剪辑合成、字幕与 TTS 配音；15–60 秒剧集导出 | 规划中 |
| Phase 4 | 任务队列（Redis/RQ）、Web 工作台、人工审核介入、成本与配额统计 | 规划中 |

Phase 1 的关键约束：**不修改 Orchestrator 和 FSM**，只新增 `NovelEngine` / `Reviewer` 的实现，并在 `drama_pipeline.build_orchestrator` 中按 `NOVEL_ENGINE` / `REVIEW_ENGINE` 选择。mock 引擎保留，继续作为 CI 的离线基线。

## 开源借鉴与许可证

见 [`docs/opensource.md`](docs/opensource.md)。要点：只借鉴思路不复制代码；ComfyUI 为 GPL-3.0，仅通过 HTTP API 调用；模型权重、媒体文件与密钥一律不入库。
