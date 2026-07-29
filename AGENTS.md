# AGENTS.md — how to use esprec

Canonical playbook for AI coding agents (Claude Code, Grok Build, Copilot, Codex, and kin) when the human says **use tig/esprec** or pastes a [README Getting Started](README.md) prompt.

Human overview: [README.md](README.md). Product requirements: [specs/spec.md](specs/spec.md). CI ladder: [specs/ci.md](specs/ci.md). Short CLI dump: `esprec agent-guide`.

**esprec is eyes, not hands.** Capture device pixels over USB serial → host PNG/GIF. Product serial commands (`btn`, `identity`, deploy) stay in the product / Silico path. Do not invent a private capture stack when this tool covers the wire.

---

## 0. Load path (do this first)

| Priority | Open | When |
|----------|------|------|
| 1 | **This file** (`AGENTS.md`) | Any “use esprec” / screenshot / golden / mockup-vs-device task |
| 2 | `esprec agent-guide` | Need flag surface only |
| 3 | [specs/spec.md](specs/spec.md) / [specs/ci.md](specs/ci.md) | Changing protocol, component, or CI shape |
| — | Product GCU `AGENTS.md` / Silico first-ship | Deploy, identity, board COM — not capture wire format |

If you only skimmed the README examples, you have not followed this playbook.

---

## 1. Mission in one line

```text
device UI → full-frame shadow → USB serial (ESPREC1 + base64) → host PNG and/or GIF
```

- **On-device:** `component/esprec` emits frames; does **not** encode PNG/GIF.
- **Host:** this package’s CLI/library receives frames and post-processes images.
- **Integrity:** ESPREC1 CRC covers **metadata + raster**. Truncation, wrong length, or header tamper **fail closed** — never silent “valid” junk images.

---

## 2. Install (host)

Python **≥ 3.11**. Prefer a **sibling clone** next to the product GCU:

```text
# layout: .../tig/esprec  and  .../tig/<gcu>
python -m pip install -e "../esprec[dev]"   # from GCU repo
# or from this checkout:
python -m pip install -e ".[dev]"
esprec agent-guide
esprec snapshot --fake -o face.png          # offline smoke (no board)
```

From git without a sibling tree:

```text
python -m pip install "git+https://github.com/tig/esprec.git"
```

**Unit gate** (esprec repo): `python -m pytest -q`

---

## 3. Prerequisites on the product firmware

Capture only works if the **product image** links esprec and answers a shot command. Without that, host CLI cannot invent pixels.

### 3.1 Link the component (ESP-IDF)

```text
# EXTRA_COMPONENT_DIRS → sibling esprec component, or vendor a copy:
#   <esprec>/component/esprec
```

Public C API: [component/esprec/include/esprec.h](component/esprec/include/esprec.h).

### 3.2 Full-frame shadow (required)

Many UIs blit strips and never keep a full resident panel buffer. Maintain (or snapshot into) a **full-frame RGB565 shadow** that matches what was last painted. Panel GRAM readback is optional and often wrong on SPI IPS — do **not** require it.

Packing for the host path in v1: **`fmt=rgb565be` `pack=spi_be`** (same byte order as typical ESP SPI DMA to the panel).

### 3.3 Command handler

On host line `esprec shot` or alias `shot` (CR/LF framed):

1. Hush concurrent `ESP_LOG` on the same console (logs interleave base64 → integrity fail).
2. Call `esprec_emit_rgb565_spi_be(shadow, w, h)` (or the `_bytes` / `_ex` variants).
3. Resume normal UI.

Optional continuous session (living UI / motion demos):

```text
Host:  esprec rec start <hz> <sec> [max_frames]
Dev:   ok rec begin storage=ram|flash ...
       (product samples when esprec_rec_due; esprec_rec_push / _push_scaled)
Host:  esprec rec stop  →  ok rec stop
Host:  esprec spool     →  ESPREC1_REC … frames … ESPREC1_REC_END
```

CLI packages that as: `esprec spool --port COMx --duration 3 --hz 5 -o live.gif`

### 3.4 Product actions (not esprec)

Buttons, navigation, theme toggles, reboot: **product** serial (e.g. `btn a`) or Silico deploy. Keep **one serial session** open for inject + multiple snaps. Reopening with default DTR/RTS can auto-reset ESP and yield black unpainted frames — esprec’s `open_port` deasserts DTR/RTS; do not bypass it with a raw `serial.Serial(port)` open.

---

## 4. Host commands (cheat sheet)

| Intent | Command |
|--------|---------|
| One still PNG | `esprec snapshot --port COMx -o face.png` |
| Offline / CI without board | `esprec snapshot --fake -o face.png` |
| Host-paced multi-frame GIF | `esprec record --port COMx --frames 5 --hz 2 -o clip.gif` |
| Device-paced continuous GIF | `esprec spool --port COMx --duration 3 --hz 5 -o live.gif` |
| Custom device line | `esprec snapshot --port COMx --command shot -o face.png` |
| Guide dump | `esprec agent-guide` |

Defaults worth knowing:

| Flag | Default | Notes |
|------|---------|--------|
| `--baud` | `115200` | Full 320×240 base64 still can take **tens of seconds** |
| `--settle` | `1.0` (snapshot/record) | Wait after open before first command |
| `--timeout` | `90` snapshot; `600` spool | Raise for large panels / slow baud |
| `--command` | `esprec shot` | Product may only implement `shot` |

Library (prefer for multi-step scripts — one open port):

```python
from esprec.serial_port import open_port
from esprec.capture import snapshot, capture_image, spool_to_gif
from esprec.image_out import caption_above, save_png, save_gif

ser = open_port("COM7")  # DTR/RTS safe
try:
    snapshot(ser, "face.png", command="shot", settle_s=1.0, timeout_s=90.0)
finally:
    ser.close()
```

**Captions:** only via `caption_above` / `--caption-prefix` — bar is **above** the panel, never over product chrome (hair banner / Details identity rows).

---

## 5. Hard rules (always)

1. **Pipeline before product** — If the PNG disagrees with the live glass (solid false color bands, off-center chrome, wrong theme that looks like endian swap), fix **capture** first (CRC, packing, cooked serial, log interleave, settle). Do not rewrite product domain code to “fix” a transport artifact.
2. **Settle then snap** — After boot, deploy, or every product action, wait for the UI to finish painting before capture. Mid-repaint snaps invent false bugs.
3. **Read the PNG** — A green exit code is not proof. Open the image (vision) and check dimensions / content against intent.
4. **Fail closed** — Integrity errors mean stop and diagnose, not “try a softer decoder.”
5. **esprec is not hands** — No touch/button injection in this package. Drive the product separately.
6. **Operator product face** (Silico first ship) — Agent PNG is evidence; it does **not** replace asking the human to confirm the real panel on first ship.
7. **Do not force esprec QEMU onto every GCU** — GCU host gate stays pytest/CTest + plate CI. esprec’s own QEMU ladder proves *esprec’s* path ([specs/ci.md](specs/ci.md)).

---

## 6. Getting Started playbooks

These map 1:1 to the README prompts. Follow the matching section end-to-end.

### 6.1 One-time capture → README hero image

> *"Use tig/esprec to capture an image of my device after boot and add it to my repos README.md as a hero image."*

**Goal:** One honest product still in the product repo README after a real boot.

```text
# A. Install host tool
python -m pip install -e "../esprec[dev]"   # or git+ URL

# B. Confirm firmware answers shot (component linked + shadow + handler)
#    Deploy product image if needed (silico deploy / idf.py flash) — product path.

# C. Wait for boot UI to settle (boot riff, splash, first idle frame)
#    Typical: 3–6 s after reset; product-specific. Prefer soft-reset only if deploy left the app parked.

# D. Capture (metal)
esprec snapshot --port COMx --command shot --settle 2 -o docs/hero.png
#    If product only implements bare "shot": --command shot  (default is "esprec shot")

# E. Verify: open docs/hero.png — correct WxH, not solid black, not corrupt bands.
#    On fail: pipeline first (see §5, §8).

# F. README — add near the top, after title/blurb:
```

```markdown
![Product face](docs/hero.png)
```

**Acceptance for the agent:**

- [ ] `esprec snapshot` exited 0 and printed `OK wrote … WxH … crc=0x…`
- [ ] PNG is non-empty, correct dimensions for the panel
- [ ] README references the path; image is committed if the product wants docs stills (else keep under a gitignored evidence path and say so)
- [ ] You did **not** claim first-ship metal acceptance without operator confirm when that Silico rule applies

**Port discovery:** product/`silico inspect`, OS device manager, or operator-provided `COMx` / `/dev/tty.*`. Do not hardcode a port you have not verified.

---

### 6.2 Goldens + CI that fails on visual regression (QEMU / host)

> *"Use tig/esprec to create goldens of feature x, y, and z. Then build tests that run as part of CI that fail if the firmware running on qemu ever deviates from the goldens."*

**Goal:** Named, host-honest tests: capture (or fixture) vs golden PNGs; red CI on deviation.

#### Step 1 — Define features as settled screens

Each golden is a **settled UI state**, not a random mid-animation frame:

| Golden id | How to reach | Capture |
|-----------|--------------|---------|
| `feature_x` | boot → idle (or product cmd) | `esprec snapshot … -o tests/goldens/feature_x.png` |
| `feature_y` | product action / inject | same, after settle |
| `feature_z` | … | … |

Prefer **deterministic** UI for goldens: fixed theme, no live clock in the compared region, or mask dynamic regions (see compare helper below).

#### Step 2 — Create goldens (author once, commit)

**Metal (honest product face):**

```text
# After each feature is on screen and settled:
esprec snapshot --port COMx --command shot --settle 1.5 -o tests/goldens/feature_x.png
```

**Or synthetic / QEMU path:** firmware draws a **known software framebuffer** (test pattern or LVGL fixture) so cloud runners need no desk panel. Real color/timing still confirmed on metal when claiming panel fidelity ([specs/ci.md](specs/ci.md) §5).

Commit goldens under e.g. `tests/goldens/` with a short README of how they were produced (port, firmware rev, command sequence).

#### Step 3 — Compare helper (product test code)

esprec does not ship a golden CLI; use Pillow in the **product** (or esprec) test suite:

```python
from pathlib import Path
from PIL import Image, ImageChops

def assert_png_matches_golden(
    actual: Path,
    golden: Path,
    *,
    max_rms: float = 2.0,
    mask: Image.Image | None = None,
) -> None:
    """Fail if actual drifts from golden. mask: L image, 0 = ignore pixel."""
    a = Image.open(actual).convert("RGB")
    g = Image.open(golden).convert("RGB")
    assert a.size == g.size, f"size {a.size} != golden {g.size}"
    if mask is not None:
        # paint ignored regions identical so RMS ignores them
        a = a.copy()
        g = g.copy()
        inv = mask.point(lambda p: 255 if p == 0 else 0)
        a.paste(g, mask=inv)
    diff = ImageChops.difference(a, g)
    # RMS over RGB
    hist = diff.histogram()
    sq = sum(value * (i % 256) ** 2 for i, value in enumerate(hist))
    rms = (sq / (float(a.size[0] * a.size[1]) * 3)) ** 0.5
    assert rms <= max_rms, f"RMS {rms:.3f} > {max_rms} ({actual} vs {golden})"
```

Tune `max_rms`: `0` = pixel-exact; small epsilon if encoder/path noise exists (PNG from the same host path should be exact for identical rasters).

#### Step 4 — Tests that produce actuals then compare

**Host-only / fake device** (always on CI — proves compare wiring):

```text
esprec snapshot --fake -o /tmp/actual.png   # not a product golden; use for pipeline smoke
```

**Product capture tests** (QEMU serial or metal harness):

```python
def test_feature_x_matches_golden(tmp_path):
    # 1) Ensure firmware under test is running (QEMU job, or skip if no serial).
    # 2) Drive UI to feature x (product commands).
    # 3) Capture:
    #    esprec snapshot --port <qemu-or-metal> --command shot -o tmp_path/"feature_x.png"
    # 4) assert_png_matches_golden(tmp_path/"feature_x.png", GOLDENS/"feature_x.png")
    ...
```

Wire into **named gates**:

| Gate | What runs | Cloud default |
|------|-----------|---------------|
| **unit** | Protocol/fake capture + golden compare against fixtures or recorded PNGs | **required** |
| **qemu** | Build firmware → [tobozo/esp32-qemu-sim](https://github.com/tobozo/esp32-qemu-sim) → host snapshot → golden assert | **required for capture-path claims** once example exists; synthetic FB OK |
| **metal** | Real board recipe | optional on cloud; local confirm |

Product GCU CI should keep its existing host gate; **add** esprec golden steps only when the product chooses visual regression. Do not replace Silico `silico gate` with “we snapped once on a desk.”

#### Step 5 — CI workflow shape

```yaml
# sketch — product or esprec repo
- run: python -m pip install -e ".[dev]"   # or path to esprec
- run: python -m pytest -q tests/test_goldens.py
# qemu job (when firmware example exists):
# - build merged flash image
# - tobozo/esp32-qemu-sim
# - esprec snapshot against exposed serial
# - compare to tests/goldens/*
# - upload actual PNGs on failure
```

**Acceptance for the agent:**

- [ ] Goldens for x, y, z exist and are documented
- [ ] Automated test fails if actual PNG RMS (or pixel equal) exceeds threshold
- [ ] CI runs the test on push/PR (host unit at minimum; QEMU when claiming firmware path without metal)
- [ ] Failure artifacts include the actual PNG (and serial log when possible)
- [ ] Dynamic UI regions are masked or frozen — flaky goldens are not “done”

---

### 6.3 Iterative UX: HTML mockup → LVGL (or custom) on device / QEMU

> *"./mockup.html is an html mockup of the UI I want on my device. Build this UI using LVGL for real on the device [or qemu]. Use tig/esprec to capture each screen as you build it, and iteratively refine until the real device UI matches the html mockup."*

**Goal:** Closed loop — mockup is the visual contract; esprec is how you see the device; iterate until they match.

#### Phase A — Inventory the mockup

1. Open `mockup.html` (and linked CSS/assets).
2. List **screens / states** (idle, settings, details, …), approximate layout, colors, typography, interactive elements.
3. Note panel size of the target (e.g. 320×240 M5GO). Scale mockup expectations to that resolution — do not expect desktop browser chrome on a 2" panel.

#### Phase B — Firmware integration checklist

- [ ] esprec component linked (§3)
- [ ] Shadow (or LVGL snapshot → RGB565 buffer) on every full paint
- [ ] `shot` / `esprec shot` works: `esprec snapshot --fake` on host, then metal/QEMU
- [ ] LVGL: prefer snapshot APIs (`lv_snapshot_take` / `take_to_buf`) so capture matches what LVGL draws, not a half-flushed partial blit — when the product opts into that path

#### Phase C — Build one screen at a time

For **each** screen in the inventory:

```text
1. Implement the screen in LVGL (or custom UI) for real.
2. Deploy (metal or QEMU firmware path).
3. Navigate to that screen (product inject / boot default).
4. Settle (animation done, no partial redraw).
5. Capture:
   esprec snapshot --port COMx --command shot --settle 1.0 \
     -o captures/screen_<name>.png
6. Open captures/screen_<name>.png AND the mockup side-by-side (vision).
7. Diff list: spacing, color tokens, font size, missing widgets, overflow.
8. Fix firmware (or mockup if mockup is wrong for the panel) — not the capture packing
   unless the PNG is a known corruption pattern (§5 pipeline first).
9. Re-capture until agent + you would accept visual parity for that screen.
10. Optionally promote the PNG to tests/goldens/screen_<name>.png (§6.2).
```

**Keyframe storyboard** when several screens exist:

```python
# one serial session
from esprec.serial_port import open_port
from esprec.capture import capture_image
from esprec.image_out import save_png, save_gif, caption_above

ser = open_port("COM7")
frames = []
try:
    for name, setup in steps:  # setup = product cmds + sleep settle
        setup(ser)
        meta, img = capture_image(ser, command="shot", timeout_s=90.0)
        save_png(img, f"captures/{name}.png")
        frames.append(caption_above(img, name))  # optional narrative bar above panel
    save_gif(frames, "captures/storyboard.gif", duration_ms=1000)
finally:
    ser.close()
```

#### Phase D — “Matches the mockup” bar

| Check | Pass |
|-------|------|
| Layout regions | Primary widgets in the same zones as mockup (within panel limits) |
| Color roles | Theme tokens match (bg, accent, text) — allow hardware gamut variance on metal |
| Copy | Labels match mockup strings (or agreed product strings) |
| No transport junk | No false bands / shifted chrome (pipeline) |
| Goldens (optional) | §6.2 tests green for each accepted screen |

Do **not** claim match from source inspection alone. **Capture is mandatory** each iteration.

#### Phase E — QEMU vs metal

| Target | Use when | Limitation |
|--------|----------|------------|
| **QEMU** | Fast loop, no board; CI visual gate with synthetic FB | May not emulate real panel IP — use software framebuffer / LVGL buffer export into esprec |
| **Metal** | Color, timing, PSRAM, real product face | Operator confirm still for first ship |

---

## 7. Serial and performance notes

| Topic | Guidance |
|-------|----------|
| Baud | 115200 default; full-panel base64 is slow — budget **~15–30 s** for 320×240 stills |
| Continuous full-rate | Prefer **keyframe** stills for state stories; use `spool` at modest Hz (e.g. 5) and often **quarter-res** rec (`esprec_rec_push_scaled`) so SPIFFS/RAM keeps up |
| One session | Open once; many `capture_image` / product cmds; then close |
| Auto-reset | Always `esprec.serial_port.open_port` or CLI (DTR/RTS low) |
| Logs during emit | Device must hush logs or host integrity fails |
| Windows ports | `COM7` form; macOS/Linux `/dev/tty.usbserial-*` / `/dev/ttyACM*` |

---

## 8. Diagnosis (pipeline first)

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| Solid color bands / shifted UI | Cooked serial / binary on text console | Confirm ESPREC1 + base64 path; not raw RGB565 dump |
| Integrity fail / CRC mismatch | Log interleave, truncate, wrong emit | Hush logs; raise timeout; check full frame length |
| Wrong colors / “theme bug” | RGB565 endian/pack mismatch | Host expects `rgb565be` + `spi_be`; fix emit packing |
| Black / unpainted frame | Snap too early after reset or DTR reboot | Longer settle; do not re-open serial with DTR high |
| Timeout | Large frame @ low baud | Raise `--timeout`; check device actually handles `shot` |
| CLI exit 2 | Missing `--port` (and not `--fake`) | Pass port or use `--fake` offline |

Keep intermediate artifacts (PNG, serial log, CRC lines) when debugging.

---

## 9. Repository map

| Path | Role |
|------|------|
| `esprec/` | Host library + CLI |
| `component/esprec/` | On-device ESP-IDF component |
| `tests/` | Host unit gate (protocol, PNG/GIF, fake device, spool) |
| `specs/spec.md` | Product requirements |
| `specs/ci.md` | Unit → QEMU → optional metal |
| `docs/examples/` | Real metal stills/GIFs (xuss-c demo) |
| `examples/synthetic_host/` | Host-buildable C emit for CRC parity |

Reference product scenarios (Xuss-C heroes): `scripts/xuss_c_*.py` + [docs/examples/](docs/examples/). Product firmware stays in [tig/xuss-c](https://github.com/tig/xuss-c) (clean-start main is docs-only).

---

## 10. What not to do

- Invent a camera-on-desk or ad-hoc binary dump when esprec is available.
- Encode GIF/PNG on-device for v1 agent path.
- Treat `--fake` solid-color PNGs as product goldens.
- Draw labels **on** product chrome for “docs” (use `caption_above` only).
- Skip settle after UI actions.
- Claim visual done without opening the captured image.
- Soft-fork protocol in the GCU instead of fixing tig/esprec.
- Force every Silico GCU CI to run esprec QEMU by default.

---

## 11. Quick “done” checklist by prompt

| Prompt | Done means |
|--------|------------|
| **Hero image** | Boot settle → successful snapshot → README embeds verified PNG |
| **Goldens + CI** | Goldens committed → automated compare fails on drift → CI job red on failure (unit ± QEMU) |
| **Mockup loop** | Each mockup screen implemented → captured → visually matched → optional goldens |

When stuck, re-run `esprec agent-guide` and re-read §5–§8 before changing product domain logic.
