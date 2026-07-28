# esprec

**ESP32 screen capture for agents** — the [tuirec](https://github.com/tui-cs/tuirec) equivalent for devices with displays.

On command, on-device firmware captures the framebuffer (raw or [LVGL](https://lvgl.io) snapshot) and sends it over USB serial. A host tool turns that into **PNG** (snapshot) or **GIF** (short recording) so [Silico](https://github.com/tig/silico) agents can *see* what the device is doing.

Primary audience: **AI agents**, not humans.

## Status

Requirements only. Specs live under [`specs/`](specs/).

| Spec | Scope |
|------|--------|
| [specs/spec.md](specs/spec.md) | Product requirements |
| [specs/ci.md](specs/ci.md) | CI: unit → QEMU ([tobozo/esp32-qemu-sim](https://github.com/tobozo/esp32-qemu-sim)) → optional metal |

## Shape (planned)

```text
device UI ──► on-device capture ──► USB serial ──► host ──► PNG or GIF
```

## License

TBD until first implementation lands.
