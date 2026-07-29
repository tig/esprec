# scripts/

**Xuss-C product scenarios** for re-recording the hero stills/GIFs under `docs/examples/`.

These are not the generic esprec CLI. Generic capture remains:

```text
esprec snapshot|record|spool
```

| Script | Role |
|--------|------|
| `xuss_c_screen_scenario.py` | Idle → theme → Details stills + `xuss-c-screens.gif` / optional `scenario.gif` |
| `xuss_c_demo_record.py` | Living spool + multi-step demo keyframes → demo GIFs |
| `xuss_c_bench_capture_rate.py` | Host-paced shot timing on metal |

Requires firmware that answers `shot` / `btn` / optional `reboot` (Xuss-C-class product on metal). Import only the public `esprec` package API.

See [docs/examples/README.md](../docs/examples/README.md) for one-liners.
