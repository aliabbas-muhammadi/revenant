import pytest

from revenant.adapters.reference import ReferenceAdapter
from revenant.executor import execute
from revenant.sink import EffectSink
from revenant.workloads import WORKLOAD_NAMES, get_workload


def test_run_before_build_fails():
    with pytest.raises(RuntimeError):
        ReferenceAdapter().run()


def test_full_linear_run(tmp_path):
    w = get_workload("linear")
    a = ReferenceAdapter()
    a.build(w, tmp_path)
    result = a.run()
    assert result.completed
    assert result.steps_run == 12
    assert a.boundaries() == 12
    assert a.state_trace() == result.trace
    assert len(EffectSink(tmp_path / "effects.jsonl").effects()) == 3


@pytest.mark.parametrize("name", WORKLOAD_NAMES)
def test_matches_in_process_executor(tmp_path, name):
    w = get_workload(name)
    a = ReferenceAdapter()
    a.build(w, tmp_path / "ref")
    assert a.run().trace == execute(w, tmp_path / "exe").trace
