import pytest

pytest.importorskip("langgraph.checkpoint.sqlite")

from revenant.adapters.langgraph_sqlite import (  # noqa: E402
    CHECKPOINT_DB,
    THREAD_ID,
    compile_graph,
    initial_state,
    open_checkpointer,
    thread_config,
)
from revenant.workloads import get_workload  # noqa: E402


def test_thread_config_is_fixed():
    assert thread_config() == {"configurable": {"thread_id": THREAD_ID}}


def test_checkpointer_lives_in_the_workdir(tmp_path):
    saver = open_checkpointer(tmp_path)
    graph = compile_graph(get_workload("linear"), tmp_path, saver)
    graph.invoke(initial_state(), thread_config())
    saver.conn.close()
    assert (tmp_path / CHECKPOINT_DB).exists()


def test_completed_run_is_stored_under_the_thread(tmp_path):
    saver = open_checkpointer(tmp_path)
    graph = compile_graph(get_workload("linear"), tmp_path, saver)
    graph.invoke(initial_state(), thread_config())
    snapshot = graph.get_state(thread_config())
    saver.conn.close()
    assert snapshot.values["step"] == 12
    assert snapshot.next == ()


def _run(tmp_path, interrupt_after=None):
    from revenant.adapters.langgraph_sqlite import run_or_resume

    saver = open_checkpointer(tmp_path)
    try:
        graph = compile_graph(get_workload("linear"), tmp_path, saver, interrupt_after)
        return run_or_resume(graph)
    finally:
        saver.conn.close()


def test_resume_continues_a_partial_run_to_the_reference_hash(tmp_path):
    from revenant.adapters.reference import ReferenceAdapter
    from revenant.canon import state_hash

    wl = get_workload("linear")
    partial = _run(tmp_path / "lg", interrupt_after=["step_4"])
    assert partial["step"] == 5
    final = _run(tmp_path / "lg")
    assert final["step"] == 12
    ref = ReferenceAdapter()
    ref.build(wl, tmp_path / "ref")
    assert state_hash(dict(final), wl.volatile_fields) == ref.run().final_hash


def test_resume_does_not_repeat_finished_steps(tmp_path):
    from revenant.sink import EffectSink

    _run(tmp_path, interrupt_after=["step_11"])
    _run(tmp_path)
    assert len(list(EffectSink(tmp_path / "effects.jsonl").effects())) == 3
