"""Qwen-MM-Plugins video-memory: hierarchical graph memory for long-video QA."""

import logging
import threading

from mcp_framework import __version__ as __version__
from mcp_framework import build_registry
from shared.env import get_env

log = logging.getLogger("qwen-mm-plugins-video-memory")

SPECS, get_handler, list_tools = build_registry(__name__, ["tools"])

# ffmpeg only needed to *build* a memory, not to query — startup:False so the server doesn't nag.
SYSTEM_DEPS = [
    {
        "label": "build memory: frame extraction (ffmpeg)",
        "extra": "video-memory",
        "tools": ["ffmpeg"],
        "hint": "apt install ffmpeg   |   brew install ffmpeg",
        "startup": False,
    },
]
SYSTEM_DEPS_NOTE = "  Query-only use (an already-built memory) needs no system tools."

USAGE_NOTE = (
    "Set GRAPH_MEMORY_PATH (and optionally EMBEDDINGS_PATH), or pass\n"
    "video_path in each tool call, to point it at a built memory."
)


def on_start() -> None:

    from . import loader

    log.info("Starting graph-memory MCP server")
    log.info("  GRAPH_MEMORY_PATH=%s", get_env("GRAPH_MEMORY_PATH") or "<not set>")
    log.info("  EMBEDDINGS_PATH=%s", get_env("EMBEDDINGS_PATH") or "<not set>")
    # Warm the cache in background when a fixed memory path is configured.
    threading.Thread(target=loader.preload, daemon=True).start()
