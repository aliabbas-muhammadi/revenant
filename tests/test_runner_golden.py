import pytest

from revenant.adapters.reference import ReferenceAdapter
from revenant.runner import golden_run
from revenant.workloads import get_workload


def test_golden_run_collects_full_trace(tmp_path):
    result = golden_run(ReferenceAdapter, get_workload("linear"), tmp_path / "g")
    assert result.completed and len(result.trace) == 12
    assert result.final_hash == result.trace[-1]


def test_golden_run_is_repeatable(tmp_path):
    a = golden_run(ReferenceAdapter, get_workload("linear"), tmp_path / "a")
    b = golden_run(ReferenceAdapter, get_workload("linear"), tmp_path / "b")
    assert a.trace == b.trace


def test_golden_run_ignores_inherited_kill_env(tmp_path, monkeypatch):
    monkeypatch.setenv("REVENANT_KILL_AT", "2")
    result = golden_run(ReferenceAdapter, get_workload("linear"), tmp_path / "g")
    assert result.completed
    assert __import__("os").environ["REVENANT_KILL_AT"] == "2"


def test_golden_run_requires_fresh_workdir(tmp_path):
    (tmp_path / "x").write_text("stale")
    with pytest.raises(ValueError):
        golden_run(ReferenceAdapter, get_workload("linear"), tmp_path)
