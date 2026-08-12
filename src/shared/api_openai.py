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

# ── Multi-provider failover pool ────────────────────────────────────────────────────────────────────
# The pool is configured with numbered providers: QWEN_MM_PROVIDER<n>_BASE_URL / _API_KEY / _MODEL
# for n=1,2,… — LOWER number = HIGHER priority, provider 1 is the primary endpoint. The legacy
# DASHSCOPE_BASE_URL / DASHSCOPE_API_KEY / DASHSCOPE_MODEL pair is honoured as a provider-1 alias
# (so existing setups keep working), but the canonical config is the numbered pool.
#
# A provider can pin its OWN model via QWEN_MM_PROVIDER<n>_MODEL — a foreign (non-qwen)
# model for a Qwen-proprietary protocol (grounding's bbox JSON, the Omni A/V protocol) is skipped
# unless the tool opts in via ``allow_foreign_model`` (vision_chat / ocr do).
#
# Numbered providers: QWEN_MM_PROVIDER1_BASE_URL / _API_KEY / _MODEL, QWEN_MM_PROVIDER2_*, …
# Discovered by scanning N=1,2,… (stop at the first gap), ordered by number — LOWER number =
# HIGHER priority.
PROVIDER_PREFIX = "QWEN_MM_PROVIDER"

# HTTP statuses worth retrying for OpenAI-compatible endpoints.
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BACKOFF = 1.0
# Request timeout (seconds) for a chat call — generous for long vision prompts, but bounded so a
# hung connection can't pin a tool call for an hour. Overridable via QWEN_MM_CHAT_TIMEOUT.
DEFAULT_CHAT_TIMEOUT = 600

# Per-model video-duration ceilings for SERVER-SIDE sampling (seconds), from Bailian/Model Studio docs
# (help.aliyun.com/zh/model-studio/vision, as of 2026-08). Prefix-matched against the model id; a model
# with no entry is treated as "unknown" → no cap (the endpoint still enforces its own limit). Only
# relevant on the OSS-upload path, where the whole video is sampled server-side.
_VL_VIDEO_MAX_SEC: dict[str, int] = {
    "qwen3.7-plus": 2 * 3600,  # flagship: up to 2 h / 2 GB
    "qwen-vl-max": 20 * 60,  # 2 s – 20 min, ≤ 1 GB
    "qwen3-vl": 20 * 60,
}


def vl_video_max_sec(model: str | None) -> int | None:
    """Server-side video-duration cap (seconds) for a VL ``model``, or None when unknown."""
    if not model:
        return None
    for prefix, cap in _VL_VIDEO_MAX_SEC.items():
        if model.startswith(prefix):
            return cap
    return None


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


def _provider_env_name(index: int, suffix: str) -> str:
    """QWEN_MM_PROVIDER<n>_<SUFFIX> for the numbered provider ``index``."""
    return f"{PROVIDER_PREFIX}{index}_{suffix}"


def _provider_env_value(index: int, suffix: str) -> str | None:
    """Value of QWEN_MM_PROVIDER<n>_<SUFFIX>; provider 1 falls back to the legacy
    DASHSCOPE_<SUFFIX> alias so existing setups keep working with no new variables."""
    v = get_env(_provider_env_name(index, suffix))
    if v is not None:
        return v
    if index == 1:
        return get_env(f"DASHSCOPE_{suffix}")
    return None


def _numbered_providers() -> list[int]:
    """Provider indices discovered by scanning QWEN_MM_PROVIDER<n>_BASE_URL for n=1,2,…
    until the first gap (a provider without a base_url ends the sequence — numbering must stay
    contiguous from 1). Provider 1 also honours the legacy DASHSCOPE_BASE_URL alias. Returns
    indices in ascending order — LOWER number = HIGHER priority.
    """
    out: list[int] = []
    n = 1
    while True:
        base = _provider_env_value(n, "BASE_URL")
        if not base:
            break  # first gap ends the scan
        out.append(n)
        n += 1
    return out


def _is_qwen_model(model: str) -> bool:
    """True if ``model`` is a Qwen-family model id (contains ``qwen``, case-insensitive)."""
    return "qwen" in model.lower()


def provider_model_override(arguments: dict[str, Any], base_url: str) -> str | None:
    """Per-provider model override for the endpoint ``base_url``, if configured.

    ``QWEN_MM_PROVIDER<n>_MODEL`` pins provider n's model (provider 1 also honours the legacy
    ``DASHSCOPE_MODEL`` alias). Matched by base_url so an explicit endpoint argument also
    resolves; returns None when no provider pins a model for this endpoint.
    """
    for i in _numbered_providers():
        p_base = _provider_env_value(i, "BASE_URL")
        if p_base and (p_base.rstrip("/") == base_url.rstrip("/") or p_base == base_url):
            model = _provider_env_value(i, "MODEL")
            if model:
                return model
    return None


def resolve_openai_endpoints(arguments: dict[str, Any]) -> list[tuple[str, str]]:
    """Resolve the ordered (base_url, api_key) pool for an OpenAI-compatible call.

    Precedence, first match wins at call time:
    1. explicit ``base_url`` / ``api_key`` arguments → a single endpoint (no failover);
    2. each numbered provider ``QWEN_MM_PROVIDER<n>_*`` for n=1,2,… — LOWER number = HIGHER
       priority (the scan stops at the first gap in base_url). Provider 1 also honours the
       legacy ``DASHSCOPE_BASE_URL`` / ``DASHSCOPE_API_KEY`` alias, so existing setups keep
       working with no new variables — but the canonical config is the numbered pool.

    A provider without a base_url is skipped; a missing api_key falls back to "EMPTY" so
    local/self-hosted servers that ignore auth still work (DashScope itself then fails fast
    with an actionable message).
    """
    explicit_base = arguments.get("base_url")
    explicit_key = arguments.get("api_key")
    if explicit_base or explicit_key:
        return [(explicit_base or _provider_env_value(1, "BASE_URL") or DEFAULT_DASHSCOPE_BASE_URL, explicit_key or "EMPTY")]

    pool: list[tuple[str, str]] = []
    for i in _numbered_providers():
        p_base = _provider_env_value(i, "BASE_URL")
        p_key = _provider_env_value(i, "API_KEY") or "EMPTY"
        pool.append((p_base.rstrip("/"), p_key))
    return pool


def resolve_openai_endpoint(arguments: dict[str, Any]) -> tuple[str, str]:
    """Resolve the FIRST (base_url, api_key) for an OpenAI-compatible call (no failover).

    Kept for callers that want a single endpoint (e.g. dry_run previews); new code should use
    ``resolve_openai_endpoints`` and let ``call_openai_chat`` fail over.
    """
    endpoints = resolve_openai_endpoints(arguments)
    if not endpoints:
        raise RuntimeError(
            "no providers configured — set QWEN_MM_PROVIDER1_BASE_URL / QWEN_MM_PROVIDER1_API_KEY "
            "(or the legacy DASHSCOPE_BASE_URL / DASHSCOPE_API_KEY pair)"
        )
    return endpoints[0]


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


def encode_video_source(
    source: str, max_frames: int = 128, *, allow_upload: bool = True, model: str | None = None
) -> dict[str, Any]:
    """OpenAI-style video content part: a URL passthrough, an OSS upload, or a local file sampled
    into frames.

    Routing for a local video mirrors the Omni path (``shared.api_omni`` / the api ``omni/_common``) so
    both share ONE trigger — ``shared.oss.is_upload_configured()``: when OSS is configured the file is
    uploaded and handed over as a signed ``video_url`` (the endpoint samples it server-side, lifting the
    inline frame cap); otherwise it is sampled locally into inline frames. That upload path samples the
    whole video server-side, which caps duration per ``model`` — so a local file longer than the cap
    skips the upload and degrades to local frame sampling instead (sparse for very long clips, but it
    still returns a result). ``allow_upload=False`` suppresses the upload (used by ``dry_run`` so a
    preview never touches the network).
    """
    if is_url(source):
        return {"type": "video_url", "video_url": {"url": source}}

    if allow_upload:
        from shared import oss

        if oss.is_upload_configured():
            from shared.video import video_duration_exceeds

            if video_duration_exceeds(source, vl_video_max_sec(model)):
                log.warning(
                    "video %s exceeds the server-side duration limit for model %r; sampling frames "
                    "locally instead of uploading",
                    source,
                    model or DEFAULT_MODEL,
                )
            else:
                url = oss.upload_and_sign(source, key_prefix=get_env("OSS_VIDEO_CLIP_PREFIX", "tmp/video_clips"))
                return {"type": "video_url", "video_url": {"url": url}}

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

    # Disable the SDK's own retry loop (OpenAI() defaults to max_retries=2) so retry_call + the
    # failover pool own the retry budget — otherwise every retry attempt fans out 3 HTTP requests.
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=_chat_timeout(), max_retries=0)
    return retry_call(
        lambda: client.chat.completions.create(**kwargs),
        attempts=max_retries,
        base_backoff=DEFAULT_RETRY_BACKOFF,
        mode="linear",
        should_retry=_is_transient,
        on_exhausted="raise",
        log=log,
    )


def call_openai_chat_failover(
    *,
    arguments: dict[str, Any] | None = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
    allow_foreign_model: bool = False,
    thinking: str | None = None,
    **kwargs: Any,
) -> Any:
    """Call OpenAI-compatible chat completions across the configured provider pool.

    ``call_openai_chat`` (single endpoint, existing signature) plus failover: the providers come
    from ``resolve_openai_endpoints(arguments or {})`` — an explicit ``base_url``/``api_key``
    yields exactly one provider (no failover, backwards compatible); otherwise the pool is walked
    in order, and when a provider exhausts its retries the next one is tried. After the last
    provider fails, the LAST error is raised.

    Per-provider model override: when the provider pins ``QWEN_MM_PROVIDER_<NAME>_MODEL`` the
    call uses that model instead of the ``model`` kwarg. A pinned model that is NOT a qwen model
    is only used when ``allow_foreign_model=True`` (vision_chat / ocr — generic caption/OCR work
    on any compatible model); otherwise that provider is skipped with a warning, because the
    Qwen-proprietary protocols (grounding bbox JSON, Omni A/V) don't transfer to foreign models.

    Retry policy per provider is the same as ``call_openai_chat`` (transient openai errors + 429/
    5xx statuses); each provider's ``api_key``/``base_url`` is logged at DEBUG only.
    """
    providers = resolve_openai_endpoints(arguments or {})
    requested_model = kwargs.get("model") or DEFAULT_MODEL
    last_error: Exception | None = None
    for base_url, api_key in providers:
        model = provider_model_override(arguments or {}, base_url) or requested_model
        if not allow_foreign_model and not _is_qwen_model(model):
            log.warning(
                "provider %s pins non-qwen model %r — skipping (this tool needs a qwen model; "
                "only vision_chat / ocr accept foreign models)",
                base_url,
                model,
            )
            continue
        log.debug("attempting provider base_url=%s model=%s", base_url, model)
        provider_kwargs = dict(kwargs)
        if thinking is not None:
            # Per-provider thinking control — the knob depends on the ACTUAL model that
            # serves the request and the endpoint, not on the base_url alone (the primary can
            # pin a foreign model like Gemini behind a DashScope URL, which rejects both knobs):
            #   · Qwen on DashScope official → ``enable_thinking`` (hybrid-thinking models)
            #   · Qwen on SiliconFlow → ``thinking_budget`` (thinking-only models honour it)
            #   · foreign models (Gemini / GPT-4o / …) → send nothing (they reject unknown fields)
            if _is_qwen_model(model):
                if "dashscope" in base_url:
                    # ``min`` → hybrid-thinking models answer directly (no CoT)
                    provider_kwargs["extra_body"] = {**provider_kwargs.get("extra_body", {}), "enable_thinking": thinking != "min"}
                elif "siliconflow" in base_url:
                    provider_kwargs["extra_body"] = {**provider_kwargs.get("extra_body", {}), "thinking_budget": 1 if thinking == "min" else 4096}
        try:
            return call_openai_chat(
                base_url=base_url, api_key=api_key, max_retries=max_retries, **{**provider_kwargs, "model": model}
            )
        except Exception as e:  # noqa: BLE001 — any provider failure moves to the next one
            last_error = e
            log.warning(
                "provider %s failed after %d attempt(s): %s — trying next provider",
                base_url,
                max_retries,
                e,
            )
    if last_error is not None:
        raise last_error
    raise RuntimeError("no providers configured")
