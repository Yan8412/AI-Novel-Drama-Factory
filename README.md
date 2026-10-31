# AI-Novel-Drama-Factory

**AI 小说 → 竖屏短剧（9:16）工厂。** 从题材与人设出发，自动完成「大纲 → 章节 → 小说审核 → 分镜 → 分镜审核 → 角色九视图/场景多视图/道具 → 图像审核 → 图生视频 → 视频审核 → 导出」的全流程，每个产出环节都有可追溯的审核记录与重试闭环。

> 当前阶段：**Phase 5 — Redis/RQ 任务队列 + 题材选择 + 实机引擎收口**。`POST /projects/{id}/run` 在 Redis 可用时入队，由 worker 跑流水线；Redis 不可用则同步内存回退。项目带题材预设与版权占位。编排器按 FSM 驱动；通过环境变量选择引擎。**默认仍是 `mock`，CI / demo 离线可跑，不要求 Redis。** Web 工作台留给下一阶段。

## 已锁定的产品决策

| 决策 | 内容 |
|---|---|
| 输出格式 | **竖屏短剧 9:16**（默认 1080×1920）。每镜 5–15 秒；导出时拼成 15–60 秒剧集（或按章分包）。 |
| 推理方式 | **混合**：小说 / 分镜 / 审核可走云端 LLM API（OpenAI 兼容）；图像 / 视频走可插拔适配器（mock / 云端 API / ComfyUI HTTP 桩）。默认全部 mock。 |
| 语言 | 中文优先（README、文档、生成内容）；代码标识符使用英文。 |
| 章节约束 | 单章 `word_min=2500`、`word_max=5000`；总字数由用户指定，自动规划章节数。 |
| 分镜密度 | 短剧节奏：约 250–800 字/镜、每章 2–10 个 5–15 秒镜头，不是电影长镜头。 |

## 流水线状态机

```
created → characters → outline → chapters → novel_review ─┬→ storyboard → storyboard_review ─┬→ assets → image_review ─┬→ video → video_review ─┬→ export → done
                                    ↑            revise   │                  ↑        revise     │           ↑   revise   │     ↑       revise    │
                                    └─────────────────────┘                  └───────────────────┘           └─────────────┘     └─────────────────┘
                              任意非终态 → failed（审核超过重试上限被 reject，或引擎异常）
```

- 状态与转移定义在 `packages/core/src/drama_core/fsm.py`，非法转移直接抛错，每一跳记录在 `Project.stage_history`。
- 审核结果统一为 `Review`（`target_type` / `scores` / `issues` / `action: pass|revise|reject`）。`RetryPolicy` 负责把「最后一次仍需修改」升级为 `reject`，并把「低分 pass」降级为 `revise`。
- 被修改的章节/分镜/图片/视频保持 **id 不变**、`revision` 递增，因此同一目标的多轮审核记录可以串起来看。
- 所有状态都存在 `Project` 上（JSON 可序列化），任意 worker 都能断点续跑。

## 仓库结构

```
apps/api/            FastAPI 编排 API + Redis/RQ 任务队列（无 Redis 时同步内存回退）
apps/cli/            drama-factory 命令行，跑 mock 或可选云端引擎全流程（`--genre` / 版权占位）
packages/core/       Project/Character/Scene/Prop/Chapter/Storyboard/Shot/Clip/Review 模型、题材预设、FSM、章节规划、字数统计
packages/llm/        OpenAI 兼容 Chat Completions 客户端（httpx）+ JSON 抽取
packages/review/     Reviewer 协议、DeterministicMockReviewer、LlmJudgeReviewer、RetryPolicy
packages/novel/      NovelEngine 协议、NovelMemory、MockNovelEngine、CloudNovelEngine
packages/storyboard/ StoryboardEngine：mock / structured（离线节拍） / cloud（LLM JSON）+ 分镜 markdown
packages/vision/     VisionEngine：结构化九视图/场景多视图/道具提示词；mock / cloud Images / ComfyUI HTTP 桩
packages/video/      VideoEngine：mock / cloud（POST /videos） / ComfyUI·Wan HTTP 桩；镜头审核规则 + videos/ 导出
packages/assemble/   Assembler：mock concat 清单 + 剧集桩；可选 ffmpeg 真拼接
packages/tts/        字幕（SRT/VTT）+ TTS 桩；openai speech 为可选付费路径
packages/pipeline/   Orchestrator：按 FSM 驱动各引擎 + 审核闭环 + 剧集导出
workflows/           ComfyUI 工作流 JSON 桩（仅 HTTP 提交，不含 GPL 源码或权重）
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

# 跑 mock 全流程（默认 12000 字 → 3 章 → 9 个镜头；不访问网络）
uv run drama-factory demo
uv run drama-factory demo --genre 玄幻 --license-status original --total-words 30000 --out output -v

# 可选：从 .env 读取引擎配置
cp .env.example .env
uv run --env-file .env drama-factory demo
```

未设置引擎变量或值为 `mock` 时，行为与 Phase 0/1 离线基线一致，适合 CI。

输出示例（节选）：

```
  [    chapters] -> [novel_review] wrote 3 chapters
  [novel_review] -> [chapters    ] 3 need revision
  [    chapters] -> [novel_review] revised 3 chapters
  [novel_review] -> [storyboard  ] all passed
  [  storyboard] -> [storyboard_review] 9 shots
  ...
  [      export] -> [done        ] exported 9 clips / N episodes

完成: 3 章 / 9 镜头 / … 条审核记录 / N 集 / 总时长 84s
```

导出目录 `output/<project_id>/` 包含：`project.json`（完整项目状态 + 全部审核记录）、`manifest.json`（9:16 时间线 + 剧集包）、`memory.md`（故事记忆）、`storyboards/chapter_XXX.md`（分镜表 + 画面/运动提示词）、`assets/*.md`（九视图 / 场景多视图 / 道具提示词与 identity anchors）、`videos/clips.json` + 每镜 sidecar / mock `.mp4` 桩、`episode/`（concat 清单、剧集桩、`PLAY.md`、字幕、TTS 旁路）、`budget.json`（重试 / 估算成本账本）。

Mock 审核是**确定性**的：每个目标第 1 次审核 `revise`、第 2 次 `pass`，所以默认 demo 必然走完每个审核环节的一次返工闭环。

### Phase 5 任务队列 / 题材 / 实机引擎（默认仍离线）

| 变量 | 默认 | Phase 5 取值 |
|---|---|---|
| `JOB_QUEUE` | `auto` | `memory`（同步内存） / `redis`（必须连上 `REDIS_URL`） / `auto`（Redis 可达则入队，否则回退 memory） |
| `REDIS_URL` | `redis://127.0.0.1:6379/0` | 仅 `JOB_QUEUE=auto\|redis` 时使用 |

- **无 Redis**：API 与 CI 走 `InlineJobQueue`，`POST /projects/{id}/run` **同步**跑完流水线，立刻返回 `succeeded` / `failed`。不需要起 worker。
- **有 Redis**：`POST /run` 把项目 JSON 写入 Redis，RQ 入队，`GET /jobs/{id}` 映射 RQ 状态（`queued` / `running` / `succeeded` / `failed`）。另开 worker：

```bash
docker compose up -d          # 仅 Redis，无 GPU / Comfy / 权重
uv run drama-factory-worker   # 或: uv run python -m drama_api.worker
uv run uvicorn drama_api.app:app --reload
```

`docker-compose.yml` **只**起 Redis。不要把 ComfyUI 源码、权重或密钥放进仓库。

题材是一等字段：预设 `都市 / 玄幻 / 古言 / 悬疑 / 甜宠 / 爽文`，也接受自由文本（如默认 demo「都市甜宠」）。`license_status`（`unknown|original|licensed`）与 `rights_note` 只是文档占位，**不构成权利声明或法律意见**。

```bash
# CLI
uv run drama-factory demo --genre 悬疑 --license-status original --rights-note "原创短篇占位"

# API
# POST /projects   {title, genre, premise, total_words, license_status?, rights_note?}
# GET  /genres     预设列表 + 版权免责声明
```

Mock / cloud 小说提示词都会带上 `题材「…」` 风格说明。

#### 从 mock 切到 cloud / Comfy（密钥不入库）

```bash
cp .env.example .env
# 只在本地 .env 填 OPENAI_API_KEY / VIDEO_API_KEY；不要 git add .env

NOVEL_ENGINE=cloud uv run --env-file .env drama-factory demo --genre 都市 --total-words 6000
VISION_ENGINE=cloud uv run --env-file .env drama-factory demo --total-words 6000
VIDEO_ENGINE=cloud  uv run --env-file .env drama-factory demo --total-words 6000

# 本地已有 ComfyUI HTTP 时才开；本仓库不 vendor ComfyUI / 权重
VISION_ENGINE=comfy VIDEO_ENGINE=comfy uv run --env-file .env drama-factory demo --total-words 6000
```

适配器报错会打码 `Bearer` / `sk-` / `api_key=`，并提示缺密钥时保持 `*_ENGINE=mock`。

可选实机测试（CI 默认跳过）：

```bash
RUN_LIVE_LLM=1    uv run pytest -m integration tests/test_live_llm.py
RUN_LIVE_VIDEO=1  uv run pytest -m integration tests/test_live_video.py
RUN_LIVE_VISION=1 uv run pytest -m integration tests/test_live_vision.py
RUN_LIVE_COMFY=1  uv run pytest -m integration tests/test_live_comfy.py
RUN_LIVE_REDIS=1  uv run pytest -m integration tests/test_live_redis.py
```

### Phase 4 剧集装配 / 字幕 / 审核覆盖（默认仍离线）

| 变量 | 默认 | Phase 4 取值 |
|---|---|---|
| `ASSEMBLE_ENGINE` | `mock` | `ffmpeg`（PATH 上有 `ffmpeg` 且片段是真实媒体时才真正拼接） |
| `TTS_ENGINE` | `mock` | `off` / `openai`（`POST {base}/audio/speech`；无密钥或失败则回退 mock，不阻断导出） |
| `SUBTITLE_FORMAT` | `both` | `srt` / `vtt` / `off` |
| `REVIEW_MAX_ATTEMPTS` | `3` | 小说 / 图像 / 视频（及分镜）共用重试上限；`REVIEW_MAX_RETRIES` 为同义 |
| `REVIEW_OVERRIDE` | （空） | `pass` / `revise` / `reject`，强制全部审核结论且**不跑模型** |
| `REVIEW_OVERRIDE_FILE` | （空） | JSON：`{ "global", "types": {chapter\|storyboard\|asset\|clip}, "targets": {id} }` |

- **装配**：`Assembler` 按镜头顺序打包 15–60 秒 9:16 剧集，优先切在章节边界；超长章拆包，过短章合并。`mock` 写 `episode/concat_*.txt` + ASCII `.mp4` 桩 + `episode/episodes.json`。`ffmpeg` 在条件满足时执行 `ffmpeg -y -f concat -safe 0 -i <list> -c copy`。
- **播放**：mock 桩**不可播**。有真实 MP4 后按 `episode/PLAY.md` 拼接 / 软字幕。
- **字幕**：从 `Shot.dialogue`（没有对白则用动作括注）写出 SRT + VTT，时间轴按 clip 时长累加。
- **TTS**：默认只写 `episode/tts/shot_XXX.json` 旁路。`TTS_ENGINE=openai` 才打付费语音；密钥不入库。
- **三层审核**：小说 / 图像 / 视频共用 `RetryPolicy.max_attempts`；revise 反馈串起来回写到对应生产阶段。每次审核与生成记入 `budget.json`（mock 估算成本为 0）。
- **人工覆盖**：CLI `--override-verdict pass` / `--override-file ovr.json`，或 `POST /projects/{id}/override`。覆盖后跳过模型与规则加严，也不再被「最后一次 revise → reject」升级。给后续 Web UI 留钩子。

```bash
# 默认 mock：小说 → 分镜 → 资产 → 片段 → 剧集包 + 字幕 + 账本
uv run drama-factory demo --total-words 6000 --out output -v

# 强制全部审核通过（不跑模型，适合对照导出）
uv run drama-factory demo --total-words 3000 --out output --override-verdict pass

# 有真实片段且本机有 ffmpeg 时尝试真拼接
ASSEMBLE_ENGINE=ffmpeg uv run drama-factory demo --total-words 6000 --out output
```

播放 / 拼接（真实 MP4 时）：

```bash
ffmpeg -y -f concat -safe 0 -i output/<project_id>/episode/concat_full.txt \
  -c copy -movflags +faststart output/<project_id>/episode/full.mp4
# 可选烧录字幕
ffmpeg -y -i output/<project_id>/episode/full.mp4 \
  -vf subtitles=output/<project_id>/episode/subtitles.srt \
  output/<project_id>/episode/full_subs.mp4
```

覆盖文件示例 `overrides.json`：

```json
{
  "global": null,
  "types": { "chapter": "pass" },
  "targets": { "clip_ab12": "revise" },
  "reason": "qa desk"
}
```

### Phase 2 分镜与资产（默认仍离线）

| 变量 | 默认 | Phase 2 取值 |
|---|---|---|
| `STORYBOARD_ENGINE` | `mock` | `structured`（离线按字数切节拍） / `cloud`（OpenAI 兼容 JSON 分镜） |
| `VISION_ENGINE` | `mock` | `cloud`（OpenAI 兼容 Images API） / `comfy` 或 `comfyui`（HTTP `/prompt` 桩） |
| `STORYBOARD_MODEL` | `gpt-4o-mini` | 分镜 LLM |
| `VISION_MODEL` | `gpt-image-1` | 云端图像模型 |
| `COMFYUI_URL` | `http://127.0.0.1:8188` | 仅 `VISION_ENGINE=comfy` 时使用 |

- `StructuredStoryboardEngine`：把章节正文切成对白/动作节拍，按 250–800 字/镜打包成 5–15 秒竖屏镜头，并回填角色 / 场景 / 道具引用。
- `CloudStoryboardEngine`：要求模型返回镜头 JSON；解析失败时回退 structured。
- 视觉层先生成**结构化提示词**（角色 3×3 九视图 + 脸/服装/色板 identity lock；场景九宫多角度 / 时段；道具 continuity；分镜首帧引用上述锁定）。`mock` 只写 `mock://` URI，不画像素。
- 分镜审核：规则（镜头数、9:16、引用、动作/提示词）+ 可选 `REVIEW_ENGINE=llm_judge`。`mock://` 图像 / 视频在 LLM judge 下自动 pass。

### Phase 3 镜头视频（默认仍离线）

| 变量 | 默认 | Phase 3 取值 |
|---|---|---|
| `VIDEO_ENGINE` | `mock` | `cloud`（OpenAI 兼容 `POST /videos`） / `comfy` 或 `comfyui` / `wan` |
| `VIDEO_MODEL` | `sora-2` | 云端 I2V 模型名 |
| `VIDEO_API_KEY` / `VIDEO_BASE_URL` | （空 → 回退 `OPENAI_*`） | 独立视频网关；`cloud:kling` / `cloud:runway` 也可读 `KLING_API_KEY` / `RUNWAY_API_KEY` |
| `COMFYUI_URL` | `http://127.0.0.1:8188` | 仅 `VIDEO_ENGINE=comfy\|wan` 时使用 |

- `MockVideoEngine`：每镜一条 `mock://` URI + 带身份锁定 / 上一镜引用的运动提示词；导出时在 `videos/` 写下可检视的文本桩 `.mp4`（不是可播放片）。
- `CloudVideoEngine`：文档化的 OpenAI 兼容形状 `POST {base_url}/videos`（`model` / `prompt` / `seconds` / `size` / `input_reference`）。立即返回 `{data:[{url}]}` 或 `{id,status}` 后轮询 `GET /videos/{id}`。Kling / Runway **原生**协议不同，请把 `VIDEO_BASE_URL` 指到兼容网关。
- `ComfyUIVideoEngine` / `WanVideoEngine`：只 HTTP POST `workflows/wan21_i2v.json` 桩，返回 `comfy://<prompt_id>`。不 vendor ComfyUI（GPL-3.0）源码，不下载权重。
- **连续性**：编排器把 Phase 2 九视图 / 场景 / 道具 URI 和上一镜 `Clip` 传入 `image_to_video`。大多数 I2V API 只吃**一张首帧 + 文本**，上一镜视频只作为 URI / 摘要提示，不是像素级锁。真实 Wan 图需要自己把 `LoadImage` 绑到分镜首帧。
- **视频审核**：规则（9:16、5–15s、时长对齐分镜、keyframe 引用）；`REVIEW_ENGINE=llm_judge` 对非 `mock://` 片段打 **motion_quality / identity_consistency / temporal_coherence**。`mock://` 自动 pass。

```bash
# 默认 mock：离线跑完 video 阶段并写出 videos/clips.json
uv run drama-factory demo --total-words 6000 --out output -v

# 云端 I2V（产生费用，CI 不跑）
VIDEO_ENGINE=cloud \
  uv run --env-file .env drama-factory demo --total-words 6000 --out output -v
```

可选：`RUN_LIVE_VIDEO=1 uv run pytest -m integration` 打一条真实 `POST /videos`（需密钥；CI 默认跳过）。

```bash
# 离线真实分镜（无 LLM），图像仍是 mock 占位
STORYBOARD_ENGINE=structured uv run drama-factory demo --total-words 6000 --out output -v
```

### Phase 1 真实云端 LLM（可选）

编排器 / FSM 只增加 `storyboard_review` 一环。CLI 与 API 都通过 `Settings.from_env()` → 各 `create_*` 工厂选实现。

| 变量 | 默认 | Phase 1 取值 |
|---|---|---|
| `NOVEL_ENGINE` | `mock` | `cloud`（OpenAI 兼容；`openai` / `deepseek` / `qwen` 为同义） |
| `REVIEW_ENGINE` | `mock` | `llm_judge` |
| `OPENAI_API_KEY` | （空） | 云端密钥，**不要提交** |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | DeepSeek / 通义等兼容网关 |
| `NOVEL_MODEL` / `REVIEW_MODEL` | `gpt-4o-mini` | 写作 / 审核各自的模型名 |

`CloudNovelEngine`：人设圣经 → 中文大纲 → 逐章写作（目标 2500–5000 字，用 `count_words` 校验，超区间会再请模型扩写/删减）→ 与 `MockNovelEngine` 相同结构的 `NovelMemory` 增量。

`LlmJudgeReviewer`：要求模型返回与 `Review` 对齐的 JSON（`scores` / `issues` / `action: pass|revise|reject`）。小说维度为 **coherence、character_consistency、word_count_band、sensitive_content**；分镜维度为 **pacing、coverage、vertical_framing、continuity**；视频维度为 **motion_quality、identity_consistency、temporal_coherence**；同时跑字数硬约束与禁词桩（`REVIEW_BANLIST`，默认空）。图像/视频在 URI 为 `mock://` 时自动 pass。

#### 现场 demo

```bash
cp .env.example .env
# 填写 OPENAI_API_KEY；如用 DeepSeek / Qwen 再改 OPENAI_BASE_URL 与模型名

# 小说走云端，审核走 LLM-as-judge；分镜/图像/视频仍是 mock
NOVEL_ENGINE=cloud REVIEW_ENGINE=llm_judge \
  uv run --env-file .env drama-factory demo --total-words 6000 --out output -v

# 分镜也走云端 JSON（失败回退 structured）；图像仍 mock
NOVEL_ENGINE=cloud STORYBOARD_ENGINE=cloud REVIEW_ENGINE=llm_judge \
  uv run --env-file .env drama-factory demo --total-words 6000 --out output -v

# 云端图像（OpenAI 兼容 /images/generations）— 会产生费用，CI 不跑
VISION_ENGINE=cloud \
  uv run --env-file .env drama-factory demo --total-words 6000 --out output -v

# 云端 I2V（OpenAI 兼容 /videos）— 会产生费用，CI 不跑
VIDEO_ENGINE=cloud \
  uv run --env-file .env drama-factory demo --total-words 6000 --out output -v
```

可选：`RUN_LIVE_LLM=1 uv run pytest -m integration` 打一条真实 Chat Completions（CI 默认跳过）。

ComfyUI 路径只通过 HTTP 提交 `workflows/*.json` 桩。本仓库不 vendor ComfyUI（GPL-3.0）源码。未启动本地 Comfy 时不要设 `VISION_ENGINE=comfy` 或 `VIDEO_ENGINE=comfy` / `wan`。

### API

```bash
uv run uvicorn drama_api.app:app --reload
# GET  /health              {status, queue: memory|redis}
# GET  /genres              题材预设 + 版权占位说明
# POST /projects            创建项目（genre + 可选 license_status / rights_note）
# POST /projects/{id}/run   入队流水线（Redis）或同步执行（内存回退）
# POST /projects/{id}/override  人工审核覆盖 {action, target_id?, target_type?, reason?}
# GET  /jobs/{id}           查询 RQ / 内存任务状态
# GET  /projects/{id}       查看完整项目（含审核记录 / 剧集 / 账本）
```

`GET /health` 的 `queue` 字段标明当前后端。无 Redis 时不要起 worker，API 仍可跑 mock demo。

### 开发检查（与 CI 一致）

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
```

CI 不设置云端引擎、不注入密钥，始终走 mock。

## 路线图

| 阶段 | 目标 | 状态 |
|---|---|---|
| **Phase 0** | 脚手架、领域模型、FSM、mock 引擎、端到端测试、CI | ✅ 已合并 |
| **Phase 1** | **真实小说生成**：云端 LLM 写作 + LLM-as-judge 小说审核；字数硬约束 | ✅ 已合并 |
| **Phase 2** | 分镜（structured / cloud）；角色九视图 + 场景多视图 + 道具提示词；可插拔视觉引擎（mock / cloud Images / Comfy HTTP 桩）；分镜审核 | ✅ 已合并 |
| **Phase 3** | 每镜 I2V（mock / cloud `POST /videos` / Comfy·Wan HTTP 桩）；身份锁定 + 上一镜连续性提示；视频规则审核 + 可选 LLM judge；`videos/` 清单导出 | ✅ 已合并 |
| **Phase 4** | 15–60s 剧集装配（concat / 可选 ffmpeg）；SRT/VTT + TTS 桩；三层审核共用重试预算账本；人工覆盖文件 / CLI / API | ✅ 已合并 |
| **Phase 5** | Redis/RQ 任务队列（无 Redis 则内存回退）；题材预设 + 版权占位；实机引擎报错收口与 `RUN_LIVE_*=1` 集成测试 | ✅ 本 PR |
| 之后 | **Web 工作台**（人工审核介入 UI）、真实配额计费 | 规划中 |

Phase 5 的关键约束：**默认 mock 离线**；CI 不要求 Redis；不把 ComfyUI / 权重 / 密钥入库；`license_status` / `rights_note` 只是文档占位。本阶段**不做**完整前端 / Web 工作台。

## 开源借鉴与许可证

见 [`docs/opensource.md`](docs/opensource.md)。要点：只借鉴思路不复制代码；ComfyUI 为 GPL-3.0，仅通过 HTTP API 调用；模型权重、媒体文件与密钥一律不入库。
