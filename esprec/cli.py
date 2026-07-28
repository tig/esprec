"""Agent-first CLI: esprec snapshot | record | help."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from esprec import __version__
from esprec.image_out import label_frame, save_gif, save_png
from esprec.pixels import raster_to_image
from esprec.protocol import ProtocolError
from esprec.transport import FakeDevicePort, grab_frame


def _open_serial(port: str, baud: int):
    try:
        import serial
    except ImportError as e:
        print("pyserial required: pip install pyserial", file=sys.stderr)
        raise SystemExit(2) from e
    # Set DTR/RTS low *before* open so Windows/ESP auto-reset does not reboot
    # the board (which leaves a black/unpainted shadow on early shot).
    ser = serial.Serial()
    ser.port = port
    ser.baudrate = baud
    ser.timeout = 0.5
    ser.dsrdtr = False
    ser.rtscts = False
    ser.dtr = False
    ser.rts = False
    ser.open()
    ser.dtr = False
    ser.rts = False
    return ser


def cmd_snapshot(args: argparse.Namespace) -> int:
    out = Path(args.output)
    if args.fake:
        from esprec.pixels import solid_rgb565_spi_be
        from esprec.protocol import build_esprec1_frame

        w, h = 32, 24
        raster = solid_rgb565_spi_be(w, h, 0, 0, 255)
        frame = build_esprec1_frame(w, h, raster)
        port = FakeDevicePort([frame])
        settle = 0.0
    else:
        if not args.port:
            print("error: --port required (or --fake for offline)", file=sys.stderr)
            return 2
        port = _open_serial(args.port, args.baud)
        settle = args.settle

    try:
        if settle:
            time.sleep(settle)
        meta, raster = grab_frame(
            port,
            timeout_s=args.timeout,
            command=args.command.encode() + b"\n"
            if isinstance(args.command, str)
            else args.command,
        )
        img = raster_to_image(raster, meta.w, meta.h, meta.fmt, meta.pack)
        save_png(img, out)
        print(
            f"OK wrote {out} {meta.w}x{meta.h} ver={meta.version} "
            f"crc=0x{meta.crc:08x}"
        )
        return 0
    except ProtocolError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    finally:
        if hasattr(port, "close"):
            port.close()


def cmd_record(args: argparse.Namespace) -> int:
    out = Path(args.output)
    n = max(1, int(args.frames))
    if args.fake:
        from esprec.pixels import solid_rgb565_spi_be
        from esprec.protocol import build_esprec1_frame

        # Cycle solid colors so --frames N is honored offline (not a fixed 3).
        palette = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
        frames_wire = []
        for i in range(n):
            color = palette[i % len(palette)]
            r = solid_rgb565_spi_be(16, 12, *color)
            frames_wire.append(build_esprec1_frame(16, 12, r))
        port = FakeDevicePort(frames_wire)
        settle = 0.0
    else:
        if not args.port:
            print("error: --port required (or --fake)", file=sys.stderr)
            return 2
        port = _open_serial(args.port, args.baud)
        settle = args.settle

    period = 1.0 / args.hz if args.hz > 0 else 0.5
    images = []
    try:
        if settle:
            time.sleep(settle)
        cmd = (
            args.command.encode() + b"\n"
            if isinstance(args.command, str)
            else args.command
        )
        for i in range(n):
            t0 = time.monotonic()
            meta, raster = grab_frame(port, timeout_s=args.timeout, command=cmd)
            img = raster_to_image(raster, meta.w, meta.h, meta.fmt, meta.pack)
            if args.caption_prefix:
                img = label_frame(img, f"{args.caption_prefix}{i}")
            if args.save_frames:
                stem = out.with_suffix("")
                save_png(img, Path(f"{stem}_{i:03d}.png"))
            images.append(img)
            print(f"OK frame {i} {meta.w}x{meta.h}")
            elapsed = time.monotonic() - t0
            time.sleep(max(0.0, period - elapsed))
        save_gif(images, out, duration_ms=int(period * 1000))
        print(f"OK wrote {out} ({len(images)} frames @ {args.hz} Hz)")
        return 0
    except ProtocolError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    finally:
        if hasattr(port, "close"):
            port.close()


def cmd_agent_guide(_: argparse.Namespace) -> int:
    print(
        f"""esprec {__version__} — agent eyes on ESP32 screens

Mission: capture device framebuffer over USB serial → host PNG/GIF.
On-device half embeds in product firmware; this CLI is the host half.

Commands:
  esprec snapshot --port COMx -o face.png
  esprec snapshot --fake -o /tmp/fake.png          # offline unit path
  esprec record --port COMx --frames 5 --hz 2 -o clip.gif
  esprec record --fake -o /tmp/fake.gif

Device must answer: `esprec shot` or `shot` with ESPREC1 (preferred) or SHOT.

Integrity: ESPREC1 CRC covers metadata + raster. Truncated or
metadata-mismatched frames fail closed (non-zero exit).

Pipeline before product: if PNG disagrees with the glass, fix capture first.
PNG/GIF is agent evidence — operator product-face confirm remains for first ship.

See specs/spec.md and component/esprec/ for firmware integration.
"""
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="esprec",
        description="ESP32 screen capture for agents (PNG/GIF over USB serial)",
    )
    p.add_argument("--version", action="version", version=f"esprec {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("agent-guide", help="print agent-oriented usage")
    g.set_defaults(func=cmd_agent_guide)

    s = sub.add_parser("snapshot", help="one PNG from device (or --fake)")
    s.add_argument("--port", default=None)
    s.add_argument("--baud", type=int, default=115200)
    s.add_argument("-o", "--output", default="face.png")
    s.add_argument("--settle", type=float, default=1.0)
    s.add_argument("--timeout", type=float, default=90.0)
    s.add_argument("--command", default="esprec shot", help="device command line")
    s.add_argument("--fake", action="store_true", help="offline fake device")
    s.set_defaults(func=cmd_snapshot)

    r = sub.add_parser("record", help="multi-frame GIF (host post-process)")
    r.add_argument("--port", default=None)
    r.add_argument("--baud", type=int, default=115200)
    r.add_argument("-o", "--output", default="clip.gif")
    r.add_argument("--frames", type=int, default=3)
    r.add_argument("--hz", type=float, default=2.0)
    r.add_argument("--settle", type=float, default=1.0)
    r.add_argument("--timeout", type=float, default=90.0)
    r.add_argument("--command", default="esprec shot")
    r.add_argument("--fake", action="store_true")
    r.add_argument("--save-frames", action="store_true")
    r.add_argument("--caption-prefix", default="")
    r.set_defaults(func=cmd_record)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
