# Custom adapter skeleton

`adapter.py` is the minimal adapter from [docs/writing-an-adapter.md](../../docs/writing-an-adapter.md):
an explicit step loop with an atomic checkpoint and ledgered tool calls. Copy it and replace
the loop body with your runtime.

```bash
uv run python examples/custom_adapter/run_sweep.py linear
```

It prints one line per kill mode and exits non-zero on any failing boundary.
