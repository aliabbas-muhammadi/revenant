import json
import os
import signal
import subprocess
import sys

import pytest

from revenant.adapters.reference import ReferenceAdapter
from revenant.checkpoint import WRITE_POINTS, load_checkpoint, write_checkpoint
from revenant.workloads import get_workload

pytestmark = pytest.mark.skipif(os.name != "posix", reason="needs POSIX signals")


def _child(workdir, kill_at=None, write=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith("REVENANT_KILL")}
    if kill_at is not None:
        env["REVENANT_KILL_AT"] = str(kill_at)
    if write is not None:
        env["REVENANT_KILL_AT_WRITE"] = str(write)
    return subprocess.run(
        [sys.executable, "-m", "revenant.adapters.reference",
         "--workload", "linear", "--workdir", str(workdir)],
        env=env, capture_output=True, text=True, timeout=60,
    )  # fmt: skip


def _trace(workdir):
    a = ReferenceAdapter()
    a.build(get_workload("linear"), workdir)
    return a.state_trace()


def test_invalid_kill_point_rejected(tmp_path):
    with pytest.raises(ValueError):
        write_checkpoint(tmp_path / "c.json", {"x": 1}, kill_point=9)


@pytest.mark.parametrize("point", WRITE_POINTS)
def test_reference_survives_kill_at_every_write_point(tmp_path, point):
    killed = tmp_path / "k"
    assert _child(killed, kill_at=3, write=point).returncode == -signal.SIGKILL
    # a crash anywhere in the write leaves a loadable checkpoint: step 2 or step 3
    saved = load_checkpoint(killed / "checkpoint.json")
    assert saved is not None and saved["state"]["step"] in (2, 3)
    assert _child(killed).returncode == 0
    assert _child(tmp_path / "g").returncode == 0
    assert _trace(killed) == _trace(tmp_path / "g")
    assert len(_trace(killed)) == 12


def test_early_points_keep_previous_checkpoint(tmp_path):
    _child(tmp_path, kill_at=3, write=1)
    assert load_checkpoint(tmp_path / "checkpoint.json")["state"]["step"] == 2
    other = tmp_path / "late"
    _child(other, kill_at=3, write=3)
    assert load_checkpoint(other / "checkpoint.json")["state"]["step"] == 3
    assert json.loads(json.dumps(WRITE_POINTS)) == [1, 2, 3, 4]
