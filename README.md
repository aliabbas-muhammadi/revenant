# revenant

A durability conformance harness for agent runtimes. It kills an agent process with `SIGKILL` at **every** step boundary, resumes it, and checks three properties:

1. **Resume determinism**: the resumed run produces the same per-step state hashes as an uninterrupted golden run.
2. **Exactly-once effects**: external side effects happen once, even when the runtime re-attempts them. Attempts and effects are reported separately.
3. **No lost or phantom steps**: every golden step appears exactly once in the stitched trace.

Status: early development. See [DESIGN.md](DESIGN.md) for the protocol and [ROADMAP.md](ROADMAP.md) for progress.

## Development

```bash
uv sync
uv run pytest
uv run ruff check
```

MIT licensed.
