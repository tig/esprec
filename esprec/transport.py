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
    """In-process device that answers ``esprec shot`` / ``shot`` with canned frames."""

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


def grab_frame(
    port: BytePort,
    *,
    timeout_s: float = 90.0,
    command: bytes = b"esprec shot\n",
) -> tuple[FrameMeta, bytes]:
    """Request one frame; return meta + verified raster bytes."""
    port.reset_input_buffer()
    port.write(command)
    port.flush()
    deadline = time.monotonic() + timeout_s
    meta: FrameMeta | None = None

    while time.monotonic() < deadline:
        line = port.readline()
        if not line:
            # FakeDevice returns empty when idle; real serial may block on timeout.
            if isinstance(port, FakeDevicePort):
                continue
            continue
        text = line.decode("utf-8", errors="replace").strip()
        if not text:
            continue
        if text.startswith("ESPREC1_ERR") or text.startswith("SHOT_ERR"):
            raise ProtocolError(text)
        try:
            meta = parse_header_line(text)
            break
        except ProtocolError:
            continue  # log noise
    if meta is None:
        raise ProtocolError("timeout waiting for frame header")

    b64_parts: list[str] = []
    raw = bytearray()
    enc = meta.enc
    saw_end = False
    end_prefixes = ("ESPREC1_END", "SHOT_END")

    if enc in ("b64", "base64"):
        while time.monotonic() < deadline:
            line = port.readline()
            if not line:
                if isinstance(port, FakeDevicePort) and not port._out:
                    break
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

    raster = verify_and_extract(meta, bytes(raw))
    return meta, raster
