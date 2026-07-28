"""Wire protocol: text-safe frames with integrity over metadata + raster.

Wire (v1, preferred)::

    Host:  esprec shot\\n   (alias: shot\\n)
    Dev:   ESPREC1 w=W h=H fmt=rgb565be pack=spi_be enc=b64 nbytes=N crc=0xXXXXXXXX
    Dev:   base64 lines (76 cols)
    Dev:   ESPREC1_END crc=0xXXXXXXXX

CRC32 (IEEE / binascii.crc32) is computed over the canonical meta prefix
plus the decoded raster bytes, so flipping width/height or pack while
keeping a pixels-only checksum is rejected.

Legacy SHOT (pixels-only CRC) is still decoded for older firmware; hosts
should prefer ESPREC1.
"""

from __future__ import annotations

import base64
import binascii
import re
from dataclasses import dataclass

ESPREC_HEADER_RE = re.compile(
    r"^ESPREC1\s+w=(?P<w>\d+)\s+h=(?P<h>\d+)\s+fmt=(?P<fmt>\S+)\s+"
    r"pack=(?P<pack>\S+)\s+enc=(?P<enc>\S+)\s+nbytes=(?P<nbytes>\d+)\s+"
    r"crc=(?P<crc>0x[0-9A-Fa-f]+)\s*$"
)

# Legacy xuss-c field protocol (pixels-only CRC).
SHOT_HEADER_RE = re.compile(
    r"^SHOT\s+w=(?P<w>\d+)\s+h=(?P<h>\d+)\s+fmt=(?P<fmt>\S+)\s+"
    r"(?:enc=(?P<enc>\S+)\s+)?"
    r"nbytes=(?P<nbytes>\d+)\s+crc=(?P<crc>0x[0-9A-Fa-f]+)\s*$"
)

B64_LINE_RE = re.compile(r"^[A-Za-z0-9+/=]+$")

# Formats / packs the host understands for RGB565 panel shadows.
FMT_RGB565BE = "rgb565be"
PACK_SPI_BE = "spi_be"  # LE memory words as sent to SPI (byte-swapped logical 565)


class ProtocolError(ValueError):
    """Malformed frame, integrity failure, or unsupported format."""


@dataclass(frozen=True)
class FrameMeta:
    w: int
    h: int
    fmt: str
    pack: str
    enc: str
    nbytes: int
    crc: int
    version: str  # "esprec1" | "shot"


def canonical_meta_prefix(
    w: int, h: int, fmt: str, pack: str, nbytes: int
) -> bytes:
    """Bytes hashed before the raster for ESPREC1 integrity."""
    return f"w={w}|h={h}|fmt={fmt}|pack={pack}|nbytes={nbytes}|".encode("ascii")


def crc_esprec1(
    w: int, h: int, fmt: str, pack: str, nbytes: int, raster: bytes
) -> int:
    prefix = canonical_meta_prefix(w, h, fmt, pack, nbytes)
    return binascii.crc32(prefix + raster) & 0xFFFFFFFF


def crc_pixels_only(raster: bytes) -> int:
    return binascii.crc32(raster) & 0xFFFFFFFF


def format_esprec1_header(
    w: int, h: int, fmt: str, pack: str, enc: str, nbytes: int, crc: int
) -> str:
    return (
        f"ESPREC1 w={w} h={h} fmt={fmt} pack={pack} enc={enc} "
        f"nbytes={nbytes} crc=0x{crc:08x}"
    )


def parse_header_line(text: str) -> FrameMeta:
    text = text.strip()
    m = ESPREC_HEADER_RE.match(text)
    if m:
        d = m.groupdict()
        return FrameMeta(
            w=int(d["w"]),
            h=int(d["h"]),
            fmt=d["fmt"],
            pack=d["pack"],
            enc=d["enc"].lower(),
            nbytes=int(d["nbytes"]),
            crc=int(d["crc"], 16),
            version="esprec1",
        )
    m = SHOT_HEADER_RE.match(text)
    if m:
        d = m.groupdict()
        return FrameMeta(
            w=int(d["w"]),
            h=int(d["h"]),
            fmt=d["fmt"],
            pack=PACK_SPI_BE,  # field default for SHOT
            enc=(d.get("enc") or "raw").lower(),
            nbytes=int(d["nbytes"]),
            crc=int(d["crc"], 16),
            version="shot",
        )
    raise ProtocolError(f"not a frame header: {text[:80]!r}")


def decode_b64_payload(parts: list[str]) -> bytes:
    s = "".join(parts)
    if not s:
        raise ProtocolError("empty base64 payload")
    # Tolerate missing pad
    s += "=" * ((4 - (len(s) % 4)) % 4)
    try:
        return base64.b64decode(s, validate=False)
    except Exception as e:
        raise ProtocolError(f"base64 decode failed: {e}") from e


def verify_and_extract(meta: FrameMeta, raster: bytes) -> bytes:
    """Fail closed on length / integrity; return exact nbytes raster.

    Over-length payloads (extra base64 after the declared raster, e.g. log
    interleaving decoded as more pixels) fail closed — do not silently trim.
    """
    if len(raster) < meta.nbytes:
        raise ProtocolError(
            f"truncated payload: got {len(raster)} want {meta.nbytes}"
        )
    if len(raster) > meta.nbytes:
        raise ProtocolError(
            f"overlong payload: got {len(raster)} want {meta.nbytes} "
            f"(interleave or length mismatch — fail closed)"
        )
    expected = meta.w * meta.h * 2
    if meta.fmt == FMT_RGB565BE and meta.nbytes != expected:
        raise ProtocolError(
            f"nbytes {meta.nbytes} does not match {meta.w}x{meta.h} rgb565 "
            f"(want {expected})"
        )
    if meta.version == "esprec1":
        calc = crc_esprec1(
            meta.w, meta.h, meta.fmt, meta.pack, meta.nbytes, raster
        )
        if calc != meta.crc:
            raise ProtocolError(
                f"integrity fail (meta+raster): header=0x{meta.crc:08x} "
                f"calc=0x{calc:08x}"
            )
    else:
        calc = crc_pixels_only(raster)
        if calc != meta.crc:
            raise ProtocolError(
                f"integrity fail (pixels): header=0x{meta.crc:08x} "
                f"calc=0x{calc:08x}"
            )
    return raster


def encode_b64_lines(data: bytes, cols: int = 76) -> list[str]:
    b64 = base64.b64encode(data).decode("ascii")
    return [b64[i : i + cols] for i in range(0, len(b64), cols)]


def build_esprec1_frame(
    w: int,
    h: int,
    raster: bytes,
    *,
    fmt: str = FMT_RGB565BE,
    pack: str = PACK_SPI_BE,
) -> tuple[str, list[str], str]:
    """Return (header_line, b64_lines, end_line) for a synthetic device."""
    nbytes = len(raster)
    crc = crc_esprec1(w, h, fmt, pack, nbytes, raster)
    header = format_esprec1_header(w, h, fmt, pack, "b64", nbytes, crc)
    end = f"ESPREC1_END crc=0x{crc:08x}"
    return header, encode_b64_lines(raster), end
