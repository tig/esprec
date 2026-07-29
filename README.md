# esprec

**ESP32 screen capture for agents** — For devices with displays. On command, product firmware emits a full-frame shadow over USB serial (text-safe base64). The **host** post-processes frames into **PNG** (still) or **GIF** (keyframe or continuous sequence). Primary audience: **AI agents** working on [Silico](https://github.com/tig/silico) GCUs.

**esprec** is the ESP32 equivalent of my popular [tuirec](https://github.com/tui-cs/tuirec) which does the same thing for terminal user interfaces.

## Getting Started

Simply tell your coding agent:

### One time capture

> "Use tig/esprec to capture an image of my device after boot and add it to my repos README.md as a hero image."

### Screen validation as part of continuous integration testing

> "Use tig/esprec to create goldens of feature x, y, and z. Then build tests that run as part of CI that fail if the firmware running on qemu ever deviates from the goldens."

### Iterative UX development

> "./mockup.html is an html mockup of the UI I want on my device. Build this UI using LVGL for real on the device [or qemu emulating my device]. Use tig/esprec to capture each screen as you build it, and iteratively refine the code you write until the real device UI matches the html mockup."

## Example

`xuss-c` is an example used to demonstrate [Silico](https://github.com/tig/silico). `xuss-c` is a M5GO device with a 320×240 display. **esprec** captured these over USB with `esprec` + ESPREC1 integrity (not a desk camera). Banner, themes, and Details firmware line are product pixels.

| Idle (blue) | Theme (orange) | Theme (red) | Details |
|-------------|----------------|-------------|---------|
| ![idle blue](docs/examples/01_idle_blue.png) | ![orange](docs/examples/02_theme_orange.png) | ![red](docs/examples/02b_theme_red.png) | ![details](docs/examples/03_details.png) |

**Keyframe sequence** (product stills only):

![xuss-c screens](docs/examples/xuss-c-screens.gif)

**Narrative GIF** (captions padded *above* the panel — never over product chrome):

![scenario](docs/examples/scenario.gif)

### Continuous / realtime session (issue #3)

Device samples the shadow into **RAM if it holds the full session**, else **SPIFFS flash**, without base64 during capture. Host later runs `esprec spool` and builds a GIF with real `ts_ms` delays (~5 Hz living UI on ESP32). Continuous store is quarter-res (80×60) so SPIFFS can keep up; shown below upscaled nearest-neighbor to 320×240 for README readability.

**Living face @ ~5 Hz** (metal, Xuss-C / M5GO — play the GIF; single stills look almost identical at quarter-res):

![living realtime](docs/examples/xuss-c-living-realtime-320.gif)

Native 80×60 stream (same delays): [xuss-c-living-realtime.gif](docs/examples/xuss-c-living-realtime.gif)

```text
esprec spool --port COMx --duration 3 --hz 5 -o docs/examples/xuss-c-living-realtime.gif
# wire: esprec rec start 5 3 [max] → …UI samples… → esprec rec stop → esprec spool
```

Keyframe storyboard re-record (product repo):

```text
# from tig/xuss-c (requires: pip install -e ../esprec)
python tools/demo_record.py --port COMx -o docs/demo --captions
```

Library:

```python
from esprec.serial_port import open_port
from esprec.capture import snapshot, spool_to_gif

ser = open_port("COM7")
try:
    snapshot(ser, "face.png", command="shot", settle_s=1.0)
    spool_to_gif(ser, "live.gif", duration_s=3.0, hz=5.0)
finally:
    ser.close()
```

## Status

Implemented host CLI + ESPREC1 protocol + ESP-IDF component + unit gate. Specs under [`specs/`](specs/).

## How an Agent Installs esprec

```text
python -m pip install -e ".[dev]"
esprec agent-guide
esprec snapshot --fake -o face.png    # offline
esprec snapshot --port COMx -o face.png
esprec record --port COMx --frames 5 --hz 2 -o clip.gif
```

## Wire (ESPREC1)

```text
Host →  esprec shot\n   (alias: shot\n)
Dev  →  ESPREC1 w=… h=… fmt=rgb565be pack=spi_be enc=b64 nbytes=N crc=0x…
Dev  →  base64 lines (76 cols)
Dev  →  ESPREC1_END crc=0x…
```

CRC32 covers **canonical metadata + raster** (fails closed on truncate, **overlong**, metadata tamper, or **missing end delimiter**). Legacy `SHOT` (pixels-only CRC) is still accepted for older firmware.

## On-device component

```text
component/esprec/   # idf_component_register; include esprec.h
esprec_emit_rgb565_spi_be(shadow, w, h);
```

Products maintain a full-frame **shadow** (panel GRAM readback not required). See `specs/spec.md`.
