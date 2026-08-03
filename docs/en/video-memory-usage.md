# Video Memory Usage Guide

**English** · [中文](../zh/video-memory-usage.md)

This document describes how to install and use the video-memory plugin for efficient semantic analysis and QA on long videos (30+ minutes).

---

## 1. Environment Variables

### Required

| Variable | Description |
|----------|-------------|
| `DASHSCOPE_API_KEY` | DashScope API key. Used for VLM calls and embedding computation. Required for both building and querying memory. |

### Optional — Embedding / API

| Variable | Description | Default |
|----------|-------------|---------|
| `DASHSCOPE_BASE_URL` | Override the DashScope API base URL (for proxies or gateways); also used by the API-backed tools in `qwen-mm-plugins-core` such as `transcribe_audio`. | `https://dashscope.aliyuncs.com/compatible-mode/v1` |

### Optional — Query

| Variable | Description | Default |
|----------|-------------|---------|
| `GRAPH_MEMORY_PATH` | Path to a specific `graph_memory.json`. **Takes precedence over the `video_path` parameter** when both are set; if unset, the server locates it via `video_path`. | Empty (looks up `<video_path>.memory/`) |
| `EMBEDDINGS_PATH` | Path to a specific `embeddings.npz`. | Empty (falls back to `<memory_dir>/embeddings.npz`) |
| `CUTOFF_SEC` | Time cutoff in seconds. Only macro events within this cutoff are loaded during queries. | None (no cutoff) |

### Optional — Build (OSS)

These variables are only needed when building memory. They enable sending video clips to the VLM via signed OSS URLs instead of inline base64 frames. If unset, the build falls back to base64 mode.

| Variable | Description | Default |
|----------|-------------|---------|
| `OSS_AK` | Alibaba Cloud OSS Access Key ID | Empty (OSS disabled) |
| `OSS_SK` | OSS Access Key Secret | Empty |
| `OSS_ENDPOINT` | OSS Endpoint URL | Empty |
| `OSS_BUCKET` | Target bucket for uploading video clips (takes precedence over `OSS_BUCKET_NAME`) | Empty |
| `OSS_VIDEO_CLIP_PREFIX` | Key prefix for uploaded video clips within the bucket | `tmp/video_clips` |
| `OSS_URL_EXPIRY` | Signed URL TTL in seconds | `7200` |

---

## 2. Install the Video Memory Plugin

Run the following commands in your terminal:

```bash
claude plugin marketplace add https://github.com/QwenLM/Qwen-MM-Plugins.git
claude plugin install qwen-mm-plugins-core@qwen-mm-plugins
claude plugin install qwen-mm-plugins-video-memory@qwen-mm-plugins
```

---

## 3. Asking Questions

In the Claude command line, use the `@local_video_path question` format:

```
@/path/to/video.mp4 What is this video about?
```

> **Note**: When the video is longer than 30 minutes, video memory is triggered automatically (this is probabilistic — in rare cases it may not trigger automatically).

---

## 4. First Query: Automatic Memory Build

For videos longer than 30 minutes, the model automatically builds memory on the first query.

- A 1-hour video takes approximately **10 minutes** to build
- Build artifacts are stored in `<video_path>.memory/` next to the video (e.g. `/path/to/video.mp4.memory/`)
- Artifacts include: `graph_memory.json`, `embeddings.npz`, `01_macros.json`, `subgraphs/`

---

## 5. Subsequent Queries: Direct Memory Lookup

After the initial build, subsequent queries on the same video will not rebuild memory. The model directly uses the existing memory and tools to answer questions.

---

## 6. Full Examples: Session Tool Call Traces

Below are two real session visualizations showing different video-memory use cases:

### Example 1: Single Video QA (1-hour cat video)

First query auto-builds memory, then answers content queries (2 turns, 9 tool calls):

[Download Session Trace — Single Video QA (HTML)](../assets/video-memory/video-memory-session-trace.html)
