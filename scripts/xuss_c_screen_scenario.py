#!/usr/bin/env python3
"""Drive xuss-c screens over one serial session; capture with esprec.

Keeps the port open (no mid-scenario reopen) so DTR/RTS reset cannot wipe UI.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from esprec.cli import _open_serial
from esprec.image_out import label_frame, save_gif, save_png
from esprec.pixels import raster_to_image
from esprec.transport import grab_frame


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


def snap(ser, path: Path, caption: str, timeout: float) -> None:
    meta, raster = grab_frame(ser, timeout_s=timeout, command=b"shot\n")
    img = raster_to_image(raster, meta.w, meta.h, meta.fmt, meta.pack)
    labeled = label_frame(img, caption)
    save_png(labeled, path)
    print(f"OK {path} {meta.w}x{meta.h} crc=0x{meta.crc:08x} — {caption}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", required=True)
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("-o", "--outdir", default="capture/xuss-c")
    ap.add_argument("--boot-wait", type=float, default=4.0)
    ap.add_argument("--timeout", type=float, default=120.0)
    args = ap.parse_args()

    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)

    ser = _open_serial(args.port, args.baud)
    frames = []
    try:
        print(f"settle {args.boot_wait}s (no reset)…")
        time.sleep(args.boot_wait)
        ser.reset_input_buffer()

        steps = []
        snap(ser, out / "01_idle_blue.png", "0 idle blue face", args.timeout)
        steps.append(out / "01_idle_blue.png")

        btn(ser, "a")
        snap(ser, out / "02_theme_orange.png", "1 theme after A", args.timeout)
        steps.append(out / "02_theme_orange.png")

        btn(ser, "a")
        snap(ser, out / "02b_theme_red.png", "2 theme after A again", args.timeout)
        steps.append(out / "02b_theme_red.png")

        btn(ser, "c")
        snap(ser, out / "03_details.png", "3 Details screen", args.timeout)
        steps.append(out / "03_details.png")

        from PIL import Image

        for p in steps:
            frames.append(Image.open(p).convert("RGB"))
        gif = out / "scenario.gif"
        save_gif(frames, gif, duration_ms=1200)
        print(f"OK wrote {gif} ({len(frames)} frames)")
        return 0
    finally:
        ser.close()


if __name__ == "__main__":
    raise SystemExit(main())
