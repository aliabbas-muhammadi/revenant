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
