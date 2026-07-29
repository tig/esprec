# scripts/

**Xuss-C product scenarios** for re-recording the hero stills/GIFs under `docs/examples/`.

These are **not** the esprec package API and are **not** generic capture. They are
product-domain drivers (btn/reboot inject + settle + snap) that *use* esprec as
eyes. They live here because xuss-c clean-start `main` is docs-only and the
hero artifacts already live in this repo (#5).

Generic capture remains:

```text
esprec snapshot|record|spool
```

| Script | Role |
|--------|------|
| `xuss_c_product.py` | Shared product serial helpers (`btn` fail-closed, snap) — not installed as a package |
| `xuss_c_screen_scenario.py` | Idle → theme → Details stills + `xuss-c-screens.gif` / optional `scenario.gif` |
| `xuss_c_demo_record.py` | Living spool + multi-step demo keyframes → demo GIFs |
| `xuss_c_bench_capture_rate.py` | Host-paced shot timing on metal |

Requires firmware that answers `shot` / `btn` / optional `reboot` (Xuss-C-class product on metal). Capture imports: public `esprec` only.

See [docs/examples/README.md](../docs/examples/README.md) for one-liners.
