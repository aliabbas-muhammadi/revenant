# FAQ

## Why SIGKILL and not SIGTERM?

`SIGTERM` can be caught, so a runtime gets to flush buffers, close files and
write a final checkpoint. That hides the failure under test. `SIGKILL` runs no
handlers and no `finally` blocks, which is what a power cut or an OOM kill looks
like to the process. The child kills itself with `os.kill(os.getpid(),
signal.SIGKILL)` when its step counter reaches `REVENANT_KILL_AT`, so the kill
point is exact and does not depend on timing.

## Why scripted models instead of a real LLM or a seeded random one?

A real model is nondeterministic, and a seeded one consumes randomness
differently after a resume. Either way a divergent resume could be blamed on the
model instead of the runtime. A scripted model returns a fixed response per step,
so any difference between the golden run and a resumed run is the runtime's
fault. It also keeps the suite fast and keyless.

## Why is an unconfirmed effect not resolved automatically?

The ledger writes `intent`, performs the effect, then writes `committed`. A kill
in between leaves an `intent` row, and the harness cannot know whether the effect
reached the outside world: an email may or may not have been sent. Deciding
needs domain knowledge, such as asking the provider whether the message exists.
Guessing either way would hide real bugs, so such effects are reported as
`unconfirmed` and make the verdict fail until a human resolves them.

## Why are attempts and effects separate columns?

Durable runtimes are at-least-once: after a resume a tool may be attempted again.
That is fine as long as the effect happens once. A report that only counted
attempts would call correct behaviour a bug, and one that only counted effects
would hide how much work was repeated.

## Why does `ledgered-fanout` fail on LangGraph?

A kill inside a superstep with parallel branches can leave an `intent` row
without a `committed` one. That is reported as unconfirmed rather than passed.
See [results.md](results.md).

## Why a reduced matrix in CI?

The full matrix is slow. CI runs `linear` on the reference and every mutant; the
full matrix is `make conformance`, with its output committed under `results/`.
