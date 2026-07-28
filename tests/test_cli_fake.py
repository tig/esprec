"""CLI + public capture API against FakeDevicePort."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from esprec.capture import capture_image, make_fake_port, record, snapshot
from esprec.cli import main
from esprec.image_out import caption_above
from esprec.pixels import solid_rgb565_spi_be
from esprec.protocol import ProtocolError, build_esprec1_frame
from esprec.transport import FakeDevicePort, grab_frame


def test_grab_frame_fake_device():
    w, h = 16, 12
    raster = solid_rgb565_spi_be(w, h, 200, 100, 50)
    wire = build_esprec1_frame(w, h, raster)
    port = FakeDevicePort([wire])
    meta, out = grab_frame(port, timeout_s=2.0)
    assert meta.w == w and out == raster


def test_capture_api_snapshot(tmp_path: Path):
    port = make_fake_port(1)
    out = tmp_path / "face.png"
    meta = snapshot(port, out, settle_s=0.0, timeout_s=2.0)
    assert meta.w == 32 and out.is_file() and out.stat().st_size > 50


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
    out1 = tmp_path / "one.gif"
    out5 = tmp_path / "five.gif"
    assert main(["record", "--fake", "-o", str(out1), "--frames", "1"]) == 0
    assert main(
        ["record", "--fake", "-o", str(out5), "--frames", "5", "--save-frames"]
    ) == 0
    stem = out5.with_suffix("")
    saved = list(tmp_path.glob(f"{stem.name}_*.png"))
    assert len(saved) == 5


def test_cli_agent_guide():
    assert main(["agent-guide"]) == 0


def test_integrity_fail_exits_nonzero_via_grab():
    w, h = 8, 8
    raster = solid_rgb565_spi_be(w, h, 1, 1, 1)
    header, b64s, end = build_esprec1_frame(w, h, raster)
    bad = FakeDevicePort([(header, b64s[:1], end)])
    with pytest.raises(ProtocolError):
        grab_frame(bad, timeout_s=2.0)


def test_missing_end_delimiter_fails():
    w, h = 4, 4
    raster = solid_rgb565_spi_be(w, h, 2, 2, 2)
    header, b64s, _end = build_esprec1_frame(w, h, raster)

    class Partial:
        def __init__(self):
            self._out = [(header + "\n").encode()] + [
                (b + "\n").encode() for b in b64s
            ]

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

    with pytest.raises(ProtocolError, match="missing ESPREC1_END"):
        grab_frame(Partial(), timeout_s=1.0)


def test_caption_above_does_not_overwrite_panel_top():
    """Captions must not paint over product chrome (y=0 of original panel)."""
    panel = Image.new("RGB", (40, 30), (10, 20, 30))
    panel.putpixel((0, 0), (255, 0, 0))
    panel.putpixel((5, 5), (0, 255, 0))
    out = caption_above(panel, "note")
    assert out.size == (40, 30 + 18)
    # Original panel top-left is now at y=18
    assert out.getpixel((0, 18)) == (255, 0, 0)
    assert out.getpixel((5, 23)) == (0, 255, 0)
    # Caption band is black-ish, not original red at (0,0)
    assert out.getpixel((0, 0)) != (255, 0, 0)


def test_no_label_frame_export():
    import esprec.image_out as io

    assert not hasattr(io, "label_frame")
