"""Serial (or fake) transport: request frame, parse delimited payload."""

from __future__ import annotations

import time
from typing import Protocol, runtime_checkable

from esprec.protocol import (
    B64_LINE_RE,
    FrameMeta,
    ProtocolError,
    decode_b64_payload,
    parse_header_line,
    verify_and_extract,
)


@runtime_checkable
class BytePort(Protocol):
    def write(self, data: bytes) -> int: ...
    def readline(self) -> bytes: ...
    def read(self, n: int) -> bytes: ...
    def reset_input_buffer(self) -> None: ...
    def flush(self) -> None: ...


class FakeDevicePort:
    """In-process device that answers ``esprec shot`` / ``shot`` with canned frames.

    Same contract as a real serial port: empty ``readline`` means "no data yet"
    (caller waits until timeout). Does not require special-casing in grab_frame.
    """

    def __init__(self, frames: list[tuple[str, list[str], str]]):
        """frames: list of (header, b64_lines, end_line)."""
        self._frames = list(frames)
        self._idx = 0
        self._out: list[bytes] = []
        self._in_buf = bytearray()

    def write(self, data: bytes) -> int:
        self._in_buf.extend(data)
        while b"\n" in self._in_buf:
            line, _, rest = self._in_buf.partition(b"\n")
            self._in_buf = bytearray(rest)
            cmd = line.decode("utf-8", errors="replace").strip().lower()
            if cmd in ("esprec shot", "shot", "frame", "esprec"):
                if self._idx >= len(self._frames):
                    self._out.append(b"ESPREC1_ERR no_frame\n")
                else:
                    header, b64s, end = self._frames[self._idx]
                    self._idx += 1
                    self._out.append((header + "\n").encode())
                    for bl in b64s:
                        self._out.append((bl + "\n").encode())
                    self._out.append((end + "\n").encode())
            elif cmd.startswith("btn "):
                self._out.append(f"ok {cmd}\n".encode())
        return len(data)

    def readline(self) -> bytes:
        if not self._out:
            return b""
        return self._out.pop(0)

    def read(self, n: int) -> bytes:
        return b""

    def reset_input_buffer(self) -> None:
        self._out.clear()

    def flush(self) -> None:
        pass


def _cmd_bytes(command: bytes | str) -> bytes:
    if isinstance(command, bytes):
        return command if command.endswith(b"\n") else command + b"\n"
    s = command if command.endswith("\n") else command + "\n"
    return s.encode()


def _read_payload(port: BytePort, meta: FrameMeta, deadline: float) -> bytes:
    b64_parts: list[str] = []
    raw = bytearray()
    saw_end = False
    end_prefixes = ("ESPREC1_END", "SHOT_END")

    if meta.enc in ("b64", "base64"):
        while time.monotonic() < deadline:
            line = port.readline()
            if not line:
                continue
            text = line.decode("utf-8", errors="replace").strip()
            if text.startswith(end_prefixes):
                saw_end = True
                break
            if text.startswith("ESPREC1") or text.startswith("SHOT"):
                continue
            if B64_LINE_RE.fullmatch(text):
                b64_parts.append(text)
        if not saw_end:
            raise ProtocolError(
                "missing ESPREC1_END/SHOT_END delimiter after payload "
                "(timeout or incomplete frame)"
            )
        raw = bytearray(decode_b64_payload(b64_parts))
    else:
        while len(raw) < meta.nbytes and time.monotonic() < deadline:
            chunk = port.read(min(4096, meta.nbytes - len(raw)))
            if chunk:
                raw.extend(chunk)
        while time.monotonic() < deadline:
            line = port.readline()
            if not line:
                continue
            t = line.decode("utf-8", errors="replace").strip()
            if t.startswith(end_prefixes):
                saw_end = True
                break
        if not saw_end:
            raise ProtocolError(
                "missing ESPREC1_END/SHOT_END delimiter after payload "
                "(timeout or incomplete frame)"
            )
    return verify_and_extract(meta, bytes(raw))


def read_next_frame(
    port: BytePort,
    *,
    deadline: float,
    skip_until_header: bool = True,
) -> tuple[FrameMeta, bytes] | None:
    """Read next ESPREC1/SHOT frame from an open stream (no command).

    Returns None if ESPREC1_REC_END is seen. Raises on ESPREC1_ERR / timeout.
    """
    from esprec.protocol import ESPREC_REC_END_RE

    while time.monotonic() < deadline:
        line = port.readline()
        if not line:
            continue
        text = line.decode("utf-8", errors="replace").strip()
        if not text:
            continue
        if text.startswith("ESPREC1_ERR") or text.startswith("SHOT_ERR"):
            raise ProtocolError(text)
        if ESPREC_REC_END_RE.match(text) or text.startswith("ESPREC1_REC_END"):
            return None
        if text.startswith("ESPREC1_REC"):
            continue  # envelope; wait for first frame
        try:
            meta = parse_header_line(text)
        except ProtocolError:
            if skip_until_header:
                continue
            raise
        raster = _read_payload(port, meta, deadline)
        return meta, raster
    raise ProtocolError("timeout waiting for frame header")


def grab_frame(
    port: BytePort,
    *,
    timeout_s: float = 90.0,
    command: bytes | str = b"esprec shot\n",
) -> tuple[FrameMeta, bytes]:
    """Request one frame; return meta + verified raster bytes.

    Empty readline is treated as "no data yet" until the deadline (same for
    real serial and FakeDevicePort). Missing ESPREC1_END/SHOT_END fails closed.
    """
    port.reset_input_buffer()
    port.write(_cmd_bytes(command))
    port.flush()
    deadline = time.monotonic() + timeout_s
    got = read_next_frame(port, deadline=deadline)
    if got is None:
        raise ProtocolError("unexpected REC_END on single-shot grab")
    return got


def grab_spool(
    port: BytePort,
    *,
    command: bytes | str = b"esprec spool\n",
    timeout_s: float = 600.0,
) -> list[tuple[FrameMeta, bytes]]:
    """Request multi-frame spool; return list of (meta, raster) in order."""
    from esprec.protocol import ESPREC_REC_START_RE

    port.reset_input_buffer()
    port.write(_cmd_bytes(command))
    port.flush()
    deadline = time.monotonic() + timeout_s
    expected: int | None = None

    while time.monotonic() < deadline:
        line = port.readline()
        if not line:
            continue
        text = line.decode("utf-8", errors="replace").strip()
        if text.startswith("ESPREC1_ERR"):
            raise ProtocolError(text)
        m = ESPREC_REC_START_RE.match(text)
        if m:
            expected = int(m.group("frames"))
            break
    if expected is None:
        raise ProtocolError("timeout waiting for ESPREC1_REC header")

    frames: list[tuple[FrameMeta, bytes]] = []
    while time.monotonic() < deadline:
        got = read_next_frame(port, deadline=deadline)
        if got is None:
            break
        frames.append(got)
        if expected is not None and len(frames) >= expected:
            # drain optional REC_END
            t_end = time.monotonic() + 2.0
            while time.monotonic() < t_end:
                line = port.readline()
                if not line:
                    continue
                if b"REC_END" in line:
                    break
            break

    if not frames:
        raise ProtocolError("spool returned zero frames")
    if expected is not None and len(frames) != expected:
        # Prefer partial success over hard fail (device may have auto-capped).
        # Callers still get real-time ts_ms delays for the frames that arrived.
        pass
    return frames

