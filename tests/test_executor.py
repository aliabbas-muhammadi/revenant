import pytest

from revenant.executor import execute
from revenant.sink import EffectSink
from revenant.workloads import WORKLOAD_NAMES, get_workload


@pytest.mark.parametrize("name", WORKLOAD_NAMES)
def test_trace_has_one_hash_per_step(tmp_path, name):
    w = get_workload(name)
    result = execute(w, tmp_path)
    assert len(result.trace) == len(w.steps)
    assert len(set(result.trace)) == len(w.steps)
    assert result.state["step"] == len(w.steps)


@pytest.mark.parametrize("name", WORKLOAD_NAMES)
def test_each_tool_step_makes_one_effect(tmp_path, name):
    w = get_workload(name)
    result = execute(w, tmp_path)
    assert len(EffectSink(tmp_path / "effects.jsonl").effects()) == len(w.tool_steps)
    assert sum(result.attempts.values()) == len(w.tool_steps)


def test_linear_writes_sandbox_file(tmp_path):
    execute(get_workload("linear"), tmp_path)
    assert (tmp_path / "sandbox" / "out" / "summary.txt").exists()
