"""Qwen-MM-Plugins omni-av: Omni-model audio/video atomic tools (caption, ASR family, grounding, counting).

A pure-tools MCP server. Each module under ``tools/`` exports ``TOOL`` + ``handle`` and is
auto-discovered by the framework; all of them call the Qwen-Omni model via ``shared.api_omni``.
"""

from mcp_framework import __version__ as __version__
from mcp_framework import build_registry

SPECS, get_handler, list_tools = build_registry(__name__, ["tools"])

# System tools pip/uv cannot install — the framework renders --check-system + startup warnings from
# this table. Every local file is fitted to the endpoint's inline cap with ffmpeg: the ASR family
# pulls out the audio track, the AV tools transcode the video (and split it into frames when it is
# too long to inline).
SYSTEM_DEPS: list[dict] = [
    {
        "label": "audio/video decoding (inline-size fitting, audio extraction, frame split)",
        "tools": ["ffmpeg", "ffprobe"],
        "hint": "apt install ffmpeg   |   brew install ffmpeg",
        "extra": "omni-av",
        "probe": "openai",
    },
]

USAGE_NOTE = (
    "Omni audio/video tools (caption with timestamps, ASR / controllable ASR / multi-speaker ASR, "
    "temporal grounding, event counting). Requires DASHSCOPE_API_KEY; model default qwen3.5-omni-plus. "
    "Local media is uploaded inline under the endpoint's 10 MB base64 cap; set OSS_AK/OSS_SK/"
    "OSS_ENDPOINT/OSS_BUCKET (plus the 'oss' extra) to have oversized video uploaded instead of split "
    "into frames."
)
