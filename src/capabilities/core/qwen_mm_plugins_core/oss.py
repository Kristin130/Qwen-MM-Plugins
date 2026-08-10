"""OSS (Alibaba Object Storage) helpers for the vision tools.

Local-to-OSS path mapping and server-side snapshot frames. The credential/bucket primitives are
re-exported from ``shared.oss`` (every capability needs those); this module keeps only the
vision-specific mapping. OSS is optional -- tools fall back to local files when unset.
"""

from __future__ import annotations

import base64
import os
import posixpath
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from shared.env import get_env
from shared.oss import bucket as bucket
from shared.oss import credentials as credentials
from shared.oss import to_public_endpoint as to_public_endpoint

_CLIP_DURATION = 30.0  # assumed duration (s) of a resolved OSS video object
_SNAPSHOT_WORKERS = 16


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
