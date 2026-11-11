# Canonical state hashing

`revenant.canon` turns an arbitrary agent state into a stable SHA-256 digest.
Resume determinism (property 1 in [DESIGN.md](../DESIGN.md)) compares these
digests between a golden run and a killed-and-resumed run, so the encoding must
change only when the state itself changes.

## Encoding rules

| Rule | Why |
| --- | --- |
| Dict keys are sorted recursively. | Insertion order is an accident of how a runtime rebuilt the dict after a checkpoint load; it is not state. |
| Compact separators `(",", ":")`. | No whitespace variation between encoders. |
| `ensure_ascii=False`, UTF-8 output. | One byte sequence per string; no `\uXXXX` escape variants. |
| Strings (keys and values) are NFC-normalised. | `é` as one code point or as `e` plus a combining accent is the same text and must hash the same. |
| NaN and ±Infinity raise `CanonError`. | They are not valid JSON and `NaN != NaN` makes equality meaningless. |
| Tuples encode as lists. | JSON has no tuple; a checkpoint round-trip turns tuples into lists and that must not look like divergence. |
| Sets, bytes and arbitrary objects raise `CanonError` naming the type and JSON path (e.g. `$.a[2]`). | Silent coercion would hide state the harness cannot compare. Unordered sets have no canonical order. |
| Non-string dict keys raise `CanonError`. | `str()` coercion would make `{1: x}` and `{"1": x}` collide. |
| `1` and `1.0` hash differently; `True` is not `1`. | A runtime that changes a number's type across a checkpoint changed its state. The harness reports that. |
| List order is significant. | Order of steps and items is state. |

## Volatile fields

`state_hash(obj, volatile_fields=())` removes keys before hashing. Fields such
as timestamps and durations differ on every run, and without exclusion every
resume would diverge spuriously.

- `"meta.ts"` removes the `ts` key under `meta` at that path.
- List positions are transparent: `"items.ts"` removes `ts` from every dict in
  the `items` list.
- A leading `*` matches at any depth: `"*.ts"` removes every `ts` key.

Volatile fields are declared explicitly per adapter, never guessed, so a
runtime cannot hide a real divergence by naming it volatile implicitly.

## Golden hash

`tests/test_canon.py` pins one golden digest. If it changes, the encoding
changed and every committed result in `results/` is invalidated.
