import json
import os
import signal
import subprocess
import sys

import pytest

from revenant.adapters.reference import ReferenceAdapter
from revenant.workloads import get_workload

pytestmark = pytest.mark.skipif(os.name != "posix", reason="needs POSIX signals")


def _child(workdir, kill_at=None):
    env = dict(os.environ)
    env.pop("REVENANT_KILL_AT", None)
    if kill_at is not None:
        env["REVENANT_KILL_AT"] = str(kill_at)
    return subprocess.run(
        [sys.executable, "-m", "revenant.adapters.reference",
         "--workload", "linear", "--workdir", str(workdir)],
        env=env, capture_output=True, text=True, timeout=60,
    )  # fmt: skip


def test_child_runs_to_completion(tmp_path):
    proc = _child(tmp_path)
    assert proc.returncode == 0
    assert json.loads(proc.stdout) == {"completed": True, "steps_run": 12}


def test_child_killed_after_checkpoint_k(tmp_path):
    proc = _child(tmp_path, kill_at=5)
    assert proc.returncode == -signal.SIGKILL
    a = ReferenceAdapter()
    a.build(get_workload("linear"), tmp_path)
    assert len(a.state_trace()) == 5


def test_resume_after_kill_matches_golden(tmp_path):
    assert _child(tmp_path / "k", kill_at=5).returncode == -signal.SIGKILL
    assert _child(tmp_path / "k").returncode == 0
    assert _child(tmp_path / "g").returncode == 0
    traces = []
    for sub in ("k", "g"):
        a = ReferenceAdapter()
        a.build(get_workload("linear"), tmp_path / sub)
        traces.append(a.state_trace())
    assert traces[0] == traces[1] and len(traces[0]) == 12


def _child_mid(workdir, kill_at):
    env = dict(os.environ)
    env["REVENANT_KILL_AT"] = str(kill_at)
    env["REVENANT_KILL_MODE"] = "mid"
    return subprocess.run(
        [sys.executable, "-m", "revenant.adapters.reference",
         "--workload", "linear", "--workdir", str(workdir)],
        env=env, capture_output=True, text=True, timeout=60,
    )  # fmt: skip


def _sink_lines(workdir):
    return (workdir / "effects.jsonl").read_text().splitlines()


def test_mid_kill_lands_after_effect_before_checkpoint(tmp_path):
    # Step 3 is the first tool step in the linear workload.
    proc = _child_mid(tmp_path, kill_at=3)
    assert proc.returncode == -signal.SIGKILL
    a = ReferenceAdapter()
    a.build(get_workload("linear"), tmp_path)
    assert len(a.state_trace()) == 2
    assert len(_sink_lines(tmp_path)) == 1


def test_mid_kill_resume_does_not_duplicate_effect(tmp_path):
    assert _child_mid(tmp_path, kill_at=3).returncode == -signal.SIGKILL
    assert _child(tmp_path).returncode == 0
    assert len(_sink_lines(tmp_path)) == 3


def test_invalid_kill_mode_is_rejected(tmp_path):
    env = dict(os.environ, REVENANT_KILL_MODE="sideways")
    proc = subprocess.run(
        [sys.executable, "-m", "revenant.adapters.reference",
         "--workload", "linear", "--workdir", str(tmp_path)],
        env=env, capture_output=True, text=True, timeout=60,
    )  # fmt: skip
    assert proc.returncode != 0
    assert "REVENANT_KILL_MODE" in proc.stderr
