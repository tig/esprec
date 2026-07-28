"""Pixel packing helpers (RGB565 panel shadow ↔ RGB for PNG/GIF)."""

from __future__ import annotations

from PIL import Image

from esprec.protocol import PACK_SPI_BE, ProtocolError


def rgb565_spi_be_to_rgb(buf: bytes, w: int, h: int) -> Image.Image:
    """Convert shadow matching ESP SPI RGB565 byte-swapped words to RGB.

    On LE ESP32, each uint16 in the shadow is stored as the same wire order
    sent to the panel (byte-swapped logical 565 with R in high bits of the
    logical word). Same mapping as field-proven xuss-c ``shot.py``.
    """
    need = w * h * 2
    if len(buf) < need:
        raise ProtocolError(f"short frame: got {len(buf)} want {need}")
    out = bytearray(w * h * 3)
    o = 0
    for i in range(0, need, 2):
        wire = buf[i] | (buf[i + 1] << 8)
        # Undo byte-swap → logical 565 (R in high bits).
        pix = ((wire & 0xFF) << 8) | ((wire >> 8) & 0xFF)
        r = (pix >> 11) & 0x1F
        g = (pix >> 5) & 0x3F
        b = pix & 0x1F
        out[o] = (r << 3) | (r >> 2)
        out[o + 1] = (g << 2) | (g >> 4)
        out[o + 2] = (b << 3) | (b >> 2)
        o += 3
    return Image.frombytes("RGB", (w, h), bytes(out))


def raster_to_image(buf: bytes, w: int, h: int, fmt: str, pack: str) -> Image.Image:
    if fmt == "rgb565be" and pack in (PACK_SPI_BE, "spi_be", ""):
        return rgb565_spi_be_to_rgb(buf, w, h)
    raise ProtocolError(f"unsupported fmt/pack {fmt!r}/{pack!r}")


def solid_rgb565_spi_be(w: int, h: int, r: int, g: int, b: int) -> bytes:
    """Build a test pattern: solid color in spi_be packing (for unit tests)."""
    # Logical 565 then byte-swap into LE memory like the panel DMA path.
    r5 = (r >> 3) & 0x1F
    g6 = (g >> 2) & 0x3F
    b5 = (b >> 3) & 0x1F
    logical = (r5 << 11) | (g6 << 5) | b5
    wire = ((logical & 0xFF) << 8) | ((logical >> 8) & 0xFF)
    lo = wire & 0xFF
    hi = (wire >> 8) & 0xFF
    pixel = bytes((lo, hi))
    return pixel * (w * h)
