"""Injected clock: time advances only when the harness says so."""

from __future__ import annotations

import math


class InjectedClock:
    """A clock whose ``now()`` changes only through ``tick()``.

    Workloads read time from this instead of the wall clock, so a resumed run
    sees the same timestamps as the golden run.
    """

    def __init__(self, start: float = 0.0) -> None:
        start = float(start)
        if not math.isfinite(start):
            raise ValueError("clock start must be finite")
        self._start = start
        self._now = start

    def now(self) -> float:
        """Return the current injected time."""
        return self._now

    def elapsed(self) -> float:
        """Return the injected time that has passed since the start value."""
        return self._now - self._start

    def __repr__(self) -> str:
        return f"InjectedClock(now={self._now!r})"

    def tick(self, seconds: float = 1.0) -> float:
        """Advance by ``seconds`` (non-negative) and return the new time."""
        if not math.isfinite(seconds):
            raise ValueError("clock tick must be finite")
        if seconds < 0:
            raise ValueError("clock cannot move backwards")
        self._now += seconds
        return self._now
