# Metal capture examples (Xuss-C)

Unlabeled acceptance stills and **realtime rec/spool** GIFs from a real M5GO-class board.

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

```text
esprec spool --port COMx --duration 3 --hz 5 -o docs/examples/xuss-c-living-realtime.gif
```

Do not draw host captions over y=0..17 of the panel (hair / Details identity).
Use `esprec.image_out.caption_above` for narrative overlays **above** the panel only.
