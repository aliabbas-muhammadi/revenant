# revenant

A durability conformance harness for agent runtimes. It kills an agent process with `SIGKILL` at **every** step boundary, resumes it, and checks three properties:

1. **Resume determinism**: the resumed run produces the same per-step state hashes as an uninterrupted golden run.
2. **Exactly-once effects**: external side effects happen once, even when the runtime re-attempts them. Attempts and effects are reported separately.
3. **No lost or phantom steps**: every golden step appears exactly once in the stitched trace.

Status: early development. See [DESIGN.md](DESIGN.md) for the protocol and [ROADMAP.md](ROADMAP.md) for progress.

## Quickstart

```bash
uv sync
uv run revenant list
uv run revenant run --adapter reference --workload linear --out report.json
```

```
killed at 12/12 boundaries · resumes: 12/12 identical · effects: 3 once each · unconfirmed: 0 · verdict: PASS
```

`--kill-at K` kills at a single boundary, `--mode mid` kills after the tool effect but before the checkpoint, and `--jobs N` runs boundaries in parallel. Saved reports can be re-rendered with `revenant report report.json --format text|md|json`.

Exit codes: `0` pass (including pass with unconfirmed effects), `1` conformance failure, `2` usage error. Committed sweeps live in [results/](results/).

## Development

```bash
uv sync
uv run pytest
uv run ruff check
```

MIT licensed.
