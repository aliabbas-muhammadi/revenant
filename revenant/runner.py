"""The killer: runs a workload uninterrupted, then kills and resumes it."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
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
