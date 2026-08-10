---
name: qwen-mm-plugins-api
description: Cloud vision-language MCP tools for understanding media — vision_chat (caption/VQA), ocr, grounding (detect/locate objects), segmentation, and transcribe_audio (ASR). Use when a question about an image/video/audio needs an external model, not just local reading.
---

# Qwen-MM-Plugins API

You have `qwen-mm-plugins-api` MCP tools available. They call external models/services to understand media: DashScope vision-language (`vision_chat`, `ocr`, `grounding`), DashScope ASR (`transcribe_audio`), and a SAM3 server (`segmentation`). Prefer these over manual scripting.

Check the `qwen-mm-plugins-api` tools in your tool list for full schemas and parameters.

## When to Use Which Tool

- **Ask an external VLM** about images/videos (caption, VQA, free-form) → `vision_chat`
- **Extract text** from an image → `ocr`
- **Detect/locate objects** in an image (bounding boxes) → `grounding`
- **Segment objects** in an image (masks) → `segmentation`
- **Transcribe speech** from audio/video → `transcribe_audio`

## Tips

**Vision chat**: pass `images`/`videos` + `text` prompt. Default model `qwen3.7-plus`. Use `dry_run=true` to inspect payloads. Details in `references/vision_chat.md`.

**Grounding**: returns normalized boxes (0–1000). Set `return_img=true` to get the annotated image back, or draw them yourself with core's `draw_bbox`. Needs `DASHSCOPE_API_KEY`.

**ASR**: accepts audio or video, auto-chunks long files. Formats: `srt` (default), `text`, `json`. Needs `DASHSCOPE_API_KEY` (and `ffmpeg` to pull the audio track from a video).

**Segmentation**: needs a SAM3 server (`SAM3_SERVER_URL`). To stand one up, run `references/launch_sam3_server.py` (multi-GPU HTTP server; see its header for prerequisites).

## Relationship to Other Capabilities (do NOT overlap)

- **Read/visualize local files** (images, video frames, PDF, Office, 3D, ...) → `qwen-mm-plugins-core` (`read_image`/`read_video`/`visualize`/`crop`/`draw_bbox`/`save_view`). Core is local and needs no API key; this capability is the cloud layer on top.
- **Confirm a fact or identify an entity** (reverse image / web) → `qwen-mm-plugins-search` (`image_search`/`web_search`/`web_extractor`).
- **Omni-model audio/video understanding** (timestamped captioning, controllable / multi-speaker ASR, temporal grounding, event counting) → `qwen-mm-plugins-omni-av`. That capability runs the Qwen-Omni model; `vision_chat`/`grounding`/`transcribe_audio` here run the qwen-vl / qwen3-asr models. Pick by which model you want.
