#!/usr/bin/env python3
"""Xuss-C product scenario: drive screens over one serial session; capture with esprec.

Lives under esprec/scripts/ (hero stills live in docs/examples/). GCU-domain
btn sequence + acceptance stills via the public esprec capture API — not a
private CLI helper.

Acceptance stills are **unlabeled** full 320x240 panel pixels. Optional GIF
captions are drawn *above* the panel via esprec.image_out.caption_above.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from PIL import Image

try:
    from esprec.capture import capture_image
    from esprec.image_out import caption_above, save_gif, save_png
    from esprec.serial_port import open_port
except ImportError:
    print(
        "esprec required: pip install -e .  # from esprec checkout\n"
        "Then: python scripts/xuss_c_screen_scenario.py --port COMx -o capture/",
        file=sys.stderr,
    )
    raise SystemExit(2)


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


def snap(ser, path: Path, note: str, timeout: float) -> Image.Image:
    meta, img = capture_image(ser, command="shot", timeout_s=timeout)
    save_png(img, path)
    print(f"OK {path} {meta.w}x{meta.h} crc=0x{meta.crc:08x} — {note}")
    return img.convert("RGB")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", required=True)
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("-o", "--outdir", default="docs/examples")
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

    ser = open_port(args.port, args.baud)
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

        # Unlabeled product loop (README keyframe hero).
        screens = out / "xuss-c-screens.gif"
        save_gif(panels, screens, duration_ms=1200)
        print(f"OK wrote {screens} ({len(panels)} frames, product pixels only)")

        if args.gif_captions:
            gif_frames = [
                caption_above(im, f"{i} {notes[i]}") for i, im in enumerate(panels)
            ]
            gif = out / "scenario.gif"
            save_gif(gif_frames, gif, duration_ms=1200)
            print(f"OK wrote {gif} ({len(gif_frames)} frames, captions above panel)")
        return 0
    finally:
        ser.close()


if __name__ == "__main__":
    raise SystemExit(main())
