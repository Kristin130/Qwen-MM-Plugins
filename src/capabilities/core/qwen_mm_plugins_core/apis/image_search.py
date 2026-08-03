"""MCP tool: reverse image search via the public Serper (Google Lens) API.

Serper Lens needs a public image URL. To stay OSS-free (external users have no OSS),
a local frame is uploaded to a free anonymous host (uguu.se) to obtain a temporary
public URL; an image_path that is already an http(s) URL is used directly.
"""

from __future__ import annotations

import os
import tempfile
from typing import Any, Optional

from pydantic import BaseModel, Field

SERPER_LENS_MAX_RETRY = 10
UPLOAD_MAX_RETRY = 5
PUBLIC_UPLOAD_URL = "https://uguu.se/upload"

_TIP = "\n\n---\nTip: Use `web_search` to cross-check this identification, then `web_extractor` on the best URL for confirmation."


class ImageSearchArgs(BaseModel):
    image_path: str = Field(description="Absolute path to the image file to search, OR a public http(s) image URL.")
    bbox: Optional[list[float]] = Field(
        default=None,
        description="Bounding box [x1, y1, x2, y2] in relative coordinates (0-1000). Optional.",
        min_length=4,
        max_length=4,
    )
    api_key: Optional[str] = Field(default=None, description="Serper API key (defaults to SERPER_API_KEY).")


TOOL: dict[str, Any] = {
    "name": "image_search",
    "description": (
        "Reverse image search using an image file path (or a public image URL). "
        "Returns similar images with their source URLs, titles, and descriptions. "
        "Use this (and/or web_search) to CONFIRM any specific identification — model/species/place/person/event — "
        "before you answer; appearance alone is not proof. "
        "Grab the frame to search with save_view (don't run ffmpeg yourself)."
    ),
    "args": ImageSearchArgs,
}


def _crop_bbox(image_path: str, bbox: list[float]) -> str:
    """Crop image by bbox [x1,y1,x2,y2] in 0-1000 coords; returns path to temp file."""
    from PIL import Image

    from shared.image import norm_to_pixel

    img = Image.open(image_path)
    x1, y1, x2, y2 = norm_to_pixel([int(v) for v in bbox], img.width, img.height)
    cropped = img.crop((x1, y1, x2, y2))
    out = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False, prefix="qvl_crop_")
    out.close()
    cropped.save(out.name, "JPEG", quality=90)
    return out.name


def _download(url: str) -> Optional[str]:
    """Download a remote image to a temp file; returns path or None."""
    import requests

    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        out = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False, prefix="qvl_dl_")
        out.write(resp.content)
        out.close()
        return out.name
    except Exception:
        return None


def _upload_public(path: str, max_retry: int = UPLOAD_MAX_RETRY) -> Optional[str]:
    """Upload a local image to a free anonymous host (uguu.se) → temporary public URL."""
    import requests

    from shared.retry import retry_call

    def _upload() -> str:
        with open(path, "rb") as f:
            resp = requests.post(PUBLIC_UPLOAD_URL, files={"files[]": f}, timeout=60)
        resp.raise_for_status()
        url = (resp.json().get("files") or [{}])[0].get("url")
        if not url:
            raise RuntimeError("upload response contained no url")
        return url

    return retry_call(_upload, attempts=max_retry, mode="exp", cap=10, on_exhausted="none")


def _lens_search(image_url: str, api_key: str, max_retry: int = SERPER_LENS_MAX_RETRY) -> list[dict[str, Any]]:
    """Reverse image search via the public Serper (Google Lens) API."""
    from qwen_mm_plugins_core.serper import post_serper

    data = post_serper("lens", {"url": image_url, "gl": "us", "hl": "en"}, api_key, max_retries=max_retry)
    return (data or {}).get("organic", [])


def _format_results(docs: list[dict[str, Any]]) -> str:
    lines = []
    for i, doc in enumerate(docs, 1):
        title = doc.get("title", "")
        link = doc.get("link", "")
        source = doc.get("source", "")
        img_url = doc.get("imageUrl", "")
        parts = [f"[{i}]"]
        if img_url:
            parts.append(f'"{img_url}"')
        if title:
            parts.append(title)
        if source:
            parts.append(f"({source})")
        if link:
            parts.append(f"\n    Link: {link}")
        lines.append(" ".join(parts))
    return "\n".join(lines) if lines else "No results found."


def handle(arguments: dict[str, Any]) -> list[dict[str, Any]]:
    from qwen_mm_plugins_core.serper import resolve_serper_key
    from shared.content import require_dep, require_file, text_error

    if err := require_dep("requests"):
        return err

    image_path = arguments.get("image_path", "")
    api_key = resolve_serper_key(arguments)
    if not api_key:
        return text_error("no API key. Set SERPER_API_KEY or pass api_key.")

    is_url = isinstance(image_path, str) and image_path.startswith(("http://", "https://"))
    bbox = arguments.get("bbox")
    want_crop = bool(bbox) and bbox != [0, 0, 1000, 1000]

    # Fast path: already a public URL and no crop needed → hand straight to Lens.
    if is_url and not want_crop:
        docs = _lens_search(image_path, api_key)
        return [{"type": "text", "text": _format_results(docs) + _TIP}]

    tmps: list[str] = []
    try:
        local = image_path
        if is_url:  # need a local copy to crop
            local = _download(image_path)
            if not local:
                return text_error(f"could not download image URL: {image_path}")
            tmps.append(local)
        else:
            if err := require_file(local):
                return err

        if want_crop:
            try:
                local = _crop_bbox(local, bbox)
                tmps.append(local)
            except Exception:
                pass

        image_url = _upload_public(local)
        if not image_url:
            return text_error(
                "failed to host image for search (uguu.se upload failed); retry or pass a public image URL."
            )

        docs = _lens_search(image_url, api_key)
        return [{"type": "text", "text": _format_results(docs) + _TIP}]
    finally:
        for t in tmps:
            if t and os.path.exists(t):
                os.unlink(t)
