# esprec

**ESP32 screen capture for agents** — the [tuirec](https://github.com/tui-cs/tuirec) *analogue* for devices with displays (mission kinship, not a port of tuirec’s pipeline).

On command, product firmware emits a full-frame shadow over USB serial (text-safe base64). The **host** post-processes frames into **PNG** (still) or **GIF** (keyframe or continuous sequence). Primary audience: **AI agents** working on [Silico](https://github.com/tig/silico) GCUs.

## Status

Implemented host CLI + protocol + ESP-IDF component + unit gate. Specs under [`specs/`](specs/).

## Install (host)

```text
python -m pip install -e ".[dev]"
esprec agent-guide
esprec snapshot --fake -o face.png    # offline
esprec snapshot --port COMx -o face.png
esprec record --port COMx --frames 5 --hz 2 -o clip.gif
```

**Named unit gate:**

```text
python -m pytest -q
```

## Wire (ESPREC1)

```text
Host →  esprec shot\n   (alias: shot\n)
Dev  →  ESPREC1 w=… h=… fmt=rgb565be pack=spi_be enc=b64 nbytes=N crc=0x…
Dev  →  base64 lines (76 cols)
Dev  →  ESPREC1_END crc=0x…
```

CRC32 covers **canonical metadata + raster** (fails closed on truncate or metadata tamper). Legacy `SHOT` (pixels-only CRC) is still accepted for older firmware.

## On-device component

```text
component/esprec/   # idf_component_register; include esprec.h
esprec_emit_rgb565_spi_be(shadow, w, h);
```

Products maintain a full-frame **shadow** (panel GRAM readback not required). See `specs/spec.md`.

## Silico

PNG/GIF is **agent evidence**. Operator **product face** confirm remains required for first-ship metal. Do not redefine GCU `sim/` as QEMU. Detail: silico `knowledge/esprec.md`.

## License

Apache-2.0 (aligned with silico).
