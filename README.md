# esprec

**ESP32 screen capture for agents** — the [tuirec](https://github.com/tui-cs/tuirec) *analogue* for devices with displays (same job: eyes on a UI; **not** a clone of tuirec’s pipeline).

On command, on-device firmware captures the framebuffer (raw, shadow buffer, or [LVGL](https://lvgl.io) snapshot) and sends **frame bytes** over USB serial. The **host** post-processes those frames into **PNG** (still) or **GIF** (sequence). GIF encoding is not done on the metal.

Primary audience: **AI agents**, not humans — especially [Silico](https://github.com/tig/silico) GCU agents that need to *see* the product face without a camera.

## Status

Requirements only. Specs live under [`specs/`](specs/).

| Spec | Scope |
|------|--------|
| [specs/spec.md](specs/spec.md) | Product requirements (Rev 0.4.1) |
| [specs/ci.md](specs/ci.md) | CI: unit → QEMU ([tobozo/esp32-qemu-sim](https://github.com/tobozo/esp32-qemu-sim)) → optional metal |

## Shape (planned)

```text
device UI ──► capture pixels ──► USB serial ──► host frames ──► PNG / GIF (host post-process)
```

**GIF styles (host):**

- **Keyframe / step** — frames only at settled steps → timelapse of states  
- **Session / continuous** — N frames/sec for a duration → movie-like session  

**Transport honesty:** captures must survive cooked serial (framing, checksum, text-safe payload). A pretty PNG that does not match the live panel is a pipeline failure first, not a product UI rewrite.

## License

TBD until first implementation lands.
