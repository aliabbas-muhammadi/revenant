# Effects ledger

The ledger (`revenant/ledger.py`) is a SQLite database in WAL mode with
`synchronous=FULL`. Every call is its own transaction, so a SIGKILL can only
land between calls, never inside one.

## Protocol

```
        begin(key)              perform effect            commit(key)
  ----------------------> ------------------------> ---------------------->
   row: (none) -> intent        outside world             row: intent -> committed
   returns EXECUTE              changes (sink)            effect is confirmed

   begin(key) on a committed key -> SUPPRESS, attempt_count + 1, no effect
   begin(key) on an intent key   -> EXECUTE,  attempt_count + 1 (crash residue)
   begin(key) with another payload hash -> IdempotencyKeyReuse, row untouched
```

## Crash windows

| Kill lands | Ledger row | Effect happened | Observable outcome after resume |
| --- | --- | --- | --- |
| Before `begin` | none | no | Step re-runs from scratch; one effect. |
| After `begin`, before the effect | `intent` | no | Reported as unconfirmed; re-attempt executes and, once committed, the effect happens once. |
| After the effect, before `commit` | `intent` | yes | Reported as unconfirmed; the re-attempt executes again, so the effect may be duplicated. The harness never auto-resolves this. |
| After `commit` | `committed` | yes | Re-attempt is suppressed: attempts rise, effects stay at one. |

The ledger cannot tell the second and third rows apart. That is why `intent`
residue is surfaced as an unconfirmed effect rather than guessed at: deciding
whether the effect happened needs domain knowledge the harness does not have.

## Attempts versus effects

`summary()` reports attempts (the sum of `attempt_count`), effects (committed
rows), suppressed attempts and unconfirmed keys as separate numbers. A correct
runtime may show attempts greater than effects; it must never show effects
greater than one per key.
