"""MCP tool: read and resize an image with model-optimized dynamic resolution."""

from __future__ import annotations

import base64
import io
from typing import Any, Literal

from pydantic import BaseModel, Field

from shared.env import DEFAULT_BUDGET, IMAGE_BUDGET_TOKENS, IMAGE_MIN_PIXELS
from shared.image import budget_to_pixels, smart_resize


class ReadImageArgs(BaseModel):
    image_path: str = Field(description="Absolute path to the image file")
    budget: Literal["small", "normal", "large"] = Field(
        default=DEFAULT_BUDGET,
        description="Resolution preset: small (~512×512), normal (~1024×1024), large (~1448×1448).",
    )


TOOL: dict[str, Any] = {
    "name": "read_image",
    "description": (
        "Read an image with model-optimized dynamic resolution. "
        "Automatically resizes to fit the target model's patch grid, "
        "balancing resolution and detail preservation. "
        "Returns the resized image for model consumption."
    ),
    "args": ReadImageArgs,
}


def process_image(img, min_pixels: int, max_pixels: int):
    """Resize a PIL Image to fit patch grid and pixel budget.

    Returns (resized_img, b64_str, target_w, target_h, mime_type).
    """
    from PIL import Image

    orig_w, orig_h = img.size

    target_h, target_w = smart_resize(
        orig_h,
        orig_w,
        min_pixels,
        max_pixels,
    )

    resized = img
    if (target_w, target_h) != (orig_w, orig_h):
        resized = img.resize((target_w, target_h), Image.LANCZOS)

    buf = io.BytesIO()
    # JPEG only handles RGB/L — keep palette/alpha as PNG; convert exotic modes to RGB.
    if img.mode in ("RGBA", "LA", "PA", "P"):
        fmt, mime, save_kwargs = "PNG", "image/png", {}
    else:
        fmt, mime, save_kwargs = "JPEG", "image/jpeg", {"quality": 90}
        if resized.mode not in ("RGB", "L"):
            resized = resized.convert("RGB")
    resized.save(buf, format=fmt, **save_kwargs)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    return resized, b64, target_w, target_h, mime


def handle(arguments: dict[str, Any]) -> list[dict[str, Any]]:
    from shared.content import image, require_dep, require_file, text

    image_path = arguments.get("image_path", "")
    budget = arguments.get("budget", DEFAULT_BUDGET)

    if err := require_file(image_path):
        return err
    if err := require_dep("PIL", "pillow"):
        return err

    from PIL import Image

    max_pixels = budget_to_pixels(budget, IMAGE_BUDGET_TOKENS)

    img = Image.open(image_path)
    orig_w, orig_h = img.size
    _, b64, target_w, target_h, mime = process_image(img, IMAGE_MIN_PIXELS, max_pixels)

    summary = f"Image: {image_path} | {orig_h}x{orig_w} → {target_h}x{target_w} (HxW)"
    return [text(summary), image(b64, mime)]
