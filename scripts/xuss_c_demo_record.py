#!/usr/bin/env python3
"""Xuss-C product scenario: end-to-end demo → smooth keyframe GIF via esprec.

Lives under esprec/scripts/ so hero re-record stays visible (xuss-c clean-start
main is docs-only). Product domain only: btn inject + settle + public esprec API.

Capture model is **host-paced single shot** (~18.5 s / full panel @ 115200).
Playback smoothness comes from GIF frame delays + settled keyframes, not from
high capture FPS. See ``scripts/xuss_c_bench_capture_rate.py``.

Captions (if enabled) are drawn *above* the panel only.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from PIL import Image

try:
    from esprec.capture import capture_image, spool_to_gif
    from esprec.image_out import caption_above, save_gif, save_png
    from esprec.serial_port import open_port
except ImportError:
    print("pip install -e .  # from esprec checkout", file=sys.stderr)
    raise SystemExit(2)

# Playback delays (ms) — tuned for readable state changes, not capture wall time.
DELAY_STATE_MS = 1100
DELAY_LIVING_MS = 400
DELAY_PLAY_MS = 1400
DELAY_DETAILS_MS = 1300


class DemoError(RuntimeError):
    """Hard fail for demo recording (do not emit misleading labeled frames)."""


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


def btn(ser, which: str, hold: float = 0.5) -> None:
    """Inject button edge; abort if firmware does not acknowledge."""
    ser.reset_input_buffer()
    ser.write(f"btn {which}\n".encode())
    ser.flush()
    ack = wait_ok(ser, "ok btn", timeout=2.0)
    if not ack:
        raise DemoError(f"btn {which}: no acknowledgement (timeout)")
    if ack.startswith("err"):
        raise DemoError(f"btn {which}: device replied {ack!r}")
    time.sleep(hold)


def snap(
    ser,
    path: Path,
    note: str,
    *,
    timeout: float,
    delay_ms: int,
    caption: bool,
) -> tuple[Image.Image, Image.Image, int]:
    """Return (product_rgb, gif_frame, delay_ms). product_rgb is never captioned."""
    meta, img = capture_image(ser, command="shot", timeout_s=timeout)
    rgb = img.convert("RGB")
    save_png(rgb, path)
    print(f"OK {path.name} {meta.w}x{meta.h} delay={delay_ms}ms — {note}")
    gif_frame = caption_above(rgb, note) if caption else rgb
    return rgb, gif_frame, delay_ms


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", required=True)
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("-o", "--outdir", default="docs/examples")
    ap.add_argument("--boot-wait", type=float, default=4.5)
    ap.add_argument("--play-wait", type=float, default=4.0)
    ap.add_argument("--hold", type=float, default=0.55, help="UI settle after btn")
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument(
        "--living-hz",
        type=float,
        default=5.0,
        help="device-side sample rate for living-face spool (realtime GIF)",
    )
    ap.add_argument(
        "--living-sec",
        type=float,
        default=2.5,
        help="seconds of living-face continuous capture via esprec rec/spool",
    )
    ap.add_argument(
        "--captions",
        action="store_true",
        help="pad captions above panel (never over product chrome)",
    )
    ap.add_argument("--no-reboot", action="store_true")
    ap.add_argument(
        "--no-spool",
        action="store_true",
        help="skip device rec/spool living segment (keyframes only)",
    )
    args = ap.parse_args()

    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)

    product_frames: list[Image.Image] = []
    demo_frames: list[Image.Image] = []
    delays: list[int] = []
    step = 0

    def add(note: str, delay_ms: int, *, after_btn: str | None = None) -> None:
        nonlocal step
        if after_btn:
            btn(ser, after_btn, hold=args.hold)
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in note)[:48]
        path = out / f"{step:02d}_{safe}.png"
        product, gif_frame, d = snap(
            ser,
            path,
            note,
            timeout=args.timeout,
            delay_ms=delay_ms,
            caption=args.captions,
        )
        product_frames.append(product)
        demo_frames.append(gif_frame)
        delays.append(d)
        step += 1

    ser = open_port(args.port, args.baud)
    try:
        if not args.no_reboot:
            ser.reset_input_buffer()
            ser.write(b"reboot\n")
            ser.flush()
            time.sleep(0.4)
            ser.close()
            time.sleep(1.2)
            ser = open_port(args.port, args.baud)

        print(f"boot wait {args.boot_wait}s…")
        time.sleep(args.boot_wait)
        ser.reset_input_buffer()

        # Continuous living-face segment: device samples at living_hz into
        # RAM/flash, then spools once (realtime GIF delays from ts_ms).
        if not args.no_spool:
            live_gif = out / "xuss-c-living-realtime.gif"
            print(
                f"device rec/spool living face {args.living_sec}s @ {args.living_hz} Hz…"
            )
            metas = spool_to_gif(
                ser,
                live_gif,
                duration_s=args.living_sec,
                hz=args.living_hz,
                settle_s=0.4,
                timeout_s=args.timeout * 3,
            )
            print(f"OK {live_gif} ({len(metas)} frames, device sample)")
            if metas:
                add("idle face (post living spool)", DELAY_STATE_MS)

        add("theme orange (A)", DELAY_STATE_MS, after_btn="a")
        add("Details sensors (C)", DELAY_DETAILS_MS, after_btn="c")
        add("exit Details face (A)", DELAY_STATE_MS, after_btn="a")
        add("theme step (A)", DELAY_STATE_MS, after_btn="a")
        add("play First by Tig (B)", DELAY_PLAY_MS, after_btn="b")
        print(f"play wait {args.play_wait}s…")
        time.sleep(args.play_wait)
        add(f"still playing ~{args.play_wait:.0f}s", DELAY_PLAY_MS)
        add("pause via A (no theme change)", DELAY_STATE_MS, after_btn="a")

        if not product_frames:
            raise DemoError("no frames captured")

        # Narrative demo GIF (may include captions above panel).
        demo_gif = out / "xuss-c-demo.gif"
        demo_frames[0].save(
            demo_gif,
            save_all=True,
            append_images=demo_frames[1:],
            duration=delays,
            loop=0,
            optimize=False,
        )
        # Always also write pure product pixels (README / docs link this path).
        product_gif = out / "xuss-c-demo-product.gif"
        product_frames[0].save(
            product_gif,
            save_all=True,
            append_images=product_frames[1:],
            duration=delays,
            loop=0,
            optimize=False,
        )
        print(
            f"OK wrote {demo_gif} + {product_gif} "
            f"({len(product_frames)} frames, delays_ms={delays})"
        )
        print(
            "capture_note: host-paced max ~0.054 fps @ 115200; "
            "GIF delays make playback smooth, not capture rate"
        )
        return 0
    except DemoError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    finally:
        ser.close()


if __name__ == "__main__":
    raise SystemExit(main())
