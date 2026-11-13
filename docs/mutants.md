# Mutant adapters

Each mutant is the reference runtime with one deliberate bug. A harness that cannot
fail a broken runtime proves nothing, so every mutant must fail the property its bug
violates. `tests/test_mutant_matrix.py` pins which properties fail and which do not.

Properties: **P1** resume determinism, **P2** exactly-once effects, **P3** no lost or
phantom steps.

| Mutant | Bug | Sweep mode | Fails | Committed result |
|---|---|---|---|---|
| `mutant_nocheckpoint` | never reads its checkpoint; restarts from step 0 every run | boundary | P2 (duplicated effects) | [json](../results/mutants/mutant_nocheckpoint-linear.json) · [md](../results/mutants/mutant_nocheckpoint-linear.md) |
| `mutant_inplace` | rewrites the live checkpoint in place; dies half-way through the write | boundary | P1, P2, P3 (resume hits `CheckpointCorrupt`) | [json](../results/mutants/mutant_inplace-linear.json) · [md](../results/mutants/mutant_inplace-linear.md) |
| `mutant_checkpoint_first` | checkpoints a step before performing its effect | mid | P2 (missing effect) | [json](../results/mutants/mutant_checkpoint_first-linear.json) · [md](../results/mutants/mutant_checkpoint_first-linear.md) |
| `mutant_noledger` | tools bypass the effects ledger | mid | P2 (duplicated effects) | [json](../results/mutants/mutant_noledger-linear.json) · [md](../results/mutants/mutant_noledger-linear.md) |
| `mutant_volatile` | wall-clock timestamp in hashed state, not declared volatile | boundary | P1 only | [json](../results/mutants/mutant_volatile-linear.json) · [md](../results/mutants/mutant_volatile-linear.md) |

## Reproducing a row

```
revenant run --adapter mutant_noledger --workload linear --mode mid --out /tmp/r.json
```

Exit code is 1 for every mutant. The committed files were produced exactly this way
with `--jobs 4`; the pinned test checks they parse, report `FAIL` and match their
markdown rendering.

## Notes

- `mutant_inplace` fails all three properties on purpose: a corrupt checkpoint stops
  the resumed child, so the post-resume trace is empty. The reference raises a named
  `CheckpointCorrupt` rather than resuming from damaged state.
- `mutant_checkpoint_first` dies between the checkpoint and the effect in mid mode;
  its boundary-mode sweep passes, which is why the mode is reported separately.
- `mutant_volatile` is fixed by listing `wall_time` in the workload's
  `volatile_fields`; a test shows determinism returns once it is declared.
