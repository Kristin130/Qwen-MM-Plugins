# Cookbook — Qwen-MM-Plugins Core (+ api / search)

`qwen-mm-plugins-core` is the local file capability: read and visualize any file at model-optimized
resolution, plus image tools (crop, annotate, extract frames). The cloud model/API tools that
used to live here now ship as two sibling capabilities — `qwen-mm-plugins-api` (caption/OCR/grounding/
segmentation/ASR) and `qwen-mm-plugins-search` (web + reverse-image search). This cookbook covers the
family; the tool list below marks which plugin each tool belongs to. See the [Cases](#cases) below
for worked examples.

---

## Tools

**`qwen-mm-plugins-core` — local reading (content fed directly to the model)**
- `read_image` — dynamic-resolution image reading
- `read_video` — extracts video frames with automatic FPS / resolution
- `media_info` — full media metadata via ffprobe (run before any clip/edit)
- `visualize` — general-purpose file visualization: PDF / Office / CSV / code / SVG / DrawIO / 3D / GIS / Notebook / LaTeX

**`qwen-mm-plugins-core` — image / frame output (saved to file + preview)**
- `crop` — crop an image by box (normed to 0-1000)
- `draw_bbox` — draw annotation boxes on an image (pairs with `grounding`)
- `save_view` — extract document pages / video frames into standalone image files

**`qwen-mm-plugins-api` — cloud understanding (DashScope + SAM3)**
- `vision_chat` — call a vlm (default: qwen3.7-plus) for vision chat, supporting image / video input
- `ocr` — text recognition in images
- `grounding` — object detection/localization, returning pixel bboxes (pairs with `draw_bbox`)
- `segmentation` — text-prompted segmentation (self-hosted SAM3)
- `transcribe_audio` — speech recognition (default: qwen3-asr), output as SRT / text / JSON

**`qwen-mm-plugins-search` — web + reverse-image search (Serper)**
- `web_search` — web search, returning titles / snippets / URLs
- `web_extractor` — fetch a web page's main text, optionally summarized
- `image_search` — search by image (reverse image search)

> For exact schemas, see each capability's `SKILL.md` or each tool's inputSchema.

---

## Install

```bash
claude plugin marketplace add https://github.com/Kristin130/Qwen-MM-Plugins.git
claude plugin install qwen-mm-plugins-core@qwen-mm-plugins      # local reading
claude plugin install qwen-mm-plugins-api@qwen-mm-plugins       # cloud understanding (optional)
claude plugin install qwen-mm-plugins-search@qwen-mm-plugins    # web/image search (optional)
```

## Environment variables

| Variable | Description |
|----------|-------------|
| `QWEN_MM_PROVIDER1_BASE_URL` / `QWEN_MM_PROVIDER1_API_KEY` | `qwen-mm-plugins-api` — the provider-pool tools (`vision_chat`, `ocr`, `grounding`, `transcribe_audio`). Provider 1 = primary, providers 2+ = failover (legacy `DASHSCOPE_API_KEY` works as provider-1 alias). `core`'s local reading needs no key. |
| `QWEN_MM_PROVIDER<n>_BASE_URL` | Optional — additional failover providers (any OpenAI-compatible endpoint). |
| `SERPER_API_KEY` | `qwen-mm-plugins-search` — the web/image tools (`web_search` / `web_extractor` / `image_search`). Sign up at [serper.dev](https://serper.dev) — a Google-search API with a free starter tier |
| `SAM3_SERVER_URL` | `qwen-mm-plugins-api` — only for `segmentation`. SAM3 is **self-hosted**: stand up the GPU HTTP server with the skill's [`references/launch_sam3_server.py`](../../src/capabilities/api/skill/references/launch_sam3_server.py) (needs the `sam3` package, a CUDA-enabled PyTorch, and the SAM3 checkpoint), then point this at it, e.g. `http://localhost:8787`. |

> Set these via env vars, `~/.qwen-mm-plugins/config`, or the guided installer **`bash install.sh`** (`bash install.sh verify` checks what's set). Precedence: env var > config file > default.

---

## Cases

### Case 1 — read a video, then read Figure 2 from a PDF (Claude Code)

Reads a full promo video, then opens a 35-page PDF and pulls out a specific figure.

▶ **[View the detailed trace in Claude Code](https://qianwen-res.oss-accelerate.aliyuncs.com/Qwen-MM-Plugins/asserts/core/case-core-cc-basic-use.html)**

<p align="center">
  <img src="assets/cc-basic-use.png" alt="Claude Code trace — video + PDF figure" width="520">
</p>

### Case 2 — locate the cakes, then identify a place through the DashScope service (Codex)

`@cakes.png` → detect every cake and draw numbered boxes; `@place.png` → identify the location, cross-checked with a web search.

▶ **[View the detailed trace in Codex](https://qianwen-res.oss-accelerate.aliyuncs.com/Qwen-MM-Plugins/asserts/core/case-core-codex-api-use.html)**


<p align="center">
  <img src="assets/codex-api-use.png" alt="Codex trace — cake detection + place identification" width="520">
</p>

### Case 3 — install the plugins in GUI harness e.g. QwenWork, QoderWork

Just **Query** the agent to set up: `hello 帮我装一下 https://github.com/Kristin130/Qwen-MM-Plugins 的 core 和 edu 插件`

The agent installs the `core` + `edu-agent` skills and the core MCP server:

<p align="center">
  <img src="assets/qwenwork-install.png" alt="QwenWork installing qwen-mm-plugins core + edu-agent (skills enabled, 14 MCP tools ready)" width="520">
</p>
