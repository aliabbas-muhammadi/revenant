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

`--kill-at K` kills at a single boundary, `--mode mid` kills after the tool effect but before the checkpoint, and `--jobs N` runs boundaries in parallel. `--kill-at` must lie within the adapter's boundaries (out of range is a usage error). `--verbose` logs progress to stderr, and `--keep-workdirs` keeps the golden and per-boundary workdirs and prints where they are. Each boundary records its wall time as `wall_seconds`, a volatile field that is ignored when comparing runs. To crash inside the checkpoint write itself, set `REVENANT_KILL_AT_WRITE` to 1-4 (temp written, fsynced, renamed, directory fsynced) next to `REVENANT_KILL_AT`. Saved reports can be re-rendered with `revenant report report.json --format text|md|json`.

Exit codes: `0` pass (including pass with unconfirmed effects), `1` conformance failure, `2` usage error. Committed sweeps live in [results/](results/); the SQLite and outbox variants are compared in [docs/outbox.md](docs/outbox.md).

## Results

Every committed sweep, generated from `results/` by `scripts/render_tables.py`:

<!-- results-table:start -->
| result | adapter | workload | kill mode | chaos | boundaries passed | duplicated | unconfirmed | verdict |
|---|---|---|---|---|---:|---:|---:|---|
| [chaos/reference-branching-all](results/chaos/reference-branching-all.json) | reference | branching | boundary | all | 10/10 | 0 | 0 | PASS |
| [chaos/reference-branching-corrupt](results/chaos/reference-branching-corrupt.json) | reference | branching | boundary | corrupt | 10/10 | 0 | 0 | PASS |
| [chaos/reference-branching-dup](results/chaos/reference-branching-dup.json) | reference | branching | boundary | dup | 10/10 | 0 | 0 | PASS |
| [chaos/reference-branching-timeout](results/chaos/reference-branching-timeout.json) | reference | branching | boundary | timeout | 10/10 | 0 | 0 | PASS |
| [chaos/reference-fanout-all](results/chaos/reference-fanout-all.json) | reference | fanout | boundary | all | 5/5 | 0 | 0 | PASS |
| [chaos/reference-fanout-corrupt](results/chaos/reference-fanout-corrupt.json) | reference | fanout | boundary | corrupt | 5/5 | 0 | 0 | PASS |
| [chaos/reference-fanout-dup](results/chaos/reference-fanout-dup.json) | reference | fanout | boundary | dup | 5/5 | 0 | 0 | PASS |
| [chaos/reference-fanout-timeout](results/chaos/reference-fanout-timeout.json) | reference | fanout | boundary | timeout | 5/5 | 0 | 0 | PASS |
| [chaos/reference-linear-all](results/chaos/reference-linear-all.json) | reference | linear | boundary | all | 12/12 | 0 | 0 | PASS |
| [chaos/reference-linear-corrupt](results/chaos/reference-linear-corrupt.json) | reference | linear | boundary | corrupt | 12/12 | 0 | 0 | PASS |
| [chaos/reference-linear-dup](results/chaos/reference-linear-dup.json) | reference | linear | boundary | dup | 12/12 | 0 | 0 | PASS |
| [chaos/reference-linear-timeout](results/chaos/reference-linear-timeout.json) | reference | linear | boundary | timeout | 12/12 | 0 | 0 | PASS |
| [langgraph/ledgered-branching](results/langgraph/ledgered-branching.json) | langgraph_sqlite | branching | mid | none | 10/10 | 0 | 0 | PASS |
| [langgraph/ledgered-fanout](results/langgraph/ledgered-fanout.json) | langgraph_sqlite | fanout | mid | none | 2/3 | 2 | 2 | FAIL |
| [langgraph/ledgered-linear](results/langgraph/ledgered-linear.json) | langgraph_sqlite | linear | mid | none | 12/12 | 0 | 0 | PASS |
| [langgraph/naive-branching](results/langgraph/naive-branching.json) | langgraph_sqlite | branching | mid | none | 0/10 | 24 | 0 | FAIL |
| [langgraph/naive-fanout](results/langgraph/naive-fanout.json) | langgraph_sqlite | fanout | mid | none | 1/3 | 5 | 0 | FAIL |
| [langgraph/naive-linear](results/langgraph/naive-linear.json) | langgraph_sqlite | linear | mid | none | 2/12 | 13 | 0 | FAIL |
| [mutants/mutant_checkpoint_first-linear](results/mutants/mutant_checkpoint_first-linear.json) | mutant_checkpoint_first | linear | mid | none | 9/12 | 0 | 0 | FAIL |
| [mutants/mutant_inplace-linear](results/mutants/mutant_inplace-linear.json) | mutant_inplace | linear | boundary | none | 0/12 | 0 | 0 | FAIL |
| [mutants/mutant_nocheckpoint-linear](results/mutants/mutant_nocheckpoint-linear.json) | mutant_nocheckpoint | linear | boundary | none | 2/12 | 21 | 0 | FAIL |
| [mutants/mutant_noledger-linear](results/mutants/mutant_noledger-linear.json) | mutant_noledger | linear | mid | none | 9/12 | 3 | 0 | FAIL |
| [mutants/mutant_volatile-linear](results/mutants/mutant_volatile-linear.json) | mutant_volatile | linear | boundary | none | 0/12 | 0 | 0 | FAIL |
| [outbox/reference_outbox-branching-mid](results/outbox/reference_outbox-branching-mid.json) | reference_outbox | branching | mid | none | 10/10 | 0 | 0 | PASS |
| [outbox/reference_outbox-branching](results/outbox/reference_outbox-branching.json) | reference_outbox | branching | boundary | none | 10/10 | 0 | 0 | PASS |
| [outbox/reference_outbox-fanout-mid](results/outbox/reference_outbox-fanout-mid.json) | reference_outbox | fanout | mid | none | 5/5 | 0 | 0 | PASS |
| [outbox/reference_outbox-fanout](results/outbox/reference_outbox-fanout.json) | reference_outbox | fanout | boundary | none | 5/5 | 0 | 0 | PASS |
| [outbox/reference_outbox-linear-mid](results/outbox/reference_outbox-linear-mid.json) | reference_outbox | linear | mid | none | 12/12 | 0 | 0 | PASS |
| [outbox/reference_outbox-linear](results/outbox/reference_outbox-linear.json) | reference_outbox | linear | boundary | none | 12/12 | 0 | 0 | PASS |
| [outbox/reference_sqlite-branching-mid](results/outbox/reference_sqlite-branching-mid.json) | reference_sqlite | branching | mid | none | 10/10 | 0 | 0 | PASS |
| [outbox/reference_sqlite-branching](results/outbox/reference_sqlite-branching.json) | reference_sqlite | branching | boundary | none | 10/10 | 0 | 0 | PASS |
| [outbox/reference_sqlite-fanout-mid](results/outbox/reference_sqlite-fanout-mid.json) | reference_sqlite | fanout | mid | none | 5/5 | 0 | 0 | PASS |
| [outbox/reference_sqlite-fanout](results/outbox/reference_sqlite-fanout.json) | reference_sqlite | fanout | boundary | none | 5/5 | 0 | 0 | PASS |
| [outbox/reference_sqlite-linear-mid](results/outbox/reference_sqlite-linear-mid.json) | reference_sqlite | linear | mid | none | 12/12 | 0 | 0 | PASS |
| [outbox/reference_sqlite-linear](results/outbox/reference_sqlite-linear.json) | reference_sqlite | linear | boundary | none | 12/12 | 0 | 0 | PASS |
| [reference-branching](results/reference-branching.json) | reference | branching | boundary | none | 10/10 | 0 | 0 | PASS |
| [reference-fanout](results/reference-fanout.json) | reference | fanout | boundary | none | 5/5 | 0 | 0 | PASS |
| [reference-linear](results/reference-linear.json) | reference | linear | boundary | none | 12/12 | 0 | 0 | PASS |
<!-- results-table:end -->

## The three properties, with an example

Take the `linear` workload: twelve steps, with a tool call at steps 3 (`send_email`), 6 (`charge_card`) and 9 (`write_file`). The harness first runs it uninterrupted to get a golden trace of twelve state hashes and the three effects it should produce. Then, for each boundary `k`, it starts the runtime in a fresh directory, `SIGKILL`s it at `k`, resumes it, and compares what it finds against the golden run:

1. **Resume determinism.** The hashes of the stitched trace (steps before the kill plus steps after the resume) must equal the golden hashes, and so must the final state. A runtime that resumes with a different clock value, or forgets a thought, diverges here and the report names the first divergent step.
2. **Exactly-once effects.** Each golden effect must appear in the effect sink exactly once. The sink is a plain append-only file, independent of the ledger, so a runtime that skips idempotency keys cannot hide a duplicate.
3. **No lost or phantom steps.** Every golden step must appear exactly once in the stitched trace. A step that never ran is lost; a step the golden run does not contain is phantom.

The committed sweep of `mutant_noledger`, a reference runtime whose tools bypass the ledger, shows how a failure reads (`results/mutants/mutant_noledger-linear.md`):

```
killed at 12/12 boundaries · resumes: 12/12 identical · effects: 2 once each · duplicated: 3 · unconfirmed: 0 · verdict: FAIL

| boundary | mode | resume | effects once | duplicated | missing | unconfirmed | lost | phantom | result |
| 3 | mid | identical | 2 | 1 | 0 | 0 | 0 | 0 | FAIL |
| 4 | mid | identical | 3 | 0 | 0 | 0 | 0 | 0 | pass |
```

Killing at boundary 3 in `mid` mode lands after the email was sent and before the checkpoint. The resume repeats step 3, and with no idempotency key the email goes out twice: the run resumes identically (property 1 holds) but property 2 fails. Boundary 4 is clean because no tool call sits between that checkpoint and the kill.

## Attempts versus effects

A runtime that resumes after a crash will often call a tool again. That second call is an **attempt**; whether it changes the outside world is a separate question, and the harness never merges the two. Attempts are counted in the ledger (`attempt_count` per idempotency key). Effects are counted by reading the append-only sink. Re-attempting a committed key is correct behaviour: the ledger suppresses it, the attempt count goes up, and the effect count stays at one.

LangGraph shows both sides on the same workload, killed at the same boundaries (`results/langgraph/`). LangGraph re-runs a node that was interrupted mid-superstep, so on `branching` both runs re-attempt tools after a kill. With the effects ledger in front of the tools (`ledgered-branching`) the repeat is suppressed:

```
killed at 10/10 boundaries · resumes: 10/10 identical · effects: 9 once each · unconfirmed: 0 · verdict: PASS
```

With the ledger bypassed (`naive-branching`, `--naive-tools`) the very same repeat performs the effect again:

```
killed at 10/10 boundaries · resumes: 10/10 identical · effects: 5 once each · duplicated: 24 · unconfirmed: 0 · verdict: FAIL
```

Both resume identically, so determinism cannot tell them apart. Only the effect count separates a runtime that tolerates retries from one that does not. An effect that ran but was never marked committed is neither counted as once nor guessed at: it is reported as `unconfirmed`.

## Development

```bash
uv sync
uv run pytest
uv run ruff check
```

MIT licensed.
