#!/usr/bin/env python3
"""Xuss-C product scenario: drive screens over one serial session; capture with esprec.

Lives under esprec/scripts/ (hero stills live in docs/examples/). GCU-domain
btn sequence + acceptance stills via the public esprec capture API — not a
private CLI helper. Product inject is intentional here (see scripts/README.md);
it is not exported from the esprec package.

Acceptance stills are **unlabeled** full 320x240 panel pixels. Optional GIF
captions are drawn *above* the panel via esprec.image_out.caption_above.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

try:
    from esprec.image_out import caption_above, save_gif
    from esprec.serial_port import open_port
except ImportError:
    print(
        "esprec required: pip install -e .  # from esprec checkout\n"
        "Then: python scripts/xuss_c_screen_scenario.py --port COMx -o docs/examples",
        file=sys.stderr,
    )
    raise SystemExit(2)

# Sibling helper (not a package module).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from xuss_c_product import ScenarioError, btn, snap_png  # noqa: E402


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

        panels = []
        notes: list[str] = []
        for which, path, note in steps:
            if which:
                btn(ser, which)
            panels.append(snap_png(ser, path, note, timeout=args.timeout))
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
    except ScenarioError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    finally:
        ser.close()


if __name__ == "__main__":
    raise SystemExit(main())
