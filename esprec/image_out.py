"""Host post-process: PNG stills and GIF sequences."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

# Rows *above* the panel for narrative captions — never over product chrome.
CAPTION_PAD = 18


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


def caption_above(img: Image.Image, caption: str, *, pad: int = CAPTION_PAD) -> Image.Image:
    """Narrative bar *outside* the panel — does not overwrite product chrome.

    Pastes the panel at y=pad so hair banner / Details identity (y≈0..18 of
    the 320×240 face) stay intact. Prefer this over any in-panel caption bar.
    """
    rgb = img.convert("RGB")
    w, h = rgb.size
    out = Image.new("RGB", (w, h + pad), (0, 0, 0))
    out.paste(rgb, (0, pad))
    draw = ImageDraw.Draw(out)
    draw.text((4, 2), caption[:48], fill=(255, 255, 255))
    return out
