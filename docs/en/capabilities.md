# Capabilities & Tools

**English** · [中文](../zh/capabilities.md)

Qwen-MM-Plugins ships six capabilities, each installed separately (see [Installation](../../README.md#-installation)). This page lists what each provides.

- [🖼 core — vision](#-core--vision)
- [🎬 video-memory — long-video memory](#-video-memory--long-video-memory)
- [✂️ video-edit — editing + generation](#-video-edit--editing--generation)
- [🧊 blender — 3D modeling](#-blender--3d-modeling)
- [📐 freecad — parametric CAD](#-freecad--parametric-cad)
- [🎓 edu-agent — tutorial videos](#-edu-agent--tutorial-videos)

---

## 🖼 core — vision

Foundational multimodal reading + analysis. Install name / entry: `qwen-mm-plugins-core`.

**Reading (content fed directly to the model)**
- `read_image` — dynamic-resolution image reading, aligned to the model's patch grid
- `read_video` — extracts video frames with automatic FPS / resolution
- `visualize` — general-purpose file visualization: PDF / Office / CSV / code / SVG / DrawIO / 3D / GIS / Notebook / LaTeX

**Multimodal APIs (DashScope)**
- `vision_chat` — vision chat, supporting image / video input
- `ocr` — text recognition in images
- `grounding` — object detection/localization, returning pixel bboxes (pairs with `draw_bbox` to draw the boxes)
- `segmentation` — text-prompted segmentation (SAM3)
- `transcribe_audio` — speech recognition (ASR), output as SRT / text / JSON

**Image / frame output (saved to file + preview)**
- `crop` — crop an image by box
- `draw_bbox` — draw annotation boxes on an image
- `save_view` — extract document pages / video frames into standalone image files

**Web (Serper)**
- `web_search` — web search, returning titles / snippets / URLs
- `web_extractor` — fetch a web page's main text, optionally summarized
- `image_search` — search by image (reverse image search)

Keys: the multimodal APIs need `DASHSCOPE_API_KEY`; the web tools need `SERPER_API_KEY`. Native image/video/document reading needs no key. See [Dependencies](../../README.md#-dependencies). For exact schemas, see the capability's `SKILL.md` or each tool's inputSchema.

---

## 🎬 video-memory — long-video memory

A hierarchical graph memory for QA over very long videos (30+ minutes). Install name / entry: `qwen-mm-plugins-video-memory`.

Usage is workflow-based: ask `@/path/to/video.mp4 <question>` in your harness. On the first query the plugin builds a 4-level graph (Root → SuperEvent → MacroEvent → Subgraph) plus an embedding index next to the video, then answers using these query tools (a drill-down pattern):

- `get_summary` — the video-level root summary (title, themes, key entities, tone)
- `get_super_events` — list the high-level narrative arcs (super events)
- `get_macro_events` — list macro events (optionally within a given super event)
- `get_subgraph` — drill into one macro event's detailed subgraph (entities / events / edges / on-screen text)
- `search_nodes` — semantic search over entity & event nodes by embedding similarity
- `enumerate_events` — enumerate ALL matching event instances in time order (built for counting / "how many times" questions)
- `search_ocr_text` — semantic search over on-screen text (OCR) nodes only
- `search_asr_text` — semantic search over the speech transcript (ASR) nodes
- `search_by_time` — find macro events covering a time range

📖 Full guide (install, env vars, examples): [video-memory-usage.md](video-memory-usage.md).

---

## ✂️ video-edit — editing + generation

A video-editing skill plus DashScope generation tools. Install name / entry: `qwen-mm-plugins-video-edit`.

**Generation tools (DashScope)**
- `qwen_image` — image generation, editing, and translation (Qwen-Image)
- `qwen_tts` — text-to-speech (Qwen3-TTS-Flash)
- `wan_s2v` — digital-human lip-sync video (Wan2.2-S2V)
- `wan_t2v` — text-to-video (Wan, wan2.7 series)
- `happyhorse` — video generation and editing (HappyHorse)

**Editing skill** — the editing side is driven by the skill under the capability's [`skill/`](../../src/capabilities/video-edit/skill/): `workflows/` (end-to-end recipes), `engines/` (rendering-engine selection matrix), `mcps/` (external-service catalog), plus `craft/`, `looks/`, and `review/` (technique, style, and QA references).

Keys: the generation tools need `DASHSCOPE_API_KEY`.

---

## 🧊 blender — 3D modeling

Drive a **running** Blender (3D modeling / materials / lighting / rendering) over a socket. Install name / entry: `qwen-mm-plugins-blender`.

Thin client: the tools talk to a live Blender carrying the bundled blender-mcp addon. `QWEN_MM_AUTOLAUNCH=1` (preset in the plugin manifests) brings Blender up on the first tool call, auto-downloading it on Linux-x86_64 if missing; otherwise start it with `qwen-mm-plugins-blender --launch-app`.

**Scene & code**
- `execute_blender_code` — run arbitrary Python in Blender (the workhorse)
- `get_scene_info` — summarize the current scene
- `get_object_info` — inspect one object
- `get_viewport_screenshot` — capture the viewport

**PolyHaven assets**
- `get_polyhaven_status`, `get_polyhaven_categories`, `search_polyhaven_assets`, `download_polyhaven_asset`, `set_texture`

**Sketchfab models**
- `get_sketchfab_status`, `search_sketchfab_models`, `get_sketchfab_model_preview`, `download_sketchfab_model`

**Hyper3D / Rodin generation**
- `get_hyper3d_status`, `generate_hyper3d_model_via_text`, `generate_hyper3d_model_via_images`, `poll_rodin_job_status`, `import_generated_asset`

**Hunyuan3D generation**
- `get_hunyuan3d_status`, `generate_hunyuan3d_model`, `poll_hunyuan_job_status`, `import_generated_asset_hunyuan`

No API key needed to drive Blender (some asset/generation back-ends have their own keys, set inside Blender). 📖 Full guide (setup, `--launch-app`, env vars, troubleshooting): [blender-freecad-usage.md](blender-freecad-usage.md).

---

## 📐 freecad — parametric CAD

Drive a **running** FreeCAD (parametric modeling, property edits, STEP/STL import/export, FEM). Install name / entry: `qwen-mm-plugins-freecad`.

Thin client: the tools talk XML-RPC to a live FreeCAD carrying the bundled FreeCADMCP addon. `QWEN_MM_AUTOLAUNCH=1` (preset in the plugin manifests) brings FreeCAD up on the first tool call, auto-downloading it on Linux-x86_64 if missing; otherwise start it with `qwen-mm-plugins-freecad --launch-app`.

**Documents**
- `create_document`, `list_documents`, `reload_document`

**Objects**
- `create_object`, `edit_object`, `delete_object`, `get_object`, `get_objects`

**Parts library**
- `get_parts_list`, `insert_part_from_library`

**Views & code**
- `get_view` — screenshot a named standard view
- `execute_code`, `execute_code_async` — run Python in FreeCAD

**FEM**
- `run_fem_analysis` — run a finite-element analysis (needs CalculiX)

No API key needed to drive FreeCAD. 📖 Full guide (setup, `--launch-app`, env vars, troubleshooting): [blender-freecad-usage.md](blender-freecad-usage.md).

---

## 🎓 edu-agent — tutorial videos

Turn a math/science problem (or an image of one) into a step-by-step Chinese explainer **video** or interactive page. Install name: `qwen-mm-plugins-edu-agent`. **Skill-only** — no MCP server.

A pure Agent Skill: the model scaffolds, renders and voices the video itself (via `npx hyperframes` + Qwen-TTS). Because there is no MCP server, `uvx` installs nothing for it — its runtime deps (Node.js ≥18, hyperframes CLI, `dashscope`/`soundfile`/`numpy`/`requests`, ffmpeg, `DASHSCOPE_API_KEY`) are prepared manually.

📖 Full setup (dependency table, network boundary, prerequisites): [installation.md](installation.md).
