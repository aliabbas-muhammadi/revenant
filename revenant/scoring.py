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
