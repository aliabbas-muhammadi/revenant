"""The killer: runs a workload uninterrupted, then kills and resumes it."""

from __future__ import annotations

import os
import signal
import subprocess
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from revenant.adapter import Adapter
from revenant.adapters.reference import KILL_ENV, KILL_MODE_ENV
from revenant.result import RunResult
from revenant.workloads import Workload

AdapterFactory = Callable[[], Adapter]


@contextmanager
def _without_kill_env() -> Iterator[None]:
    """Hide kill variables so an inherited ``REVENANT_KILL_AT`` cannot hit a golden run."""
    saved = {k: os.environ.pop(k) for k in (KILL_ENV, KILL_MODE_ENV) if k in os.environ}
    try:
        yield
    finally:
        os.environ.update(saved)


def golden_run(factory: AdapterFactory, workload: Workload, workdir: str | Path) -> RunResult:
    """Run ``workload`` to completion with no interruption in a fresh ``workdir``."""
    workdir = Path(workdir)
    if workdir.exists() and any(workdir.iterdir()):
        raise ValueError(f"golden run needs an empty workdir, got {workdir}")
    adapter = factory()
    adapter.build(workload, workdir)
    with _without_kill_env():
        result = adapter.run()
    if not result.completed:
        raise RuntimeError("golden run did not complete")
    return result


class ChildStatus(Enum):
    """How a child process ended."""

    COMPLETED = "completed"
    KILLED = "killed"
    ERROR = "error"


@dataclass(frozen=True)
class ChildOutcome:
    """Exit classification plus captured output of one child process."""

    status: ChildStatus
    returncode: int
    stdout: str
    stderr: str


def classify_exit(returncode: int) -> ChildStatus:
    """0 is completed, death by SIGKILL is killed, anything else is an error."""
    if returncode == 0:
        return ChildStatus.COMPLETED
    if returncode == -signal.SIGKILL:
        return ChildStatus.KILLED
    return ChildStatus.ERROR


def spawn_child(
    argv: Sequence[str],
    env: Mapping[str, str] | None = None,
    timeout: float = 60.0,
) -> ChildOutcome:
    """Run ``argv`` with ``env`` layered over the current environment.

    Kill variables are scrubbed from the inherited environment, so only values
    passed in ``env`` can trigger a kill in the child.
    """
    full = {k: v for k, v in os.environ.items() if k not in (KILL_ENV, KILL_MODE_ENV)}
    full.update(env or {})
    proc = subprocess.run(
        list(argv), env=full, capture_output=True, text=True, timeout=timeout, check=False
    )
    return ChildOutcome(classify_exit(proc.returncode), proc.returncode, proc.stdout, proc.stderr)
