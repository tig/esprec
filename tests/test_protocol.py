"""Protocol integrity: metadata-bound CRC, truncate, encode/decode."""

from __future__ import annotations

import pytest

from esprec.pixels import solid_rgb565_spi_be
from esprec.protocol import (
    PACK_SPI_BE,
    ProtocolError,
    build_esprec1_frame,
    crc_esprec1,
    crc_pixels_only,
    decode_b64_payload,
    encode_b64_lines,
    parse_header_line,
    verify_and_extract,
)


def test_esprec1_roundtrip_header_and_crc():
    w, h = 8, 4
    raster = solid_rgb565_spi_be(w, h, 255, 0, 0)
    header, b64s, end = build_esprec1_frame(w, h, raster)
    meta = parse_header_line(header)
    assert meta.version == "esprec1"
    assert meta.w == w and meta.h == h
    raw = decode_b64_payload(b64s)
    out = verify_and_extract(meta, raw)
    assert out == raster
    assert end.startswith("ESPREC1_END")


def test_truncated_payload_fails_closed():
    w, h = 8, 4
    raster = solid_rgb565_spi_be(w, h, 0, 255, 0)
    header, _, _ = build_esprec1_frame(w, h, raster)
    meta = parse_header_line(header)
    with pytest.raises(ProtocolError, match="truncated"):
        verify_and_extract(meta, raster[:10])


def test_metadata_tamper_fails_even_if_pixels_crc_would_pass():
    """Normative 6.1: integrity covers metadata + raster.

    Flipping w/h with same pixel count keeps pixels-only CRC identical
    but must fail ESPREC1 meta+raster CRC.
    """
    w, h = 16, 8  # same nbytes as 8x16
    raster = solid_rgb565_spi_be(w, h, 10, 20, 30)
    true_crc = crc_esprec1(w, h, "rgb565be", PACK_SPI_BE, len(raster), raster)
    pixels_crc = crc_pixels_only(raster)

    # Attacker swaps w/h but keeps pixels-only CRC in header (old bug class).
    bad_header = (
        f"ESPREC1 w={h} h={w} fmt=rgb565be pack={PACK_SPI_BE} enc=b64 "
        f"nbytes={len(raster)} crc=0x{pixels_crc:08x}"
    )
    meta = parse_header_line(bad_header)
    with pytest.raises(ProtocolError, match="integrity fail"):
        verify_and_extract(meta, raster)

    # Correct meta CRC accepts.
    good = parse_header_line(
        f"ESPREC1 w={w} h={h} fmt=rgb565be pack={PACK_SPI_BE} enc=b64 "
        f"nbytes={len(raster)} crc=0x{true_crc:08x}"
    )
    assert verify_and_extract(good, raster) == raster


def test_legacy_shot_pixels_crc():
    w, h = 4, 4
    raster = solid_rgb565_spi_be(w, h, 1, 2, 3)
    crc = crc_pixels_only(raster)
    header = (
        f"SHOT w={w} h={h} fmt=rgb565be enc=b64 nbytes={len(raster)} "
        f"crc=0x{crc:08x}"
    )
    meta = parse_header_line(header)
    assert meta.version == "shot"
    assert verify_and_extract(meta, raster) == raster


def test_legacy_shot_bad_crc_fails():
    w, h = 4, 4
    raster = solid_rgb565_spi_be(w, h, 1, 2, 3)
    header = (
        f"SHOT w={w} h={h} fmt=rgb565be enc=b64 nbytes={len(raster)} "
        f"crc=0xdeadbeef"
    )
    meta = parse_header_line(header)
    with pytest.raises(ProtocolError, match="integrity fail"):
        verify_and_extract(meta, raster)


def test_b64_lines_roundtrip():
    data = bytes(range(256)) * 3
    lines = encode_b64_lines(data, cols=76)
    assert all(len(x) <= 76 for x in lines)
    assert decode_b64_payload(lines) == data
