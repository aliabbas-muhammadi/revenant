# Contributing

## Setup

```bash
uv sync --all-extras
make test      # pytest
make lint      # ruff and mypy
```

Python 3.11 or newer. The core uses only the standard library; the LangGraph
adapter lives behind the `langgraph` extra.

## Workflow

- Pick the first unticked task in `ROADMAP.md`; `DESIGN.md` is the spec.
- Ship code with tests in the same commit. Tests must be fast and deterministic;
  subprocess tests use tiny workloads.
- `uv run ruff check`, `uv run mypy` and `uv run pytest` must pass before a commit.
- Commit messages are conventional and one line: `feat(ledger): ...`,
  `fix: ...`, `docs: ...`, `test(canon): ...`.

## Results files

Everything under `results/` is produced by the CLI, never edited by hand.
Regenerate with `make conformance`, which also refreshes the README table
(`make table`). `tests/test_committed_results.py` checks that they stay consistent.

## Adding an adapter

See `docs/writing-an-adapter.md` and `examples/custom_adapter/`. A new adapter
should pass `linear` and be registered in the adapter registry.

## Adding a mutant

A mutant breaks exactly one durability property. Add it next to the existing
`mutant_*` adapters, give it a test asserting the harness fails it, and add it
to `scripts/ci_conformance.sh`.
