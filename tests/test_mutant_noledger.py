import os
import sys

import pytest

from revenant.adapters.mutant_noledger import NoLedgerMutant
from revenant.runner import sweep
from revenant.workloads import get_workload

posix = pytest.mark.skipif(os.name != "posix", reason="needs POSIX signals")


def _argv(workdir):
    return [sys.executable, "-m", "revenant.adapters.mutant_noledger",
            "--workload", "linear", "--workdir", str(workdir)]  # fmt: skip


@posix
def test_boundary_kills_pass_without_a_ledger(tmp_path):
    res = sweep(
        NoLedgerMutant, get_workload("linear"), tmp_path,
        boundaries=[2, 5], argv_for=_argv,
    )  # fmt: skip
    assert res.passed, res.failing()


@posix
def test_mid_step_kills_duplicate_effects(tmp_path):
    res = sweep(
        NoLedgerMutant, get_workload("linear"), tmp_path,
        mode="mid", boundaries=[3, 6], argv_for=_argv,
    )  # fmt: skip
    assert not res.passed
    assert res.failing() == (3, 6)
    assert res.duplicated == 2
    assert all(b.effects.duplicated for b in res.boundaries)
