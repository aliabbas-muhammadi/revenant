import os
import sys

import pytest

from revenant.adapters.mutant_checkpoint_first import CheckpointFirstMutant
from revenant.runner import sweep
from revenant.workloads import get_workload

posix = pytest.mark.skipif(os.name != "posix", reason="needs POSIX signals")


def _argv(workdir):
    return [sys.executable, "-m", "revenant.adapters.mutant_checkpoint_first",
            "--workload", "linear", "--workdir", str(workdir)]  # fmt: skip


@posix
def test_boundary_kills_still_pass(tmp_path):
    res = sweep(
        CheckpointFirstMutant, get_workload("linear"), tmp_path,
        boundaries=[2, 5], argv_for=_argv,
    )  # fmt: skip
    assert res.passed, res.failing()


@posix
def test_mid_step_kill_loses_the_effect(tmp_path):
    res = sweep(
        CheckpointFirstMutant, get_workload("linear"), tmp_path,
        mode="mid", boundaries=[3, 6], argv_for=_argv,
    )  # fmt: skip
    assert not res.passed
    assert res.failing() == (3, 6)
    assert res.duplicated == 0
    assert all(b.effects.missing for b in res.boundaries)
