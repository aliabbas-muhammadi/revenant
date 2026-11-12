"""Result types shared by adapters and the runner."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RunResult:
    """What one ``Adapter.run`` call produced."""

    completed: bool
    steps_run: int
    trace: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.steps_run < 0:
            raise ValueError("steps_run cannot be negative")
        if self.steps_run > len(self.trace):
            raise ValueError("steps_run exceeds trace length")

    @property
    def final_hash(self) -> str | None:
        """Hash after the last recorded step, or ``None`` for an empty trace."""
        return self.trace[-1] if self.trace else None
