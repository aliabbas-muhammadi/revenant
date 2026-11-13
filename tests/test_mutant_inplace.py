import os
import sys

import pytest

from revenant.adapters.mutant_inplace import InPlaceMutant
from revenant.runner import sweep
from revenant.workloads import get_workload

posix = pytest.mark.skipif(os.name != "posix", reason="needs POSIX signals")


def _argv(workdir):
    return [sys.executable, "-m", "revenant.adapters.mutant_inplace",
            "--workload", "linear", "--workdir", str(workdir)]  # fmt: skip


@posix
def test_kill_during_checkpoint_write_is_detected(tmp_path):
    res = sweep(
        InPlaceMutant, get_workload("linear"), tmp_path,
        boundaries=[3, 6], argv_for=_argv,
    )  # fmt: skip
    assert res.adapter == "mutant_inplace"
    assert not res.passed
    assert res.failing() == (3, 6)
    assert res.identical_resumes < res.total
    assert res.duplicated == 0
