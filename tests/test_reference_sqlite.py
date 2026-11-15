import os
import signal
import subprocess
import sys

import pytest

from revenant.adapters.reference_sqlite import SqliteReferenceAdapter, SqliteStore
from revenant.checkpoint import WRITE_POINTS, CheckpointCorrupt
from revenant.runner import sweep
from revenant.workloads import get_workload

posix = pytest.mark.skipif(os.name != "posix", reason="needs POSIX signals")


def _argv(workdir):
    return [sys.executable, "-m", "revenant.adapters.reference_sqlite",
            "--workload", "linear", "--workdir", str(workdir)]  # fmt: skip


def _child(workdir, kill_at=None, write=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith("REVENANT_KILL")}
    if kill_at is not None:
        env["REVENANT_KILL_AT"] = str(kill_at)
    if write is not None:
        env["REVENANT_KILL_AT_WRITE"] = str(write)
    return subprocess.run(_argv(workdir), env=env, capture_output=True, text=True, timeout=60)


def _trace(workdir):
    a = SqliteReferenceAdapter()
    a.build(get_workload("linear"), workdir)
    return a.state_trace()


def test_store_round_trip(tmp_path):
    with SqliteStore(tmp_path / "s.db") as store:
        assert store.load_checkpoint() is None
        store.save_checkpoint({"state": {"step": 1}, "trace": ["a"]})
        store.save_checkpoint({"state": {"step": 2}, "trace": ["a", "b"]})
        assert store.load_checkpoint()["state"]["step"] == 2


def test_store_rejects_bad_kill_point(tmp_path):
    with SqliteStore(tmp_path / "s.db") as store, pytest.raises(ValueError):
        store.save_checkpoint({"x": 1}, kill_point=9)


def test_tampered_checkpoint_is_detected(tmp_path):
    with SqliteStore(tmp_path / "s.db") as store:
        store.save_checkpoint({"state": {"step": 1}, "trace": []})
        store._conn.execute(
            "UPDATE checkpoint SET body = CAST(replace(CAST(body AS TEXT), '1', '7') AS BLOB)"
        )
        with pytest.raises(CheckpointCorrupt):
            store.load_checkpoint()


def test_boundary_count(tmp_path):
    a = SqliteReferenceAdapter()
    a.build(get_workload("linear"), tmp_path)
    assert a.boundaries() == 12


@posix
def test_full_run_matches_file_reference(tmp_path):
    assert _child(tmp_path / "a").returncode == 0
    from revenant.adapters.reference import ReferenceAdapter

    ref = ReferenceAdapter()
    ref.build(get_workload("linear"), tmp_path / "b")
    ref.run()
    assert _trace(tmp_path / "a") == ref.state_trace()
    assert not (tmp_path / "a" / "checkpoint.json").exists()


@posix
@pytest.mark.parametrize("point", WRITE_POINTS)
def test_survives_kill_at_every_write_point(tmp_path, point):
    killed = tmp_path / "k"
    assert _child(killed, kill_at=3, write=point).returncode == -signal.SIGKILL
    assert _child(killed).returncode == 0
    assert _child(tmp_path / "g").returncode == 0
    assert _trace(killed) == _trace(tmp_path / "g")
    assert len(_trace(killed)) == 12


@posix
def test_sweep_passes(tmp_path):
    res = sweep(
        SqliteReferenceAdapter, get_workload("linear"), tmp_path,
        boundaries=[2, 5, 9], argv_for=_argv,
    )  # fmt: skip
    assert res.passed, res.failing()
