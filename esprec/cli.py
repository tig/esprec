"""Agent-first CLI: thin wrapper over esprec.capture + esprec.serial_port."""

from __future__ import annotations

import argparse
import sys

from esprec import __version__
from esprec.capture import make_fake_port, record, snapshot, spool_to_gif
from esprec.protocol import ProtocolError
from esprec.serial_port import open_port


def _port_for_args(args: argparse.Namespace, *, n_frames: int = 1):
    if args.fake:
        return make_fake_port(n_frames), 0.0
    if not args.port:
        print("error: --port required (or --fake for offline)", file=sys.stderr)
        raise SystemExit(2)
    return open_port(args.port, args.baud), float(args.settle)


def cmd_snapshot(args: argparse.Namespace) -> int:
    port, settle = _port_for_args(args, n_frames=1)
    try:
        meta = snapshot(
            port,
            args.output,
            command=args.command,
            timeout_s=args.timeout,
            settle_s=settle,
        )
        print(
            f"OK wrote {args.output} {meta.w}x{meta.h} ver={meta.version} "
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
    n = max(1, int(args.frames))
    port, settle = _port_for_args(args, n_frames=n)
    try:
        metas = record(
            port,
            args.output,
            frames=n,
            hz=args.hz,
            command=args.command,
            timeout_s=args.timeout,
            settle_s=settle,
            save_frame_pngs=args.save_frames,
            caption_prefix=args.caption_prefix or "",
        )
        for i, meta in enumerate(metas):
            print(f"OK frame {i} {meta.w}x{meta.h}")
        print(f"OK wrote {args.output} ({len(metas)} frames @ {args.hz} Hz)")
        return 0
    except ProtocolError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    finally:
        if hasattr(port, "close"):
            port.close()


def cmd_spool(args: argparse.Namespace) -> int:
    """Device-side continuous record then spool → realtime-delay GIF."""
    if args.fake:
        print(
            "error: --fake does not simulate device rec/spool; use metal or unit tests",
            file=sys.stderr,
        )
        return 2
    if not args.port:
        print("error: --port required", file=sys.stderr)
        return 2
    port = open_port(args.port, args.baud)
    try:
        metas = spool_to_gif(
            port,
            args.output,
            duration_s=args.duration,
            hz=args.hz,
            settle_s=args.settle,
            timeout_s=args.timeout,
            save_frame_pngs=args.save_frames,
        )
        print(
            f"OK wrote {args.output} ({len(metas)} frames @ ~{args.hz} Hz device sample)"
        )
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
  esprec snapshot --fake -o face.png
  esprec record --port COMx --frames 5 --hz 2 -o clip.gif   # host-paced (slow)
  esprec spool --port COMx --duration 3 --hz 5 -o live.gif  # device rec→spool (smooth)

Library:
  from esprec.serial_port import open_port
  from esprec.capture import snapshot, record, spool_to_gif

Device: `shot` | `esprec rec start <hz> <sec>` | `esprec rec stop` | `esprec spool`.

Integrity: ESPREC1 CRC covers metadata + raster. Captions (if any) are *above*
the panel — never over product chrome.

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
    r.add_argument(
        "--caption-prefix",
        default="",
        help="optional captions *above* each panel (never over product pixels)",
    )
    r.set_defaults(func=cmd_record)

    sp = sub.add_parser(
        "spool",
        help="device multi-frame rec then spool → GIF (realtime delays)",
    )
    sp.add_argument("--port", default=None)
    sp.add_argument("--baud", type=int, default=115200)
    sp.add_argument("-o", "--output", default="spool.gif")
    sp.add_argument("--duration", type=float, default=3.0, help="seconds to sample")
    sp.add_argument("--hz", type=float, default=5.0, help="device sample rate")
    sp.add_argument("--settle", type=float, default=0.3)
    sp.add_argument("--timeout", type=float, default=600.0)
    sp.add_argument("--save-frames", action="store_true")
    sp.add_argument("--fake", action="store_true")
    sp.set_defaults(func=cmd_spool)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
