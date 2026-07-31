"""Public serial open helper (DTR/RTS safe for ESP auto-reset).

ESP boards decode DTR/RTS as an auto-reset request. The table is the same
whether the circuit is discrete (CP210x, CH34x, FTDI) or built into the chip
(ESP32-S3/C3/C6/H2 USB-Serial-JTAG):

    DTR=0 and RTS=1  ->  EN low   (reset)
    DTR=1 and RTS=0  ->  IO0 low  (download mode)

So the host must never let the lines pass through ``DTR=0, RTS=1``. Both hosts
can hit that state, but at opposite moments, so the fix is opposite too.

* **Windows** is safe at open: the DCB is applied in one step, so whatever the
  lines end up as, they get there together. The hazard is at **close**. A
  session that left the lines asserted drops them on close and the board
  reboots, which is the black unpainted shadow on the *next* shot. Deasserting
  means there is nothing left to drop.

* **POSIX** is the mirror image. The kernel raises both lines together at open,
  so opening is safe, but pyserial then lowers them one at a time, always DTR
  first, and that passes straight through the reset combination. Here the fix
  is to leave the lines alone and clear HUPCL so close does not drop them
  either.

Measured on ESP32 boards with a boot counter in NVS, native USB and CP2104
bridge alike: on Linux and macOS every ``deassert`` rebooted the board at open;
on Windows 11 nothing rebooted at open, but closing a ``keep`` session rebooted
it every time and closing a ``deassert`` session never did.

Set ``ESPREC_CONTROL_LINES`` to ``keep`` or ``deassert`` to override.
"""

from __future__ import annotations

import os
import sys

KEEP = "keep"  # do not touch DTR/RTS at all
DEASSERT = "deassert"  # drive both lines low, atomically, at open
AUTO = "auto"

_MODES = (KEEP, DEASSERT, AUTO)


def default_mode() -> str:
    """Control-line policy this host can implement without a reset glitch."""
    return DEASSERT if os.name == "nt" else KEEP


def resolve_mode(control_lines: str | None = None) -> str:
    """Explicit argument wins, then ``ESPREC_CONTROL_LINES``, then the host."""
    mode = control_lines or os.environ.get("ESPREC_CONTROL_LINES") or AUTO
    mode = mode.strip().lower()
    if mode not in _MODES:
        raise SystemExit(
            f"invalid control-lines mode {mode!r}; expected one of {', '.join(_MODES)}"
        )
    return default_mode() if mode == AUTO else mode


def _clear_hupcl(ser) -> bool:
    """Stop the kernel from dropping DTR/RTS when the port is closed.

    This is the POSIX half of the same problem Windows has at close. Boards with
    a discrete auto-reset circuit (CP210x, CH34x, FTDI) reboot when the lines
    rise again, and with HUPCL set they fall on every close, so the next open
    resets the board. Clearing HUPCL leaves them asserted between sessions,
    which is what makes back-to-back snapshots keep the running screen.

    Best effort: not every platform or fake port has termios.
    """
    if os.name != "posix":
        return False
    try:
        import termios

        fd = ser.fileno()
        attrs = termios.tcgetattr(fd)
        if not attrs[2] & termios.HUPCL:
            return True
        attrs[2] &= ~termios.HUPCL
        termios.tcsetattr(fd, termios.TCSANOW, attrs)
        return True
    except Exception:
        return False


def open_port(
    port: str,
    baud: int = 115200,
    *,
    timeout: float = 0.5,
    control_lines: str | None = None,
):
    """Open USB serial without rebooting the board."""
    try:
        import serial
    except ImportError as e:
        print("pyserial required: pip install pyserial", file=sys.stderr)
        raise SystemExit(2) from e

    mode = resolve_mode(control_lines)

    ser = serial.Serial()
    ser.port = port
    ser.baudrate = baud
    ser.timeout = timeout
    ser.dsrdtr = False
    ser.rtscts = False
    if mode == DEASSERT:
        # Stored here; the Windows driver applies both together at open, and
        # leaving them low is what keeps close from rebooting the board.
        ser.dtr = False
        ser.rts = False
    ser.open()
    if mode == DEASSERT:
        ser.dtr = False
        ser.rts = False
    else:
        _clear_hupcl(ser)
    return ser
