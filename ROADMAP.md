# Roadmap

Ordered task list. Work top to bottom. Each task ends green (`uv run pytest` and `uv run ruff check` pass) and is ticked `[x]` in the same commit that completes it. A task may take one to three commits (for example the implementation with its tests, then a docs or refactor follow-up), each green on its own. Everything must stay consistent with [DESIGN.md](DESIGN.md). Python stdlib only unless a task names a dependency.

## M1 · Canonical state hashing (`revenant/canon.py`)

- [x] R001 `canonical_json(obj) -> bytes`: recursively sorted keys, separators `(",", ":")`, `ensure_ascii=False`, UTF-8. Tests: key order independence, nested dicts and lists.
- [x] R002 NFC-normalise every string key and value before encoding. Test: composed and decomposed `é` produce identical bytes.
- [ ] R003 Reject NaN and ±Infinity with `CanonError`. Tests for each.
- [ ] R004 Tuples encode as lists; sets, bytes and arbitrary objects raise `CanonError` naming the type and the JSON path (e.g. `$.a[2]`). Tests.
- [ ] R005 Reject non-string dict keys with `CanonError` (no silent `str()` coercion). Test.
- [ ] R006 `state_hash(obj, volatile_fields=()) -> str`: SHA-256 hex of the canonical bytes. Test pins one golden hash literal so accidental encoding changes fail loudly.
- [ ] R007 Volatile-field exclusion by dotted path (`"meta.ts"`) at any depth, including inside lists of dicts. Tests.
- [ ] R008 Wildcard volatile paths (`"*.ts"` matches a `ts` key at any depth). Tests.
- [ ] R009 Decide and document int/float handling (`1` vs `1.0`); add a test that pins the chosen behaviour.
- [ ] R010 Permutation test: hash is invariant under dict insertion order across 200 seeded random permutations (stdlib `random`, fixed seed).
- [ ] R011 Module docstring plus `docs/canon.md` describing the encoding rules and why each exists.

## M2 · Effects ledger (`revenant/ledger.py`)

- [ ] R012 `Ledger(path)` opens SQLite, sets `journal_mode=WAL` and `synchronous=FULL`, creates the `effects` table exactly as in DESIGN.md. Test asserts the pragmas and the CHECK constraint.
- [ ] R013 `payload_hash(payload)` using `canon.state_hash`. Test.
- [ ] R014 `begin(key, payload) -> Decision` where `Decision` is an enum `EXECUTE | SUPPRESS`. New key inserts an `intent` row with `attempt_count=1` and returns `EXECUTE`. Tests.
- [ ] R015 `commit(key)` moves `intent` to `committed`; committing an unknown or already committed key raises `LedgerError`. Tests.
- [ ] R016 Re-attempt on a `committed` key returns `SUPPRESS` and increments `attempt_count`. Test.
- [ ] R017 Re-attempt on an `intent` key (crash residue) returns `EXECUTE` and increments `attempt_count`; document why in a docstring. Test.
- [ ] R018 Same key with a different payload hash raises `IdempotencyKeyReuse`, leaving the row unchanged. Test.
- [ ] R019 `unconfirmed() -> list[str]`: keys still in `intent`. Test.
- [ ] R020 `summary() -> LedgerSummary` dataclass: attempts, effects (committed), suppressed, unconfirmed. Tests.
- [ ] R021 Each call runs in its own transaction; test that a reopened ledger sees every committed row.
- [ ] R022 Crash test: a subprocess records an intent and SIGKILLs itself before commit; the parent reopens the ledger and finds exactly one unconfirmed key. Skip on non-POSIX.
- [ ] R023 Context manager support and idempotent `close()`. Tests.
- [ ] R024 `docs/ledger.md`: ASCII diagram of intent → execute → commit and a table of every crash window with its observable outcome.

## M3 · Deterministic model, clock and tools

- [ ] R025 `revenant/clock.py`: `InjectedClock(start)` whose `now()` advances only via `tick()`. Tests.
- [ ] R026 `revenant/model.py`: `ScriptedModel(script)` returning the scripted response for a step index; raises `ScriptExhausted` past the end. Tests.
- [ ] R027 Optional expected-prompt hashes in the script; a mismatched prompt raises `PromptDivergence` so input drift is caught at the source. Tests.
- [ ] R028 `revenant/sink.py`: `EffectSink(path)`, an append-only fsynced JSONL file that stands for the outside world. `effects()` reads it back. Tests.
- [ ] R029 `revenant/tools.py`: `Tool` base with `name`, `idempotency_key(args)` and `perform(args, sink)`. Ledgered invocation path: `begin` → `perform` → `commit`. Tests with a fake tool.
- [ ] R030 Attempts counter on every tool call, independent of ledger and sink. Test.
- [ ] R031 `send_email(to, subject, body)` tool. Tests.
- [ ] R032 `charge_card(customer, amount_cents)` tool; rejects non-int and non-positive amounts. Tests.
- [ ] R033 `write_file(relpath, content)` tool confined to a sandbox directory; absolute paths and `..` traversal raise `ToolError`. Tests.
- [ ] R034 Naive mode: a flag that bypasses the ledger. Test that a repeated naive call produces two sink effects.
- [ ] R035 Tool registry `get_tool(name)` with an error listing known tools. Test.

## M4 · Workloads (`revenant/workloads.py`)

- [ ] R036 `Workload` dataclass: name, ordered step specs, model script, volatile fields. Test construction and validation (empty steps rejected).
- [ ] R037 `linear` workload: 12 steps; steps 3, 6 and 9 call one tool each. Test step count and tool positions.
- [ ] R038 `get_workload(name)` registry with an error listing known names. Test.
- [ ] R039 `branching` workload: the scripted model loops over tool calls until the script says stop (about 10 steps). Test.
- [ ] R040 `fanout` workload: three branches with one tool call each, merged in a final step. Document the serialised order. Test.
- [ ] R041 In-process executor used by tests: runs a workload with no runtime and returns its state trace. Test.
- [ ] R042 Determinism test: each workload executed twice yields identical state-hash traces.

## M5 · Adapter contract and reference runtime

- [ ] R043 `revenant/adapter.py`: `Adapter` ABC with `build(workload, workdir)`, `run(kill_at=None)`, `state_trace()`, `boundaries()`. Test that it cannot be instantiated.
- [ ] R044 `RunResult` dataclass (completed, steps_run, trace, final_hash). Tests.
- [ ] R045 `revenant/adapters/reference.py`: step loop executing a workload in-process with no checkpointing yet. Test a full linear run.
- [ ] R046 Atomic checkpoint write: temp file, `fsync`, `os.replace`, then `fsync` the directory. Test file contents.
- [ ] R047 Resume: load the checkpoint and skip completed steps. Test resuming after a simulated stop at step 5.
- [ ] R048 Checkpoint `schema_version`; unknown versions raise `CheckpointError`. Test.
- [ ] R049 Checkpoint integrity digest; a mismatch raises `CheckpointCorrupt`. Test with a truncated file.
- [ ] R050 Boundary kill hook: when `REVENANT_KILL_AT=k`, SIGKILL itself right after checkpoint `k` is durable. Subprocess test checks the return code is `-SIGKILL`.
- [ ] R051 Mid-step kill mode `REVENANT_KILL_MODE=mid`: SIGKILL after the tool effect of step `k` but before its checkpoint. Subprocess test.
- [ ] R052 Per-step trace file: append `{step, hash}` JSONL and fsync. Test.
- [ ] R053 `boundaries()` returns the boundary count for a workload. Test for all three workloads.
- [ ] R054 Child entry point `python -m revenant.adapters.reference --workload X --workdir D`. Test via subprocess.

## M6 · The killer (`revenant/runner.py`)

- [ ] R055 Golden run: run uninterrupted in a fresh workdir and collect its trace. Test.
- [ ] R056 Child spawn helper with env, timeout and captured output; classifies exit as completed, killed or error. Tests with tiny fake children.
- [ ] R057 Kill-then-resume for one boundary, returning the stitched trace. Test with reference at k=5.
- [ ] R058 `stitch(pre, post)` as a pure function. Unit tests on synthetic traces, including overlap at the boundary.
- [ ] R059 Property 1 scorer (resume determinism). Unit tests: pass, divergent hash, divergent final state.
- [ ] R060 Property 2 scorer (effects from sink and ledger: once, duplicated, missing, unconfirmed). Unit tests.
- [ ] R061 Property 3 scorer (lost and phantom steps). Unit tests.
- [ ] R062 `BoundaryResult` and `ConformanceResult` dataclasses with aggregation. Tests.
- [ ] R063 Full sweep k=1..N. Integration test: reference + linear passes every property.
- [ ] R064 Mid-step sweep. Integration test: unconfirmed effects are reported, never hidden.
- [ ] R065 Fresh temporary workdir per boundary; test no state leaks between boundaries.
- [ ] R066 Child timeout recorded as `HANG`, distinct from crash. Test with a sleeping fake child.
- [ ] R067 `--jobs N` parallel sweep with deterministic result ordering. Test ordering is identical for jobs=1 and jobs=4.

## M7 · Reports and CLI

- [ ] R068 One-line text summary exactly as in DESIGN.md. Test the exact string.
- [ ] R069 Verdict rules: `PASS`, `PASS_WITH_UNCONFIRMED`, `FAIL`. Tests for each.
- [ ] R070 Markdown table report (one row per boundary). Test.
- [ ] R071 JSON report with `schema_version` and a versions header (Python, revenant, platform). Test.
- [ ] R072 `revenant run --adapter A --workload W [--kill-at K] [--mode boundary|mid] [--jobs N]`. Tests through `main(argv)`.
- [ ] R073 `revenant report PATH --format text|md|json`. Tests.
- [ ] R074 `revenant list` prints adapters and workloads. Test.
- [ ] R075 Exit codes: 0 pass, 1 conformance failure, 2 usage error. Tests.
- [ ] R076 `--out PATH` writes the JSON report. Test.
- [ ] R077 Commit `results/reference-linear.{json,md}` produced by the CLI.
- [ ] R078 Commit reference results for `branching` and `fanout`.
- [ ] R079 README quickstart showing a real run and its output.

## M8 · Mutant adapters (prove the harness catches bugs)

- [ ] R080 `adapters/mutant_nocheckpoint.py`: restarts from step 0 on every run. Test it FAILS property 2 or 3 on the linear sweep.
- [ ] R081 `adapters/mutant_inplace.py`: writes the checkpoint in place (no temp + rename). Add a kill-during-checkpoint-write hook. Test that the harness detects corruption.
- [ ] R082 `adapters/mutant_checkpoint_first.py`: checkpoints before performing the step's effect. Test that a mid-step kill produces a lost effect.
- [ ] R083 `adapters/mutant_noledger.py`: reference runtime with naive tools. Test duplicate effects under mid-step kills.
- [ ] R084 `adapters/mutant_volatile.py`: puts a wall-clock timestamp in state without declaring it volatile. Test the harness flags divergence and the message points at the field.
- [ ] R085 Mutant matrix test: every mutant fails with its expected property and no other.
- [ ] R086 `docs/mutants.md`: table of mutant → bug → property that catches it → committed result.
- [ ] R087 Commit mutant results under `results/mutants/`.

## M9 · LangGraph adapter

- [ ] R088 Add the `langgraph` extra (`langgraph`, `langgraph-checkpoint-sqlite`) with `uv add --optional langgraph`. Tests needing it use `pytest.importorskip`.
- [ ] R089 Graph builder for `linear`: one node per step.
- [ ] R090 `SqliteSaver` checkpointer in the workdir and a fixed `thread_id`.
- [ ] R091 Resume by invoking with the same `thread_id` and `None` input. Test.
- [ ] R092 Kill hook inside nodes; define and document `boundaries()` as superstep count.
- [ ] R093 State hashing with the adapter's volatile fields. Test.
- [ ] R094 Naive-tools flag (`--naive-tools`) and ledgered tools as default.
- [ ] R095 `branching` graph with conditional edges.
- [ ] R096 `fanout` graph with parallel branches.
- [ ] R097 Integration test: linear + ledgered passes effects exactly-once.
- [ ] R098 Integration test: naive tools under mid-step kills record duplicate effects > 0. The test asserts the measurement, not a pass.
- [ ] R099 Report header includes the installed LangGraph version.
- [ ] R100 Commit LangGraph results, naive and ledgered, for all three workloads.
- [ ] R101 `docs/langgraph.md`: superstep granularity, what was measured, and the naive vs ledgered delta.

## M10 · Chaos extensions

- [ ] R102 Duplicate-delivery injection: the same tool result delivered twice. Tests on reference.
- [ ] R103 Tool-timeout injection: a tool attempt hangs and is retried. Tests.
- [ ] R104 Checkpoint truncation: adapters must raise a named error. Tests for reference and LangGraph.
- [ ] R105 Checkpoint bit-flip corruption. Tests.
- [ ] R106 Ledger file deleted between kill and resume: must be detected, not silently re-run. Tests.
- [ ] R107 Sink file truncated mid-line: reader reports the partial record. Tests.
- [ ] R108 `--chaos none|dup|timeout|corrupt|all` CLI flag. Tests.
- [ ] R109 Chaos columns in text, markdown and JSON reports. Tests.
- [ ] R110 Commit chaos results.

## M11 · Hardening

- [ ] R111 Kill at each write inside the checkpoint routine (`REVENANT_KILL_AT_WRITE`). Test the reference survives every point.
- [ ] R112 `--keep-workdirs` debug flag. Test.
- [ ] R113 Reproducibility test: two full sweeps produce byte-identical JSON reports once timing fields are removed.
- [ ] R114 Per-boundary wall time recorded as a volatile report field. Test it is excluded from comparisons.
- [ ] R115 Structured logging via stdlib `logging` with `--verbose`. Test.
- [ ] R116 Clear error when run on a platform without `SIGKILL`. Test with monkeypatching.
- [ ] R117 Guard against `REVENANT_KILL_AT` leaking into the golden run. Test.
- [ ] R118 Validate `--kill-at` against `boundaries()`; out of range is a usage error. Test.
- [ ] R119 Type hints across the package; add `mypy` to the dev group and a strict config for `revenant/`. Fix findings.
- [ ] R120 Add mypy to CI.

## M12 · Transactional reference variant (outbox pattern)

- [ ] R121 `adapters/reference_sqlite.py`: checkpoint state and ledger rows in one SQLite transaction.
- [ ] R122 Outbox: effects recorded in the same transaction and dispatched after commit. Tests.
- [ ] R123 Dispatcher resumes undelivered outbox rows after a kill. Tests.
- [ ] R124 Full sweeps for all workloads. Integration tests.
- [ ] R125 Commit results and a `docs/outbox.md` comparison with the file-checkpoint reference.

## M13 · Docs, CI and release

- [ ] R126 README: the three properties with a worked example.
- [ ] R127 README: attempts vs effects explained with a real committed result.
- [ ] R128 `scripts/render_tables.py` builds the README headline table from `results/`. Test that README matches the rendered output.
- [ ] R129 `docs/writing-an-adapter.md` with a complete minimal adapter.
- [ ] R130 `examples/custom_adapter/`: a runnable skeleton that passes on `linear`. Test it.
- [ ] R131 `Makefile` with `test`, `lint`, `conformance` (full matrix) targets.
- [ ] R132 CI reduced conformance job: `linear` on reference and every mutant.
- [ ] R133 CI conformance job for LangGraph `linear`.
- [ ] R134 CONTRIBUTING.md.
- [ ] R135 CHANGELOG.md following Keep a Changelog.
- [ ] R136 CI badge and results summary in README.
- [ ] R137 Bump to 0.1.0 and update the changelog.

## M14 · Deeper analysis

- [ ] R138 `revenant diff A.json B.json`: compare two reports boundary by boundary. Tests.
- [ ] R139 Report the first divergent step and field when determinism fails. Tests.
- [ ] R140 Per-tool attempts/effects breakdown in reports. Tests.
- [ ] R141 Histogram of attempts per effect in markdown reports. Tests.
- [ ] R142 `docs/results.md`: narrative of every committed result.
- [ ] R143 `docs/faq.md`: why SIGKILL, why scripted models, why unconfirmed is not auto-resolved.
- [ ] R144 Property-based workload generator: random step/tool layouts from a seed, swept on reference. Tests.
- [ ] R145 Generated-workload sweep in CI with three fixed seeds.

## Added during development

Append new tasks here (continuing the R numbering) only when everything above is done. They must stay inside DESIGN.md's scope and be as specific as the tasks above.
