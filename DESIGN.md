# revenant design

Durable execution is a crowded product category: Temporal, Restate, Inngest, Hatchet, DBOS and LangGraph checkpointing all promise that an agent can crash and resume without repeating side effects. revenant does not add another runtime. It is the test suite for that promise: kill the agent at every step boundary, resume it, and measure what actually happened.

The headline output is one line per adapter and workload, for example:

```
killed at 12/12 boundaries · resumes: 12/12 identical · effects: 3 once each · unconfirmed: 0 · verdict: PASS
```

## The three properties

1. **Resume determinism.** Run the workload once without interruption to get the golden sequence of per-step state hashes. For every boundary `k`: kill at `k`, resume, run to completion. The final state hash and the post-`k` hash sequence must equal the golden run's.
2. **Exactly-once effects, not attempts.** Durable systems are at-least-once at the attempt level. Correctness means the *effect* happens once. Every side-effecting tool routes through a ledger and re-attempts after resume are suppressed by idempotency key. Reports count attempts and effects in separate columns, because conflating them is how durability claims get oversold.
3. **No lost or phantom steps.** Every step in the golden run appears exactly once in the stitched (pre-kill + post-resume) trace. Nothing skipped, nothing invented.

## Architecture decisions

- **Deterministic workload, deterministic kill.** The agent under test uses a scripted mock model and an injected clock, so any divergence is attributable to the runtime and not the model. The child process kills itself with `os.kill(os.getpid(), signal.SIGKILL)` when its step counter reaches `REVENANT_KILL_AT=k`. Self-kill is race-free and reproducible; `SIGKILL` runs no cleanup handlers, which is the honest crash.
- **Ledger = SQLite in WAL mode** with table
  `effects(idempotency_key TEXT PRIMARY KEY, payload_hash TEXT, status TEXT CHECK(status IN ('intent','committed')), attempt_count INTEGER)`.
  Protocol: record `intent`, execute the effect, mark `committed`.
  - A kill between execute and commit leaves an `intent` row. The harness reports these as **unconfirmed effects**. It never auto-resolves them: deciding whether an unconfirmed effect happened needs domain knowledge the harness does not have.
  - A second attempt on a `committed` key is suppressed (counted as an attempt, not an effect).
  - The same key with a different `payload_hash` is a hard failure (idempotency-key reuse bug).
- **State hashes over canonical JSON**: recursively sorted keys, NFC-normalised strings, and volatile fields (timestamps, durations) excluded through an explicit per-adapter `volatile_fields` list.
- **An effect sink independent of the ledger.** Tools write real effects to an append-only JSONL "outside world" file, so duplicate effects are observable even when a runtime bypasses the ledger.

## Adapters

An adapter wraps one runtime behind `build(workload, workdir)`, `run(kill_at)`, `state_trace()` and `boundaries()`.

- `reference`: a ~200-line runtime with an explicit step loop and an atomic per-step checkpoint (`tmp` + `fsync` + `os.replace`). It is the baseline that should pass everything.
- `langgraph_sqlite`: LangGraph with `SqliteSaver`, resumed by `thread_id`. Run twice: with naive tools (expected: duplicate effects on kills mid-superstep, because LangGraph re-runs interrupted node work, which is documented behaviour) and with ledgered tools (expected: exactly-once effects with re-attempts visible in the attempts column).
- **Mutant adapters**: deliberately broken runtimes (no checkpoint, non-atomic checkpoint, checkpoint-before-effect). Each must fail the property it violates. They prove the harness actually detects bugs.

## Workloads

- `linear`: 12-step pipeline, tool calls at fixed steps.
- `branching`: a tool loop where the scripted model decides when to stop.
- `fanout`: parallel branches merged at the end. Boundaries are a total order defined per adapter (the reference adapter serialises; LangGraph batches supersteps), and every report says which definition it used.

## Edge cases that must be handled

1. `SIGKILL`, not `SIGTERM`: `SIGTERM` lets cleanup handlers run and masks the failure under test.
2. Self-kill on the step counter, never external timing.
3. Kill **at a boundary** (tests resume) and kill **mid-step** (before the checkpoint write; tests the intent/commit residue) are separate modes, reported separately.
4. Attempts and effects are separate columns. At-least-once attempts with exactly-once effects is correct behaviour.
5. `intent`-without-`committed` residue is reported, never auto-resolved.
6. Reference checkpoints are atomic. A kill mid-write must leave the previous valid checkpoint.
7. State hashes exclude volatile fields, or every resume "diverges" spuriously.
8. The mock model is scripted per workload, not seeded-random, because a resume consumes randomness differently.
9. LangGraph superstep granularity: a kill mid-node re-runs the node. The harness measures the consequence; it does not "fix" LangGraph.
10. The SQLite ledger uses WAL and the two-phase intent/commit protocol. An insert-on-success ledger loses the crash window entirely.
11. Fan-out boundaries are defined per adapter in `boundaries()` and stated in the report.
12. CI runs a reduced matrix; the full matrix is a local `make conformance` with committed results.
13. Committed results carry library versions (Python, revenant, LangGraph). Durability behaviour changes across releases.

## Acceptance criteria

- `uv run pytest` green, keyless, under 2 minutes.
- `revenant run --adapter reference --workload linear` reports `verdict: PASS`, `12/12 boundaries`, `unconfirmed: 0`.
- `revenant run --adapter langgraph_sqlite --workload branching --naive-tools` reports duplicate effects > 0; without `--naive-tools`, effects are exactly-once and attempts > effects.
- A corrupted checkpoint makes the adapter fail loudly with a named error, never a silent wrong resume.
- `results/` holds committed reports for every adapter, including library versions, and the README headline table matches them.
- CI green with zero secrets.
