# Multi-provider failover

`vision_chat` / `ocr` / `grounding` / the Omni family use **DashScope** by default (`DASHSCOPE_API_KEY` / `DASHSCOPE_BASE_URL`). When an endpoint is unavailable (rate-limited, down, out of credit), you can configure **several backup providers** that are tried in order: the failover pool walks providers until one succeeds.

## Naming

Numbered providers use `QWEN_MM_PROVIDER<n>_*` — **lower number = higher priority**:

```
QWEN_MM_PROVIDER1_BASE_URL=…     # first backup (highest priority)
QWEN_MM_PROVIDER1_API_KEY=…
QWEN_MM_PROVIDER1_MODEL=…        # optional: model this provider always uses

QWEN_MM_PROVIDER2_BASE_URL=…     # second backup
QWEN_MM_PROVIDER2_API_KEY=…
QWEN_MM_PROVIDER2_MODEL=…

QWEN_MM_PROVIDER3_*  …           # and so on
```

- Numbering must stay **contiguous from 1** (the runtime scan stops at the first gap; `config_env.sh` keeps it contiguous when adding/removing).
- When `MODEL` is unset, the tool's default model is used (`qwen3.7-plus` / `qwen3.5-omni-plus`).
- The **primary can also pin a model** via `DASHSCOPE_MODEL` (e.g. `gemini-2.5-pro`) — same rules as backups (non-qwen works for `vision_chat` / `ocr` only).

## Priority

High to low:

1. **Call arguments** `base_url` / `api_key` (explicit → that single endpoint, no failover)
2. **`DASHSCOPE_BASE_URL` / `DASHSCOPE_API_KEY`** (the primary, always first; `DASHSCOPE_MODEL` pins its model)
3. **`QWEN_MM_PROVIDER1_*`** → **`QWEN_MM_PROVIDER2_*`** → … (ascending)

Each provider retries transient failures first (429 / 5xx / timeout / network, 3 attempts by default); only when retries are exhausted does it move to the next provider. If all fail, the **last** error is raised.

Value lookup for every variable: **shell env > `~/.qwen-mm-plugins/config` > default**.

## Model rules

Each provider can pin its own model (`QWEN_MM_PROVIDER<n>_MODEL`), including non-qwen models (Google Gemini, GPT-4o, …). But tools differ in what they accept:

| Tool | Non-qwen backup model allowed? | Why |
|------|:---:|------|
| `vision_chat` | ✅ | generic caption / VQA works on any compatible model |
| `ocr` | ✅ | generic text extraction |
| `grounding` | ❌ | depends on qwen's bbox-JSON output; non-qwen providers are **skipped** (no request is sent) |
| Omni family (ASR / A/V caption / grounding / counting / music) | ❌ | the streaming A/V protocol is qwen-proprietary; non-qwen providers are always skipped |

> The check is **model id contains `qwen`** (case-insensitive). `Qwen/Qwen2.5-VL-72B-Instruct`, `org/qwen2.5-vl` count; `gemini-2.5-pro`, `gpt-4o` don't.

## Quick start (interactive script)

The repo ships `scripts/config_env.sh` (pure bash, zero deps):

```bash
./scripts/config_env.sh            # interactive menu
./scripts/config_env.sh --list     # show current config
./scripts/config_env.sh --unset K  # remove a variable
```

Menu:
1. **Primary** — set `DASHSCOPE_API_KEY` / `DASHSCOPE_BASE_URL` / `DASHSCOPE_MODEL` (`-` = tool default qwen model)
2. **Show config** — primary + all providers (keys masked)
3. **Edit a provider** — base_url / api_key / model (Enter keeps, `-` clears)
4. **Remove a provider** — deletes and renumbers (keeps numbering contiguous from 1)
5. **Add a provider** — auto-assigns the next number; **model is required** (`-` = "use the tool default qwen model")
6. **Other vars** — `QWEN_MM_CHAT_TIMEOUT` / `QWEN_MM_FFMPEG_TIMEOUT` / `QWEN_MM_CACHE`

Config is written to `~/.qwen-mm-plugins/config` (override with `QWEN_MM_CONFIG`); MCP servers pick it up on the next call — no restart needed.

## Manual examples

### DashScope primary + SiliconFlow qwen backup

```bash
export DASHSCOPE_API_KEY=sk-ds-main

export QWEN_MM_PROVIDER1_BASE_URL=https://api.siliconflow.cn/v1
export QWEN_MM_PROVIDER1_API_KEY=sk-sf-123
export QWEN_MM_PROVIDER1_MODEL=Qwen/Qwen2.5-VL-72B-Instruct
```

### DashScope primary + Google Gemini backup + SiliconFlow qwen backup

```bash
export DASHSCOPE_API_KEY=sk-ds-main

# backup 1: Google Gemini (OpenAI-compatible endpoint)
export QWEN_MM_PROVIDER1_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
export QWEN_MM_PROVIDER1_API_KEY=gk-xxx
export QWEN_MM_PROVIDER1_MODEL=gemini-2.5-pro

# backup 2: SiliconFlow (qwen model)
export QWEN_MM_PROVIDER2_BASE_URL=https://api.siliconflow.cn/v1
export QWEN_MM_PROVIDER2_API_KEY=sk-sf-123
export QWEN_MM_PROVIDER2_MODEL=Qwen/Qwen2.5-VL-72B-Instruct
```

**Runtime behavior**:
- Primary DashScope healthy → everything uses DashScope
- DashScope down → `vision_chat` / `ocr` fail over to **Gemini** (`gemini-2.5-pro`)
- `grounding` / Omni → **skip Gemini** (non-qwen model), go straight to SiliconFlow's qwen
- Gemini also down → `vision_chat` / `ocr` continue to SiliconFlow's qwen

### Writing the config file (GUI-launched harnesses read it too)

```bash
cat >> ~/.qwen-mm-plugins/config <<'EOF'
DASHSCOPE_API_KEY=sk-ds-main
QWEN_MM_PROVIDER1_BASE_URL=https://api.siliconflow.cn/v1
QWEN_MM_PROVIDER1_API_KEY=sk-sf-123
QWEN_MM_PROVIDER1_MODEL=Qwen/Qwen2.5-VL-72B-Instruct
EOF
chmod 600 ~/.qwen-mm-plugins/config
```

## Notes

- `QWEN_MM_PROVIDERS` (the old comma-separated name list + `QWEN_MM_PROVIDER_<NAME>_*`) is **deprecated** — migrate to `QWEN_MM_PROVIDER<n>_*`.
- A provider without `BASE_URL` ends the scan (numbering must be contiguous).
- A provider without `API_KEY` falls back to `"EMPTY"` (so local/self-hosted servers that ignore auth still work; DashScope with an empty key 401s fast and triggers failover).
- Backup providers are tried **only on failure** — no parallel requests when the primary succeeds.
