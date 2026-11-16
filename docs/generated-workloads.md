# Generated workloads

Besides `linear`, `branching` and `fanout`, any adapter built on the reference
runtime can be swept over randomly laid-out workloads. They exist to catch bugs
that only show up for a particular step and tool arrangement.

## Names

- `gen-<seed>`: a linear-style workload. 4 to 14 steps; each step calls a tool
  with probability 1/3, the tool picked at random from `send_email`,
  `charge_card` and `write_file`.
- `genloop-<seed>`: a branching-style loop. 2 to 10 tool calls, then a stop step.

`<seed>` is any integer. The layout comes from `random.Random(seed)` alone, so the
same name builds the same workload in every process; that is how the killed child
rebuilds it from `--workload`. Tool arguments derive from the step number, so
file paths never collide.

## Running one

```bash
uv run revenant run --adapter reference --workload gen-7 --out gen-7.json
```

## Reproducing a failing seed

The report's `workload` field holds the name, so rerunning with that name
reproduces the failure exactly. Use `--kill-at K` to rerun a single boundary and
`--keep-workdirs` to inspect the checkpoint, ledger and sink files afterwards.

## Where they run

CI sweeps `gen-1`, `gen-2` and `gen-3` on the reference adapter
(`scripts/ci_conformance.sh`). The test suite also covers the SQLite variants in
`mid` mode, the chaos modes, and all five mutants.
