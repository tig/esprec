# esprec — requirements

**Rev 0.2 · July 2026**

**esprec** is the [tuirec](https://github.com/tui-cs/tuirec) equivalent for **ESP32-class devices with screens**. It lets hosts — especially AI agents working on [Silico](https://github.com/tig/silico) GCUs — **see what is on the device display** without a camera pointed at the panel.

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
| Primary customer | Agents producing demo/regression visuals | Agents (and CI) that need eyes on metal UI |
| Typical companion | Terminal.Gui / any TUI | Silico GCUs, LVGL or custom UI firmware |

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

### 3.1 On-device (firmware, C)

- Lives as an **integrable component** in product firmware (ESP-IDF-oriented).
- On host command, **captures** the current display content and **sends** it over serial.
- Must not permanently steal the display pipeline; after capture/transmit, the product UI continues normally.
- Must coexist with normal serial logging (captures are structured so the host can recover them amid log noise).

### 3.2 Host (CLI / agent tool)

- Opens the device serial port, requests capture(s), receives frame data, writes **PNG** or **GIF**.
- Discoverable by agents (`agent-guide`-class help, machine-readable command surface, short project summary for LLMs).
- Usable without a full IDE; one-shot commands preferred.

```text
  device UI ──► on-device capture ──► USB serial ──► host ──► PNG or GIF
```

---

## 4. Capture sources

### 4.1 Raw framebuffer (required)

Products that own a panel buffer (or can expose one) register that buffer (or a copy callback). esprec transmits pixels in a documented host-understandable format (e.g. RGB565 / RGB888 class formats common on ESP LCDs).

### 4.2 LVGL snapshot (optional, first-class)

When the product UI is **LVGL**, esprec **must** offer a path that uses LVGL’s snapshot APIs (`lv_snapshot_take`, `lv_snapshot_take_to_buf`, and equivalents across supported LVGL majors) so the capture matches what LVGL is drawing — not a half-flushed panel mid-blit.

Choosing raw vs LVGL is an **explicit** product integration choice, not a silent guess.

---

## 5. Host outputs

| Mode | Output | Intent |
|------|--------|--------|
| **Snapshot** | Single **PNG** | “What is on screen right now?” — agent verification, docs stills |
| **Record** | Animated **GIF** | Short sequences (boot, navigation, alarm flash) — demos and multi-step UI checks |

User/agent chooses mode. Defaults should be boring and safe (finite duration / frame cap on record so a stuck stream cannot fill the disk).

---

## 6. Functional requirements

1. **Commanded capture** — Host requests a snapshot or a bounded recording; device responds with image data (or a clear error).
2. **Serial transport** — USB serial (CDC/UART class) as the v1 path; no requirement for Wi‑Fi/HTTP in v1.
3. **PNG snapshot** — Host produces a valid PNG of the reported dimensions.
4. **GIF record** — Host produces a multi-frame GIF from a sequence of captures at a configurable rate/duration/max-frames.
5. **Device identity / capability query** — Host can learn at least: display size, pixel format, capture backend in use, component version.
6. **Agent-operable CLI** — Non-interactive flags; stable exit codes; one-line actionable errors on failure.
7. **Offline host verification** — Host logic must be testable without a physical board (unit tests + host-side fake device / fixtures).
8. **Product integration surface** — Clear, minimal C API / component boundary so a GCU can adopt esprec without rewriting its UI stack.
9. **CI with a Silico-shaped ladder** — See §12 and [ci.md](ci.md): **unit tests first**, then **QEMU validation** with `tobozo/esp32-qemu-sim`; metal optional on CI.

---

## 7. Non-functional requirements

1. **Agent-first, human-second** — Same philosophy as tuirec: scripts and agents are the main users.
2. **Polite guest on-device** — Bounded RAM expectations documented; prefer RGB565-class formats on large panels; no forced exclusive display ownership.
3. **Predictable performance** — Full-panel captures are large; defaults (baud, fps, timeouts) must be honest about that.
4. **Cross-platform host** — Windows, macOS, Linux hosts for the CLI.
5. **No network required** for capture (serial only in v1).
6. **Host-honest CI** — Green CI means named gates passed (unit, then QEMU), not merely “workflow file exists.”

---

## 8. Primary users and use cases

1. **Silico / GCU agents** after UI changes: deploy → snapshot → *view the PNG* before claiming the face is correct.
2. **CI** — unit + QEMU gates on every change; optional metal recipes that archive face images when a board is available.
3. **Humans** debugging “what is the device showing?” without external cameras.
4. **Docs** — stills and short GIFs of real metal UI (when the product wants them).

---

## 9. Out of scope (v1)

- Touch / button / input injection (esprec is **eyes**, not hands).
- Video containers (MP4/WebM), audio.
- Cloud upload or hosted streaming service.
- On-device PNG/GIF encoding as a hard requirement (host may own encoding).
- Non-ESP platforms (e.g. RP2040) unless later expanded.
- Replacing product logging or serial consoles.
- Full remote desktop / continuous high-FPS streaming as a product.

---

## 10. Success criteria

esprec is meeting its mission when:

1. A product with the on-device component can answer a host **snapshot** with a PNG that matches the live UI at capture time.
2. A short **GIF** can be produced on demand for multi-step UI behavior.
3. LVGL-based products can opt into snapshot APIs rather than only raw FB.
4. Agents can discover how to run captures without reading source (guide + CLI help).
5. **Unit gate** is green without metal or QEMU.
6. **QEMU gate** is green on CI via `tobozo/esp32-qemu-sim` + host capture assertions (synthetic FB allowed when panel IP is not emulated).
7. Metal remains confirmation for real panels — not the only proof path.

---

## 11. Open decisions (do not invent in product code yet)

These are deliberately unresolved at requirements level:

- Exact serial framing / versioning scheme.
- Host implementation language (tuirec is Go; Silico spine is Python — pick later for fit).
- Whether record is “N host-paced snapshots” vs “device-paced stream.”
- Chunking / compression for large panels and low-RAM parts.
- How deeply Silico pins or vendors esprec vs treating it as an external tool.
- Default QEMU chip target and golden-image strictness (see [ci.md](ci.md) §8).

---

## 12. CI (summary)

**There must be CI.** Detail: **[specs/ci.md](ci.md)**.

| Stage | What | Silico analogue |
|-------|------|-----------------|
| **Unit** | Host unit/smoke tests; fake device OK; no board | Host gate / unit proof |
| **QEMU** | Build example firmware → [tobozo/esp32-qemu-sim](https://github.com/tobozo/esp32-qemu-sim) → host snapshot/record assertions | Sim / host-honest firmware path without metal |
| **Metal** | Optional physical board | Metal confirms |

Order: **unit first**, then **QEMU**. Both required for merge once the QEMU example exists. Cloud CI does not require a serial desk board.

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
