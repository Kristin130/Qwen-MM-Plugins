# Multi-provider failover (unified numbered pool)

`vision_chat` / `ocr` / `grounding` / the Omni family talk to a **pool of OpenAI-compatible providers**. The pool is configured with numbered providers `QWEN_MM_PROVIDER<n>_*` — **provider 1 is the primary endpoint**, providers 2+ are automatic failover backups tried in order when an earlier one fails (rate-limited, down, out of credit).

## Naming

```
QWEN_MM_PROVIDER1_BASE_URL=…     # primary endpoint (highest priority)
QWEN_MM_PROVIDER1_API_KEY=…
QWEN_MM_PROVIDER1_MODEL=…        # optional: model this provider always uses

QWEN_MM_PROVIDER2_BASE_URL=…     # first backup
QWEN_MM_PROVIDER2_API_KEY=…
QWEN_MM_PROVIDER2_MODEL=…

QWEN_MM_PROVIDER3_*  …           # and so on
```

- Numbering must stay **contiguous from 1** (the runtime scan stops at the first gap; `config_env.sh` keeps it contiguous when adding/removing).
- When `MODEL` is unset, the tool's default model is used (`qwen3.7-plus` / `qwen3.5-omni-plus`).
- **Legacy compatibility**: the old `DASHSCOPE_BASE_URL` / `DASHSCOPE_API_KEY` / `DASHSCOPE_MODEL` trio is still honoured as a **provider-1 alias** — if `QWEN_MM_PROVIDER1_*` is unset, provider 1 falls back to the `DASHSCOPE_*` values. Existing configs keep working; the canonical config is the numbered pool.

## Priority

High to low:

1. **Call arguments** `base_url` / `api_key` (explicit → that single endpoint, no failover)
2. **`QWEN_MM_PROVIDER1_*`** (primary) → **`QWEN_MM_PROVIDER2_*`** → … (ascending; provider 1 falls back to the `DASHSCOPE_*` alias)

Each provider retries transient failures first (429 / 5xx / timeout / network, 3 attempts by default); only when retries are exhausted does it move to the next provider. If all fail, the **last** error is raised.

Value lookup for every variable: **shell env > `~/.qwen-mm-plugins/config` > default**.

## Model rules

Each provider can pin its own model (`QWEN_MM_PROVIDER<n>_MODEL`), including non-qwen models (Google Gemini, GPT-4o, …). But tools differ in what they accept:

| Tool | Non-qwen provider model allowed? | Why |
|------|:---:|------|
| `vision_chat` | ✅ | generic caption / VQA works on any compatible model |
| `ocr` | ✅ | generic text extraction |
| `grounding` | ❌ | depends on qwen's bbox-JSON output; non-qwen providers are **skipped** (no request is sent) |
| Omni family (ASR / A/V caption / grounding / counting / music) | ❌ | the streaming A/V protocol is qwen-proprietary; non-qwen providers are always skipped |

> The check is **model id contains `qwen`** (case-insensitive). `Qwen/Qwen3-VL-30B-A3B-Thinking`, `org/qwen2.5-vl` count; `gemini-3.5-flash-lite`, `gpt-4o` don't.

## Thinking control (grounding)

`grounding` is a perception task — it minimizes chain-of-thought so the model emits clean bbox JSON fast. The knob is picked **per provider** based on the actual model serving the request:

| Provider endpoint | Qwen model | Parameter |
|------|------|-----------|
| DashScope official (`dashscope…aliyuncs.com`) | hybrid-thinking (e.g. `qwen-vl-max`) | `enable_thinking: false` |
| SiliconFlow (`api.siliconflow.cn`) | thinking-only (e.g. `Qwen/Qwen3-VL-30B-A3B-Thinking`) | `thinking_budget: 1` (≈ no CoT) |
| Any endpoint | foreign model (Gemini / GPT-4o / …) | nothing sent (they reject unknown fields with 400) |

> SiliconFlow **rejects** `enable_thinking` even on `*-Thinking` models (they are thinking-only, not hybrid); it honours `thinking_budget` instead. `thinking_budget` must be ≥ 1.

## Quick start (interactive script)

The repo ships `scripts/config_env.sh` (pure bash, zero deps):

```bash
./scripts/config_env.sh            # interactive menu
./scripts/config_env.sh --list     # show current config
./scripts/config_env.sh --unset K  # remove a variable
```

Menu:
1. **Legacy DashScope** — set `DASHSCOPE_API_KEY` / `DASHSCOPE_BASE_URL` / `DASHSCOPE_MODEL` (provider-1 alias; `-` = tool default qwen model)
2. **Show config** — alias + all providers (keys masked)
3. **Edit a provider** — base_url / api_key / model (Enter keeps, `-` clears)
4. **Remove a provider** — deletes and renumbers (keeps numbering contiguous from 1)
5. **Add a provider** — auto-assigns the next number; **model is required** (`-` = "use the tool default qwen model")
6. **Other vars** — `QWEN_MM_CHAT_TIMEOUT` / `QWEN_MM_FFMPEG_TIMEOUT` / `QWEN_MM_CACHE`

Config is written to `~/.qwen-mm-plugins/config` (override with `QWEN_MM_CONFIG`); MCP servers pick it up on the next call — no restart needed.

## Manual examples

### Google Gemini primary + SiliconFlow qwen backup

```bash
# primary: Google Gemini (cheap/free vision for vision_chat / ocr)
export QWEN_MM_PROVIDER1_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
export QWEN_MM_PROVIDER1_API_KEY=gk-xxx
export QWEN_MM_PROVIDER1_MODEL=gemini-3.5-flash-lite

# backup: SiliconFlow (qwen model for grounding / Omni)
export QWEN_MM_PROVIDER2_BASE_URL=https://api.siliconflow.cn/v1
export QWEN_MM_PROVIDER2_API_KEY=sk-sf-123
export QWEN_MM_PROVIDER2_MODEL=Qwen/Qwen3-VL-30B-A3B-Thinking
```

### DashScope primary + Google Gemini backup + SiliconFlow qwen backup

```bash
# primary: DashScope (provider 1 — can also be written as DASHSCOPE_*)
export QWEN_MM_PROVIDER1_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
export QWEN_MM_PROVIDER1_API_KEY=sk-ds-main
export QWEN_MM_PROVIDER1_MODEL=qwen3.7-plus

# backup 1: Google Gemini (OpenAI-compatible endpoint)
export QWEN_MM_PROVIDER2_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
export QWEN_MM_PROVIDER2_API_KEY=gk-xxx
export QWEN_MM_PROVIDER2_MODEL=gemini-3.5-flash-lite

# backup 2: SiliconFlow (qwen model)
export QWEN_MM_PROVIDER3_BASE_URL=https://api.siliconflow.cn/v1
export QWEN_MM_PROVIDER3_API_KEY=sk-sf-123
export QWEN_MM_PROVIDER3_MODEL=Qwen/Qwen3-VL-30B-A3B-Thinking
```

**Runtime behavior**:
- Provider 1 healthy → everything uses provider 1
- Provider 1 down → `vision_chat` / `ocr` fail over to provider 2 (e.g. Gemini)
- `grounding` / Omni → **skip non-qwen providers** (e.g. Gemini), go straight to the first qwen provider
- All providers down → the **last** error is raised

### Writing the config file (GUI-launched harnesses read it too)

```bash
cat >> ~/.qwen-mm-plugins/config <<'EOF'
QWEN_MM_PROVIDER1_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
QWEN_MM_PROVIDER1_API_KEY=gk-xxx
QWEN_MM_PROVIDER1_MODEL=gemini-3.5-flash-lite
QWEN_MM_PROVIDER2_BASE_URL=https://api.siliconflow.cn/v1
QWEN_MM_PROVIDER2_API_KEY=sk-sf-123
QWEN_MM_PROVIDER2_MODEL=Qwen/Qwen3-VL-30B-A3B-Thinking
EOF
chmod 600 ~/.qwen-mm-plugins/config
```

## Notes

- `QWEN_MM_PROVIDERS` (the old comma-separated name list + `QWEN_MM_PROVIDER_<NAME>_*`) is **deprecated** — migrate to `QWEN_MM_PROVIDER<n>_*`.
- A provider without `BASE_URL` ends the scan (numbering must be contiguous).
- A provider without `API_KEY` falls back to `"EMPTY"` (so local/self-hosted servers that ignore auth still work; DashScope with an empty key 401s fast and triggers failover).
- Backup providers are tried **only on failure** — no parallel requests when the primary succeeds.
