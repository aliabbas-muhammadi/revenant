import os
import sys

import pytest

from revenant.adapters.mutant_nocheckpoint import NoCheckpointMutant
from revenant.runner import sweep
from revenant.workloads import get_workload

posix = pytest.mark.skipif(os.name != "posix", reason="needs POSIX signals")


def _argv(workdir):
    return [sys.executable, "-m", "revenant.adapters.mutant_nocheckpoint",
            "--workload", "linear", "--workdir", str(workdir)]  # fmt: skip


@posix
def test_restart_from_zero_is_caught(tmp_path):
    res = sweep(
        NoCheckpointMutant, get_workload("linear"), tmp_path,
        boundaries=[3, 6], argv_for=_argv,
    )  # fmt: skip
    assert res.adapter == "mutant_nocheckpoint"
    assert not res.passed
    assert res.failing() == (3, 6)
    assert res.duplicated > 0
    assert res.identical_resumes == res.total
