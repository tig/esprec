"""Host post-process: PNG stills and GIF sequences."""

from __future__ import annotations

from pathlib import Path

from PIL import Image


def save_png(img: Image.Image, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(path, format="PNG")
    return path


def save_gif(
    frames: list[Image.Image],
    path: str | Path,
    *,
    duration_ms: int = 500,
    loop: int = 0,
) -> Path:
    if not frames:
        raise ValueError("no frames for GIF")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rgb = [f.convert("RGB") for f in frames]
    rgb[0].save(
        path,
        save_all=True,
        append_images=rgb[1:],
        duration=duration_ms,
        loop=loop,
        format="GIF",
    )
    return path


def label_frame(img: Image.Image, caption: str) -> Image.Image:
    """Optional host-side caption bar for keyframe GIFs."""
    from PIL import ImageDraw

    out = img.copy().convert("RGB")
    draw = ImageDraw.Draw(out)
    bar_h = 16
    draw.rectangle([0, 0, out.width, bar_h], fill=(0, 0, 0))
    draw.text((4, 2), caption[:48], fill=(255, 255, 255))
    return out
