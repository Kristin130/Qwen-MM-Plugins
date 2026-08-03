# Video Memory 使用手册

[English](../en/video-memory-usage.md) · **中文**

本文档介绍如何安装和使用 video-memory 插件，对长视频（30 分钟以上）进行高效的语义分析和问答。

---

## 1. 环境变量配置

### 必需

| 变量 | 说明 |
|------|------|
| `DASHSCOPE_API_KEY` | DashScope API 密钥，用于 VLM 调用和 embedding 计算。构建和查询 memory 均需要。 |

### 可选 — Embedding / API

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DASHSCOPE_BASE_URL` | 覆盖 DashScope API 地址（用于代理或网关）；也用于 qwen-mm-plugins-core 中需要 API 的工具（如 transcribe_audio）。 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |

### 查询可选

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `GRAPH_MEMORY_PATH` | 指定 `graph_memory.json` 路径。**同时设置时优先于 `video_path` 参数**;未设置时通过 `video_path` 自动定位。 | 空（按 `<video_path>.memory/` 查找） |
| `EMBEDDINGS_PATH` | 指定 `embeddings.npz` 路径。 | 空（按 `<memory_dir>/embeddings.npz` 查找） |
| `CUTOFF_SEC` | 查询时的时间截止点（秒），仅加载截止时间内的 macro event。 | 无（不截断） |

### 构建可选（OSS）

以下变量仅在构建 memory 时需要，用于通过 OSS 签名 URL 向 VLM 传递视频片段（而非 base64 帧）。不设置时自动回退到 base64 模式。

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `OSS_AK` | 阿里云 OSS Access Key ID | 空（OSS 不启用） |
| `OSS_SK` | OSS Access Key Secret | 空 |
| `OSS_ENDPOINT` | OSS Endpoint URL | 空 |
| `OSS_BUCKET` | 上传视频片段的目标 Bucket（优先级高于 `OSS_BUCKET_NAME`） | 空 |
| `OSS_VIDEO_CLIP_PREFIX` | Bucket 内视频片段的 Key 前缀 | `tmp/video_clips` |
| `OSS_URL_EXPIRY` | 签名 URL 有效期（秒） | `7200` |

---

## 2. 安装 Video Memory 插件

在终端中执行以下命令：

```bash
claude plugin marketplace add https://github.com/QwenLM/Qwen-MM-Plugins.git
claude plugin install qwen-mm-plugins-core@qwen-mm-plugins
claude plugin install qwen-mm-plugins-video-memory@qwen-mm-plugins
```

---

## 3. 提问方式

在 Claude 命令行中，使用 `@本地视频路径 问题` 的格式提问：

```
@/path/to/video.mp4 这个视频讲了什么事情?
```

> **注意**：当视频时长超过 30 分钟时，会自动触发 video memory 功能（概率性触发，少部分情况不会自动触发）。

---

## 4. 首次提问：自动构建 Memory

对于 30 分钟以上的视频，首次提问时模型会自动构建 memory。

- 1 小时的视频预计约 **10分钟** 构建完毕
- 构建产物存储在视频同级目录的 `<video_path>.memory/` 下（如 `/path/to/video.mp4.memory/`）
- 产物包含：`graph_memory.json`、`embeddings.npz`、`01_macros.json`、`subgraphs/`

---

## 5. 后续提问：直接查询 Memory

构建完成后，对同一视频的后续提问不会重复构建 memory，模型会直接根据已有的 memory 和工具来回答问题。

---

## 6. 完整示例：Session 工具调用轨迹

以下是两个真实 session 的可视化记录，展示了 video-memory 的不同使用场景：

### 示例 1：单视频 QA（1小时猫咪视频）

首次提问自动构建 memory，然后基于 memory 回答内容查询（2 轮对话，9 次工具调用）：

[下载 Session Trace — 单视频 QA (HTML)](../assets/video-memory/video-memory-session-trace.html)
