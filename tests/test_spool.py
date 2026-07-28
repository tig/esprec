"""Multi-frame spool receive (host path for issue #3)."""

from __future__ import annotations

from pathlib import Path

from esprec.pixels import solid_rgb565_spi_be
from esprec.protocol import build_esprec1_frame, parse_header_line
from esprec.transport import FakeDevicePort, grab_spool


class SpoolPort:
    """Replay a canned multi-frame spool stream."""

    def __init__(self, lines: list[str]):
        self._out = [(ln + "\n").encode() for ln in lines]
        self._in = bytearray()

    def write(self, data: bytes) -> int:
        self._in.extend(data)
        return len(data)

    def readline(self) -> bytes:
        return self._out.pop(0) if self._out else b""

    def read(self, n: int) -> bytes:
        return b""

    def reset_input_buffer(self) -> None:
        pass

    def flush(self) -> None:
        pass


def test_parse_header_with_seq_ts():
    w, h = 4, 2
    r = solid_rgb565_spi_be(w, h, 1, 2, 3)
    header, _, _ = build_esprec1_frame(w, h, r, seq=2, ts_ms=1500)
    meta = parse_header_line(header)
    assert meta.seq == 2 and meta.ts_ms == 1500


def test_grab_spool_three_frames(tmp_path: Path):
    w, h = 8, 4
    lines = ["ESPREC1_REC frames=3 storage=ram interval_ms=200 w=8 h=4"]
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
    for i, c in enumerate(colors):
        r = solid_rgb565_spi_be(w, h, *c)
        header, b64s, end = build_esprec1_frame(
            w, h, r, seq=i, ts_ms=1000 + i * 200
        )
        lines.append(header)
        lines.extend(b64s)
        lines.append(end)
    lines.append("ESPREC1_REC_END frames=3")

    port = SpoolPort(lines)
    frames = grab_spool(port, command="esprec spool", timeout_s=5.0)
    assert len(frames) == 3
    assert frames[0][0].seq == 0
    assert frames[1][0].ts_ms == 1200
    assert frames[2][0].w == 8
