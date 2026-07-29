"""Shared Xuss-C *product* serial helpers for hero re-record scripts.

Not part of the esprec package API. esprec remains eyes-only (capture);
these scripts live under ``scripts/`` so product scenarios stay next to
``docs/examples/`` while xuss-c clean-start ``main`` is docs-only.

Product domain: ``btn`` / ``identity`` / ``reboot`` inject on metal.
Capture: public ``esprec`` API only.
"""

from __future__ import annotations

import time
from pathlib import Path

from PIL import Image

from esprec.capture import capture_image
from esprec.image_out import save_png


class ScenarioError(RuntimeError):
    """Hard fail — do not write labeled heroes for an unknown UI state."""


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
        raise ScenarioError(f"btn {which}: no acknowledgement (timeout)")
    if ack.startswith("err"):
        raise ScenarioError(f"btn {which}: device replied {ack!r}")
    time.sleep(hold)


def snap_png(ser, path: Path, note: str, *, timeout: float) -> Image.Image:
    """Capture one still; write PNG; return RGB panel image."""
    meta, img = capture_image(ser, command="shot", timeout_s=timeout)
    rgb = img.convert("RGB")
    save_png(rgb, path)
    print(f"OK {path.name} {meta.w}x{meta.h} crc=0x{meta.crc:08x} — {note}")
    return rgb
