# Qwen-MM-Plugins

**English** · [中文](README.zh.md)

Native multimodal plugins for Qwen models. Make any agent harness multimodal-native.

## Contents

- [✨ What's New in This Fork](#-whats-new-in-this-fork)
- [🧩 Capabilities](#-capabilities)
- [🏗 Architecture](#-architecture)
- [📦 Installation](#-installation)
- [🔧 Dependencies](#-dependencies)
- [🔑 Configuration](#-configuration)
- [🚀 Getting Started (install → configure → verify)](#-getting-started-install--configure--verify)
- [🚀 Quick Start](#-quick-start)
- [🧪 Development](#-development)

## ✨ What's New in This Fork

This fork builds on upstream `QwenLM/Qwen-MM-Plugins` with the following optimizations and improvements:

### 🔄 Multi-Provider Failover for Cloud APIs

The `api` capability (`vision_chat` / `ocr` / `grounding` / the Omni family) previously only spoke to a single DashScope endpoint. Now it supports a **failover pool of OpenAI-compatible providers** — when the primary endpoint is rate-limited, down, or out of credit, it automatically retries then falls back to backup providers in order:

```bash
# Unified numbered provider pool — provider 1 is the PRIMARY endpoint.
# (The legacy DASHSCOPE_BASE_URL / DASHSCOPE_API_KEY / DASHSCOPE_MODEL trio is still
# honoured as a provider-1 alias, but the canonical config is the numbered pool.)

QWEN_MM_PROVIDER1_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/   # e.g. Google Gemini
QWEN_MM_PROVIDER1_API_KEY=…
QWEN_MM_PROVIDER1_MODEL=gemini-3.5-flash-lite        # optional: pin provider 1's model

QWEN_MM_PROVIDER2_BASE_URL=https://api.siliconflow.cn/v1
QWEN_MM_PROVIDER2_API_KEY=…
QWEN_MM_PROVIDER2_MODEL=Qwen/Qwen3-VL-30B-A3B-Thinking

QWEN_MM_PROVIDER3_BASE_URL=…                 # and so on, numbering contiguous from 1
QWEN_MM_PROVIDER3_API_KEY=…
QWEN_MM_PROVIDER3_MODEL=…
```

- **Retries & fallback**: a provider gets 3 retries (429 / 5xx / timeouts) before the next one is tried.
- **Per-provider model pinning**: each provider pins its own model via `QWEN_MM_PROVIDER<n>_MODEL`.
- **Foreign-model aware**: generic caption/OCR (`vision_chat` / `ocr`) accept any compatible model — e.g. run the cheap **Google Gemini** as provider 1 and only fall back to Qwen; perception tasks that need Qwen's structured output (`grounding`, Omni) automatically skip non-Qwen models and use a Qwen-capable provider.
- **Cost control**: put a cheap/free endpoint first, a Qwen endpoint second — quota exhausted? It just works.

### 🖼️ SiliconFlow Compatibility

- `grounding` picks the right thinking knob **per provider** based on the actual model serving the request: DashScope → `enable_thinking` (hybrid models), SiliconFlow → `thinking_budget` (thinking-only models honour it — 1 token ≈ no CoT), foreign models (Gemini / GPT-4o / …) → nothing (they reject unknown fields).
- OpenAI-spec servers (e.g. vLLM) can opt into raw-base64 `input_audio` via `QWEN_MM_AUDIO_RAW_B64` (previously only DashScope's `data:;base64,…` form worked).

### 📦 New Files

- `scripts/config_env.sh` — interactive env/config editor for the failover pool (keeps provider numbering contiguous).
- `docs/en/multi_provider.md`, `docs/zh/multi_provider.md` — full multi-provider configuration guide.
- `uv.lock` — dependency lockfile for reproducible installs.

### 🧭 Full configuration reference

See [`docs/en/multi_provider.md`](docs/en/multi_provider.md) for the complete guide (priority order, examples, per-harness setup).

## 🧩 Capabilities

Each capability is installed separately — a **skill** (so the model knows the toolset exists) plus an optional **MCP server** (the tools themselves).

We ship [**cookbooks**](cookbooks/) of Qwen3.8-Max + these plugins in action — each capability's cookbook (linked in the table below) has its full tool listing, setup, and worked cases. Enjoy!

| Capability | What it does | Install name | Cookbook |
|---|---|---|---|
| **core** | Local I/O plugin: read images and video in dynamic resolution, and visualize any file (e.g. docs, 3D, and more) — plus some image tools (crop, annotate, extract frames) | `qwen-mm-plugins-core` | [link](cookbooks/core/usage.md) |
| **api** | Cloud APIs for understanding media, by model family: VL (vision chat, OCR, grounding), Omni A/V (timestamped captioning, ASR / multi-speaker diarization, temporal grounding, event counting), plus ASR and segmentation (SAM3). **Now with multi-provider failover** — any OpenAI-compatible endpoint (DashScope, Google Gemini, SiliconFlow, …) with automatic fallback | `qwen-mm-plugins-api` | [link](cookbooks/api/usage.md) |
| **search** | Web + reverse-image search to confirm facts: web search, page extraction, reverse image search; currently supports Serper | `qwen-mm-plugins-search` | [TBD](cookbooks/core/usage.md) |
| **video-memory** | Long-video memory: a hierarchical graph memory that powers QA over very long videos | `qwen-mm-plugins-video-memory` | [TBD](cookbooks/video-memory/usage.md) |
| **video-edit** | Video editing + generation: editing workflows + image / video / audio generation | `qwen-mm-plugins-video-edit` | [TBD](cookbooks/video-edit/usage.md) |
| **blender** | Blender 3D modeling: drive a **running** Blender via Python (thin client, 22 tools) — modeling / materials / lighting / rendering | `qwen-mm-plugins-blender` | [TBD](cookbooks/blender/usage.md) |
| **freecad** | FreeCAD parametric CAD: drive a **running** FreeCAD (thin client, 14 tools) — modeling, property edits, STEP/STL import/export, FEM analysis | `qwen-mm-plugins-freecad` | [TBD](cookbooks/freecad/usage.md) |
| **edu-agent** | Educational tutorial videos: turn a math/science problem or an image into a step-by-step Chinese explainer video / interactive page (**skill-only**, no MCP server) | `qwen-mm-plugins-edu-agent` | [TBD](cookbooks/edu-agent/usage.md) |

## 🏗 Architecture

![Qwen-MM-Plugins Architecture](docs/assets/architecture.svg)

## 📦 Installation

A capability = a **skill** (so the model knows the tools exist) + an optional **MCP server** (the tools themselves, launched on demand by `uvx` — needs [uv](https://docs.astral.sh/uv/), no manual pip).

### Recommended: the guided installer

One script handles **install · configure · verify · uninstall** across every harness it supports (Claude Code · Codex · Qoder · OpenClaw · Qwen Code · Gemini CLI). It drives each harness's own native install under the hood — nothing reinvented — and writes a single shared config file (`~/.qwen-mm-plugins/config`) that GUI and terminal harnesses both read, so you set things up once:

```bash
curl -fsSL https://raw.githubusercontent.com/Kristin130/Qwen-MM-Plugins/main/install.sh | bash
```

Or run one action at a time — `bash install.sh install` / `configure` / `verify` / `uninstall` (what `configure` and `verify` do is detailed under [Configuration](#-configuration) and [Dependencies](#-dependencies)).

**Windows x64:** use WSL2 (Ubuntu recommended) and clone the repository inside your WSL
home directory (for example `~/code`), rather than under a mounted Windows drive such as
`/mnt/c`. Then run the same commands there. WSL2 is currently the only supported Windows
environment; native Windows has not yet been validated. See the concise
[Windows notes](docs/en/installation.md#windows-wsl2).

### By hand (per-harness)

Prefer your harness's own commands — or you're on opencode / pi / QwenPaw, which the installer doesn't cover? Register the skill + MCP yourself.

**Plugin-marketplace harnesses** (Claude Code · Qoder · Codex · OpenClaw · Qwen Code) — add the marketplace, then install a capability (replace `<cap>` with `core` / `api` / `search` / `video-memory` / `video-edit` / `blender` / `freecad`). Install `core` by default — it's the local-I/O base every other capability builds on — plus whichever others you need:

```bash
# Claude Code
claude   plugin  marketplace add https://github.com/Kristin130/Qwen-MM-Plugins.git
claude   plugin  install       qwen-mm-plugins-<cap>@qwen-mm-plugins
# Qoder
qodercli plugins marketplace add https://github.com/Kristin130/Qwen-MM-Plugins.git
qodercli plugins install       qwen-mm-plugins-<cap>@qwen-mm-plugins
# Codex
codex    plugin  marketplace add https://github.com/Kristin130/Qwen-MM-Plugins.git
codex    plugin  add           qwen-mm-plugins-<cap>@qwen-mm-plugins
# OpenClaw
openclaw plugins install       qwen-mm-plugins-<cap> --marketplace https://github.com/Kristin130/Qwen-MM-Plugins.git
# Qwen Code
qwen extensions install https://github.com/Kristin130/Qwen-MM-Plugins.git:qwen-mm-plugins-<cap> --consent
```

`marketplace add` also accepts a local repo path; re-running is safe. On **codex**, `marketplace add` does **not** refresh an already-added marketplace, so run `codex plugin marketplace upgrade qwen-mm-plugins` before `plugin add` to pick up newly-published capabilities.

**Other harnesses** (Gemini CLI · opencode · pi · QwenPaw · …) register the skill + MCP in their own config — exact per-harness blocks are in [`docs/en/installation.md`](docs/en/installation.md). Easiest of all: **just ask the agent** — "install `qwen-mm-plugins-<cap>`".

## 🔧 Dependencies

`uvx` installs the Python dependencies for the chosen profile on first launch — no manual pip. The only things you install yourself are **system tools**: `ffmpeg` (video / audio), plus optional `libreoffice` / `blender` / `texlive` / `chromium` for `visualize`. Run `bash install.sh verify` to self-test what's installed — it confirms your API key and reports any missing system tools (fetching each capability's env and running `--check-system` under the hood). Full system-tool table, the edu-agent (skill-only) setup, and the blender/freecad thin-client notes: see [`docs/en/installation.md`](docs/en/installation.md).

## 🔑 Configuration

The API-based tools need a key — native image / video / document reading doesn't:

- `QWEN_MM_PROVIDER<n>_API_KEY` — the `api` capability (`vision_chat` / `ocr` / `grounding` / `transcribe_audio` / Omni audio-video understanding). Provider 1 is the primary endpoint; providers 2+ are automatic failover backups (any OpenAI-compatible endpoint: DashScope, Google Gemini, SiliconFlow, vLLM, …). The legacy `DASHSCOPE_API_KEY` trio still works as a provider-1 alias.
- `SERPER_API_KEY` — `web_search` / `web_extractor` / `image_search`
- `DASHSCOPE_API_KEY` — generation (`qwen_image` / `wan_*` / TTS) and video-memory builds (these use the DashScope-native REST API, not the provider pool)

### 🛠 Config helper script

The repo ships `scripts/config_env.sh` — an interactive editor for the provider pool and env keys (writes `~/.qwen-mm-plugins/config`, keeps provider numbering contiguous):

```bash
# interactive menu: add / list / remove providers, set API keys
bash scripts/config_env.sh

# print the current effective configuration
bash scripts/config_env.sh --list

# remove a key (e.g. a provider)
bash scripts/config_env.sh --unset QWEN_MM_PROVIDER2_BASE_URL
```

It manages `QWEN_MM_PROVIDER<n>_BASE_URL` / `_API_KEY` / `_MODEL` for the failover pool, plus `SERPER_API_KEY` and the legacy `DASHSCOPE_*` trio. Shell-exported vars always win at runtime; the config file is the fallback (so GUI-launched harnesses pick the keys up too).

### Or configure by hand

```bash
# Provider pool (example: Google Gemini primary + SiliconFlow Qwen backup)
export QWEN_MM_PROVIDER1_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
export QWEN_MM_PROVIDER1_API_KEY=…
export QWEN_MM_PROVIDER1_MODEL=gemini-3.5-flash-lite
export QWEN_MM_PROVIDER2_BASE_URL=https://api.siliconflow.cn/v1
export QWEN_MM_PROVIDER2_API_KEY=…
export QWEN_MM_PROVIDER2_MODEL=Qwen/Qwen3-VL-30B-A3B-Thinking

# Web search
export SERPER_API_KEY=…
```

The guided installer's Configure step also writes the config file for you:

```bash
bash install.sh configure
```

For non-interactive/automation setup and the full environment-variable catalog, see [`docs/en/installation.md`](docs/en/installation.md) and [`docs/en/multi_provider.md`](docs/en/multi_provider.md).

## 🚀 Getting Started (install → configure → verify)

**1. Install** a capability (from this fork):

```bash
curl -fsSL https://raw.githubusercontent.com/Kristin130/Qwen-MM-Plugins/main/install.sh | bash
# or pick just the api capability: bash install.sh install api
```

**2. Configure your providers** — provider 1 is the primary, providers 2+ are failover backups:

```bash
# interactive editor (recommended)
bash scripts/config_env.sh
#   → option 5: add a provider (base_url / api_key / model)
#   → provider 1 = primary, provider 2 = first fallback, …

# or export them directly
bash scripts/config_env.sh --list   # see what's configured
```

A sensible starter setup: **Google Gemini as provider 1** (cheap/free vision) and **SiliconFlow Qwen as provider 2** (Qwen-native grounding & Omni):

```bash
export QWEN_MM_PROVIDER1_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
export QWEN_MM_PROVIDER1_API_KEY=…
export QWEN_MM_PROVIDER1_MODEL=gemini-3.5-flash-lite
export QWEN_MM_PROVIDER2_BASE_URL=https://api.siliconflow.cn/v1
export QWEN_MM_PROVIDER2_API_KEY=…
export QWEN_MM_PROVIDER2_MODEL=Qwen/Qwen3-VL-30B-A3B-Thinking
```

> `vision_chat` / `ocr` run on provider 1 (any OpenAI-compatible model); `grounding` / Omni need Qwen's structured output, so they automatically skip non-Qwen providers and use the first Qwen one. When provider 1 is rate-limited / down / out of credit, the pool fails over to the next provider automatically.

**3. Verify** the servers start and the keys resolve:

```bash
bash install.sh verify
# or per server: uvx --from "qwen-mm-plugins[api] @ git+https://github.com/Kristin130/Qwen-MM-Plugins.git@main" qwen-mm-plugins-api --check-system
```

**4. Use it** — reference a file in your harness and just ask (examples below).

## 🚀 Quick Start

Once a capability is installed, reference a file in your harness and just ask — the model picks the right tool automatically. Reading is **dynamic-resolution**: every image, video frame, and document page is auto-scaled to the VL model's patch grid, so a 4K screenshot's fine print and a tiny thumbnail both come in at the detail they need — no manual resizing.

```text
# core — read images / video / docs / 3D models (local, dynamic-resolution)
@dashboard-4k.png      Read every number in this dashboard.
@report.pdf            Summarize page 3.

# api — cloud VL + Omni APIs: caption / OCR / grounding / segmentation / ASR, plus Omni audio-video understanding
@receipt.jpg           OCR this and total the line items.
@street.jpg            Draw a box around every car in the scene.                    # grounding
@meeting.mp4           Transcribe this with speaker labels and timestamps.          # omni
@sports-clip.mp4       Count every completed pass and list when each one occurs.    # omni
@song.mp3              Tag the genre, mood, instruments, key, and vocal profile.    # omni

# search — web + reverse-image search to confirm what's on screen
@place.jpg             Where was this photo taken?                 # image_search + web_search

# video-memory — QA over long videos; the first query auto-builds memory
@lecture-2h.mp4        What are the main points, with timestamps?

# video-edit — image / video / audio generation + editing workflows
                       Generate a 1024×1024 image of a red panda coding at night.
@/path/to/media        Help me edit this video down to about 3 minutes.

# blender — drive a running Blender to model / texture / light / render (thin client, 22 tools)
                       Model a low-poly wooden stool, add a warm key light, and render it.

# freecad — parametric CAD in a running FreeCAD (thin client, 14 tools; STEP/STL, FEM)
                       Model an M6 hex bolt 30 mm long and export it as STEP.

# edu-agent — turn a math/science problem into a step-by-step Chinese explainer video (skill-only)
@geometry-problem.png  Explain how to solve this as a narrated video.
```

See each capability's 🍳 [cookbook](cookbooks/) for every tool, setup, and a worked case.

## 🧪 Development

Development setup, contribution guidelines, and verification commands are in
[`CONTRIBUTING.md`](CONTRIBUTING.md). Detailed guides: [local development](docs/en/local_development.md)
· [adding a capability](docs/en/how_to_add_new_capability.md) · [testing](docs/en/testing.md).

## 📄 License

Apache-2.0 — see [`LICENSE`](LICENSE). The Blender and FreeCAD capabilities vendor third-party MIT-licensed code; see [`src/capabilities/blender/NOTICE.md`](src/capabilities/blender/NOTICE.md) and [`src/capabilities/freecad/NOTICE.md`](src/capabilities/freecad/NOTICE.md) for attribution.
