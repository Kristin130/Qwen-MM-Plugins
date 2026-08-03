"""OpenAI-compatible chat client (shared): endpoint resolution + chat call with retry.

Used by the vision server's vision_chat / ocr / grounding. Targets any OpenAI-compatible endpoint
(DashScope's compatible-mode is only the default base_url). The `openai` SDK is imported lazily so
tool discovery stays cheap. DashScope native-REST generation lives in `api_dashscope`.
"""

from __future__ import annotations

import base64
import logging
import mimetypes
from pathlib import Path
from typing import Any

from shared.env import DEFAULT_DASHSCOPE_BASE_URL, get_env

log = logging.getLogger(__name__)

DEFAULT_MODEL = "qwen3.7-plus"
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BACKOFF = 1.0
# Request timeout (seconds) for a chat call — generous for long vision prompts, but bounded so a
# hung connection can't pin a tool call for an hour. Overridable via QWEN_MM_CHAT_TIMEOUT.
DEFAULT_CHAT_TIMEOUT = 600


def _chat_timeout() -> int:
    """QWEN_MM_CHAT_TIMEOUT (seconds), read at call time; unset/bad values fall back to the default."""
    raw = get_env("QWEN_MM_CHAT_TIMEOUT")
    try:
        return int(raw) if raw else DEFAULT_CHAT_TIMEOUT
    except ValueError:
        log.warning("QWEN_MM_CHAT_TIMEOUT=%r is not a valid integer; using default %d", raw, DEFAULT_CHAT_TIMEOUT)
        return DEFAULT_CHAT_TIMEOUT


# HTTP statuses worth retrying for OpenAI-compatible endpoints.
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


def resolve_openai_endpoint(arguments: dict[str, Any]) -> tuple[str, str]:
    """Resolve (base_url, api_key) for an OpenAI-compatible call.

    Precedence: explicit argument → DashScope env → default. api_key falls back to
    "EMPTY" so local/self-hosted servers that ignore auth still work.
    """
    base_url = arguments.get("base_url") or get_env("DASHSCOPE_BASE_URL") or DEFAULT_DASHSCOPE_BASE_URL
    api_key = arguments.get("api_key") or get_env("DASHSCOPE_API_KEY") or "EMPTY"
    return base_url, api_key


def is_url(value: str) -> bool:
    return value.startswith(("http://", "https://", "data:"))


def encode_image_source(source: str) -> dict[str, Any]:
    """OpenAI-style image content part: a URL/data-URL passthrough, or a local file base64'd."""
    if is_url(source):
        return {"type": "image_url", "image_url": {"url": source}}
    path = Path(source)
    mime_type, _ = mimetypes.guess_type(path.name)
    if mime_type is None or not mime_type.startswith("image/"):
        mime_type = "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    return {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{encoded}"}}


def encode_video_source(source: str, max_frames: int = 128) -> dict[str, Any]:
    """OpenAI-style video content part: a URL passthrough, or a local file sampled into frames."""
    if is_url(source):
        return {"type": "video_url", "video_url": {"url": source}}

    from shared.env import DEFAULT_FPS, TOKEN_SIZE, VIDEO_MIN_PIXELS
    from shared.image import smart_resize
    from shared.video import compute_dynamic_fps, extract_frames_by_seeking, get_video_info

    info = get_video_info(source)
    target_h, target_w = smart_resize(info["height"], info["width"], VIDEO_MIN_PIXELS, 1280 * TOKEN_SIZE**2)
    fps, nframes = compute_dynamic_fps(info["duration"], info["native_fps"], 4, max_frames, DEFAULT_FPS)
    frame_interval = info["duration"] / nframes if nframes > 0 else 0
    timestamps = [i * frame_interval for i in range(nframes)]
    frames = extract_frames_by_seeking(source, timestamps, target_h, target_w)
    frame_urls = [f"data:image/jpeg;base64,{b64}" for _, b64 in frames]
    return {"type": "video", "video": frame_urls, "fps": round(fps, 2)}


def call_openai_chat(
    *,
    base_url: str,
    api_key: str,
    max_retries: int = DEFAULT_MAX_RETRIES,
    **kwargs: Any,
) -> Any:
    """Call OpenAI-compatible chat completions, retrying transient failures.

    Retries on the SDK's typed transient errors (rate limit, timeout,
    connection, 5xx) and on retryable HTTP status codes, rather than matching
    substrings of the error message.
    """
    import openai
    from openai import OpenAI

    from shared.retry import retry_call

    # A missing key against DashScope just 401s with "No API-key provided"; give an actionable
    # message. Local/self-hosted servers ignore auth, so only guard the DashScope endpoint.
    if api_key in ("", "EMPTY") and "dashscope" in base_url:
        raise RuntimeError("no API key — set DASHSCOPE_API_KEY (or pass api_key)")

    retryable = (
        openai.RateLimitError,
        openai.APITimeoutError,
        openai.APIConnectionError,
        openai.InternalServerError,
    )

    def _is_transient(e: Exception) -> bool:
        return isinstance(e, retryable) or (
            isinstance(e, openai.APIStatusError) and getattr(e, "status_code", None) in _RETRYABLE_STATUS
        )

    client = OpenAI(api_key=api_key, base_url=base_url, timeout=_chat_timeout())
    return retry_call(
        lambda: client.chat.completions.create(**kwargs),
        attempts=max_retries,
        base_backoff=DEFAULT_RETRY_BACKOFF,
        mode="linear",
        should_retry=_is_transient,
        on_exhausted="raise",
        log=log,
    )
