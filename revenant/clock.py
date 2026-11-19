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

    @property
    def start(self) -> float:
        """The value the clock started from (and ``reset()`` returns to)."""
        return self._start

    def now(self) -> float:
        """Return the current injected time."""
        return self._now

    def elapsed(self) -> float:
        """Return the injected time that has passed since the start value."""
        return self._now - self._start

    def is_at_start(self) -> bool:
        """True when no time has passed since the start value."""
        return self._now == self._start

    def until(self, when: float) -> float:
        """Return the seconds from now until ``when``, or ``0.0`` if it has passed."""
        if not math.isfinite(when):
            raise ValueError("clock time must be finite")
        return max(0.0, float(when) - self._now)

    def has_reached(self, when: float) -> bool:
        """True once the current time is at or past the absolute time ``when``."""
        if not math.isfinite(when):
            raise ValueError("clock time must be finite")
        return self._now >= when

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

    def advance_to(self, when: float) -> float:
        """Move to the absolute time ``when`` and return it.

        ``when`` must be finite and not earlier than the current time.
        """
        if not math.isfinite(when):
            raise ValueError("clock time must be finite")
        if when < self._now:
            raise ValueError("clock cannot move backwards")
        self._now = float(when)
        return self._now

    def reset(self) -> None:
        """Return to the start value."""
        self._now = self._start
