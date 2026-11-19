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

## Inspecting a ledger

`status(key)` returns `(status, attempt_count)`, or `None` for a key the ledger
has never seen. `entries()` lists every row as `(key, status, attempt_count)`
sorted by key, and `len(ledger)` counts distinct keys (not attempts).

For quick checks there are three narrower accessors: `attempts(key)` returns the
attempt count (`0` for an unknown key), `is_committed(key)` is true only once a
key has been committed, and `keys(status=None)` lists keys sorted, optionally
limited to `"intent"` or `"committed"`.

`tools()` lists the distinct tool names (the `tool:` prefix of each key) sorted,
and `count(status=None)` counts rows, optionally limited to `"intent"` or
`"committed"`.

`reattempted()` lists keys attempted more than once, whether the retry was
suppressed (committed key) or re-executed (crash residue), sorted by key.

## Inspecting the sink

The effect sink has matching helpers: `tools()` lists the distinct tool names,
`filter(tool)` returns one tool's whole records in append order, and `since(n)`
returns whole records from index `n` onward (negative `n` raises `ValueError`).
A torn final line is never included in any of them; use `read()` to see it.

`has(tool)` reports whether any whole record names a tool, `tail(n)` returns the
last `n` whole records (negative `n` raises `ValueError`), and `is_empty()` is true
when there are no whole records. On the ledger, `payload_hash_of(key)` returns the
stored payload hash (`None` for an unknown key) and `has_unconfirmed()` is true while
any key is still in `intent`. `ScriptedModel.peek(step)` fetches a response without a
prompt check, and `InjectedClock.start` exposes the value `reset()` returns to.

`max_attempts()` returns the highest attempt count on any key (`0` when empty),
`suppressed_keys()` lists committed keys that were attempted again (an upper bound,
like `LedgerSummary.suppressed`), and `is_empty()` is true before any key is recorded.
On the sink, `values(field)` collects one field across whole records in append order.
`ScriptedModel.window(start, stop)` returns a clamped slice of the script and
`is_pinned(step)` says whether a prompt hash is pinned; `InjectedClock.until(when)`
gives the seconds left until an absolute time.

`status_counts()` returns the number of `intent` and `committed` rows (both keys are
always present) and `first_unconfirmed()` gives the smallest key still in `intent`.
On the sink, `group_by(field)` buckets whole records by a field value and `duplicates()`
returns `(record, count)` pairs for records that appear more than once, which is the
quickest way to see a repeated effect. `ScriptedModel.find(response)` returns the first
step with an equal response, `InjectedClock.has_reached(when)` tests an absolute
deadline and `fork()` copies a clock that then moves independently.

`total_attempts()` sums attempts over every key and `tool_counts(status=None)` counts keys
per tool prefix, optionally restricted to `intent` or `committed`. On the sink, `unique()`
returns the records with repeats removed (the complement of `duplicates()`),
`ScriptedModel.last_step()` gives the final step index and `InjectedClock.ticks` counts how
many times the clock has been advanced.

`committed_keys()` and `intent_keys()` are named shortcuts for `keys("committed")` and
`keys("intent")`; the latter is the same set as `unconfirmed()`. On the sink,
`count_unique(tool=None)` counts distinct whole records, so comparing it with `len()`
shows at a glance whether anything was delivered twice.
