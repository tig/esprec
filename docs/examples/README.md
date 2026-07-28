# Metal capture examples (Xuss-C)

Unlabeled acceptance stills from a real M5GO-class board (ESP32 / COM USB serial).

| File | Content |
|------|---------|
| `01_idle_blue.png` | Idle face, scrolling banner, button hints |
| `02_theme_orange.png` | Theme after Button A |
| `02b_theme_red.png` | Next theme |
| `03_details.png` | Details + `fw_name=XUSSC fw_version=0.0.1` |
| `xuss-c-screens.gif` | Keyframe loop of the four stills |
| `scenario.gif` | Same stills with optional captions **above** the panel |

Do not draw host captions over y=0..17 of the panel (hair / Details identity).
Use `esprec.image_out.caption_above` or `--gif-captions` on the **xuss-c**
`tools/screen_scenario.py` driver (not an esprec product script).
