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
