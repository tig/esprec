"""CLI entry points against FakeDevicePort (--fake)."""

from __future__ import annotations

from pathlib import Path

from esprec.cli import main
from esprec.protocol import build_esprec1_frame, parse_header_line, verify_and_extract
from esprec.pixels import solid_rgb565_spi_be
from esprec.transport import FakeDevicePort, grab_frame


def test_grab_frame_fake_device():
    w, h = 16, 12
    raster = solid_rgb565_spi_be(w, h, 200, 100, 50)
    wire = build_esprec1_frame(w, h, raster)
    port = FakeDevicePort([wire])
    meta, out = grab_frame(port, timeout_s=2.0)
    assert meta.w == w and out == raster


def test_cli_snapshot_fake(tmp_path: Path):
    out = tmp_path / "face.png"
    rc = main(["snapshot", "--fake", "-o", str(out)])
    assert rc == 0
    assert out.is_file() and out.stat().st_size > 50


def test_cli_record_fake(tmp_path: Path):
    out = tmp_path / "clip.gif"
    rc = main(["record", "--fake", "-o", str(out), "--frames", "3"])
    assert rc == 0
    assert out.is_file() and out.stat().st_size > 100


def test_cli_record_fake_honors_frame_count(tmp_path: Path):
    """--fake must use requested --frames, not a fixed fixture length."""
    out1 = tmp_path / "one.gif"
    out5 = tmp_path / "five.gif"
    assert main(["record", "--fake", "-o", str(out1), "--frames", "1"]) == 0
    assert main(
        ["record", "--fake", "-o", str(out5), "--frames", "5", "--save-frames"]
    ) == 0
    # Five numbered PNG side-frames prove five grabs (stem_000 … stem_004).
    stem = out5.with_suffix("")
    saved = list(tmp_path.glob(f"{stem.name}_*.png"))
    assert len(saved) == 5


def test_cli_agent_guide():
    assert main(["agent-guide"]) == 0


def test_integrity_fail_exits_nonzero_via_grab():
    """Truncated fake payload must not silently yield an image."""
    w, h = 8, 8
    raster = solid_rgb565_spi_be(w, h, 1, 1, 1)
    header, b64s, end = build_esprec1_frame(w, h, raster)
    # Drop most b64 lines → short payload
    bad = FakeDevicePort([(header, b64s[:1], end)])
    try:
        grab_frame(bad, timeout_s=2.0)
        raised = False
    except Exception as e:
        raised = True
        assert "truncated" in str(e).lower() or "integrity" in str(e).lower() or "base64" in str(e).lower() or "empty" in str(e).lower()
    assert raised


def test_missing_end_delimiter_fails():
    w, h = 4, 4
    raster = solid_rgb565_spi_be(w, h, 2, 2, 2)
    header, b64s, _end = build_esprec1_frame(w, h, raster)
    # No ESPREC1_END line — FakeDevicePort still emits end from build; craft manually.
    class Partial:
        def __init__(self):
            self._out = [(header + "\n").encode()] + [(b + "\n").encode() for b in b64s]
            # deliberately no end line
        def write(self, data: bytes) -> int:
            return len(data)
        def readline(self) -> bytes:
            return self._out.pop(0) if self._out else b""
        def read(self, n: int) -> bytes:
            return b""
        def reset_input_buffer(self) -> None:
            pass
        def flush(self) -> None:
            pass

    import pytest
    from esprec.protocol import ProtocolError

    with pytest.raises(ProtocolError, match="missing ESPREC1_END"):
        grab_frame(Partial(), timeout_s=1.0)
