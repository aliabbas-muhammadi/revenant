"""The adapter contract: how a runtime under test plugs into the harness."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from revenant.result import RunResult
from revenant.workloads import Workload


class Adapter(ABC):
    """Wraps one runtime behind four operations.

    ``build`` prepares the runtime for a workload inside ``workdir``. ``run``
    executes (or resumes) it, optionally killing the process at boundary
    ``kill_at``. ``state_trace`` returns the per-step state hashes recorded so
    far, and ``boundaries`` says how many kill points the runtime exposes for
    the built workload.
    """

    name: str

    @abstractmethod
    def build(self, workload: Workload, workdir: str | Path) -> None:
        """Prepare the runtime for ``workload`` using ``workdir`` for all state."""

    @abstractmethod
    def run(self, kill_at: int | None = None) -> RunResult:
        """Run or resume to completion; with ``kill_at`` the process dies at that boundary."""

    @abstractmethod
    def state_trace(self) -> tuple[str, ...]:
        """Per-step state hashes recorded in the workdir so far."""

    @abstractmethod
    def boundaries(self) -> int:
        """Number of kill boundaries for the built workload."""


__all__ = ["Adapter", "RunResult"]
