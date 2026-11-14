# LangGraph adapter

`revenant.adapters.langgraph_sqlite` runs each workload as a LangGraph `StateGraph`
with a `SqliteSaver` checkpointer in the workdir and a fixed `thread_id`. Install
the extra with `uv sync --extra langgraph`. Tool calls go through the effects
ledger by default; `--naive-tools` bypasses it.

## Granularity: the superstep

LangGraph persists state once per superstep, not once per node. `boundaries()` is
therefore the superstep count:

| Workload | Steps | Supersteps (boundaries) | Why |
|---|---:|---:|---|
| `linear` | 12 | 12 | one node per step, one node per superstep |
| `branching` | 10 | 10 | conditional edges still run one node at a time |
| `fanout` | 3 tool calls + merge | 3 | the three branches run in parallel inside one superstep |

Boundary `k` kills the process with `k` supersteps saved. A mid-step kill dies
inside the node after its tool effect but before the superstep is saved, so
LangGraph re-runs the node on resume. That replay is what the ledger has to absorb.

Resume is `invoke(None, config)` with the same `thread_id`; the adapter never
replays input.

## What was measured

Mid-step sweeps, every boundary, `--jobs 4`. Reports live in
`results/langgraph/` and record the installed `langgraph` and
`langgraph-checkpoint-sqlite` versions in their header.

| Workload | Ledgered tools | Naive tools |
|---|---|---|
| `linear` | PASS, 3 effects once each | FAIL, 13 duplicated |
| `branching` | PASS, 9 effects once each | FAIL, 24 duplicated |
| `fanout` | FAIL, 2 duplicated, 2 unconfirmed | FAIL, 5 duplicated |

In every workload the resumed state hashes are identical to the golden run
(P1 holds for both modes): LangGraph's checkpointing is sound. What fails is
exactly-once *effects*, and only without the ledger.

## Naive vs ledgered

The delta on `linear` and `branching` is the point of the project: the same
runtime, the same checkpoints, the same kills, and the only difference is whether
tool calls consult the ledger. Without it, every replayed node repeats its
side effect.

`fanout` is the honest exception. With parallel branches, a kill can land while a
sibling has performed its effect but not yet committed its ledger row. That
row stays in `intent`, so the resumed run executes it again: the effect is
duplicated, and the key is reported as unconfirmed rather than hidden. This is
the crash window documented in `docs/ledger.md` (effect performed, commit not
reached); parallelism makes it reachable from a kill in a different node. The
ledger narrows the window but cannot close it without the tool being idempotent
at the destination.
