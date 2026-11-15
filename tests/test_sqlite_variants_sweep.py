"""Full sweeps of both SQLite reference variants on every workload."""

import os
import sys

import pytest

from revenant.adapters.reference_sqlite import SqliteOutboxAdapter, SqliteReferenceAdapter
from revenant.runner import sweep
from revenant.workloads import WORKLOAD_NAMES, get_workload

pytestmark = pytest.mark.skipif(os.name != "posix", reason="needs POSIX signals")

VARIANTS = [
    (SqliteReferenceAdapter, "reference_sqlite"),
    (SqliteOutboxAdapter, "reference_outbox"),
]


@pytest.mark.parametrize("workload", WORKLOAD_NAMES)
@pytest.mark.parametrize("mode", ["boundary", "mid"])
@pytest.mark.parametrize(("factory", "module"), VARIANTS)
def test_every_boundary_passes(tmp_path, factory, module, mode, workload):
    def argv_for(workdir):
        return [sys.executable, "-m", f"revenant.adapters.{module}",
                "--workload", workload, "--workdir", str(workdir)]  # fmt: skip

    res = sweep(factory, get_workload(workload), tmp_path, mode=mode, argv_for=argv_for, jobs=4)
    assert res.passed, res.failing()
    assert res.duplicated == 0
    assert res.unconfirmed == 0
