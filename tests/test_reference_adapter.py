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


def test_checkpoint_written_after_each_step(tmp_path):
    from revenant.checkpoint import load_checkpoint

    a = ReferenceAdapter()
    a.build(get_workload("linear"), tmp_path)
    a._execute(stop_after=5)
    ckpt = load_checkpoint(tmp_path / "checkpoint.json")
    assert ckpt["state"]["step"] == 5
    assert len(ckpt["trace"]) == 5


@pytest.mark.parametrize("name", WORKLOAD_NAMES)
def test_resume_after_stop_at_step_5_or_earlier(tmp_path, name):
    w = get_workload(name)
    golden = ReferenceAdapter()
    golden.build(w, tmp_path / "golden")
    expected = golden.run()

    a = ReferenceAdapter()
    a.build(w, tmp_path / "run")
    stop = min(5, len(w.steps) - 1)
    partial = a._execute(stop_after=stop)
    assert not partial.completed
    assert partial.steps_run == stop

    resumed = ReferenceAdapter()
    resumed.build(w, tmp_path / "run")
    result = resumed.run()
    assert result.completed
    assert result.trace == expected.trace
    assert len(EffectSink(tmp_path / "run" / "effects.jsonl").effects()) == len(w.tool_steps)


def test_trace_file_is_jsonl_with_step_and_hash(tmp_path):
    import json

    a = ReferenceAdapter()
    a.build(get_workload("linear"), tmp_path)
    result = a.run()
    rows = [json.loads(x) for x in (tmp_path / "trace.jsonl").read_text().splitlines()]
    assert [r["step"] for r in rows] == list(range(1, 13))
    assert tuple(r["hash"] for r in rows) == result.trace


def test_trace_file_repaired_on_resume(tmp_path):
    w = get_workload("linear")
    a = ReferenceAdapter()
    a.build(w, tmp_path)
    a._execute(stop_after=4)
    trace_path = tmp_path / "trace.jsonl"
    lines = trace_path.read_text().splitlines()
    trace_path.write_text("\n".join(lines[:-1]) + "\n")  # simulate a kill before the append
    b = ReferenceAdapter()
    b.build(w, tmp_path)
    result = b.run()
    assert b.state_trace() == result.trace
    assert len(b.state_trace()) == 12


@pytest.mark.parametrize("name", WORKLOAD_NAMES)
def test_boundaries_match_step_count(tmp_path, name):
    w = get_workload(name)
    a = ReferenceAdapter()
    a.build(w, tmp_path)
    assert a.boundaries() == len(w.steps)
