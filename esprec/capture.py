"""Public capture API: grab one or more frames → PNG/GIF.

CLI and product scripts should call these helpers instead of re-assembling
``grab_frame`` + pixel decode + encode.
"""

from __future__ import annotations

import time
from pathlib import Path

from PIL import Image

from esprec.image_out import caption_above, save_gif, save_png
from esprec.pixels import raster_to_image
from esprec.protocol import FrameMeta
from esprec.transport import BytePort, grab_frame


def capture_image(
    port: BytePort,
    *,
    command: bytes = b"esprec shot\n",
    timeout_s: float = 90.0,
) -> tuple[FrameMeta, Image.Image]:
    """Request one frame; return meta + RGB image."""
    if isinstance(command, str):
        command = command.encode() if command.endswith("\n") else (command + "\n").encode()
    meta, raster = grab_frame(port, timeout_s=timeout_s, command=command)
    img = raster_to_image(raster, meta.w, meta.h, meta.fmt, meta.pack)
    return meta, img


def snapshot(
    port: BytePort,
    path: str | Path,
    *,
    command: bytes | str = b"esprec shot\n",
    timeout_s: float = 90.0,
    settle_s: float = 0.0,
) -> FrameMeta:
    """Capture one still PNG. Returns frame meta."""
    if settle_s > 0:
        time.sleep(settle_s)
    meta, img = capture_image(port, command=command, timeout_s=timeout_s)
    save_png(img, path)
    return meta


def record(
    port: BytePort,
    path: str | Path,
    *,
    frames: int = 3,
    hz: float = 2.0,
    command: bytes | str = b"esprec shot\n",
    timeout_s: float = 90.0,
    settle_s: float = 0.0,
    save_frame_pngs: bool = False,
    caption_prefix: str = "",
) -> list[FrameMeta]:
    """Capture N frames; write multi-frame GIF (host post-process).

    If ``caption_prefix`` is set, captions are drawn **above** the panel
    (never over product pixels).
    """
    n = max(1, int(frames))
    period = 1.0 / hz if hz > 0 else 0.5
    if settle_s > 0:
        time.sleep(settle_s)

    out = Path(path)
    images: list[Image.Image] = []
    metas: list[FrameMeta] = []
    for i in range(n):
        t0 = time.monotonic()
        meta, img = capture_image(port, command=command, timeout_s=timeout_s)
        if caption_prefix:
            img = caption_above(img, f"{caption_prefix}{i}")
        if save_frame_pngs:
            stem = out.with_suffix("")
            save_png(img, Path(f"{stem}_{i:03d}.png"))
        images.append(img)
        metas.append(meta)
        elapsed = time.monotonic() - t0
        time.sleep(max(0.0, period - elapsed))

    save_gif(images, out, duration_ms=int(period * 1000))
    return metas


def make_fake_port(n_frames: int = 1):
    """In-process FakeDevicePort with N solid-color ESPREC1 frames (tests/CLI)."""
    from esprec.pixels import solid_rgb565_spi_be
    from esprec.protocol import build_esprec1_frame
    from esprec.transport import FakeDevicePort

    palette = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (0, 0, 255)]
    n = max(1, int(n_frames))
    frames_wire = []
    for i in range(n):
        # snapshot default: one blue 32x24; multi: small 16x12 cycle
        if n == 1:
            r = solid_rgb565_spi_be(32, 24, 0, 0, 255)
            frames_wire.append(build_esprec1_frame(32, 24, r))
        else:
            color = palette[i % len(palette)]
            r = solid_rgb565_spi_be(16, 12, *color)
            frames_wire.append(build_esprec1_frame(16, 12, r))
    return FakeDevicePort(frames_wire)
