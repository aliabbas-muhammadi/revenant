# Reading the committed results

Every file under `results/` is the output of `revenant run`, one JSON and one
markdown report per adapter, workload and mode. The headline table in the README
is rendered from them by `scripts/render_tables.py`. This page says what each
group shows and why.

## Reference runtime (`results/reference-*`)

The baseline. `linear` (12 boundaries), `branching` (10) and `fanout` (5) all
pass: every resume is identical to the golden run, effects happen once each,
nothing is unconfirmed. If the reference ever fails, the harness or the
workloads are broken, not the system under test.

## Chaos (`results/chaos/`)

The reference runtime again, run with `--chaos` modes: `dup`, `timeout`,
`corrupt` (a bit flipped in the checkpoint body) and `all`. All twelve reports
pass, so the reference tolerates duplicate and slow deliveries and a damaged
checkpoint without losing determinism or exactly-once effects.

## Mutants (`results/mutants/`)

Deliberately broken runtimes, each of which must fail the property it violates:

| mutant | what is broken | what the report shows |
|---|---|---|
| `mutant_nocheckpoint` | nothing is checkpointed | 2/12 pass, 21 duplicated effects |
| `mutant_inplace` | checkpoint rewritten in place, not atomically | 0/12 pass, 78 lost steps |
| `mutant_volatile` | volatile fields leak into the state hash | 0/12 pass, every resume diverges although the effects are fine |
| `mutant_noledger` | tools bypass the ledger | 9/12 pass, 3 duplicated effects at mid-step kills |
| `mutant_checkpoint_first` | checkpoint written before the effect | 9/12 pass, an effect is missing after mid-step kills |

A harness that only ever reports PASS proves nothing; these failures are the
evidence that it can tell the difference.

## LangGraph (`results/langgraph/`)

`langgraph_sqlite` with `SqliteSaver`, killed mid-step.

- **Naive tools** (`naive-*`): every workload fails. `linear` passes 2/12 with
  13 duplicated effects, `branching` passes 0/10 with 24, `fanout` passes 1/3
  with 5. LangGraph re-runs a node interrupted mid-superstep, so any
  side effect inside it happens again. This is documented behaviour; the
  harness measures its consequence.
- **Ledgered tools** (`ledgered-*`): `linear` and `branching` pass at every
  boundary. Attempts exceed effects, which is correct: the re-attempt is
  suppressed by the ledger.
- **`ledgered-fanout` still fails**: boundary 2 shows 2 duplicated and 2
  unconfirmed effects. A kill inside a superstep with parallel branches can
  leave an `intent` row without a `committed` one. The harness reports those as
  unconfirmed and does not resolve them on its own, so the verdict stays FAIL.

## Outbox and SQLite variants (`results/outbox/`)

`reference_sqlite` keeps the checkpoint in the ledger database;
`reference_outbox` additionally queues each tool call in the checkpoint
transaction and performs it afterwards (see [outbox.md](outbox.md)). Both run in
`boundary` and `mid` kill modes on all three workloads. All twelve pass, so the
properties hold across storage designs, not just for one implementation.

## Reproducing

```
make conformance
python scripts/render_tables.py --check
```

Each report records the Python, revenant and platform versions it was produced
with, because durability behaviour changes across releases.
