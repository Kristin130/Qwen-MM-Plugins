"""OSS (Alibaba Object Storage) primitives shared by every capability.

Credentials, bucket construction, and content-addressed upload + signed URL. OSS is optional
everywhere: callers check ``is_upload_configured()`` and fall back to inline media when it is unset.
The ``oss2`` SDK is an optional dependency (the ``oss`` extra) and is imported lazily, so importing
this module never requires it.

Also here: the local-path → OSS-object resolution + server-side snapshot frames used by the media
readers and the ASR tool. Both the ``core`` reader (``read_video``) and the ``api`` capability
(``transcribe_audio``) share it, so it lives here rather than in either capability.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import posixpath
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from shared.env import get_env

log = logging.getLogger(__name__)

DEFAULT_URL_EXPIRY = 7200
_MD5_CHUNK = 8 * 1024 * 1024
_CLIP_DURATION = 30.0  # assumed duration (s) of a resolved OSS video object
_SNAPSHOT_WORKERS = 16


def credentials() -> tuple[str, str]:
    """(access_key_id, access_key_secret) from OSS_AK / OSS_SK."""
    return get_env("OSS_AK", ""), get_env("OSS_SK", "")


def to_public_endpoint(endpoint: str) -> str:
    """Convert an internal OSS endpoint to a public one."""
    return endpoint.replace("-internal", "")


def bucket(endpoint: str, bucket_name: str):
    """Return an oss2.Bucket. Raises RuntimeError when credentials are unset."""
    import oss2

    ak, sk = credentials()
    if not ak or not sk:
        raise RuntimeError("OSS credentials not set. Set OSS_AK/OSS_SK, OSS_ENDPOINT, OSS_BUCKET.")
    return oss2.Bucket(oss2.Auth(ak, sk), to_public_endpoint(endpoint), bucket_name)


def url_expiry() -> int:
    """Signed-URL TTL in seconds (OSS_URL_EXPIRY, default 7200)."""
    raw = get_env("OSS_URL_EXPIRY")
    try:
        return int(raw) if raw else DEFAULT_URL_EXPIRY
    except ValueError:
        log.warning("OSS_URL_EXPIRY=%r is not a valid integer; using %d", raw, DEFAULT_URL_EXPIRY)
        return DEFAULT_URL_EXPIRY


def is_upload_configured() -> bool:
    """True when uploading is actually possible: creds + endpoint + OSS_BUCKET **and** oss2 installed.

    Checking the SDK here (not just the env) keeps callers from picking the OSS path and then failing
    mid-request — a half-configured setup degrades to whatever inline fallback the caller has.
    """
    ak, sk = credentials()
    if not (ak and sk and get_env("OSS_ENDPOINT") and get_env("OSS_BUCKET")):
        return False
    try:
        import oss2  # noqa: F401
    except ImportError:
        log.warning("OSS_* is configured but the oss2 SDK is missing — install the 'oss' extra to use it")
        return False
    return True


def upload_and_sign(path: str, *, key_prefix: str = "", expires: int | None = None) -> str:
    """Upload a local file to OSS_BUCKET and return a signed HTTPS URL.

    The object key is content-addressed (``<key_prefix>/<md5><ext>``), so re-uploading the same bytes
    overwrites the same object instead of littering the bucket — and a repeated call on an unchanged
    file is effectively idempotent.
    """
    endpoint = get_env("OSS_ENDPOINT")
    bucket_name = get_env("OSS_BUCKET")
    if not endpoint or not bucket_name:
        raise RuntimeError("OSS upload needs OSS_ENDPOINT + OSS_BUCKET (plus OSS_AK/OSS_SK)")

    digest = hashlib.md5()  # noqa: S324 — a content address, not a security digest
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(_MD5_CHUNK), b""):
            digest.update(chunk)
    key = posixpath.join(key_prefix.strip("/"), f"{digest.hexdigest()}{os.path.splitext(path)[1]}")

    b = bucket(endpoint, bucket_name)
    with open(path, "rb") as fh:
        b.put_object(key, fh)
    url = b.sign_url("GET", key, expires if expires is not None else url_expiry(), slash_safe=True)
    log.info("uploaded %.1f MB to oss://%s/%s", os.path.getsize(path) / 1e6, bucket_name, key)
    return url.replace("http://", "https://")


# ── Local-path → OSS-object resolution + server-side snapshot frames ────────────────────────────
# Used by the media readers (read_video) and the ASR tool (transcribe_audio) to serve source videos
# by signed URL and pull frames via OSS video/snapshot instead of downloading + decoding locally.

_EGOLIFE_FILENAME_RE = re.compile(r"^(DAY\d+)_(.+?)_(\d{5,})\.\w+$", re.IGNORECASE)


def _infer_subdirectory(filename: str) -> str | None:
    """DAY1_A1_JAKE_11240000.mp4 → A1_JAKE/DAY1/DAY1_A1_JAKE_11240000.mp4"""
    m = _EGOLIFE_FILENAME_RE.match(filename)
    if not m:
        return None
    day, person, _ = m.groups()
    return f"{person}/{day}/{filename}"


def resolve_video(video_path: str) -> dict[str, Any] | None:
    """Map a local video path to an OSS object via OSS_VIDEO_* env vars.

    Returns {bucket, endpoint, oss_key, clip_duration} or None.
    """
    bucket_name = get_env("OSS_VIDEO_BUCKET")
    endpoint = get_env("OSS_ENDPOINT")
    key_prefix = get_env("OSS_VIDEO_KEY_PREFIX")
    local_prefix = get_env("OSS_VIDEO_LOCAL_PREFIX", "").rstrip("/")
    if not all([bucket_name, endpoint, key_prefix]):
        return None

    if local_prefix and video_path.startswith(local_prefix + "/"):
        rel = video_path[len(local_prefix) + 1 :]
    elif not os.path.isabs(video_path):
        rel = video_path
    else:
        return None

    # Reject path traversal — a rel escaping the key prefix must not map to an OSS key.
    rel = posixpath.normpath(rel)
    if posixpath.isabs(rel) or rel == ".." or rel.startswith("../"):
        return None

    # Bare filename → try egolife convention to infer subdirectory.
    if "/" not in rel:
        rel = _infer_subdirectory(rel) or rel

    effective_prefix = key_prefix.rstrip("/")
    for entry in get_env("OSS_VIDEO_KEY_PREFIX_MAP", "").split(","):
        entry = entry.strip()
        if "=" in entry:
            path_pfx, oss_pfx = entry.split("=", 1)
            if rel.startswith(path_pfx.strip()):
                effective_prefix = oss_pfx.strip().rstrip("/")
                break

    return {
        "bucket": bucket_name,
        "endpoint": endpoint,
        "oss_key": f"{effective_prefix}/{rel}",
        "clip_duration": _CLIP_DURATION,
    }


def signed_url(oss_info: dict, expires: int = 21600) -> str:
    """A signed HTTPS URL for a resolved OSS video object."""
    url = bucket(oss_info["endpoint"], oss_info["bucket"]).sign_url(
        "GET", oss_info["oss_key"], expires, slash_safe=True
    )
    return url.replace("http://", "https://")


def snapshot_frames(
    oss_info: dict, timestamps_ms: list[int], max_dim: int, max_workers: int = _SNAPSHOT_WORKERS
) -> list[tuple[float, str]]:
    """Fetch frames via OSS server-side video/snapshot. Returns [(second, base64_jpeg)]."""
    b = bucket(oss_info["endpoint"], oss_info["bucket"])
    oss_key = oss_info["oss_key"]

    def _fetch(ts_ms: int) -> tuple[float, str] | None:
        process = f"video/snapshot,t_{ts_ms},w_{max_dim},f_jpg,m_fast"
        url = b.sign_url("GET", oss_key, 21600, slash_safe=True, params={"x-oss-process": process}).replace(
            "http://", "https://"
        )
        try:
            with urllib.request.urlopen(urllib.request.Request(url), timeout=30) as resp:
                data = resp.read()
            if data:
                return (round(ts_ms / 1000.0, 2), base64.b64encode(data).decode("ascii"))
        except Exception:
            pass
        return None

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        return [r for r in pool.map(_fetch, timestamps_ms) if r is not None]
