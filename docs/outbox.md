# Outbox variant vs the file-checkpoint reference

Three runtimes share the same step loop and the same effects ledger. They differ in
where the checkpoint lives and when a step's tool call is performed.

| | `reference` | `reference_sqlite` | `reference_outbox` |
|---|---|---|---|
| Checkpoint | `checkpoint.json`, temp file + `fsync` + `os.replace` | row in `ledger.db`, one SQLite transaction | same as `reference_sqlite` |
| Tool call | performed inline, before the checkpoint | performed inline, before the checkpoint | queued in the checkpoint transaction, performed after it commits |
| Window a kill can hit | effect done, checkpoint not yet written | same | checkpoint committed, effect not yet delivered |
| What resume does | repeats the step; the ledger suppresses the committed effect | same | dispatches the undelivered rows first, then continues |
| `REVENANT_KILL_AT_WRITE` points | 1 temp written, 2 temp fsynced, 3 renamed, 4 directory fsynced | 1 after `BEGIN`, 2 row written, 3 after `COMMIT`, 4 WAL checkpointed | same |

## Why the outbox exists

With inline effects, the checkpoint and the effect are two separate durable writes, so
one of them has to go first. Effect first leaves a window where the effect has happened
and the state does not know it; the ledger closes that by suppressing the repeat.
The outbox reverses the order: the intent to call the tool is part of the checkpoint
transaction, so the state can never promise a call that was not recorded, and the
effect itself happens only after the state is durable.

The cost is a different crash window. A kill between the commit and the dispatch
leaves rows with status `pending`. They are delivered by the dispatcher when the
runtime resumes (`SqliteOutboxAdapter._load_saved`), still through the ledger, so a
row whose effect already ran is suppressed rather than repeated.

## What the committed sweeps show

`results/outbox/` holds a full sweep of both SQLite variants on every workload, in
boundary mode and in mid-step mode (`*-mid`). All twelve report `PASS`:

- every kill resumes to a state trace identical to the golden run;
- every effect lands once, with no duplicates, missing effects or unconfirmed rows.

Mid-step kills are the instructive difference. In `reference_sqlite` the kill lands
after the tool performed its effect, so the resume re-attempts the call and the
ledger suppresses it. In `reference_outbox` nothing has been performed at that point,
so the resume simply performs the call for the first time. The reports are the same;
the attempts column in the ledger is not.

Kills after the commit are covered by `tests/test_outbox.py`: with
`REVENANT_KILL_AT_WRITE=3` or `4` the queued row is still pending and no effect exists
in the sink until the next run delivers it.

## Reproducing

```
uv run revenant run --adapter reference_outbox --workload linear --mode mid --out out.json
```

One honest limit: an effect performed after the ledger recorded `intent` but before it
recorded `committed` is still reported as unconfirmed, exactly as in the file
reference. The outbox narrows where the checkpoint and the effect can disagree; it
does not give exactly-once delivery to a non-idempotent external system.
