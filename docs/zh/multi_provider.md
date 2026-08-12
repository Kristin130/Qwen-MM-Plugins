# 多 Provider 回退（统一编号池）

`vision_chat` / `ocr` / `grounding` / Omni 系工具连接一个 **OpenAI 兼容 Provider 池**。池子用编号 provider `QWEN_MM_PROVIDER<n>_*` 配置 —— **provider 1 是主端点**，provider 2+ 是自动回退的备用：前面的端点失败（限流、宕机、欠费）时按顺序尝试下一个，直到成功。

## 命名规则

```
QWEN_MM_PROVIDER1_BASE_URL=…     # 主端点（最高优先级）
QWEN_MM_PROVIDER1_API_KEY=…
QWEN_MM_PROVIDER1_MODEL=…        # 可选：该 provider 固定用的模型

QWEN_MM_PROVIDER2_BASE_URL=…     # 第一个备用
QWEN_MM_PROVIDER2_API_KEY=…
QWEN_MM_PROVIDER2_MODEL=…

QWEN_MM_PROVIDER3_*  …           # 以此类推
```

- 编号必须**从 1 开始连续**（运行时扫描在第一个空缺处停止；`config_env.sh` 添加/删除时自动保持连续）
- `MODEL` 不设置时，使用工具的默认模型（`qwen3.7-plus` / `qwen3.5-omni-plus`）
- **旧配置兼容**：老的 `DASHSCOPE_BASE_URL` / `DASHSCOPE_API_KEY` / `DASHSCOPE_MODEL` 三件套仍作为 **provider 1 的别名** —— 当 `QWEN_MM_PROVIDER1_*` 未设置时，provider 1 回退读 `DASHSCOPE_*`。旧配置继续可用；规范配置是编号池。

## 优先级

从高到低：

1. **调用参数** `base_url` / `api_key`（显式传入 → 只用它，不轮询）
2. **`QWEN_MM_PROVIDER1_*`**（主端点）→ **`QWEN_MM_PROVIDER2_*`** → …（升序；provider 1 可回退到 `DASHSCOPE_*` 别名）

每个 provider 先重试瞬时错误（429 / 5xx / 超时 / 网络，默认 3 次）；重试耗尽才切下一个。全部失败时抛**最后一个**错误。

变量取值顺序：**shell 环境 > `~/.qwen-mm-plugins/config` > 默认值**。

## 模型规则

每个 provider 可用 `QWEN_MM_PROVIDER<n>_MODEL` 固定自己的模型（包括非 qwen 模型：Google Gemini、GPT-4o …）。但不同工具接受度不同：

| 工具 | 允许非 qwen 模型？ | 原因 |
|------|:---:|------|
| `vision_chat` | ✅ | 通用看图 / VQA 任意兼容模型都行 |
| `ocr` | ✅ | 通用文字提取 |
| `grounding` | ❌ | 依赖 qwen 的 bbox-JSON 输出；非 qwen provider 被**跳过**（不发送请求） |
| Omni 系（ASR / 音视频描述 / grounding / 计数 / 音乐） | ❌ | 流式 A/V 协议是 qwen 专有；非 qwen provider 总是跳过 |

> 判断依据是**模型 id 是否含 `qwen`**（不区分大小写）。`Qwen/Qwen3-VL-30B-A3B-Thinking`、`org/qwen2.5-vl` 算；`gemini-3.5-flash-lite`、`gpt-4o` 不算。

## 思考控制（grounding）

`grounding` 是感知任务 —— 它最小化思维链，让模型快速输出干净的 bbox JSON。控制参数**按 provider 实际服务的模型**选择：

| Provider 端点 | Qwen 模型 | 参数 |
|------|------|-----------|
| DashScope 官方（`dashscope…aliyuncs.com`） | hybrid 思考（如 `qwen-vl-max`） | `enable_thinking: false` |
| SiliconFlow（`api.siliconflow.cn`） | thinking-only（如 `Qwen/Qwen3-VL-30B-A3B-Thinking`） | `thinking_budget: 1`（≈ 不思考） |
| 任意端点 | 外来模型（Gemini / GPT-4o …） | 不传（它们拒绝未知字段，返回 400） |

> SiliconFlow **拒绝** `enable_thinking`（即使 `*-Thinking` 模型也不行 —— 它们是 thinking-only 而非 hybrid）；它支持的是 `thinking_budget`。`thinking_budget` 必须 ≥ 1。

## 快速开始（交互脚本）

仓库自带 `scripts/config_env.sh`（纯 bash，零依赖）：

```bash
./scripts/config_env.sh            # 交互菜单
./scripts/config_env.sh --list     # 查看当前配置
./scripts/config_env.sh --unset K  # 删除某个变量
```

菜单：
1. **旧 DashScope 别名** —— 设置 `DASHSCOPE_API_KEY` / `DASHSCOPE_BASE_URL` / `DASHSCOPE_MODEL`（provider-1 别名；`-` = 工具默认 qwen 模型）
2. **查看配置** —— 别名 + 所有 provider（key 打码）
3. **编辑某个 provider** —— base_url / api_key / model（回车保留，`-` 清除）
4. **删除某个 provider** —— 删除并重新编号（保持从 1 连续）
5. **添加 provider** —— 自动分配下一个编号；**model 必填**（`-` = 用工具默认 qwen 模型）
6. **其他变量** —— `QWEN_MM_CHAT_TIMEOUT` / `QWEN_MM_FFMPEG_TIMEOUT` / `QWEN_MM_CACHE`

配置写入 `~/.qwen-mm-plugins/config`（可用 `QWEN_MM_CONFIG` 覆盖）；MCP 服务器下次调用即生效，无需重启。

## 手动配置示例

### Google Gemini 主端点 + SiliconFlow qwen 备用

```bash
# 主端点：Google Gemini（便宜/免费的视觉，给 vision_chat / ocr 用）
export QWEN_MM_PROVIDER1_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
export QWEN_MM_PROVIDER1_API_KEY=gk-xxx
export QWEN_MM_PROVIDER1_MODEL=gemini-3.5-flash-lite

# 备用：SiliconFlow（qwen 模型，给 grounding / Omni 用）
export QWEN_MM_PROVIDER2_BASE_URL=https://api.siliconflow.cn/v1
export QWEN_MM_PROVIDER2_API_KEY=sk-sf-123
export QWEN_MM_PROVIDER2_MODEL=Qwen/Qwen3-VL-30B-A3B-Thinking
```

### DashScope 主端点 + Google Gemini 备用 + SiliconFlow qwen 备用

```bash
# 主端点：DashScope（provider 1 —— 也可写成 DASHSCOPE_*）
export QWEN_MM_PROVIDER1_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
export QWEN_MM_PROVIDER1_API_KEY=sk-ds-main
export QWEN_MM_PROVIDER1_MODEL=qwen3.7-plus

# 备用 1：Google Gemini（OpenAI 兼容端点）
export QWEN_MM_PROVIDER2_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
export QWEN_MM_PROVIDER2_API_KEY=gk-xxx
export QWEN_MM_PROVIDER2_MODEL=gemini-3.5-flash-lite

# 备用 2：SiliconFlow（qwen 模型）
export QWEN_MM_PROVIDER3_BASE_URL=https://api.siliconflow.cn/v1
export QWEN_MM_PROVIDER3_API_KEY=sk-sf-123
export QWEN_MM_PROVIDER3_MODEL=Qwen/Qwen3-VL-30B-A3B-Thinking
```

**运行时行为**：
- provider 1 健康 → 全部走 provider 1
- provider 1 挂了 → `vision_chat` / `ocr` 回退到 provider 2（如 Gemini）
- `grounding` / Omni → **跳过非 qwen provider**（如 Gemini），直接用第一个支持 qwen 的
- 全部挂了 → 抛**最后一个**错误

### 直接写配置文件（GUI 启动的 harness 也读它）

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

## 说明

- `QWEN_MM_PROVIDERS`（旧的逗号分隔名字列表 + `QWEN_MM_PROVIDER_<NAME>_*`）已**弃用** —— 迁移到 `QWEN_MM_PROVIDER<n>_*`。
- 没有 `BASE_URL` 的 provider 会终止扫描（编号必须连续）。
- 没有 `API_KEY` 的 provider 回退为 `"EMPTY"`（本地/自托管服务器忽略认证也能工作；DashScope 空 key 快速 401 并触发回退）。
- 备用 provider 只在**失败时**才尝试 —— 主端点成功时不会并行请求。
