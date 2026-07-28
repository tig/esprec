#!/usr/bin/env python3
"""Drive xuss-c screens over one serial session; capture with esprec.

Keeps the port open (no mid-scenario reopen) so DTR/RTS reset cannot wipe UI.

Acceptance stills are **unlabeled** full 320x240 panel pixels (banner hair and
Details firmware line must remain visible for agent/spec judgment). Optional
GIF captions are drawn on a **taller canvas above** the panel, never over product
pixels (never y=0..16 of the 320x240 face).
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from PIL import Image, ImageDraw

from esprec.cli import _open_serial
from esprec.image_out import save_gif, save_png
from esprec.pixels import raster_to_image
from esprec.transport import grab_frame

CAPTION_PAD = 18  # rows *above* the panel for optional GIF narrative only


def wait_ok(ser, prefix: str = "ok", timeout: float = 3.0) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        line = ser.readline()
        if not line:
            continue
        text = line.decode("utf-8", errors="replace").strip()
        if text.startswith(prefix) or text.startswith("err"):
            return text
    return ""


def btn(ser, which: str, hold: float = 0.45) -> None:
    ser.reset_input_buffer()
    ser.write(f"btn {which}\n".encode())
    ser.flush()
    wait_ok(ser, "ok btn", timeout=2.0)
    time.sleep(hold)


def caption_above(img: Image.Image, caption: str) -> Image.Image:
    """Narrative bar *outside* the panel — does not overwrite product chrome."""
    rgb = img.convert("RGB")
    w, h = rgb.size
    out = Image.new("RGB", (w, h + CAPTION_PAD), (0, 0, 0))
    out.paste(rgb, (0, CAPTION_PAD))
    draw = ImageDraw.Draw(out)
    draw.text((4, 2), caption[:48], fill=(255, 255, 255))
    return out


def snap(ser, path: Path, note: str, timeout: float) -> Image.Image:
    """Save unlabeled panel PNG; return RGB image for optional GIF assembly."""
    meta, raster = grab_frame(ser, timeout_s=timeout, command=b"shot\n")
    img = raster_to_image(raster, meta.w, meta.h, meta.fmt, meta.pack)
    save_png(img, path)
    print(f"OK {path} {meta.w}x{meta.h} crc=0x{meta.crc:08x} — {note}")
    return img.convert("RGB")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", required=True)
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("-o", "--outdir", default="capture/xuss-c")
    ap.add_argument("--boot-wait", type=float, default=4.0)
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument(
        "--gif-captions",
        action="store_true",
        help="build scenario.gif with captions above panel (never over product pixels)",
    )
    args = ap.parse_args()

    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)

    steps: list[tuple[str, Path, str]] = [
        ("", out / "01_idle_blue.png", "idle blue face + banner"),
        ("a", out / "02_theme_orange.png", "theme after A (orange)"),
        ("a", out / "02b_theme_red.png", "theme after A again (red)"),
        ("c", out / "03_details.png", "Details + firmware identity"),
    ]

    ser = _open_serial(args.port, args.baud)
    try:
        print(f"settle {args.boot_wait}s (no reset)…")
        time.sleep(args.boot_wait)
        ser.reset_input_buffer()

        panels: list[Image.Image] = []
        notes: list[str] = []
        for which, path, note in steps:
            if which:
                btn(ser, which)
            panels.append(snap(ser, path, note, args.timeout))
            notes.append(note)

        if args.gif_captions:
            gif_frames = [
                caption_above(im, f"{i} {notes[i]}") for i, im in enumerate(panels)
            ]
        else:
            gif_frames = panels

        gif = out / "scenario.gif"
        save_gif(gif_frames, gif, duration_ms=1200)
        print(
            f"OK wrote {gif} ({len(gif_frames)} frames, "
            f"captions_above_panel={args.gif_captions})"
        )
        return 0
    finally:
        ser.close()


if __name__ == "__main__":
    raise SystemExit(main())
