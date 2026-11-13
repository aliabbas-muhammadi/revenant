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


@posix
def test_each_boundary_gets_its_own_fresh_workdir(tmp_path):
    from revenant.sink import EffectSink

    wl = get_workload("linear")
    sweep(ReferenceAdapter, wl, tmp_path, boundaries=[1, 6, 12])
    golden = EffectSink(tmp_path / "golden" / "effects.jsonl").effects()
    for k in (1, 6, 12):
        d = tmp_path / f"k{k}"
        assert d.is_dir()
        # No boundary sees another's effects: a resumed run holds exactly the golden set.
        assert EffectSink(d / "effects.jsonl").effects() == golden


@posix
def test_sweep_refuses_a_dirty_boundary_workdir(tmp_path):
    stale = tmp_path / "k2"
    stale.mkdir()
    (stale / "checkpoint.json").write_text("{}")
    with pytest.raises(ValueError, match="start empty"):
        sweep(ReferenceAdapter, get_workload("linear"), tmp_path, boundaries=[2])


@posix
def test_parallel_sweep_orders_like_serial(tmp_path):
    wl = get_workload("linear")
    serial = sweep(ReferenceAdapter, wl, tmp_path / "a", boundaries=range(1, 7), jobs=1)
    parallel = sweep(ReferenceAdapter, wl, tmp_path / "b", boundaries=range(1, 7), jobs=4)
    assert [b.boundary for b in parallel.boundaries] == [1, 2, 3, 4, 5, 6]
    assert parallel == serial


def test_jobs_must_be_positive(tmp_path):
    with pytest.raises(ValueError, match="jobs"):
        sweep(ReferenceAdapter, get_workload("linear"), tmp_path, jobs=0)
