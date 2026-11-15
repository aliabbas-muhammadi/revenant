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


def test_golden_run_ignores_every_inherited_kill_variable(tmp_path, monkeypatch):
    monkeypatch.setenv("REVENANT_KILL_AT", "2")
    monkeypatch.setenv("REVENANT_KILL_MODE", "mid")
    monkeypatch.setenv("REVENANT_KILL_AT_WRITE", "1")
    result = golden_run(ReferenceAdapter, get_workload("linear"), tmp_path / "g")
    assert result.completed and len(result.trace) == 12


def test_golden_run_restores_kill_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("REVENANT_KILL_AT", "2")
    golden_run(ReferenceAdapter, get_workload("linear"), tmp_path / "g")
    import os

    assert os.environ["REVENANT_KILL_AT"] == "2"


def test_spawned_children_do_not_inherit_kill_variables(monkeypatch):
    import sys

    from revenant.runner import spawn_child

    monkeypatch.setenv("REVENANT_KILL_AT", "2")
    monkeypatch.setenv("REVENANT_KILL_AT_WRITE", "3")
    code = "import os; print(sorted(k for k in os.environ if k.startswith('REVENANT_KILL')))"
    out = spawn_child([sys.executable, "-c", code])
    assert out.stdout.strip() == "[]"
    explicit = spawn_child([sys.executable, "-c", code], env={"REVENANT_KILL_AT": "1"})
    assert "REVENANT_KILL_AT" in explicit.stdout
