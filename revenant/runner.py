"""The killer: runs a workload uninterrupted, then kills and resumes it."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from collections.abc import Callable, Iterator, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from revenant.adapter import Adapter
from revenant.adapters.reference import KILL_ENV, KILL_MODE_ENV
from revenant.conformance import BoundaryResult, ConformanceResult, aggregate
from revenant.ledger import Ledger
from revenant.result import RunResult
from revenant.scoring import score_determinism, score_effects, score_steps
from revenant.sink import EffectSink
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
    HANG = "hang"


@dataclass(frozen=True)
class ChildOutcome:
    """Exit classification plus captured output of one child process."""

    status: ChildStatus
    returncode: int
    stdout: str
    stderr: str


HANG_RETURNCODE = -1000  # sentinel: no exit code exists for a child we had to kill


def _text(data: str | bytes | None) -> str:
    if data is None:
        return ""
    return data.decode("utf-8", "replace") if isinstance(data, bytes) else data


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
    try:
        proc = subprocess.run(
            list(argv), env=full, capture_output=True, text=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired as exc:
        # A hang is not a crash: the child was still alive when we gave up on it.
        return ChildOutcome(
            ChildStatus.HANG, HANG_RETURNCODE, _text(exc.stdout), _text(exc.stderr)
        )
    return ChildOutcome(classify_exit(proc.returncode), proc.returncode, proc.stdout, proc.stderr)


def stitch(
    pre: Sequence[str], post: Sequence[str], offset: int = 0
) -> tuple[str | None, ...]:
    """Join the trace recorded before a kill with the one recorded after resume.

    ``post[i]`` is the hash of step ``offset + i + 1``. Where the two overlap
    (``offset < len(pre)``) the post-resume hash wins, because it is what the
    run ended up with. A gap (``offset > len(pre)``) is kept as ``None`` entries
    so the lost-step scorer can see it instead of the join hiding it.
    """
    if offset < 0:
        raise ValueError("offset cannot be negative")
    size = max(len(pre), offset + len(post))
    out: list[str | None] = [None] * size
    out[: len(pre)] = pre
    out[offset : offset + len(post)] = post
    return tuple(out)


@dataclass(frozen=True)
class KillResume:
    """One boundary's kill run and its resume."""

    boundary: int
    killed: ChildOutcome
    resumed: ChildOutcome
    stitched: tuple[str | None, ...]
    residue: tuple[str, ...] = ()


def reference_argv(workload: str, workdir: str | Path) -> list[str]:
    """Command line for the reference child entry point."""
    return [
        sys.executable, "-m", "revenant.adapters.reference",
        "--workload", workload, "--workdir", str(workdir),
    ]  # fmt: skip


def _ledger_residue(workdir: Path) -> tuple[str, ...]:
    """Keys left in ``intent`` by the killed run, read before the resume can touch them."""
    path = workdir / "ledger.db"
    if not path.exists():
        return ()
    with Ledger(path) as ledger:
        return tuple(sorted(ledger.unconfirmed()))


def kill_and_resume(
    factory: AdapterFactory,
    workload: Workload,
    workdir: str | Path,
    boundary: int,
    mode: str = "boundary",
    argv: Sequence[str] | None = None,
    timeout: float = 60.0,
) -> KillResume:
    """Kill a child at ``boundary``, resume it in the same workdir, stitch the traces.

    ``argv`` is the child command (default: the reference entry point).
    """
    workdir = Path(workdir)
    cmd = list(argv) if argv is not None else reference_argv(workload.name, workdir)
    killed = spawn_child(
        cmd, {KILL_ENV: str(boundary), KILL_MODE_ENV: mode}, timeout=timeout
    )
    residue = _ledger_residue(workdir)
    adapter = factory()
    adapter.build(workload, workdir)
    pre = adapter.state_trace()
    resumed = spawn_child(cmd, timeout=timeout)
    post = adapter.state_trace()
    # The reference trace is cumulative, so the post-resume trace starts at step 1.
    return KillResume(boundary, killed, resumed, stitch(pre, post), residue)


def _read_effects(workdir: Path) -> list[dict[str, object]]:
    path = workdir / "effects.jsonl"
    return list(EffectSink(path).effects()) if path.exists() else []


def sweep(
    factory: AdapterFactory,
    workload: Workload,
    root: str | Path,
    mode: str = "boundary",
    boundaries: Sequence[int] | None = None,
    argv_for: Callable[[Path], Sequence[str]] | None = None,
    jobs: int = 1,
) -> ConformanceResult:
    """Kill and resume at every boundary (default ``1..N``) and score all three properties.

    ``root`` receives a ``golden`` directory and one ``k<boundary>`` directory per kill.
    ``argv_for(workdir)`` builds the child command for an adapter other than the reference.
    ``jobs`` runs that many boundaries at once; results are always ordered by boundary.
    """
    root = Path(root)
    golden = golden_run(factory, workload, root / "golden")
    golden_effects = _read_effects(root / "golden")
    adapter_name = factory().name
    points = list(boundaries) if boundaries is not None else range(1, len(golden.trace) + 1)
    if jobs < 1:
        raise ValueError("jobs must be at least 1")

    def one(k: int) -> BoundaryResult:
        workdir = root / f"k{k}"
        if workdir.exists() and any(workdir.iterdir()):
            raise ValueError(f"boundary workdir must start empty, got {workdir}")
        argv = argv_for(workdir) if argv_for is not None else None
        run = kill_and_resume(factory, workload, workdir, k, mode=mode, argv=argv)
        return BoundaryResult(
            k,
            mode,
            score_determinism(golden.trace, run.stitched, k),
            score_effects(golden_effects, _read_effects(workdir), run.residue),
            score_steps(golden.trace, run.stitched),
        )

    if jobs == 1:
        results = [one(k) for k in points]
    else:
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            results = list(pool.map(one, points))
    return aggregate(adapter_name, workload.name, results)
