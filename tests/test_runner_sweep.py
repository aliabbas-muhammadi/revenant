import os

import pytest

from revenant.adapters.reference import ReferenceAdapter
from revenant.runner import sweep
from revenant.workloads import get_workload

posix = pytest.mark.skipif(os.name != "posix", reason="needs POSIX signals")


@posix
def test_full_boundary_sweep_passes_every_property(tmp_path):
    wl = get_workload("linear")
    res = sweep(ReferenceAdapter, wl, tmp_path)
    assert res.adapter == "reference" and res.workload == "linear"
    assert res.total == 12
    assert res.passed, res.failing()
    assert res.identical_resumes == 12
    assert res.duplicated == 0 and res.lost_or_phantom == 0 and res.unconfirmed == 0
    assert res.effects_once == 3


@posix
def test_sweep_can_target_chosen_boundaries(tmp_path):
    res = sweep(ReferenceAdapter, get_workload("linear"), tmp_path, boundaries=[3, 7])
    assert [b.boundary for b in res.boundaries] == [3, 7] and res.passed


@posix
def test_mid_step_sweep_passes_on_reference(tmp_path):
    res = sweep(ReferenceAdapter, get_workload("linear"), tmp_path, mode="mid")
    assert res.total == 12 and res.passed, res.failing()
    assert all(b.mode == "mid" for b in res.boundaries)


_FAKE_CHILD = """
import os, signal, sys
from revenant.ledger import Ledger
workdir = sys.argv[1]
if os.environ.get("REVENANT_KILL_AT"):
    os.makedirs(workdir, exist_ok=True)
    ledger = Ledger(os.path.join(workdir, "ledger.db"))
    ledger.begin("charge:c1", {"amount": 5})
    os.kill(os.getpid(), signal.SIGKILL)
"""


@posix
def test_unconfirmed_residue_is_reported_not_hidden(tmp_path):
    import sys

    def argv_for(workdir):
        return [sys.executable, "-c", _FAKE_CHILD, str(workdir)]

    res = sweep(
        ReferenceAdapter, get_workload("linear"), tmp_path,
        mode="mid", boundaries=[2, 4], argv_for=argv_for,
    )  # fmt: skip
    assert res.unconfirmed == 2
    assert all(b.effects.unconfirmed == ("charge:c1",) for b in res.boundaries)
