# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- `revenant diff`, first-divergence reporting, per-tool breakdown and an
  attempts-per-effect histogram in reports.
- Seeded random workloads (`--workload gen-<seed>` and `genloop-<seed>`); CI sweeps three
  fixed seeds on the reference adapter.
- `docs/results.md` and `docs/faq.md`.
- `Ledger.entries()`, `len(Ledger)`, `attempts()`, `is_committed()` and `keys()` accessors.
- `key in ledger`, `iter(ledger)`, iterable `EffectSink`, `EffectSink.last()` and `canon.short_hash()`.
- `InjectedClock.elapsed()`, `len(EffectSink)`, `EffectSink.by_tool()` and `ScriptedModel.remaining()`.
- `InjectedClock.advance_to()` and `reset()`, `EffectSink.first()` and `count()`,
  `Ledger.tools()` and `count()`, and `ScriptedModel.is_exhausted()`.
- `EffectSink.tools()`, `filter()` and `since()`, `Ledger.reattempted()`,
  `ScriptedModel.responses()` and iteration, and `InjectedClock.is_at_start()`.
- `EffectSink.has()`, `tail()` and `is_empty()`, `Ledger.payload_hash_of()` and
  `has_unconfirmed()`, `ScriptedModel.peek()` and `InjectedClock.start`.
- `InjectedClock.until()`, `ScriptedModel.window()` and `is_pinned()`,
  `Ledger.max_attempts()`, `suppressed_keys()` and `is_empty()`,
  `EffectSink.values()` and `canon.same_state()`.
- `InjectedClock.has_reached()` and `fork()`, `Ledger.status_counts()` and
  `first_unconfirmed()`, `EffectSink.group_by()` and `duplicates()`,
  `ScriptedModel.find()` and `canon.canonical_size()`.
- `InjectedClock.ticks`, `ScriptedModel.last_step()`, `canon.diff_paths()`,
  `Ledger.total_attempts()` and `tool_counts()`, `EffectSink.unique()`.
- `Ledger.committed_keys()` and `intent_keys()`, `EffectSink.count_unique()`.
- `ScriptedModel.count()`, `EffectSink.last_for()`, `Ledger.keys_for()` and `most_attempted()`,
  and `canon.leaf_paths()`.
- `ScriptedModel.indices_of()` and `distinct_count()`, `InjectedClock.tick_n()`,
  `EffectSink.contains()` and `field_counts()`, `Ledger.keys_with_attempts()` and
  `canon.excluded_paths()`.
- `Ledger.summary_for()`, `EffectSink.index_of()` and `InjectedClock.span()`.

### Fixed
- `InjectedClock` rejects NaN and infinite values.

## [0.1.0] - 2026-11-15

### Added
- SIGKILL conformance runner: kills at every step boundary (and mid-step), resumes,
  and checks resume determinism, exactly-once effects and lost or phantom steps.
- Reference adapter with atomic file checkpoints and an idempotency ledger, plus
  SQLite and outbox variants.
- Five mutant adapters, each breaking one property, all failed by the harness.
- Chaos injectors: duplicate delivery, timeouts, checkpoint corruption.
- LangGraph adapter with a SQLite checkpointer; ledgered and naive tool modes.
- `revenant run`, `list` and `report` commands; text, markdown and JSON reports.
- Committed sweep results under `results/`, README table rendered from them.
- Docs: adapter guide, outbox comparison, custom adapter example.
- CI: lint, type check, tests, reduced conformance and LangGraph jobs.
- `Makefile` targets for test, lint and the full conformance matrix.

[Unreleased]: https://github.com/aliabbas-muhammadi/revenant/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/aliabbas-muhammadi/revenant/releases/tag/v0.1.0
