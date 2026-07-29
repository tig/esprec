# Metal capture examples (Xuss-C)

Unlabeled acceptance stills and **realtime rec/spool** GIFs from a real M5GO-class board.

**Re-record scripts** live under [`scripts/`](../../scripts/) in this repo (not on xuss-c clean-start `main`). They are **Xuss-C product scenarios** (btn inject + settle + snap) using the public esprec API only.

```text
# from esprec checkout (metal M5GO running Xuss-C firmware that answers shot/btn)
pip install -e ".[dev]"

# keyframe stills + xuss-c-screens.gif (product pixels)
python scripts/xuss_c_screen_scenario.py --port COMx -o docs/examples

# same stills + scenario.gif with captions *above* the panel
python scripts/xuss_c_screen_scenario.py --port COMx -o docs/examples --gif-captions

# living face only (device rec → spool, realtime delays)
esprec spool --port COMx --duration 3 --hz 5 -o docs/examples/xuss-c-living-realtime.gif

# full demo (living spool + theme/Details/play keyframes → demo GIFs)
python scripts/xuss_c_demo_record.py --port COMx -o docs/examples --captions

# host-paced capture rate bench (why keyframe delays, not high fps)
python scripts/xuss_c_bench_capture_rate.py --port COMx
```

Upscale native 80×60 living GIF for README readability with any NN resize (e.g. Pillow) → `xuss-c-living-realtime-320.gif`.

## Keyframe stills (full 320×240 shot)

| File | Content |
|------|---------|
| `01_idle_blue.png` | Idle face, scrolling banner, button hints |
| `02_theme_orange.png` | Theme after Button A |
| `02b_theme_red.png` | Next theme |
| `03_details.png` | Details + `fw_name=XUSSC fw_version=0.0.1` |
| `xuss-c-screens.gif` | Keyframe loop of the four stills |
| `scenario.gif` | Same stills with optional captions **above** the panel |

## Continuous living face (rec → spool, ~5 Hz)

Judge motion from the **GIF**, not stills — quarter-res frames of a slowly scrolling banner look nearly identical one-by-one.

| File | Content |
|------|---------|
| `xuss-c-living-realtime.gif` | Native 80×60 store (device sample rate) |
| `xuss-c-living-realtime-320.gif` | Same frames, NN-upscaled to 320×240 for README |

Do not draw host captions over y=0..17 of the panel (hair / Details identity).
Use `esprec.image_out.caption_above` for narrative overlays **above** the panel only.
