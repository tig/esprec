#!/usr/bin/env python3
"""Xuss-C product scenario: measure host-paced esprec capture rate on metal.

Lives under esprec/scripts/. Findings (typical M5GO / CH9102 @ 115200, 320×240 RGB565 base64):

- One full-panel shot ≈ **18.5 s** wall clock → **~0.054 fps** host-paced max.
- Bound is **USB serial + base64**, not host CPU. Device UI/audio is blocked for
  the duration of the emit (printf over console).
- Identity RTT stays ~tens of ms before and after a shot once emit finishes.
- Raising host ``--hz`` above ~0.05 does **not** go faster: each shot waits for
  the previous full dump. Extra settle between shots only *slows* keyframe demos.

Implication for smooth *playback* GIFs: use **keyframe / step** capture with
GIF frame delays (e.g. 0.8–1.5 s per state), not continuous full-rate movie.
True continuous session capture needs **device-side multi-frame spool** (see
tig/esprec issues).
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

try:
    from esprec.capture import capture_image
    from esprec.serial_port import open_port
except ImportError:
    print("pip install -e .  # from esprec checkout", file=sys.stderr)
    raise SystemExit(2)


def identity_rtt(ser, timeout: float = 2.0) -> tuple[float | None, str | None]:
    ser.reset_input_buffer()
    t0 = time.monotonic()
    ser.write(b"identity\n")
    ser.flush()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        line = ser.readline()
        if not line:
            continue
        text = line.decode("utf-8", errors="replace").strip()
        if "fw_name=" in text:
            return time.monotonic() - t0, text
    return None, None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", required=True)
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--shots", type=int, default=4, help="back-to-back shots after warmup")
    ap.add_argument("-o", "--json-out", default="", help="optional path for JSON report")
    args = ap.parse_args()

    ser = open_port(args.port, args.baud)
    report: dict = {
        "port": args.port,
        "baud": args.baud,
        "panel": "320x240 rgb565be base64 ESPREC1",
        "model": "host-paced single shot (no device multi-frame spool)",
    }
    try:
        time.sleep(1.0)
        rtt0, id0 = identity_rtt(ser)
        report["identity_idle_rtt_s"] = rtt0
        report["identity_idle"] = id0
        print(f"identity_idle_rtt={rtt0}s {id0}")

        times: list[float] = []
        for i in range(max(1, args.shots)):
            t0 = time.monotonic()
            meta, _img = capture_image(ser, command="shot", timeout_s=120.0)
            dt = time.monotonic() - t0
            times.append(dt)
            print(f"shot[{i}] {dt:.2f}s {meta.w}x{meta.h} crc=0x{meta.crc:08x}")

        rtt1, id1 = identity_rtt(ser)
        report["identity_after_shot_rtt_s"] = rtt1
        report["identity_after_shot"] = id1
        mean = statistics.mean(times)
        report["shot_times_s"] = times
        report["shot_mean_s"] = mean
        report["shot_min_s"] = min(times)
        report["shot_max_s"] = max(times)
        report["max_sustainable_host_paced_fps"] = 1.0 / mean
        report["recommended_keyframe_gif_delay_ms"] = 1000
        report["recommended_living_sample_gif_delay_ms"] = 400
        report["notes"] = [
            "Do not set continuous --hz above ~0.05 at 115200 full panel; wasted waits.",
            "UI blocked during emit; schedule keyframes after settle, not mid-action.",
            "For true continuous session GIFs, need device ring-buffer spool (esprec issue).",
        ]
        print(f"mean_shot_s={mean:.2f} max_host_paced_fps={1/mean:.4f}")
        print(f"identity_after_shot_rtt={rtt1}s")
        print(json.dumps(report, indent=2))
        if args.json_out:
            Path(args.json_out).write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(f"wrote {args.json_out}")
        return 0
    finally:
        ser.close()


if __name__ == "__main__":
    raise SystemExit(main())
