# esprec — CI requirements

**Rev 0.1 · July 2026**

Continuous integration is **required**, not optional polish. esprec must prove itself the way [Silico](https://github.com/tig/silico) dictates for host-side truth: **named gates**, **host-first**, and **CI that means something** about the firmware path — not “it built on my desk.”

This document is normative for CI shape. Product mission remains in [spec.md](spec.md).

---

## 1. Silico CI doctrine (what we adopt)

Silico’s model, which esprec **must** leverage rather than reinvent:

| Principle | Meaning for esprec |
|-----------|-------------------|
| **Host-first** | Done lives on the host (tests/gates) before anyone treats metal as proof. Metal confirms; metal does not define done. |
| **Named host gate** | One (or a small ordered set of) **named** commands/jobs that must be green. “I flashed a board” is not a gate. |
| **Test-first / host-honest** | Automated unit and smoke expectations exist with the change; green gate is the proof trail. |
| **CI on every push / PR** | Default branch and PRs run the host gate path. |
| **CI has no serial metal by default** | Cloud runners do not assume a physical board. Hardware harness is optional and local (or a future self-hosted metal job). |
| **Sim before metal** | Prove behavior without a desk board first — Silico’s [sim](https://github.com/tig/silico/blob/main/specs/lexicon.md) idea; for ESP binaries that means **QEMU runners**, not only pure host doubles. |
| **Plate-shaped workflows** | Prefer the same *shape* as Silico GCU CI: clear jobs, host gate first, sibling tooling when needed — not a bespoke mystery pipeline. |

esprec is tooling, not a GCU, but it **serves** Silico GCUs. Its CI must be legible to agents who already know Silico’s host-gate vocabulary.

---

## 2. Required CI ladder

Jobs run in this **order of dependency**. Later stages must not be the only proof of earlier claims.

```text
  unit (host)  ──►  qemu-sim (ESP binary in QEMU)  ──►  [optional] metal
       ▲                        ▲
       │                        │
   always on CI            always on CI (v1)
                           via tobozo/esp32-qemu-sim
```

### 2.1 Stage A — Unit tests (host)

**Required. First. Fast. No firmware image. No QEMU. No board.**

Proves pure host logic and any host-side doubles:

- Protocol encode/decode, resync, CRC / framing contracts
- Pixel format conversion
- PNG snapshot encode path
- GIF multi-frame encode path
- CLI / library surface that can run against an **in-process or pipe** fake device
- Any portable C host tests if the firmware component shares codec logic with the host

**Gate name (conceptual):** `unit` / “host unit gate.”

**Fail means:** change is not done. Do not skip to QEMU to paper over unit failures.

### 2.2 Stage B — QEMU validation (`tobozo/esp32-qemu-sim`)

**Required on CI after unit is green (or in parallel only if unit also runs and both must pass).**

Proves the **on-device path** without metal:

1. Build a **canonical ESP-IDF (or agreed) example** that links the esprec component and draws a **known** test pattern (or LVGL fixture) into a capturable buffer.
2. Run that binary under [**tobozo/esp32-qemu-sim**](https://github.com/tobozo/esp32-qemu-sim) (Espressif QEMU) on a supported chip class (`esp32` / `esp32s3` / `esp32c3` as chosen for the example).
3. Drive capture from the **host side of CI** against the QEMU serial log/path the action exposes (or an equivalent documented serial attachment).
4. Assert a **successful capture pipeline**: host receives a valid frame, writes PNG (and optionally a short GIF), and image properties match the fixture (dimensions at minimum; golden or structural checks preferred over “file exists”).

**Gate name (conceptual):** `qemu` / “QEMU sim gate.”

**Why this action:** Silico-style host-honest proof for ESP firmware needs a **runner that executes the compiled image and exposes serial**. `tobozo/esp32-qemu-sim` is the required QEMU runner integration for esprec CI unless Silico later standardizes a different pinned QEMU action — if so, follow Silico’s pin and document the swap here.

**Constraints to respect (from the action):**

- Prefer a **merged flash image** when possible.
- Flash mode constraints (e.g. DIO/80 MHz class) apply as required by QEMU.
- Use a finite `qemu-timeout` (and timeout-interrupt patterns when the fixture prints a completion marker).
- Pin the action version (tag/SHA); do not float on `@main` for production CI.

### 2.3 Stage C — Metal (optional on CI; required for product claims)

Physical board capture remains the **confirmation** of product face on real panels (timing, color quirks, PSRAM, USB-CDC vs UART).

- **Not required** for esprec’s default GitHub-hosted CI to be green.
- Local / self-hosted metal jobs may exist later; they do not replace unit or QEMU gates.
- Silico GCU agents still use real USB for first-ship product face; esprec metal recipes support that without making cloud CI depend on hardware.

---

## 3. Named gates and “done”

| Claim | Minimum green gates |
|-------|---------------------|
| Host library / CLI change is done | **Unit** |
| On-device component / wire path is done | **Unit + QEMU** |
| “Works on my panel” product face claim | **Unit + QEMU** locally, plus **metal** confirm when asserting real hardware UI |

Agents and humans must not claim firmware capture works because unit tests alone passed, if the change touches on-device or protocol behavior that QEMU exercises.

Align language with Silico: say **host gate** / **unit gate** / **QEMU gate** explicitly; do not say “the gate” without which one.

---

## 4. Workflow shape (requirements, not YAML)

CI **must**:

1. Trigger on **push** to default/mainline branches and on **pull_request**.
2. Run **unit** on every such event.
3. Run **QEMU** (build example + `tobozo/esp32-qemu-sim` + host capture assertions) on every such event once the example exists; until the example lands, CI must still have a **failing or skipped-with-tracking** QEMU job policy — preferred: land a minimal QEMU-capable example early so the job is real, not eternally skipped.
4. Upload capture artifacts (PNG/GIF, QEMU serial logs) on failure (and optionally on success) so agents can inspect without re-running blind.
5. Fail the workflow if unit **or** QEMU fails (both required for merge once QEMU job exists).

CI **should** mirror Silico plate readability:

- Separate jobs or clearly ordered steps: `unit` then `qemu` (qemu may `needs: unit`).
- Document the exact local commands that match CI (so agents run the same gates on the desk).
- Avoid secret-dependent steps for the default ladder.

---

## 5. What QEMU is expected to prove (and not)

### Proves

- Firmware with esprec **boots** under QEMU for the chosen chip.
- Serial path carries **commanded capture** traffic the host understands.
- Host can produce a **valid PNG** (and optionally GIF) from that traffic.
- Regression on protocol/framing and basic capture plumbing without a desk board.

### Does not prove alone

- True panel timing, color calibration, or touch hardware.
- Full LVGL visual fidelity on every real SKU (QEMU may use a **synthetic framebuffer / test pattern** backend when display IP is not faithfully emulated).
- Silico deploy/identity on arbitrary product boards.

When display hardware is not faithfully emulated, the QEMU example **must** still exercise esprec through a **deterministic software framebuffer** (known pattern) so the serial + host path remains honest. Real-panel confidence stays a metal confirm.

---

## 6. Relationship to GCU / Silico product CI

- esprec’s own repo CI is defined here.
- A **GCU that vendors esprec** continues to run **its** Silico host gate (`silico gate` / plate `ci.yml`); it may optionally add an esprec snapshot step in product CI later.
- esprec must not force every GCU to run QEMU; it must make **esprec’s** QEMU gate strong enough that GCUs can trust the component pin.

---

## 7. Success criteria (CI)

1. Default-branch CI is red if unit tests fail.
2. Default-branch CI is red if the QEMU example fails to produce an accepted capture (once the example is in-tree).
3. Agents can name and run the same unit and QEMU gates locally with documented commands.
4. Artifacts (or logs) from QEMU failures are enough to debug serial/capture without a physical board.
5. CI language and job order are understandable to someone who already knows Silico’s host-gate model.

---

## 8. Open decisions (CI-specific)

- Exact chip default for the QEMU example (`esp32` vs `esp32s3` vs `esp32c3`).
- Whether host capture in CI attaches live to QEMU’s serial during the action, or post-processes action-captured logs/artifacts (implementation detail; requirement is an automated pass/fail on capture success).
- Golden image strictness (pixel-exact vs dimension + checksum of pattern regions).
- Whether Silico later absorbs a standard “ESP QEMU job” template that esprec should call instead of wiring the action only in this repo.
