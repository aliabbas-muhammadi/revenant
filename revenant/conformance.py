"""Per-boundary and aggregate conformance results."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from revenant.scoring import DeterminismScore, EffectsScore, StepsScore


@dataclass(frozen=True)
class BoundaryResult:
    """Scores for one kill boundary."""

    boundary: int
    mode: str
    determinism: DeterminismScore
    effects: EffectsScore
    steps: StepsScore

    @property
    def passed(self) -> bool:
        return self.determinism.passed and self.effects.passed and self.steps.passed


@dataclass(frozen=True)
class ConformanceResult:
    """All boundary results for one adapter and workload."""

    adapter: str
    workload: str
    boundaries: tuple[BoundaryResult, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.boundaries, tuple):
            object.__setattr__(self, "boundaries", tuple(self.boundaries))

    @property
    def total(self) -> int:
        return len(self.boundaries)

    @property
    def identical_resumes(self) -> int:
        return sum(1 for b in self.boundaries if b.determinism.passed)

    @property
    def effects_once(self) -> int:
        """Effects that happened exactly once, taken from the worst boundary."""
        return min((b.effects.once for b in self.boundaries), default=0)

    @property
    def duplicated(self) -> int:
        return sum(len(b.effects.duplicated) for b in self.boundaries)

    @property
    def unconfirmed(self) -> int:
        return sum(len(b.effects.unconfirmed) for b in self.boundaries)

    @property
    def lost_or_phantom(self) -> int:
        return sum(len(b.steps.lost) + len(b.steps.phantom) for b in self.boundaries)

    @property
    def passed(self) -> bool:
        return all(b.passed for b in self.boundaries)

    def failing(self) -> tuple[int, ...]:
        """Boundaries that failed any property, in order."""
        return tuple(b.boundary for b in self.boundaries if not b.passed)


def aggregate(
    adapter: str, workload: str, results: Sequence[BoundaryResult]
) -> ConformanceResult:
    """Build a result with boundaries sorted so ordering is deterministic."""
    return ConformanceResult(adapter, workload, tuple(sorted(results, key=lambda r: r.boundary)))
