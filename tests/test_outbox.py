import json
import os
import signal
import subprocess
import sys

import pytest

from revenant.adapters.reference_sqlite import SqliteOutboxAdapter, SqliteStore
from revenant.runner import sweep
from revenant.workloads import get_workload

posix = pytest.mark.skipif(os.name != "posix", reason="needs POSIX signals")


def _argv(workdir):
    return [sys.executable, "-m", "revenant.adapters.reference_outbox",
            "--workload", "linear", "--workdir", str(workdir)]  # fmt: skip


def _child(workdir, **env_extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith("REVENANT_KILL")}
    env.update({k: str(v) for k, v in env_extra.items()})
    return subprocess.run(_argv(workdir), env=env, capture_output=True, text=True, timeout=60)


def _effects(workdir):
    path = workdir / "effects.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def test_store_queues_rows_with_the_checkpoint(tmp_path):
    with SqliteStore(tmp_path / "s.db") as store:
        store.save_checkpoint({"n": 1}, outbox=[("k1", {"tool": "t", "args": {}})])
        assert store.pending() == [("k1", {"tool": "t", "args": {}})]
        store.mark_delivered("k1")
        assert store.pending() == []


def test_failed_checkpoint_queues_nothing(tmp_path):
    with SqliteStore(tmp_path / "s.db") as store:
        store.save_checkpoint({"n": 0})
        with pytest.raises(TypeError):
            store.save_checkpoint({"n": 1}, outbox=[("k", {"x": object()})])
        assert store.pending() == []
        assert store.load_checkpoint()["n"] == 0


@posix
def test_clean_run_delivers_every_effect_once(tmp_path):
    assert _child(tmp_path).returncode == 0
    a = SqliteOutboxAdapter()
    a.build(get_workload("linear"), tmp_path)
    assert len(a.state_trace()) == 12
    effects = _effects(tmp_path)
    assert effects and len({json.dumps(e, sort_keys=True) for e in effects}) == len(effects)
    with SqliteStore(tmp_path / "ledger.db") as store:
        assert store.pending() == []
        assert store.unconfirmed() == []


@posix
def test_mid_step_kill_performs_nothing_early(tmp_path):
    # the effect is only queued, so a kill before the checkpoint leaves no effect behind
    res = _child(tmp_path, REVENANT_KILL_AT=3, REVENANT_KILL_MODE="mid")
    assert res.returncode == -signal.SIGKILL
    clean = tmp_path.parent / (tmp_path.name + "-clean")
    _child(clean)
    done_before = len(_effects(tmp_path))
    assert done_before < len(_effects(clean))
    assert _child(tmp_path).returncode == 0
    assert _effects(tmp_path) == _effects(clean)


@posix
def test_sweep_passes_with_mid_kills(tmp_path):
    res = sweep(
        SqliteOutboxAdapter, get_workload("linear"), tmp_path,
        mode="mid", boundaries=[2, 4, 7], argv_for=_argv,
    )  # fmt: skip
    assert res.passed, res.failing()


def _pending(workdir):
    with SqliteStore(workdir / "ledger.db") as store:
        return [key for key, _ in store.pending()]


@posix
@pytest.mark.parametrize("point", [3, 4])
def test_kill_after_commit_leaves_queued_effect_undelivered(tmp_path, point):
    res = _child(tmp_path, REVENANT_KILL_AT=3, REVENANT_KILL_AT_WRITE=point)
    assert res.returncode == -signal.SIGKILL
    assert len(_pending(tmp_path)) == 1
    assert _effects(tmp_path) == []


@posix
@pytest.mark.parametrize("point", [3, 4])
def test_resume_dispatches_undelivered_rows_exactly_once(tmp_path, point):
    _child(tmp_path, REVENANT_KILL_AT=3, REVENANT_KILL_AT_WRITE=point)
    assert _child(tmp_path).returncode == 0
    clean = tmp_path.parent / (tmp_path.name + "-clean")
    assert _child(clean).returncode == 0
    assert _effects(tmp_path) == _effects(clean)
    assert _pending(tmp_path) == []


@posix
def test_kill_before_commit_queues_nothing(tmp_path):
    for point in (1, 2):
        workdir = tmp_path / str(point)
        _child(workdir, REVENANT_KILL_AT=3, REVENANT_KILL_AT_WRITE=point)
        assert _pending(workdir) == []
        assert _child(workdir).returncode == 0
        assert len(_effects(workdir)) == 3


@posix
def test_sweep_passes_with_boundary_kills(tmp_path):
    res = sweep(
        SqliteOutboxAdapter, get_workload("linear"), tmp_path,
        boundaries=[3, 6, 9], argv_for=_argv,
    )  # fmt: skip
    assert res.passed, res.failing()
