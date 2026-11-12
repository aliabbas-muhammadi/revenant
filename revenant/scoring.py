"""Pure scorers for the three durability properties."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class DeterminismScore:
    """Property 1: resume determinism."""

    passed: bool
    first_divergent_step: int | None = None
    final_state_matches: bool = True
    detail: str = ""


def score_determinism(
    golden: Sequence[str], stitched: Sequence[str | None], boundary: int
) -> DeterminismScore:
    """Compare the post-``boundary`` hashes and the final hash with the golden run.

    Steps are 1-based. Only steps after ``boundary`` are compared here; lost or
    phantom steps are property 3's concern, so a missing hash counts as a
    divergence at that step rather than being skipped silently.
    """
    for step in range(boundary + 1, len(golden) + 1):
        got = stitched[step - 1] if step <= len(stitched) else None
        if got != golden[step - 1]:
            return DeterminismScore(
                False,
                step,
                _final(golden, stitched),
                f"step {step}: expected {golden[step - 1][:12]}, got "
                f"{'nothing' if got is None else got[:12]}",
            )
    final_ok = _final(golden, stitched)
    if not final_ok:
        return DeterminismScore(
            False, None, False, "final state hash differs from the golden run"
        )
    return DeterminismScore(True)


def _final(golden: Sequence[str], stitched: Sequence[str | None]) -> bool:
    return bool(stitched) and bool(golden) and stitched[-1] == golden[-1]


@dataclass(frozen=True)
class EffectsScore:
    """Property 2: effects (not attempts) happened exactly once.

    ``unconfirmed`` keys are reported, never counted as passed or failed effects:
    deciding whether they happened needs domain knowledge.
    """

    once: int
    duplicated: tuple[str, ...]
    missing: tuple[str, ...]
    unexpected: tuple[str, ...]
    unconfirmed: tuple[str, ...]

    @property
    def passed(self) -> bool:
        """True when nothing was duplicated, missing or invented."""
        return not (self.duplicated or self.missing or self.unexpected)


def score_effects(
    expected: Sequence[dict[str, object]],
    observed: Sequence[dict[str, object]],
    unconfirmed: Sequence[str] = (),
) -> EffectsScore:
    """Compare the effects in the sink with the golden run's effects.

    Effects are identified by their canonical hash, so ordering is ignored.
    ``expected`` is the golden sink; ``observed`` is the sink after kill and resume.
    """
    from collections import Counter

    from revenant.canon import state_hash

    want = Counter(state_hash(e) for e in expected)
    got = Counter(state_hash(e) for e in observed)
    once = sum(1 for h, n in want.items() if got.get(h, 0) == n == 1)
    duplicated = sorted(h for h in want if got.get(h, 0) > want[h])
    missing = sorted(h for h in want if got.get(h, 0) < want[h])
    unexpected = sorted(h for h in got if h not in want)
    return EffectsScore(
        once, tuple(duplicated), tuple(missing), tuple(unexpected), tuple(sorted(unconfirmed))
    )
