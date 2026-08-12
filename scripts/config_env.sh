#!/usr/bin/env bash
#
# config_env.sh — interactive env/config editor for qwen-mm-plugins.
#
# Manages ~/.qwen-mm-plugins/config (the KEY=VALUE file read by shared.env.get_env, used by
# every MCP server). The canonical config is the numbered provider pool
# QWEN_MM_PROVIDER1_BASE_URL / _API_KEY / _MODEL, QWEN_MM_PROVIDER2_*, … (provider 1 = primary,
# lower number = higher priority) used by vision_chat / ocr / grounding / omni — plus the
# legacy DASHSCOPE_API_KEY / DASHSCOPE_BASE_URL / DASHSCOPE_MODEL trio (provider-1 alias),
# SERPER_API_KEY, and runtime knobs (QWEN_MM_CHAT_TIMEOUT / FFMPEG_TIMEOUT / CACHE).
#
# Usage:
#     scripts/config_env.sh            # interactive menu
#     scripts/config_env.sh --list     # print current effective values
#     scripts/config_env.sh --unset K  # remove a key
#
# Env vars set in the SHELL still win at runtime — the config file is only a fallback.
# A blank entry keeps the existing value, "-" clears it.
set -u

CONFIG="${QWEN_MM_CONFIG:-$HOME/.qwen-mm-plugins/config}"

# ── helpers ────────────────────────────────────────────────────────────────────────

# provider_env N SUFFIX -> QWEN_MM_PROVIDER<N>_<SUFFIX>
provider_env() { printf 'QWEN_MM_PROVIDER%s_%s' "$1" "$2"; }

# current value of a key: shell env wins, else the config file (first occurrence).
get_val() {
  local key="$1" val
  val="${!key:-}"
  if [ -n "$val" ]; then
    printf '%s' "$val"
    return
  fi
  if [ -f "$CONFIG" ]; then
    val="$(sed -n "s/^${key}=//p" "$CONFIG" | head -1)"
    printf '%s' "$val"
  fi
}

# next free provider index (first n where QWEN_MM_PROVIDER<n>_BASE_URL is unset)
next_provider_index() {
  local n=1
  while [ -n "$(get_val "$(provider_env "$n" BASE_URL)")" ]; do n=$((n + 1)); done
  printf '%s' "$n"
}

# all configured provider indices in order (1..first gap)
all_provider_indices() {
  local n=1 out=""
  while [ -n "$(get_val "$(provider_env "$n" BASE_URL)")" ]; do
    out="${out:+$out }$n"
    n=$((n + 1))
  done
  printf '%s' "$out"
}

# write KEY=VALUE into the config (append or replace), atomic + 0600.
set_key() {
  local key="$1" val="$2" tmp
  mkdir -p "$(dirname "$CONFIG")"
  tmp="${CONFIG}.tmp"
  if [ -f "$CONFIG" ]; then
    grep -v "^${key}=" "$CONFIG" > "$tmp" || true
  else
    : > "$tmp"
  fi
  printf '%s=%s\n' "$key" "$val" >> "$tmp"
  chmod 600 "$tmp"
  mv -f "$tmp" "$CONFIG"
}

# delete KEY from the config file.
del_key() {
  local key="$1" tmp
  [ -f "$CONFIG" ] || return 0
  tmp="${CONFIG}.tmp"
  grep -v "^${key}=" "$CONFIG" > "$tmp" || true
  chmod 600 "$tmp"
  mv -f "$tmp" "$CONFIG"
}

current_providers() {
  all_provider_indices
}

# prompt PROMPT CURRENT -> echoed line; blank keeps current, '-' clears (returns "").
prompt_val() {
  local cur="${2:-}" raw
  if [ -n "$cur" ]; then
    read -r -p "$1 [$cur]: " raw || exit 0
  else
    read -r -p "$1: " raw || exit 0
  fi
  if [ -z "$raw" ]; then
    printf '%s' "$cur"
  elif [ "$raw" = "-" ]; then
    printf ''
  else
    printf '%s' "$raw"
  fi
}

# prompt_secret PROMPT [CURRENT] -> like prompt_val but masks the current value.
prompt_secret() {
  local cur="${2:-}" raw hint=""
  [ -n "$cur" ] && hint=" [(set)]"
  read -r -p "$1${hint}: " raw || exit 0
  if [ -z "$raw" ]; then
    printf '%s' "$cur"
  elif [ "$raw" = "-" ]; then
    printf ''
  else
    printf '%s' "$raw"
  fi
}

# ── actions ───────────────────────────────────────────────────────────────────────

do_list() {
  echo "config file: $CONFIG"
  echo
  local key
  echo "Legacy DashScope (honoured as provider-1 alias):"
  for key in DASHSCOPE_API_KEY DASHSCOPE_BASE_URL DASHSCOPE_MODEL; do
    local v; v="$(get_val "$key")"
    if [ "$key" = DASHSCOPE_API_KEY ] && [ -n "$v" ]; then
      printf '  %s = (set)\n' "$key"
    elif [ "$key" = DASHSCOPE_MODEL ]; then
      printf '  %s = %s\n' "$key" "${v:-(unset → tool default qwen)}"
    else
      printf '  %s = %s\n' "$key" "${v:-(unset)}"
    fi
  done

  local idx
  local idxs; idxs="$(all_provider_indices)"
  if [ -n "$idxs" ]; then
    echo
    echo "Provider pool (lower number = higher priority, 1 = primary):"
    for idx in $idxs; do
      local base key model
      base="$(get_val "$(provider_env "$idx" BASE_URL)")"
      key="$(get_val "$(provider_env "$idx" API_KEY)")"
      model="$(get_val "$(provider_env "$idx" MODEL)")"
      echo "  provider$idx:"
      printf '    base_url = %s\n' "${base:-(missing)}"
      printf '    api_key  = %s\n' "$([ -n "$key" ] && echo '(set)' || echo '(missing)')"
      printf '    model    = %s\n' "${model:-(unset → tool default qwen)}"
    done
  else
    echo
    echo "Provider pool: none"
  fi
}

do_add_provider() {
  echo
  echo "── Add a failover provider ──────────────────────────────────────"
  echo "Each provider = a backup OpenAI-compatible endpoint, used after the"
  echo "primary (DASHSCOPE_*) fails. Lower number = higher priority."
  echo "MODEL is REQUIRED — e.g. google gemini, Qwen/Qwen2.5-VL-72B-Instruct."
  echo "Enter '-' for 'use the tool default qwen model'."
  echo "Note: a non-qwen model only works with vision_chat / ocr; grounding/Omni skip it."
  local idx base key model
  idx="$(next_provider_index)"
  echo "  (will use QWEN_MM_PROVIDER${idx}_*)"
  base="$(prompt_val "  base_url (e.g. https://api.siliconflow.cn/v1)" "")"
  [ -n "$base" ] || { echo "  (empty base_url — nothing added)"; return 1; }
  key="$(prompt_secret "  api_key")"
  model="$(prompt_val "  model" "")"
  [ -n "$model" ] || { echo "  (empty model — nothing added)"; return 1; }
  if [ "$model" = "-" ]; then
    del_key "$(provider_env "$idx" MODEL)"   # '-' = no override, use tool default
  else
    set_key "$(provider_env "$idx" MODEL)" "$model"
  fi
  set_key "$(provider_env "$idx" BASE_URL)" "$base"
  [ -n "$key" ] && set_key "$(provider_env "$idx" API_KEY)" "$key" || del_key "$(provider_env "$idx" API_KEY)"
  echo "  added provider$idx (model=$model)."
}

do_edit_provider() {
  local idx="$1" base key model newbase newkey newmodel
  echo
  echo "── Edit provider$idx ───────────────────────────────────────"
  base="$(get_val "$(provider_env "$idx" BASE_URL)")"
  key="$(get_val "$(provider_env "$idx" API_KEY)")"
  model="$(get_val "$(provider_env "$idx" MODEL)")"
  newbase="$(prompt_val "  base_url" "$base")"
  newkey="$(prompt_secret "  api_key" "$key")"
  newmodel="$(prompt_val "  model ('-' = tool default)" "$model")"
  # blank keeps; "-" clears; a real value sets.
  if [ -n "$newbase" ] && [ "$newbase" != "$base" ]; then set_key "$(provider_env "$idx" BASE_URL)" "$newbase"; fi
  if [ -z "$newbase" ] && [ -n "$base" ]; then del_key "$(provider_env "$idx" BASE_URL)"; fi
  if [ -n "$newkey" ] && [ "$newkey" != "$key" ]; then set_key "$(provider_env "$idx" API_KEY)" "$newkey"; fi
  if [ -z "$newkey" ] && [ -n "$key" ]; then del_key "$(provider_env "$idx" API_KEY)"; fi
  if [ -n "$newmodel" ] && [ "$newmodel" != "$model" ]; then set_key "$(provider_env "$idx" MODEL)" "$newmodel"; fi
  if [ -z "$newmodel" ] && [ -n "$model" ]; then del_key "$(provider_env "$idx" MODEL)"; fi
}

do_remove_provider() {
  local idx="$1" shift=0 n src
  del_key "$(provider_env "$idx" BASE_URL)"
  del_key "$(provider_env "$idx" API_KEY)"
  del_key "$(provider_env "$idx" MODEL)"
  # renumber: shift every provider with a HIGHER number down by one, so numbering stays
  # contiguous from 1 (the runtime scan stops at the first gap).
  n=$((idx + 1))
  while [ -n "$(get_val "$(provider_env "$n" BASE_URL)")" ]; do
    for suffix in BASE_URL API_KEY MODEL; do
      src="$(get_val "$(provider_env "$n" "$suffix")")"
      if [ -n "$src" ]; then
        set_key "$(provider_env "$((n - 1))" "$suffix")" "$src"
      else
        del_key "$(provider_env "$((n - 1))" "$suffix")"
      fi
      del_key "$(provider_env "$n" "$suffix")"
    done
    n=$((n + 1))
  done
  echo "  removed provider$idx."
}

# ── entry ─────────────────────────────────────────────────────────────────────────

case "${1:-}" in
  --list|-l)
    do_list
    exit 0
    ;;
  --unset)
    [ $# -ge 2 ] || { echo "usage: config_env.sh --unset KEY" >&2; exit 2; }
    del_key "$2"
    echo "removed $2 from $CONFIG"
    exit 0
    ;;
  -h|--help)
    sed -n '3,15p' "$0"
    exit 0
    ;;
esac

# interactive menu
while true; do
  echo
  echo "──────────────────────────────────────────────"
  echo "qwen-mm-plugins 环境配置  (config: $CONFIG)"
  echo "1. 主端点 (DashScope / DASHSCOPE_*)"
  echo "2. 查看当前配置"
  local_providers="$(current_providers)"
  if [ -n "$local_providers" ]; then
    echo "3. 编辑备用 provider"
    echo "4. 删除备用 provider"
  fi
  echo "5. 添加备用 provider (failover)"
  echo "6. 其他常用变量 (OSS / 超时 / 缓存)"
  echo "0. 退出"
  read -r -p "选择 > " choice || { echo; break; }

  case "$choice" in
    1)
      dk="$(prompt_secret "DASHSCOPE_API_KEY" "$(get_val DASHSCOPE_API_KEY)")"
      db="$(prompt_val "DASHSCOPE_BASE_URL" "$(get_val DASHSCOPE_BASE_URL)")"
      dm="$(prompt_val "DASHSCOPE_MODEL ('-' = tool default qwen)" "$(get_val DASHSCOPE_MODEL)")"
      [ -n "$dk" ] && set_key DASHSCOPE_API_KEY "$dk" || del_key DASHSCOPE_API_KEY
      [ -n "$db" ] && set_key DASHSCOPE_BASE_URL "$db" || del_key DASHSCOPE_BASE_URL
      [ -n "$dm" ] && set_key DASHSCOPE_MODEL "$dm" || del_key DASHSCOPE_MODEL
      echo "已保存。"
      ;;
    2) do_list ;;
    3)
      [ -n "$local_providers" ] || break
      echo "可选 provider 编号: $local_providers"
      read -r -p "输入要编辑的 provider 编号: " pidx || exit 0
      case " $local_providers " in *" $pidx "*) do_edit_provider "$pidx" ;; *) echo "未知编号";; esac
      ;;
    4)
      [ -n "$local_providers" ] || break
      echo "可选 provider 编号: $local_providers"
      read -r -p "输入要删除的 provider 编号: " pidx || exit 0
      case " $local_providers " in *" $pidx "*) do_remove_provider "$pidx" ;; *) echo "未知编号";; esac
      ;;
    5) do_add_provider ;;
    6)
      ct="$(prompt_val "QWEN_MM_CHAT_TIMEOUT (秒, 默认600)" "$(get_val QWEN_MM_CHAT_TIMEOUT)")"
      ft="$(prompt_val "QWEN_MM_FFMPEG_TIMEOUT (秒, 默认120)" "$(get_val QWEN_MM_FFMPEG_TIMEOUT)")"
      cc="$(prompt_val "QWEN_MM_CACHE (缓存目录)" "$(get_val QWEN_MM_CACHE)")"
      [ -n "$ct" ] && set_key QWEN_MM_CHAT_TIMEOUT "$ct" || del_key QWEN_MM_CHAT_TIMEOUT
      [ -n "$ft" ] && set_key QWEN_MM_FFMPEG_TIMEOUT "$ft" || del_key QWEN_MM_FFMPEG_TIMEOUT
      [ -n "$cc" ] && set_key QWEN_MM_CACHE "$cc" || del_key QWEN_MM_CACHE
      echo "已保存。"
      ;;
    0) break ;;
    *) echo "无效选择。";;
  esac
done
