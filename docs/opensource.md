# 开源借鉴清单 (Open-source borrow list)

原则：**只借鉴思路与接口设计，不复制代码**。需要用到其运行时能力时，通过进程边界（HTTP API / CLI / 独立服务）调用。下表许可证已于 2026-10 通过 GitHub API 核对。

| 项目 | 许可证 | 借鉴点 | 对应本仓库位置 |
|---|---|---|---|
| [GOAT-AI-lab/GOAT-Storytelling-Agent](https://github.com/GOAT-AI-lab/GOAT-Storytelling-Agent) | MIT | 自顶向下规划：premise → 大纲 → 章节 → 场景的分层生成；长篇一致性的提示词结构 | `packages/novel`：`NovelEngine.write_outline / write_chapter` |
| [xiaoxiaoxiaotao/novel-bot](https://github.com/xiaoxiaoxiaotao/novel-bot) | MIT | 以纯文件（markdown）作为长期记忆；agent 循环「读记忆 → 写章节 → 回写记忆」 | `packages/novel/memory.py`（`NovelMemory`, `memory.md`），`Chapter.memory_delta` |
| [mocksu/itube-public](https://github.com/mocksu/itube-public) | MIT | 小说 → 视频的整体编排；单卡 16GB 下 FLUX + Wan + PuLID 的 ComfyUI 流程拆分 | `packages/pipeline` 编排、`workflows/` 规划 |
| [Gitruck/ai-drama-desk](https://github.com/Gitruck/ai-drama-desk) | MIT | 分镜以 markdown 表格作为人可编辑的中间产物，再驱动 I2V | `drama_storyboard.to_markdown`，导出 `storyboards/*.md` + 每镜 9:16 提示词 |
| [Wan-Video/Wan2.1](https://github.com/Wan-Video/Wan2.1) | Apache-2.0 | 本地 I2V 主力模型（480P/720P，支持竖屏） | `drama_video.WanVideoEngine` / `ComfyUIVideoEngine`：仅 HTTP POST `workflows/wan21_i2v.json` |
| [cubiq/PuLID_ComfyUI](https://github.com/cubiq/PuLID_ComfyUI) | Apache-2.0 | 角色 ID 锁定（人脸一致性）节点 | `Character.visual_lock`、`workflows/character_nine_view.json` |
| [instantX-research/InstantID](https://github.com/instantX-research/InstantID) / [cubiq/ComfyUI_InstantID](https://github.com/cubiq/ComfyUI_InstantID) | Apache-2.0 | 备选 ID 锁定方案 | `VisualLock.id_method = "instantid"` |
| [baaivision/JudgeLM](https://github.com/baaivision/JudgeLM) | Apache-2.0 | LLM-as-judge：多维打分 + 理由；交换位置消除偏置；参考答案引导 | `packages/review`：`Reviewer` 协议、`Review.scores/issues`、`RetryPolicy` |

## 许可证边界

- **ComfyUI 本体是 GPL-3.0**（[comfyanonymous/ComfyUI](https://github.com/comfyanonymous/ComfyUI)）。本仓库只把它当作独立服务，通过 HTTP/WebSocket API 提交 `workflows/*.json`。**禁止** `import comfy`、复制其源码或将其静态链接/打包进本仓库的 Python 包。
- 自定义节点（PuLID、InstantID、Wan wrapper 等）各自有许可证，同样只在 ComfyUI 进程内运行，不进入 `packages/`。
- **模型权重许可证 ≠ 代码许可证**。例如 PuLID / InstantID 依赖的 InsightFace 人脸模型（antelopev2 等）仅限非商业研究用途；商用前须单独评估或替换。Wan2.1 权重为 Apache-2.0。
- 权重一律运行时下载到 `WEIGHTS_DIR`，不提交到仓库（见 `.gitignore`）。

## 新增条目流程

1. 用 `gh api repos/<owner>/<repo> --jq .license.spdx_id` 核对许可证。
2. 写清「借鉴什么」和「落在本仓库哪个接口」。
3. GPL/AGPL/非商业许可证必须标注边界，默认只允许进程外调用。
