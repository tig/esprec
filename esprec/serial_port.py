"""Public serial open helper (DTR/RTS safe for ESP auto-reset)."""

from __future__ import annotations

import sys


def open_port(port: str, baud: int = 115200, *, timeout: float = 0.5):
    """Open USB serial with DTR/RTS deasserted before and after open.

    Setting lines low *before* open avoids Windows/ESP auto-reset that
    reboots the board mid-session (black unpainted shadow on early shot).
    """
    try:
        import serial
    except ImportError as e:
        print("pyserial required: pip install pyserial", file=sys.stderr)
        raise SystemExit(2) from e

    ser = serial.Serial()
    ser.port = port
    ser.baudrate = baud
    ser.timeout = timeout
    ser.dsrdtr = False
    ser.rtscts = False
    ser.dtr = False
    ser.rts = False
    ser.open()
    ser.dtr = False
    ser.rts = False
    return ser
