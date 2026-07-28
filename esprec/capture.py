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
from esprec.protocol import FrameMeta, ProtocolError
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


def spool_to_gif(
    port: BytePort,
    path: str | Path,
    *,
    duration_s: float = 3.0,
    hz: float = 5.0,
    max_frames: int | None = None,
    settle_s: float = 0.3,
    timeout_s: float = 600.0,
    save_frame_pngs: bool = False,
) -> list[FrameMeta]:
    """Device-side record (sample at hz) then spool → GIF with real delays.

    Commands: ``esprec rec start <hz> <sec>`` → wait → ``esprec rec stop`` →
    ``esprec spool``. Playback delays come from device ``ts_ms`` when present.
    """
    from esprec.transport import grab_spool

    hz = max(0.5, float(hz))
    duration_s = max(0.2, float(duration_s))
    if max_frames is None:
        max_frames = int(hz * duration_s) + 2
    max_frames = max(1, int(max_frames))

    if settle_s > 0:
        time.sleep(settle_s)

    # start recording on device
    cmd = f"esprec rec start {hz:g} {duration_s:g}\n"
    port.reset_input_buffer()
    port.write(cmd.encode())
    port.flush()

    # wait for ok + recording window (+ small margin for last sample)
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        line = port.readline()
        if not line:
            continue
        text = line.decode("utf-8", errors="replace").strip()
        if text.startswith("ok rec begin"):
            break
        if text.startswith("ESPREC1_ERR"):
            raise ProtocolError(text)
    time.sleep(duration_s + 0.35)

    port.write(b"esprec rec stop\n")
    port.flush()
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        line = port.readline()
        if not line:
            continue
        text = line.decode("utf-8", errors="replace").strip()
        if text.startswith("ok rec stop"):
            break
        if text.startswith("ESPREC1_ERR"):
            raise ProtocolError(text)

    frames = grab_spool(port, command="esprec spool", timeout_s=timeout_s)
    if not frames:
        raise ProtocolError("empty spool")

    out = Path(path)
    images: list[Image.Image] = []
    metas: list[FrameMeta] = []
    delays: list[int] = []
    default_ms = int(1000.0 / hz)

    for i, (meta, raster) in enumerate(frames):
        img = raster_to_image(raster, meta.w, meta.h, meta.fmt, meta.pack)
        if save_frame_pngs:
            stem = out.with_suffix("")
            save_png(img, Path(f"{stem}_{i:03d}.png"))
        images.append(img)
        metas.append(meta)
        if i + 1 < len(frames):
            nmeta = frames[i + 1][0]
            if meta.ts_ms is not None and nmeta.ts_ms is not None:
                d = max(20, int(nmeta.ts_ms - meta.ts_ms))
            else:
                d = default_ms
        else:
            d = default_ms
        delays.append(d)

    images[0].save(
        out,
        save_all=True,
        append_images=images[1:],
        duration=delays,
        loop=0,
        format="GIF",
        optimize=False,
    )
    return metas
