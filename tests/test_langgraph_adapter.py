import pytest

pytest.importorskip("langgraph.checkpoint.sqlite")

from revenant.adapters.langgraph_sqlite import LangGraphAdapter  # noqa: E402
from revenant.adapters.reference import ReferenceAdapter  # noqa: E402
from revenant.workloads import get_workload  # noqa: E402


def test_clean_run_trace_equals_the_reference_trace(tmp_path):
    wl = get_workload("linear")
    lg = LangGraphAdapter()
    lg.build(wl, tmp_path / "lg")
    ref = ReferenceAdapter()
    ref.build(wl, tmp_path / "ref")
    got, want = lg.run(), ref.run()
    assert got.completed and got.trace == want.trace
    assert lg.state_trace() == want.trace


def test_state_trace_is_empty_before_any_run(tmp_path):
    lg = LangGraphAdapter()
    lg.build(get_workload("linear"), tmp_path)
    assert lg.state_trace() == ()
    assert lg.boundaries() == 12


def test_volatile_fields_do_not_enter_the_hash(tmp_path):
    from dataclasses import replace

    wl = get_workload("linear")
    a = LangGraphAdapter()
    a.build(replace(wl, volatile_fields=("clock",)), tmp_path / "a")
    b = LangGraphAdapter()
    b.build(wl, tmp_path / "b")
    assert a.run().trace != b.run().trace
