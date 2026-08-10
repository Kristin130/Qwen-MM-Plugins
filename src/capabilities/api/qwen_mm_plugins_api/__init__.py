"""Qwen-MM-Plugins api: cloud vision-language APIs for understanding media.

A pure-tools MCP server. Each module under ``tools/`` exports ``TOOL`` + ``handle`` and is
auto-discovered by the framework. These tools call external models/services — DashScope VL
(vision_chat / ocr / grounding), DashScope ASR (transcribe_audio), and a SAM3 server
(segmentation). Local file reading/visualization lives in ``core``.
"""

from mcp_framework import __version__ as __version__
from mcp_framework import build_registry

# Auto-discover tools from tools/.
SPECS, get_handler, list_tools = build_registry(__name__, ["tools"])

# System tools pip/uv cannot install; the framework renders --check-system + startup warnings from
# this table. transcribe_audio pulls the audio track out of a video with ffmpeg before uploading.
SYSTEM_DEPS = [
    {
        "label": "transcribe_audio (extract audio track from video/audio)",
        "tools": ["ffmpeg", "ffprobe"],
        "hint": "apt install ffmpeg   |   brew install ffmpeg",
        "extra": "api",
        "probe": "openai",
    },
]

USAGE_NOTE = (
    "Cloud vision-language APIs: vision_chat (caption/VQA), ocr, grounding, transcribe_audio "
    "(all DashScope — need DASHSCOPE_API_KEY), and segmentation (needs a SAM3 server via "
    "SAM3_SERVER_URL). Read/visualize local files with qwen-mm-plugins-core; find/confirm facts "
    "with qwen-mm-plugins-search."
)
