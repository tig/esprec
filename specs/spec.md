# esprec — requirements

**Rev 0.4 · July 2026**

**esprec** is the [tuirec](https://github.com/tui-cs/tuirec) *analogue* for **ESP32-class devices with screens** — same job (agent eyes on a UI), **not** a port of tuirec’s architecture or CLI model. It lets hosts — especially AI agents working on [Silico](https://github.com/tig/silico) GCUs — **see what is on the device display** without a camera pointed at the panel.

This document is the **product-level** requirements contract: mission, shape of the system, what must work, and what is explicitly out of scope. It is not an implementation plan, protocol design, or code layout.

**CI is mandatory.** Continuous integration follows Silico’s host-first / named-gate model: unit tests first, then validation on ESP binaries under QEMU via [tobozo/esp32-qemu-sim](https://github.com/tobozo/esp32-qemu-sim). Normative CI detail: **[specs/ci.md](ci.md)**.

---

## 1. Mission

When an agent (or human) is developing, testing, or documenting firmware for a screened ESP32 product, esprec should:

1. **Capture** the current on-device UI (framebuffer / UI tree snapshot) **on command**.
2. **Transmit** that capture to the host over the same USB serial path already used for logs and deploy.
3. **Materialize** captures as **PNG** (still) or **GIF** (short sequence), as the operator chooses.
4. Prefer **agent-first** UX: stable, scriptable CLI; discoverable usage; reliable failures — same posture as tuirec.

A codebase change that only “looks right in source” is not good enough for UI work. Agents must be able to **look at the device face** the way tuirec lets them look at a TUI.

---

## 2. Relationship to tuirec and Silico

| | **tuirec** | **esprec** |
|--|------------|------------|
| Domain | Terminal apps on the host (PTY) | ESP32 (and class) devices with displays |
| What is captured | Terminal session → cast → image | Device screen → pixels → image |
| Where images are made | Host (agg from cast) | **Host only** (post-process from frame bytes) |
| Primary customer | Agents producing demo/regression visuals | Agents (and CI) that need eyes on metal UI |
| Typical companion | Terminal.Gui / any TUI | Silico GCUs, LVGL or custom UI firmware |

**Kinship, not slavery.** esprec shares tuirec’s *mission* (agents need eyes; scriptable; stable failures) and some *UX posture* (agent-guide, exit codes). It must **not** copy tuirec’s pipeline shape (PTY, asciinema cast, agg, keystroke scripts) or treat tuirec’s feature set as a ceiling. Metal has no terminal cast; the unit of work is **framebuffer frames**. Design for that domain.

esprec is **tooling**, not a GCU product. Product firmware **embeds or links** the on-device half; the host half is a standalone CLI (or library) agents invoke.

### 2.1 Silico CI and “done” (adopt, do not reinvent)

esprec **must** leverage the CI / proof model Silico dictates for host-side honesty:

- **Host-first** — automated gates on the host (and host runners) are how “done” is claimed; metal confirms.
- **Named host gate** — a clear command/job set that must be green; desk folklore is not a gate.
- **CI on push/PR** — default branch and pull requests run those gates.
- **No metal required on cloud CI** — physical boards are optional/local confirmation.
- **Sim before metal** — for ESP firmware, sim means **QEMU runners** ([tobozo/esp32-qemu-sim](https://github.com/tobozo/esp32-qemu-sim)), not only pure host doubles.

Full ladder and job requirements: **[specs/ci.md](ci.md)**.

---

## 3. System shape

Two cooperating parts:

### 3.1 On-device (firmware, C) — capture and transmit only

- Lives as an **integrable component** in product firmware (ESP-IDF-oriented).
- On host command, **captures** the current display content and **sends frame bytes** over serial.
- Must not permanently steal the display pipeline; after capture/transmit, the product UI continues normally.
- Must coexist with normal serial logging (captures are structured so the host can recover them amid log noise).
- **Does not encode GIF** (and need not encode PNG). Metal is eyes + serial pipe, not a media encoder. On-device image containers are neither required nor desired for v1.

### 3.2 Host (CLI / agent tool) — receive and post-process

- Opens the device serial port, requests capture(s), receives frame data.
- **PNG and GIF are host-side post-processing** of received frames (encode happens on the host after frames arrive, not on the GCU).
- Discoverable by agents (`agent-guide`-class help, machine-readable command surface, short project summary for LLMs).
- Usable without a full IDE; one-shot commands preferred.

```text
  device UI ──► capture pixels ──► USB serial ──► host frames ──► PNG and/or GIF (post-process)
```

---

## 4. Capture sources

### 4.1 Raw framebuffer (required)

Products that own a panel buffer (or can expose one) register that buffer (or a copy callback). esprec transmits pixels in a documented host-understandable format (e.g. RGB565 / RGB888 class formats common on ESP LCDs).

**Shadow buffer is first-class.** Many products blit strips or partial regions to the panel and never keep a full resident frame. esprec must support products that maintain (or snapshot into) a **full-frame shadow** that matches what was last painted, not only “read the glass back.” Panel GRAM readback is optional and unreliable on many SPI IPS parts; do not require it for v1.

### 4.2 LVGL snapshot (optional, first-class)

When the product UI is **LVGL**, esprec **must** offer a path that uses LVGL’s snapshot APIs (`lv_snapshot_take`, `lv_snapshot_take_to_buf`, and equivalents across supported LVGL majors) so the capture matches what LVGL is drawing — not a half-flushed panel mid-blit.

Choosing raw vs LVGL is an **explicit** product integration choice, not a silent guess.

---

## 5. Capture modes and host outputs

### 5.1 Still

| Mode | Output | Intent |
|------|--------|--------|
| **Snapshot** | Single **PNG** (host-encoded) | “What is on screen right now?” — agent verification, docs stills |

### 5.2 Sequence → GIF (host post-process)

GIF is **not** a device feature. The host collects an ordered sequence of frames (with timestamps or fixed delays as appropriate), then **assembles/encodes a GIF** as a post-processing step.

Two first-class sequence styles (both valid; agent chooses by intent):

| Style | How frames are taken | What the GIF feels like |
|-------|----------------------|-------------------------|
| **Keyframe / step** | Snapshots only at **specific steps** (after settle, after agent action, at script markers) | **Timelapse** of states — boot → theme → details → play; each frame is a settled UI |
| **Session / continuous** | Capture at **N frames per second** (or equivalent pace) for a duration / until stop | **Movie-like** session — boot animation, scroll, live update; motion is the story |

Requirements:

1. **Keyframe sequences** must be expressible without faking continuous capture (explicit multi-snapshot or “capture now” under host control).
2. **Continuous sequences** must support a user/agent-chosen rate (fps or interval), duration and/or max-frames caps.
3. Host **GIF encode** runs after (or as) frames are in hand — never as a required on-metal step.
4. Defaults stay boring and safe (finite duration / frame cap so a stuck stream cannot fill the disk).
5. Optional intermediate artifacts (raw frames, PNG per frame) are allowed; GIF is the common agent-facing animation deliverable.
6. Host may **annotate** keyframes (captions) when assembling a GIF for agent narratives; annotation is host-side polish, not a device feature.

tuirec’s “one cast → one agg GIF” model is **not** normative here. esprec’s natural unit is a **list of pixel frames** that the host may still, timelapse, or movie-ize.

### 5.3 When to prefer which style

- Prefer **keyframe / step** when the story is a sequence of *states* (theme change, open Details, play/pause) and each state must be readable.
- Prefer **session / continuous** when *motion itself* is the story (banner scroll, animation, live sensor numbers).
- After every product action (button, command, deploy settle), **wait for the UI to settle** before the next snapshot. Snapping mid-repaint invents false bugs.

---

## 6. Transport integrity (normative)

USB serial is a **shared, often cooked** channel (logs, identity, deploy chatter). Field capture work showed that naive binary dumps invent product “bugs” that never appear on the glass: solid false color bands, off-center chrome, missing glyphs. Specs must not allow those failure modes to be silent.

### 6.1 Requirements

1. **Text-safe payload on cooked consoles** — Frame bytes must not rely on a raw binary stream that line-ending conversion or log interleaving can corrupt. A text-safe encoding of the raster (e.g. base64 with a clear header) is acceptable and preferred for v1 over bare RGB565 on stdout.
2. **Structured header** — Before payload: at least width, height, pixel format, payload byte length (decoded size), and a checksum/CRC of the decoded raster. Host must fail closed if length or checksum fails.
3. **Recoverable amid logs** — Captures are delimited so the host can resync if ESP log lines appear around (not preferably inside) a capture. Concurrent log noise during payload emit must be suppressed, or interleaving must be detectable as failure.
4. **Documented pixel packing** — Host decode must use the same packing the producer used (RGB565 endian/swap, RGB888 order, stride). A wrong swap looks like a theme bug; treat that as a protocol/host defect.
5. **Honest timeouts** — Full-panel captures at common baud rates take seconds; defaults and docs must say so.

### 6.2 Pipeline before product

If a PNG/GIF disagrees with what a human sees on the live panel:

1. **Suspect the capture pipeline first**, not the product UI.
2. Keep intermediate artifacts (raw/decoded frame, CRC, serial log).
3. A green CLI exit and a file that “looks like an image” are not enough — validate dimensions, checksum, and that the frame is not a known corruption pattern when possible.

Agents must not rewrite product domain code to “fix” a yellow bar that was really a cooked-serial shift.

---

## 7. Functional requirements

1. **Commanded capture** — Host requests a snapshot or a bounded sequence; device responds with image data (or a clear error).
2. **Serial transport** — USB serial (CDC/UART class) as the v1 path; no requirement for Wi‑Fi/HTTP in v1. Transport must meet §6.
3. **PNG snapshot** — Host produces a valid PNG of the reported dimensions from one frame.
4. **GIF as host post-process** — Host produces a multi-frame GIF from a sequence of frames (keyframe **or** continuous), not from on-device encoding.
5. **Keyframe and continuous modes** — Both §5.2 styles are in scope; agents can choose timelapse vs session movie by how/when frames are requested.
6. **Device identity / capability query** — Host can learn at least: display size, pixel format, capture backend in use, component version.
7. **Agent-operable CLI** — Non-interactive flags; stable exit codes; one-line actionable errors on failure.
8. **Offline host verification** — Host logic must be testable without a physical board (unit tests + host-side fake device / fixtures), including framing/CRC and PNG/GIF encode.
9. **Product integration surface** — Clear, minimal C API / component boundary so a GCU can adopt esprec without rewriting its UI stack (register buffer or snapshot callback; shadow FB path supported).
10. **CI with a Silico-shaped ladder** — See §13 and [ci.md](ci.md): **unit tests first**, then **QEMU validation** with `tobozo/esp32-qemu-sim`; metal optional on CI.

---

## 8. Non-functional requirements

1. **Agent-first, human-second** — Same philosophy as tuirec: scripts and agents are the main users.
2. **Polite guest on-device** — Bounded RAM expectations documented; prefer RGB565-class formats on large panels; no forced exclusive display ownership.
3. **Predictable performance** — Full-panel captures are large; defaults (baud, fps, timeouts) must be honest about that.
4. **Cross-platform host** — Windows, macOS, Linux hosts for the CLI.
5. **No network required** for capture (serial only in v1).
6. **Host-honest CI** — Green CI means named gates passed (unit, then QEMU), not merely “workflow file exists.”
7. **Capture honesty** — Specs, guides, and defaults bias agents toward pipeline-before-product and settle-then-snap (§5.3, §6.2).

---

## 9. Primary users and use cases

1. **Silico / GCU agents** after UI changes: deploy → settle → snapshot → *view the PNG* before claiming the face is correct.
2. **CI** — unit + QEMU gates on every change; optional metal recipes that archive face images when a board is available.
3. **Humans** debugging “what is the device showing?” without external cameras.
4. **Docs** — stills and short GIFs of real metal UI (when the product wants them).
5. **Multi-step demos** — host-orchestrated keyframe GIF (theme → Details → play → pause) with optional frame captions for agent narratives.

---

## 10. Out of scope (v1)

- Touch / button / input injection as an **esprec** feature (esprec is **eyes**, not hands). Host scripts may still drive **product** serial commands (`identity`, product-specific `btn`, etc.) alongside esprec captures; that orchestration is not esprec’s domain.
- Video containers (MP4/WebM), audio (GIF is enough for agent vision demos).
- Cloud upload or hosted streaming service.
- **On-device GIF (or required on-device PNG) encoding** — host post-process only.
- Non-ESP platforms (e.g. RP2040) unless later expanded.
- Replacing product logging or serial consoles.
- Guaranteed high-FPS “desktop remote” quality on large panels (honest caps and timeouts instead).
- Matching tuirec feature-for-feature (keystroke scripts, cast format, agg, etc.).
- Requiring panel GRAM readback as the only capture source.
- Rewriting product UI contracts into agent-optimized token tables so captures pass — capture tooling absorbs pipeline discipline.

---

## 11. Success criteria

esprec is meeting its mission when:

1. A product with the on-device component can answer a host **snapshot** with a PNG that matches the live UI at capture time (geometry and packing correct; not a transport-corrupted impostor).
2. Host can build a **timelapse GIF** from step/keyframe captures and a **session GIF** from continuous N-fps capture — both without encoding on metal.
3. LVGL-based products can opt into snapshot APIs rather than only raw FB.
4. Agents can discover how to run captures without reading source (guide + CLI help), including settle-then-snap and pipeline-before-product.
5. **Unit gate** is green without metal or QEMU (including framing/CRC/decode fixtures that catch cooked-stream class bugs).
6. **QEMU gate** is green on CI via `tobozo/esp32-qemu-sim` + host capture assertions (synthetic FB allowed when panel IP is not emulated).
7. Metal remains confirmation for real panels — not the only proof path.

---

## 12. Open decisions (do not invent in product code yet)

These are deliberately unresolved at requirements level:

- Exact serial framing / versioning scheme (header fields beyond §6.1 minimum; text-safe encoding choice).
- Host implementation language (tuirec is Go; Silico spine is Python — pick later for fit).
- Whether continuous mode is host-paced “poll N times/sec” vs device-paced stream (both can satisfy §5.2).
- Chunking / compression for large panels and low-RAM parts.
- How deeply Silico pins or vendors esprec vs treating it as an external tool.
- Default QEMU chip target and golden-image strictness (see [ci.md](ci.md) §8).
- Whether keyframe mode is pure host orchestration (repeated CAPTURE) or first-class device “mark” support.
- Optional host caption/annotation API for scenario GIFs (v1 may stay “PNG sequence → GIF” only).

---

## 13. CI (summary)

**There must be CI.** Detail: **[specs/ci.md](ci.md)**.

| Stage | What | Silico analogue |
|-------|------|-----------------|
| **Unit** | Host unit/smoke tests; fake device OK; framing/CRC/decode fixtures; no board | Host gate / unit proof |
| **QEMU** | Build example firmware → [tobozo/esp32-qemu-sim](https://github.com/tobozo/esp32-qemu-sim) → host snapshot/record assertions | Sim / host-honest firmware path without metal |
| **Metal** | Optional physical board | Metal confirms |

Order: **unit first**, then **QEMU**. Both required for merge once the QEMU example exists. Cloud CI does not require a serial desk board.

Unit fixtures **should** include at least one case that would fail if the host assumed a raw binary stream without length/CRC (integrity of the protocol decoder), so “file exists” cannot pass for truncated payloads.

---

## 14. Field lessons (informative; inform requirements above)

Drawn from real metal capture work on a Silico C GCU (shadow RGB565 over USB serial, PNG stills, multi-step scenario GIF):

| Lesson | Spec implication |
|--------|------------------|
| Cooked serial line-ending conversion corrupts any `0x0A` in RGB565 and invents solid color bands / off-center UI | §6.1 text-safe payload + header/CRC |
| Concurrent ESP_LOG during dump interleaves garbage into the payload | §6.1 delimit + hush or detect interleaving |
| Agents treated capture artifacts as product face bugs | §6.2 pipeline before product |
| Continuous full-rate capture is expensive at 115200 baud | §5.2 honest caps; keyframe style first-class |
| Multi-step demos (theme → Details → play) need settled snaps, not one noisy movie | §5.2–5.3 keyframe style |
| Host RGB565 endian/swap errors look like wrong themes | §6.1 documented packing |
| esprec should stay eyes-only; product may expose its own inject for demos | §10 hands out of scope |
| Product manuals need not become agent token tables for capture to work | §10 last bullet |

These are not a second architecture. They are why §§5–6 and success criteria require more than “send some pixels.”

---

## Spec map

| Spec | Scope |
|------|--------|
| **[specs/spec.md](spec.md)** (this file) | Product/tool requirements for esprec |
| **[specs/ci.md](ci.md)** | CI ladder: unit → QEMU (`tobozo/esp32-qemu-sim`) → optional metal; Silico-aligned gates |
| *future* protocol | Wire format, pixel formats, errors |
| *future* firmware-api | On-device integration contract |
| *future* host-cli | Flags, exit codes, agent surfaces |
| *future* silico-integration | How GCUs and agents are expected to invoke esprec |

Root-level marketing README and implementation design belong elsewhere; this file (plus [ci.md](ci.md) for CI) is the requirements source of truth until those land.
