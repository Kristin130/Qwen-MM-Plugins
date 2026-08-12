# 多 Provider 备用 / 轮询配置

`vision_chat` / `ocr` / `grounding` / Omni 系工具默认走 **DashScope**（`DASHSCOPE_API_KEY` / `DASHSCOPE_BASE_URL`）。当一个端点不可用（限流、宕机、欠费）时，可以配置**多个备用 provider** 自动轮询切换：主端点失败后依次尝试备用，直到有一个成功。

## 命名规则

编号 provider 用 `QWEN_MM_PROVIDER<n>_*` 命名，**数字越小优先级越高**：

```
QWEN_MM_PROVIDER1_BASE_URL=…     # 第一个备用（最高优先级）
QWEN_MM_PROVIDER1_API_KEY=…
QWEN_MM_PROVIDER1_MODEL=…        # 可选：该 provider 固定用的模型

QWEN_MM_PROVIDER2_BASE_URL=…     # 第二个备用
QWEN_MM_PROVIDER2_API_KEY=…
QWEN_MM_PROVIDER2_MODEL=…

QWEN_MM_PROVIDER3_*  …           # 以此类推
```

- 编号必须**从 1 开始连续**（运行时扫描在第一个空缺处停止；`config_env.sh` 添加/删除时自动保持连续）
- `MODEL` 不设置时，使用工具的默认模型（`qwen3.7-plus` / `qwen3.5-omni-plus`）
- **主端点也可以指定模型**：`DASHSCOPE_MODEL`（如 `gemini-2.5-pro`），规则与备用 provider 相同（非 qwen 仅 vision_chat / ocr 可用）

## 优先级

从高到低：

1. **调用参数** `base_url` / `api_key`（显式传入 → 只用它，不轮询）
2. **`DASHSCOPE_BASE_URL` / `DASHSCOPE_API_KEY`**（主端点，永远第一；可用 `DASHSCOPE_MODEL` 指定主端点模型）
3. **`QWEN_MM_PROVIDER1_*`** → **`QWEN_MM_PROVIDER2_*`** → …（按编号升序）

每个 provider 内部先重试（429 / 5xx / 超时 / 网络错误，默认 3 次），重试耗尽才换下一个；全部失败时抛**最后一个**错误。

取值链（每个变量）：**shell 环境变量 > `~/.qwen-mm-plugins/config` > 默认值**。

## 模型规则

每个 provider 可以用**自己的模型**（`QWEN_MM_PROVIDER<n>_MODEL`），包括非 qwen 模型（如 Google Gemini、GPT-4o）。但工具对模型的约束不同：

| 工具 | 允许非 qwen 备用模型？ | 说明 |
|------|:---:|------|
| `vision_chat` | ✅ | 通用描述 / VQA，任何兼容模型都能干 |
| `ocr` | ✅ | 文字识别通用 |
| `grounding` | ❌ | 依赖 qwen 特有的 bbox JSON 输出协议，非 qwen 的 provider 会被**跳过**（不发请求） |
| Omni 系（ASR / A/V caption / grounding / counting / music） | ❌ | Omni 流式 A/V 协议是 qwen 专有，非 qwen provider 一律跳过 |

> 判定是**模型名包含 `qwen`**（不区分大小写）。`Qwen/Qwen2.5-VL-72B-Instruct`、`org/qwen2.5-vl` 都算 qwen 系；`gemini-2.5-pro`、`gpt-4o` 不算。

## 快速开始（交互脚本）

仓库自带 `scripts/config_env.sh`（纯 bash，零依赖）：

```bash
./scripts/config_env.sh            # 交互菜单
./scripts/config_env.sh --list     # 查看当前配置
./scripts/config_env.sh --unset K  # 删除某个变量
```

菜单：
1. **主端点** — 设置 `DASHSCOPE_API_KEY` / `DASHSCOPE_BASE_URL` / `DASHSCOPE_MODEL`（模型可填 `-` 用工具默认 qwen）
2. **查看当前配置** — 主端点 + 所有 provider（key 打码）
3. **编辑备用 provider** — 改 base_url / api_key / model（回车保持，`-` 清空）
4. **删除备用 provider** — 删除并自动重排编号（保持从 1 连续）
5. **添加备用 provider** — 自动分配编号，model **必填**（输入 `-` 表示"用工具默认 qwen 模型"）
6. **其他常用变量** — `QWEN_MM_CHAT_TIMEOUT` / `QWEN_MM_FFMPEG_TIMEOUT` / `QWEN_MM_CACHE`

配置写入 `~/.qwen-mm-plugins/config`（`QWEN_MM_CONFIG` 可覆盖），MCP 服务器下次调用即生效，无需重启。

## 手动配置示例

### 场景：DashScope 主 + 硅基流动 qwen 备用

```bash
# 主端点
export DASHSCOPE_API_KEY=sk-ds-main

# 备用 1：硅基流动（qwen 模型）
export QWEN_MM_PROVIDER1_BASE_URL=https://api.siliconflow.cn/v1
export QWEN_MM_PROVIDER1_API_KEY=sk-sf-123
export QWEN_MM_PROVIDER1_MODEL=Qwen/Qwen2.5-VL-72B-Instruct
```

### 场景：DashScope 主 + Google Gemini 备用 + 硅基流动 qwen 备用

```bash
export DASHSCOPE_API_KEY=sk-ds-main

# 备用 1：Google Gemini（OpenAI 兼容端点）
export QWEN_MM_PROVIDER1_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
export QWEN_MM_PROVIDER1_API_KEY=gk-xxx
export QWEN_MM_PROVIDER1_MODEL=gemini-2.5-pro

# 备用 2：硅基流动（qwen 模型）
export QWEN_MM_PROVIDER2_BASE_URL=https://api.siliconflow.cn/v1
export QWEN_MM_PROVIDER2_API_KEY=sk-sf-123
export QWEN_MM_PROVIDER2_MODEL=Qwen/Qwen2.5-VL-72B-Instruct
```

**运行时行为**：
- 主端点 DashScope 正常 → 全部走 DashScope
- DashScope 挂了 → `vision_chat` / `ocr` 切到 **Gemini**（用 `gemini-2.5-pro`）
- `grounding` / Omni 系 → **跳过 Gemini**（非 qwen 模型），直接用硅基流动的 qwen
- Gemini 也挂了 → `vision_chat` / `ocr` 继续切到硅基流动的 qwen

### 场景：写入配置文件（GUI 启动的 harness 也能读到）

```bash
# 写 ~/.qwen-mm-plugins/config（KEY=VALUE 每行一个）
cat >> ~/.qwen-mm-plugins/config <<'EOF'
DASHSCOPE_API_KEY=sk-ds-main
QWEN_MM_PROVIDER1_BASE_URL=https://api.siliconflow.cn/v1
QWEN_MM_PROVIDER1_API_KEY=sk-sf-123
QWEN_MM_PROVIDER1_MODEL=Qwen/Qwen2.5-VL-72B-Instruct
EOF
chmod 600 ~/.qwen-mm-plugins/config
```

## 注意事项

- `QWEN_MM_PROVIDERS`（旧命名，逗号分隔的名字列表 + `QWEN_MM_PROVIDER_<NAME>_*`）**已废弃**，请迁移到 `QWEN_MM_PROVIDER<n>_*`
- provider 没配 `BASE_URL` → 该编号之后的 provider 不会被扫描到（编号必须连续）
- provider 没配 `API_KEY` → 回退 `"EMPTY"`（兼容忽略鉴权的本地服务器；DashScope 端点配空 key 会 401 快速失败并触发轮询）
- 备用 provider 是"失败才切换"，不成功时不会并行请求
