"""Pixel decode + host PNG/GIF post-process on real shipped helpers."""

from __future__ import annotations

from pathlib import Path

from esprec.image_out import save_gif, save_png
from esprec.pixels import raster_to_image, rgb565_spi_be_to_rgb, solid_rgb565_spi_be
from esprec.protocol import PACK_SPI_BE


def test_solid_blue_decodes_to_blueish(tmp_path: Path):
    w, h = 20, 10
    raster = solid_rgb565_spi_be(w, h, 0, 0, 255)
    img = rgb565_spi_be_to_rgb(raster, w, h)
    assert img.size == (w, h)
    r, g, b = img.getpixel((0, 0))
    assert b > 200 and r < 40 and g < 40
    p = save_png(img, tmp_path / "blue.png")
    assert p.is_file() and p.stat().st_size > 50


def test_gif_multi_frame(tmp_path: Path):
    frames = []
    for color in [(255, 0, 0), (0, 255, 0), (0, 0, 255)]:
        raster = solid_rgb565_spi_be(8, 8, *color)
        frames.append(
            raster_to_image(raster, 8, 8, "rgb565be", PACK_SPI_BE)
        )
    gif = save_gif(frames, tmp_path / "clip.gif", duration_ms=100)
    assert gif.is_file() and gif.stat().st_size > 100
