# workflows/

这里将存放 ComfyUI 工作流 JSON（API 格式），供 `drama_vision.ComfyUIVisionEngine` 与 `drama_video.WanVideoEngine` 通过 HTTP API 提交。Phase 0 为空。

规划中的工作流：

| 文件 | 用途 | 依赖节点 |
|---|---|---|
| `character_nine_view.json` | 角色 3×3 九视图定妆 | PuLID / InstantID |
| `scene_reference.json` | 场景参考图 | — |
| `prop_reference.json` | 道具参考图 | — |
| `shot_keyframe.json` | 分镜首帧（参考角色九视图 + 场景） | PuLID / IPAdapter |
| `wan21_i2v.json` | Wan2.1 图生视频 9:16 | Wan wrapper |

约定：

- 只提交 **API 格式 JSON**（体积小、可 diff）。不要提交模型权重、示例图片或视频（`.gitignore` 已拦截）。
- 节点所需权重在 README 中写明下载地址，运行时下载到 `WEIGHTS_DIR`。
- ComfyUI 本体为 **GPL-3.0**：本仓库只通过其 HTTP/WebSocket API 调用，不 import、不复制其 Python 代码。自定义节点各有许可证，见 `docs/opensource.md`。
